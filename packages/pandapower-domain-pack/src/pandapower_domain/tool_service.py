"""Pack-owned published tool execution with an application-selected workspace."""

from __future__ import annotations

import hashlib
import json
import os
import re
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from capability_agent.runtime.execution_queue import ExecutionReceiptError
from pandapower_domain.authority import ContentReferenceVerifier, PandapowerArtifactAuthority, SimulatorIntegrityError

from pandapower_domain.execution import (GridctlExecutor, SimulatorCapabilityError,
    source_execution_queue, execution_receipt_writer)
from pandapower_domain.profile import build_pandapower_profile
from pandapower_domain.provisioning import PandapowerRuntimeProvisioner


_TASK_ID = re.compile(r'^[A-Za-z0-9_-]{1,80}$')


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _argument_references(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from _argument_references(item)
    elif isinstance(value, list):
        for item in value:
            yield from _argument_references(item)
    elif isinstance(value, str) and re.fullmatch(r'(?:result|evidence|context|revision):sha256:[0-9a-f]{64}', value):
        yield value


class PandapowerToolService:
    """Serve the installed pandapower profile's published tools."""

    def __init__(self, *, workspace_root: Path | None = None) -> None:
        configured = os.environ.get('CAPSTONE_DOMAIN_TOOL_WORKSPACE')
        self._root = Path(workspace_root or configured or (Path(os.environ.get('CAPSTONE_RUNS_ROOT', '/tmp')) / 'domain-tools'))
        self._receipt_root = Path(os.environ.get('CAPSTONE_DOMAIN_EXECUTION_RECEIPTS_ROOT') or self._root)
        self._lock = Lock()
        self._profile = None
        self._capabilities: dict[str, str] = {}
        self._executors: dict[str, GridctlExecutor] = {}
        self._read_only: dict[str, bool] = {}
        self._queue = source_execution_queue()

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

    def invoke(self, document: dict, *, workspace_id: str, authority_inputs=()) -> dict:
        if not isinstance(workspace_id, str) or not _TASK_ID.fullmatch(workspace_id):
            raise ValueError('domain workspace identity is invalid')
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
        read_only = self._read_only.get(name, False)
        refs = set(_argument_references(arguments))
        owned_inputs = [item for item in authority_inputs if item['authority_id'] == PandapowerArtifactAuthority.authority_id]
        linked = [item for item in owned_inputs if refs.intersection((*item['result_refs'], *item['evidence_refs']))]
        delegated = next((item for item in linked if refs.issubset((*item['result_refs'], *item['evidence_refs']))), None)
        with ExitStack() as opened:
            execution_id = workspace_id
            if delegated is not None and read_only:
                folder = Path(opened.enter_context(TemporaryDirectory(prefix='grant-', dir=self._root)))
                execution_id = folder.name
            resource = str((self._root / execution_id).resolve())
            lease = opened.enter_context(self._queue.acquire(receipt, resource=resource, read_only=read_only))
            try:
                if linked and (delegated is None or not read_only):
                    raise ValueError('delegated authority input requires a granted read-only tool call')
                if delegated is not None:
                    if not _TASK_ID.fullmatch(delegated['owner']):
                        raise ValueError('delegated authority owner is invalid')
                    owner = PandapowerArtifactAuthority(self._root / delegated['owner'])
                    owner.stage_read_inputs(self._root / execution_id, delegated['result_refs'], delegated['evidence_refs'])
                result = self._executor(execution_id).invoke(capability, arguments,
                    execution_lease=lease,
                    execution_observer=lambda phase: self._queue.record(receipt, phase, provenance='authority_process'))
                response = ({'ok': True, 'result': result} if isinstance(result, dict)
                    else {'ok': False, 'error': {'message': 'domain tool call failed'}})
                if isinstance(result, dict):
                    authority = PandapowerArtifactAuthority(self._root / execution_id)
                    verified = authority.admit(capability, result, ())
                    evidence = {item.reference: item for item in verified.evidence}
                    result_refs = {item.reference for item in verified.results}
                    if delegated is not None and (not result_refs.issubset(delegated['result_refs'])
                            or not evidence.keys() <= set(delegated['evidence_refs'])):
                        raise ValueError('delegated authority response exceeds the grant')
                    if result_refs and not evidence:
                        prior_evidence = (delegated['evidence_refs'] if delegated is not None else
                            document.get('management', {}).get('prior_evidence_refs', ()))
                        for ref in prior_evidence:
                            try:
                                item = authority.verify_evidence(ref)
                            except SimulatorIntegrityError:
                                # A different Pack or workspace can own a historical handle.
                                continue
                            if (item.document.get('result_ref') in result_refs
                                    and item.document.get('context_ref') == result.get('context_ref')
                                    and item.document.get('revision_ref') == result.get('revision_ref')):
                                evidence[ref] = item
                    if result_refs or evidence:
                        response['authority_references'] = {
                            'authority_id': authority.authority_id,
                            'capability_id': capability,
                            'result_refs': [item.reference for item in verified.results],
                            'evidence_refs': list(evidence),
                        }
            except ExecutionReceiptError:
                raise
            except SimulatorCapabilityError as error:
                response = {'ok': False, 'error': error.error if isinstance(error.error, dict) else {'message': 'domain tool call failed'}}
            except Exception:
                response = {'ok': False, 'error': {'message': 'domain tool call failed'}}
        return {**response, 'execution_receipt': receipt}

    def recover(self, receipt):
        """Admit a saved task scope only after finding its exact owner receipt."""
        task_id = receipt.get('task_id')
        if not isinstance(task_id, str) or not re.fullmatch(r'pi-[a-f0-9]{64}', task_id):
            raise ValueError('legacy task identity is invalid')
        ledger = ContentReferenceVerifier(self._receipt_root / task_id)
        directory = ('execution-receipts',)
        try:
            files = ledger._list_directory(directory)
            if len(files) > 256:
                raise ValueError('legacy receipt directory exceeds bounds')
            for name in files:
                if not re.fullmatch(r'[a-f0-9]{32}\.json', name):
                    continue
                saved = ledger._try_json_document((*directory, name), 'legacy execution receipt')
                if saved is not None and saved[1] == receipt:
                    return PandapowerArtifactAuthority(self._root / task_id).recover_references()
        except SimulatorIntegrityError:
            raise ValueError('legacy authority content is unavailable') from None
        raise ValueError('legacy execution receipt does not match its owner')

    def _receipt_writer(self, task_id):
        # Each invocation gets a private control record, independent of HTTP
        # delivery. This is host telemetry, never an Authority result/evidence.
        return execution_receipt_writer(self._receipt_root, task_id)

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
