"""Published pandapower tools for a general-executor call.

This worker owns the Domain Pack. The general executor only receives the
published names, descriptions, and input schemas, then relays each call here.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from threading import Lock
from capability_agent.runtime.execution_queue import ExecutionQueue, ExecutionReceiptError
from uuid import uuid4

from pandapower_domain.execution import GridctlExecutor, SimulatorCapabilityError
from pandapower_domain.profile import build_pandapower_profile
from pandapower_domain.provisioning import PandapowerRuntimeProvisioner


_TASK_ID = re.compile(r'^[A-Za-z0-9_-]{1,80}$')


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


class PandapowerDomainToolService:
    """Serve the installed pandapower profile's published tools."""

    def __init__(self, *, workspace_root: Path | None = None) -> None:
        configured = os.environ.get('CAPSTONE_DOMAIN_TOOL_WORKSPACE')
        self._root = Path(workspace_root or configured or (Path(os.environ.get('CAPSTONE_RUNS_ROOT', '/tmp')) / 'domain-tools'))
        self._lock = Lock()
        self._profile = None
        self._capabilities: dict[str, str] = {}
        self._executors: dict[str, GridctlExecutor] = {}
        self._read_only: dict[str, bool] = {}
        self._queue = ExecutionQueue(capacity=int(os.environ.get('CAPSTONE_DOMAIN_EXECUTION_CAPACITY', '8')))

    def _installed(self):
        if self._profile is None:
            self._profile = build_pandapower_profile()
        return self._profile

    def catalog(self, profile_id: str, profile_version: str) -> dict:
        profile = self._installed()
        manifest = profile.manifest
        if profile_id != manifest.domain_id or profile_version != manifest.version:
            raise KeyError('domain pack is not published by this worker')
        tools, hashes, capabilities, read_only = {}, {}, {}, {}
        for document in profile.contract_source.load():
            if document.get('availability') != 'published':
                continue
            name = document.get('tool_name')
            capability = document.get('id')
            schema = document.get('input_schema')
            if not isinstance(name, str) or not isinstance(capability, str) or not isinstance(schema, dict):
                continue
            describe = profile.tool_description_builder
            if describe is None:
                raise ValueError('published domain tool description builder is unavailable')
            description = describe(document)
            body = {'description': description, 'inputSchema': schema, 'capability': capability}
            tools[name] = {'description': description, 'inputSchema': schema}
            hashes[name] = hashlib.sha256(_canonical(body).encode()).hexdigest()
            capabilities[name] = capability
            read_only[name] = document.get('state_effect') == 'none'
        if not tools:
            raise KeyError('domain pack is not published by this worker')
        with self._lock:
            self._capabilities = capabilities
            self._read_only = read_only
        return {
            'schema': 'capstone-domain-tool-catalog/1',
            'profile_id': manifest.domain_id,
            'profile_version': manifest.version,
            'implementation_family': 'pandapower',
            'tools': tools,
            'tool_hashes': hashes,
        }

    def invoke(self, document: dict) -> dict:
        task_id = document.get('task_id')
        name = document.get('name')
        arguments = document.get('arguments')
        if (not isinstance(task_id, str) or not _TASK_ID.fullmatch(task_id)
                or not isinstance(name, str) or not isinstance(arguments, dict)):
            raise ValueError('domain tool call is invalid')
        if not self._capabilities:
            manifest = self._installed().manifest
            self.catalog(manifest.domain_id, manifest.version)
        capability = self._capabilities.get(name)
        if capability is None:
            raise KeyError('domain tool is not published')
        call_id = document.get('call_id')
        if not isinstance(call_id, str) or not call_id or len(call_id) > 256:
            raise ValueError('domain tool call identity is invalid')
        receipt = self._queue.receipt(task_id=task_id, call_id=call_id,
            observer=self._receipt_writer(task_id))
        with self._queue.acquire(receipt, resource=task_id, read_only=self._read_only.get(name, False)):
            try:
                result = self._executor(task_id).invoke(capability, arguments,
                    execution_observer=lambda phase: self._queue.record(receipt, phase, provenance='authority_process'))
                response = ({'ok': True, 'result': result} if isinstance(result, dict)
                    else {'ok': False, 'error': {'message': 'domain tool call failed'}})
            except ExecutionReceiptError:
                raise
            except SimulatorCapabilityError as error:
                response = {'ok': False, 'error': error.error if isinstance(error.error, dict) else {'message': 'domain tool call failed'}}
            except Exception:
                response = {'ok': False, 'error': {'message': 'domain tool call failed'}}
        return {**response, 'execution_receipt': receipt}

    def _receipt_writer(self, task_id):
        # Each invocation gets a private control record, independent of HTTP
        # delivery. This is host telemetry, never an Authority result/evidence.
        directory = self._root / task_id / 'execution-receipts'
        path = directory / (uuid4().hex + '.json')
        def persist(receipt):
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            temporary = directory / ('.' + uuid4().hex + '.tmp')
            try:
                with temporary.open('x', encoding='utf-8') as stream:
                    temporary.chmod(0o600)
                    json.dump(receipt, stream, ensure_ascii=False, separators=(',', ':'))
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
        return persist

    def _executor(self, task_id: str) -> GridctlExecutor:
        with self._lock:
            cached = self._executors.get(task_id)
            if cached is not None:
                return cached
            if len(self._executors) >= 64:
                self._executors.pop(next(iter(self._executors)))
            workspace = self._root / task_id
            workspace.mkdir(parents=True, exist_ok=True)
            root = Path(__file__).resolve().parents[4]
            executable = PandapowerRuntimeProvisioner(repository_root=root)._resolve_executable()
            executor = GridctlExecutor(executable=executable, workspace=workspace, timeout_seconds=180)
            self._executors[task_id] = executor
            return executor
