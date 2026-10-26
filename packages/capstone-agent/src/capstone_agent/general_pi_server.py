"""Private general Pi control service, separate from professional workers."""
from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import asyncio
from concurrent.futures import CancelledError
import json
import math
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import threading
import time
from urllib.parse import urlsplit, parse_qs
import httpx

from .general_pi_executor import GeneralPiProcess, native_pi_launch, task_workspace, collect_artifacts
from .pi_delegation import PiTaskRequest, PiTaskResult, MAX_DOCUMENT_BYTES, MAX_TASK_DOCUMENT_BYTES
from .general_pi_storage import GeneralPiStorage, request_hash
from .general_pi_relay import ProviderRelay, forward_provider
from .bounded_http_loop import run_http
from .application_capacity import limits, initialize_capacity, current_capacity, CapacityExceeded, observe_capacity


def _adaptive_agent_loop(request):
    from .native_task_context import resolve_research_policy
    native = request.native_context
    publication = resolve_research_policy(native['policy']['system_policy']) if native is not None else None
    return publication is not None and getattr(publication, 'adaptive_agent_loop', False) is True


def _electrical_view_from_verified_result(result, arguments):
    """Project a ready open response only after exact gateway receipt admission."""
    from .grid_electrical_view import electrical_descriptor
    try:
        text = result['content'][0]['text']
        if not isinstance(text, str) or len(text.encode()) > limits.mcp_frame_bytes:
            return None
        upstream = json.loads(text)
        content = upstream.get('structuredContent', {})
        if upstream.get('isError') or content.get('status') not in {'ok', 'partial'}:
            return None
        data = content['data']
        if (data.get('state') != 'ready' or data.get('model_ref') != arguments.get('model_ref')
                or data.get('representation') != arguments.get('representation', 'source_node_breaker')
                or data.get('target') != arguments.get('target')):
            return None
        for argument, field in [('expected_model_revision', 'model_revision'), ('selection_ref', 'selection_ref'),
                                ('artifact_ref', 'artifact_ref')]:
            if arguments.get(argument) is not None and arguments[argument] != data.get(field):
                return None
        return electrical_descriptor(data)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        return None


class GeneralPiHost:
    def __init__(self, *, root: Path, identity: dict, run_task: Callable,
                 max_tasks: int | None = None, max_records: int | None = None, retention_seconds: float | None = None,
                 max_storage_bytes: int | None = None, max_saved_receipts: int | None = None) -> None:
        max_tasks = limits.native_task_count if max_tasks is None else max_tasks
        max_records = limits.native_record_count if max_records is None else max_records
        self.root, self.identity, self._run = root, dict(identity), run_task
        self.capability = {'capability_id': 'general-pi', 'display_name': 'General Pi agent',
            'task_schemas': ['capstone-pi-task/1', 'capstone-pi-task/2'],
            'enabled': True, 'available': True, 'operations': ['answer', 'rewrite', 'external_lookup'],
            'executor_identity': self.identity}
        self.capability['native_context_schemas'] = ['capstone-native-context/1']
        self.capability['research_bridge_schemas'] = ['capstone-research-bridge/1']
        self.capability['research_graph_schemas'] = ['capstone-enterprise-graph/2']
        self.capability['delivery_review_schemas'] = ['capstone-delivery-review/1']
        from .native_diagnosis import DIAGNOSIS_POLICY
        self.capability['systematic_diagnosis'] = dict(DIAGNOSIS_POLICY)
        gateway = getattr(run_task, 'gateway', None)
        self.capability['data_gateway'] = (gateway.publication() if gateway else
            getattr(run_task, 'gateway_publication', {'available': False, 'reason': 'not_configured'}))
        from .native_task_context import research_policy_capabilities
        self.capability['research_policy_profiles'] = research_policy_capabilities()
        self._max_tasks, self._max_records = max_tasks, max_records
        self._lock = threading.RLock()
        self._tasks: dict[str, dict] = {}
        root.mkdir(parents=True, exist_ok=True, mode=0o711)
        (root / 'receipts').mkdir(exist_ok=True, mode=0o700)
        (root / 'receipts').chmod(0o700)
        self.storage = GeneralPiStorage(root / 'receipts', retention_seconds=retention_seconds,
            max_receipts=max_saved_receipts, max_bytes=max_storage_bytes)
        from .native_resource_staging import NativeResourceStaging
        (root / 'inputs').mkdir(exist_ok=True, mode=0o711)
        (root / 'inputs').chmod(0o711)
        self.resource_staging = NativeResourceStaging(root / 'inputs' / '.staging')
        # This host exclusively owns the input volume. No child survives its
        # container restart; retain resumable uploads, discard execution copies.
        for path in (root / 'inputs').iterdir():
            if path.name != '.staging' and path.is_dir():
                shutil.rmtree(path)
        self.resource_staging.sweep(set())
        bind_resources = getattr(run_task, 'bind_resource_staging', None)
        if callable(bind_resources):
            bind_resources(self.resource_staging)
        for task_id in self.storage.sweep(set()):
            shutil.rmtree(self.root / 'tasks' / task_id, ignore_errors=True)
            shutil.rmtree(self.root / 'tasks' / '.contexts' / task_id, ignore_errors=True)
            shutil.rmtree(self.root / 'tasks' / '.diagnoses' / task_id, ignore_errors=True)
            shutil.rmtree(self.storage.root / 'diagnoses' / task_id, ignore_errors=True)
            shutil.rmtree(self._research_path(task_id), ignore_errors=True)
            shutil.rmtree(self.resource_staging.root / task_id, ignore_errors=True)
        bind_research = getattr(run_task, 'bind_research_reader', None)
        if callable(bind_research):
            bind_research(self.research_mirror)
        bind_context = getattr(run_task, 'bind_graph_context_provider', None)
        if callable(bind_context):
            bind_context(self.graph_context)
        bind_diagnosis = getattr(run_task, 'bind_diagnosis_provider', None)
        if callable(bind_diagnosis):
            bind_diagnosis(self.diagnosis_context)

    def diagnosis_context(self, request, workspace, uid):
        from .native_diagnosis import NativeDiagnosis, DIAGNOSIS_POLICY
        from .native_task_context import checked_native_context
        native = checked_native_context(request.native_context)
        if native.get('systematic_diagnosis') != DIAGNOSIS_POLICY:
            raise ValueError('diagnosis was not selected by the application')
        context = NativeDiagnosis(root=self.root / 'tasks' / '.diagnoses' / request.task_id,
            state_root=self.storage.root / 'diagnoses' / request.task_id, uid=uid,
            policy=native['systematic_diagnosis'], storage=self.storage)
        with self._lock:
            self._tasks[request.task_id]['diagnosis_context'] = context
        return context

    def graph_context(self, request, workspace, uid):
        """Runner supplies the actual isolated UID; model input cannot select it."""
        from .native_graph_context import NativeGraphContext
        from .native_research_bridge import read_json
        binding = request.to_document()['research_binding']
        if binding.get('graph_schema') != 'capstone-enterprise-graph/2':
            raise ValueError('graph context requires the published graph protocol')
        mirror = self.research_mirror(request.task_id)
        context = NativeGraphContext(root=self.root / 'tasks' / '.contexts' / request.task_id,
            workspace=workspace, uid=uid, task_id=request.task_id,
            attempt_id=request.parent_attempt_id, owner=binding['cycle_owner'], storage=self.storage,
            adaptive_agent_loop=_adaptive_agent_loop(request),
            view_provider=lambda: {'binding': binding, 'view': read_json(mirror.root / 'view.json',
                maximum=mirror.limits['research_response_bytes'])})
        with self._lock:
            self._tasks[request.task_id]['graph_context'] = context
        return context

    def submit(self, request: PiTaskRequest) -> None:
        if request.to_document()['executor_identity'] != self.identity:
            raise ValueError('General Pi configuration changed')
        if request.native_context is not None:
            from .native_task_context import checked_native_context
            # PiTaskRequest admits native context only with a typed v2 profile.
            assert request.resource_profile is not None
            native = checked_native_context(request.native_context)
            role = 'direct_pi' if request.entrypoint == 'direct' else 'delegated_pi'
            store = getattr(self._run, 'resources', None)
            profile = (store.accepted(role, request.resource_profile['revision']) if store is not None
                       else self.capability.get('resource_profiles', {}).get(role, {}))
            published = set(self.capability.get('native_tools', ()))
            from .data_gateway_relay import research_gateway_tools
            published.update(research_gateway_tools(native, self.capability.get('data_gateway', {})))
            published.update(profile.get('load_receipt', {}).get('published_tool_ids', ()))
            if request.research_binding is not None:
                from .native_research_bridge import ALL_ENTERPRISE_RESEARCH_TOOLS
                published.update(ALL_ENTERPRISE_RESEARCH_TOOLS)
            if native['selected_task_records']:
                published.add('agent_task_records_read')
            from .native_diagnosis import DIAGNOSIS_POLICY, DIAGNOSIS_TOOLS
            if native.get('systematic_diagnosis') == DIAGNOSIS_POLICY:
                published.update(DIAGNOSIS_TOOLS)
            if not set(native['policy']['allowed_tools']) <= published:
                raise ValueError('native application requested an unpublished tool')
        with self._lock:
            self.sweep()
            old = self._tasks.get(request.task_id)
            if old is not None:
                if old['request'].to_document() != request.to_document():
                    raise ValueError('General Pi task identity conflict')
                return
            self._make_room()
            saved = self.storage.load(request.task_id)
            if saved is not None:
                if saved['request_hash'] != request_hash(request.to_document()):
                    raise ValueError('General Pi task identity conflict')
                if saved['result'] is None:
                    saved['result'] = {'schema': 'capstone-pi-task-result/1',
                        'task_id': request.task_id, 'parent_attempt_id': request.parent_attempt_id,
                        'executor_identity': self.identity, 'status': 'failed',
                        'answer': ('Result retention expired; task was not repeated.' if saved.get('expired')
                                   else 'Previous execution outcome is unknown; the task was not repeated.'),
                        'sources': [], 'artifacts': [], 'usage': {}}
                result = PiTaskResult.from_document(saved['result'], request)
                self._tasks[request.task_id] = {'request': request, 'status': result.status,
                    'events': [], 'result': result.to_document(), 'cancel': threading.Event()}
                return
            active_count = sum(item['status'] in {'queued', 'running'} for item in self._tasks.values())
            if active_count >= self._max_tasks:
                raise CapacityExceeded('native_task_count', active_count + 1, self._max_tasks,
                                       'native_task_admission', mode=current_capacity().mode)
            record = {'request': request, 'status': 'running', 'events': [], 'result': None,
                      'cancel': threading.Event(), 'research_sources': [], 'research_call_hashes': {}}
            if request.research_binding is not None:
                from .native_research_bridge import ResearchMirror
                record['research'] = ResearchMirror(self._research_path(request.task_id),
                    json.loads(json.dumps(request.to_document()['research_binding'])))
            # An accepted receipt prevents replaying an unknown side effect after restart.
            self._save(request, None)
            self._tasks[request.task_id] = record
            threading.Thread(target=self._execute, args=(request, record), daemon=True).start()

    def _save(self, request: PiTaskRequest, result: dict | None) -> None:
        self.storage.save(request.to_document(), result)

    def verify_gateway_observation(self, request, call_id, name, result, *, include_arguments=False):
        gateway = getattr(self._run, 'gateway', None)
        details = result.get('details', {})
        content = result.get('content', [])
        if (gateway is None or not content or content[0].get('type') != 'text'
                or not gateway.verify(request.task_id, call_id, name, details, content[0].get('text'))):
            raise ValueError('gateway observation was not issued by this host')
        if include_arguments:
            return gateway.verified_arguments(request.task_id, call_id, name, details, content[0]['text'])

    def record_network_policy(self, event: str, state: dict) -> None:
        path = self.root / 'receipts' / 'network-policy.jsonl'
        data = json.dumps({'schema': 'capstone-network-policy-event/1',
                           'time': time.time(), 'event': event, **state}) + '\n'
        descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, 'a') as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())

    def _make_room(self):
        if len(self._tasks) >= self._max_records:
            if current_capacity().mode == 'debug':
                raise CapacityExceeded('native_record_count', len(self._tasks) + 1, self._max_records,
                                       'native_record_admission', mode='debug')
            completed = next((key for key, item in self._tasks.items()
                              if item['status'] not in {'queued', 'running'}), None)
            if completed is None:
                raise CapacityExceeded('native_record_count', len(self._tasks) + 1, self._max_records,
                                       'native_record_admission', mode=current_capacity().mode)
            shutil.rmtree(self._research_path(completed), ignore_errors=True)
            del self._tasks[completed]

    def sweep(self):
        with self._lock:
            active = {key for key, item in self._tasks.items() if item['status'] in {'queued', 'running'}}
            self.resource_staging.sweep(active)
            for task_id in self.storage.sweep(active):
                shutil.rmtree(self.root / 'tasks' / task_id, ignore_errors=True)
                shutil.rmtree(self.root / 'tasks' / '.contexts' / task_id, ignore_errors=True)
                shutil.rmtree(self.root / 'tasks' / '.diagnoses' / task_id, ignore_errors=True)
                shutil.rmtree(self.storage.root / 'diagnoses' / task_id, ignore_errors=True)
                self._tasks.pop(task_id, None)
                shutil.rmtree(self._research_path(task_id), ignore_errors=True)
                self.resource_staging.remove(task_id)

    def _research_path(self, task_id):
        # Compose keeps the root filesystem read-only. Task control mirrors
        # belong on its existing private writable tasks mount, outside output.
        task = task_workspace(self.root / 'tasks', task_id)
        return task.parent / ('.research-' + task.name)

    def read_artifact(self, task_id, artifact_id):
        task_workspace(self.root, task_id)
        task_workspace(self.root, artifact_id)
        self.sweep()
        return self.storage.read_artifact(task_id, artifact_id)

    def research_mirror(self, task_id):
        with self._lock:
            item = self._tasks[task_id]
            if 'research' not in item:
                raise KeyError('research channel is not available')
            return item['research']

    def research_control(self, task_id, document):
        mirror = self.research_mirror(task_id)
        operation, owner = document.get('operation'), document.get('owner')
        if operation == 'pending' and set(document) == {'operation', 'owner'}:
            pending = mirror.pending(owner)
            with self._lock:
                refs = list(self._tasks[task_id].get('research_sources', []))
            return {'requests': pending, 'source_refs': refs}
        if set(document) != {'operation', 'owner', 'document'}:
            raise ValueError('research control fields are invalid')
        if operation == 'bootstrap':
            mirror.bootstrap(owner, document['document'])
        elif operation == 'acknowledge':
            mirror.acknowledge(owner, document['document'])
        else:
            raise ValueError('research control operation is invalid')
        return {'status': 'accepted'}

    def _execute(self, request: PiTaskRequest, record: dict) -> None:
        started = time.monotonic()
        sources = []
        from .native_diagnosis import DIAGNOSIS_POLICY, DIAGNOSIS_TOOLS
        native = request.native_context
        adaptive = _adaptive_agent_loop(request)
        direct_calls = {}
        diagnostic_sources = (set(DIAGNOSIS_TOOLS).intersection(native['policy']['allowed_tools'])
            if native is not None and native.get('systematic_diagnosis') == DIAGNOSIS_POLICY
            and self.capability.get('systematic_diagnosis') == DIAGNOSIS_POLICY else set())
        def cancelled():
            return record['cancel'].is_set() or time.monotonic() - started >= request.timeout_seconds
        def publish(payload):
            # Assign the transport sequence only after text coalescing. The
            # receiver still persists each event before acknowledging its page.
            while not cancelled():
                with self._lock:
                    if len(record['events']) < limits.event_buffer_count and len(json.dumps(record['events']).encode()) < limits.event_buffer_bytes:
                        sequence = record.get('event_sequence', 0) + 1
                        record['events'].append({'event_id': 'event-' + str(sequence), **payload})
                        record['event_sequence'] = sequence
                        return
                time.sleep(.02)
            raise InterruptedError('event delivery stopped with task')
        from .stream_progress import TextDeltaBuffer
        text_buffer = TextDeltaBuffer(lambda text: publish({'type': 'assistant_delta', 'text': text}))
        thinking_buffer = TextDeltaBuffer(lambda text: publish({'type': 'assistant_thinking_delta', 'text': text}))
        def capture_direct_observation(call_id, tool_name, result, *, is_error=False):
            context = record.get('graph_context')
            if (not adaptive or native is None or context is None or direct_calls.get(call_id) != tool_name
                    or tool_name not in native['policy']['allowed_tools']):
                raise ValueError('Direct observation has no authorized native call')
            failed = is_error or result.get('isError') is True
            gateway_tool = tool_name in self.capability.get('data_gateway', {}).get('catalog', {}).get('tools', {})
            if tool_name not in {'read', 'bash', 'edit', 'write', 'grep', 'find', 'ls'} and not gateway_tool:
                raise ValueError('Direct observation tool is invalid')
            if gateway_tool and (not failed or result.get('details', {}).get('kind') == 'external_gateway_observation'):
                self.verify_gateway_observation(request, call_id, tool_name, result)
            expected_ref = 'native-observation:' + request.task_id + ':' + sha256(call_id.encode()).hexdigest()
            issued = result.get('details', {}).get('native_research_source')
            if (issued != {'task_id': request.task_id, 'tool_call_id': call_id, 'source_ref': expected_ref}
                    and (not failed or issued is not None)):
                raise ValueError('Direct observation source identity changed')
            body = json.dumps(result, ensure_ascii=False).encode()
            digest = sha256(body).hexdigest()
            status = 'failed' if failed else 'completed'
            previous = record['research_call_hashes'].get(call_id)
            if previous is not None:
                if previous != digest or record.get('direct_call_statuses', {}).get(call_id) != status:
                    raise ValueError('Direct observation call identity changed')
                return
            from .application_capacity import require_capacity
            require_capacity('context_references', len(sources) + 1, 'direct_observation')
            observation_id = 'observation-' + str(len(sources)) + '-' + digest
            self.storage.observation(request.task_id, observation_id, body)
            if not failed:
                context.admit_direct_observation(expected_ref, observation_id, digest,
                    tool_call_id=call_id, tool_name=tool_name)
            record['research_call_hashes'][call_id] = digest
            record.setdefault('direct_call_statuses', {})[call_id] = status
            if not failed:
                record['research_sources'].append({'task_id': request.task_id,
                    'parent_attempt_id': request.parent_attempt_id, 'source_ref': expected_ref,
                    'observation_sha256': digest})
            sources.append({'source_id': observation_id, 'task_id': request.task_id,
                'parent_attempt_id': request.parent_attempt_id, 'kind': 'native_tool_observation',
                'metadata': {'tool_name': tool_name, 'tool_call_id': call_id, 'output_sha256': digest,
                    'execution_mode': 'direct', 'status': status, **({'source_ref': expected_ref} if not failed else {})}})

        def capture_graph_observation(call_id, tool_name, result, *, is_error=False, child=False):
            failed = is_error or result.get('isError') is True
            gateway_tool = tool_name in self.capability.get('data_gateway', {}).get('catalog', {}).get('tools', {})
            if gateway_tool and (not failed or result.get('details', {}).get('kind') == 'external_gateway_observation'):
                self.verify_gateway_observation(request, call_id, tool_name, result)
            issued = result.get('details', {}).get('native_research_source')
            guard, context = record.get('graph_events'), record.get('graph_context')
            if guard is None and failed and issued is None:
                return  # SDK validation failed before any graph lease existed.
            if guard is None or context is None:
                raise ValueError('graph observation has no host context')
            action_id = guard.action_for_call(call_id, tool_name, required=not failed)
            expected_ref = 'native-observation:' + request.task_id + ':' + sha256(call_id.encode()).hexdigest()
            expected_source = {'task_id': request.task_id, 'tool_call_id': call_id, 'source_ref': expected_ref}
            # The SDK can reject an unknown child selection before a native
            # wrapper runs. Its exact bound failure is diagnostic only: it has
            # no issued observation and grants no tool execution or source.
            unentered_rejection = (child and failed and issued is None
                and guard.failures.get(call_id) in {'failed', 'cancelled'})
            if ((tool_name not in {'read', 'bash', 'edit', 'write', 'grep', 'find', 'ls'} and not gateway_tool
                    and not (child and (tool_name == 'agent_task_return' or tool_name in diagnostic_sources))
                    and not unentered_rejection)
                    or issued != expected_source and (not failed or issued is not None)):
                raise ValueError('native observation source identity changed')
            # SDK validation and pre-execution aborts can fail before a wrapper
            # obtains a lease. Keep their bounded error event unowned; never
            # infer an action from the current graph or mint a source grant.
            if action_id is None:
                if issued is not None:
                    raise ValueError('unexecuted native call claimed an observation source')
                return
            status = guard.failures.get(call_id, 'failed' if failed else 'completed')
            if not failed and status != 'completed':
                raise ValueError('failed native call claimed a successful observation')
            body = json.dumps(result, ensure_ascii=False).encode()
            digest = sha256(body).hexdigest()
            previous = record['research_call_hashes'].get(call_id)
            if previous is not None:
                if previous != digest or record['graph_call_statuses'][call_id] != status:
                    raise ValueError('native observation call identity changed content or status')
                return
            from .application_capacity import require_capacity
            require_capacity('context_references', len(sources) + 1, 'graph_observation')
            observation_id = 'observation-' + str(len(sources)) + '-' + digest
            self.storage.observation(request.task_id, observation_id, body)
            if not failed:
                context.admit_observation(expected_ref, observation_id, digest, action_id=action_id)
            record['research_call_hashes'][call_id] = digest
            record.setdefault('graph_call_statuses', {})[call_id] = status
            if not failed:
                record['research_sources'].append({'task_id': request.task_id,
                    'parent_attempt_id': request.parent_attempt_id, 'source_ref': expected_ref,
                    'observation_sha256': digest})
            provenance = ({'execution_receipt': 'execution-receipt:' + sha256(
                (request.task_id + '\0' + call_id).encode()).hexdigest()} if failed else {'source_ref': expected_ref})
            sources.append({'source_id': observation_id, 'task_id': request.task_id,
                'parent_attempt_id': request.parent_attempt_id, 'kind': 'native_tool_observation',
                'metadata': {'tool_name': tool_name, 'tool_call_id': call_id,
                    'output_sha256': digest, **provenance, 'action_id': action_id, 'status': status}})
        def emit(event):
            # Public transport uses bounded receipts, never raw native frames.
            kind = event.get('type')
            # The isolated image includes this exact dependency-free Kernel
            # projection as a standalone module, without the full Kernel runtime.
            try:
                from capstone_runtime_events import project_runtime_action  # type: ignore[reportMissingImports]
            except ModuleNotFoundError:
                from capability_agent.runtime.step_events import project_runtime_action
            payload = project_runtime_action(event)
            if kind in {'delegation_child_started', 'delegation_child_tool', 'delegation_child_finished', 'delegation_child_response'}:
                from .native_research_bridge import checked_branch_progress, read_json
                if request.research_binding is None:
                    raise ValueError('research branch requires an accepted owner')
                mirror = self.research_mirror(request.task_id)
                from .native_task_context import checked_native_context, resolve_research_policy
                publication = resolve_research_policy(checked_native_context(request.native_context)['policy']['system_policy']) if request.native_context is not None else None
                allow_review = publication is not None and publication.delivery_review
                payload = checked_branch_progress(event, binding=request.to_document()['research_binding'],
                    task_id=request.task_id, attempt_id=request.parent_attempt_id,
                    allow_delivery_review=allow_review,
                    view=read_json(mirror.root / 'view.json', maximum=mirror.limits['research_response_bytes']))
                if payload['parent_tool_call_id'] not in record.get('delegate_calls', set()):
                    raise ValueError('research branch parent tool call was not observed')
                identity = (payload['parent_tool_call_id'], payload['child_id'])
                immutable = {key: payload[key] for key in ('subordinate', 'owner', 'attempt_id', 'parent_action_id',
                    'parent_step_id', 'parent_tool_call_id', 'child_id', 'title', 'questions', 'expected_outputs', 'checkpoint')}
                immutable['review_mode'] = payload.get('review_mode')
                bindings = record.setdefault('branch_bindings', {})
                if identity in bindings and bindings[identity] != immutable:
                    raise ValueError('research branch identity changed')
                bindings[identity] = immutable
                if kind == 'delegation_child_finished':
                    terminal = record.setdefault('branch_terminals', {})
                    if identity in terminal and terminal[identity] != payload:
                        raise ValueError('research branch terminal changed')
                    terminal[identity] = payload
            elif kind == 'enterprise_graph_progress':
                from .native_research_bridge import checked_graph_progress, read_json
                if request.research_binding is None:
                    raise ValueError('research graph requires an accepted owner')
                mirror = self.research_mirror(request.task_id)
                payload = checked_graph_progress(event, binding=request.to_document()['research_binding'],
                    task_id=request.task_id, attempt_id=request.parent_attempt_id,
                    view=read_json(mirror.root / 'view.json', maximum=mirror.limits['research_response_bytes']))
                if adaptive:
                    context = record.get('graph_context')
                    if context is None:
                        raise ValueError('Graph source validation has no host context')
                    context.validate_direct_sources(payload['graph'])
                from .native_graph_events import NativeGraphEvents
                if 'graph_events' not in record:
                    record['graph_events'] = NativeGraphEvents(owner=payload['owner'],
                        task_id=request.task_id, attempt_id=request.parent_attempt_id,
                        private_roots=(str(record['graph_context'].root),) if record.get('graph_context') is not None else ())
                record['graph_events'].admit_progress(payload)
            elif kind == 'systematic_diagnosis_request':
                context = record.get('diagnosis_context')
                if context is None:
                    raise ValueError('diagnosis context is not configured')
                context.handle(event)
                return  # Private request/receipt transport, not Authority evidence.
            elif kind == 'enterprise_graph_context_request':
                context = record.get('graph_context')
                if context is None:
                    raise ValueError('graph context is not configured')
                context.handle(event)
                return  # Private host RPC and handles never enter public progress.
            elif kind.startswith('enterprise_graph_'):
                guard = record.get('graph_events')
                if guard is None:
                    raise ValueError('graph native event preceded its committed graph')
                payload = guard.admit(event)
                if kind == 'enterprise_graph_tool_failure':
                    return  # Private per-call failure status; the native end is public.
                if kind == 'enterprise_graph_child_tool' and event.get('activity') == 'end':
                    capture_graph_observation(event['tool_call_id'], event['tool_name'], event.get('result', {}),
                        is_error=event.get('is_error') is True, child=True)
            elif kind == 'enterprise_cycle_progress':
                from .native_research_bridge import checked_cycle_progress, read_json
                if request.research_binding is None:
                    raise ValueError('research cycle progress requires an accepted owner')
                mirror = self.research_mirror(request.task_id)
                payload = checked_cycle_progress(event, binding=request.to_document()['research_binding'],
                    task_id=request.task_id, attempt_id=request.parent_attempt_id,
                    view=read_json(mirror.root / 'view.json', maximum=mirror.limits['research_response_bytes']))
            elif kind in {'tool_execution_start', 'tool_execution_end'}:
                payload = {'type': kind, 'tool_name': str(event.get('toolName', ''))[:128],
                           'tool_call_id': str(event.get('toolCallId', ''))[:128]}
                if adaptive and kind == 'tool_execution_start':
                    call_id, tool_name = payload['tool_call_id'], payload['tool_name']
                    if not call_id or (call_id in direct_calls and direct_calls[call_id] != tool_name):
                        raise ValueError('Native tool call identity changed')
                    from .application_capacity import require_capacity
                    require_capacity('event_buffer_count', len(direct_calls) + (call_id not in direct_calls), 'direct_observation')
                    direct_calls[call_id] = tool_name
                if kind == 'tool_execution_start' and event.get('toolName') == 'agent_delegate':
                    record.setdefault('delegate_calls', set()).add(payload['tool_call_id'])
                from capstone_agent.progress import project_native_tool_activity
                if request.research_binding is not None and request.research_binding.get('graph_schema') == 'capstone-enterprise-graph/2':
                    from .native_graph_events import project_graph_tool_activity
                    activity = project_graph_tool_activity(event,
                        (str(record['graph_context'].root),) if record.get('graph_context') is not None else ())
                else:
                    activity = project_native_tool_activity(event)
                if activity:
                    payload['activity'] = activity
                if kind == 'tool_execution_end' and (type(event.get('isError')) is bool
                        or event.get('result', {}).get('isError') is True):
                    payload['is_error'] = event.get('isError') is True or event.get('result', {}).get('isError') is True
                if kind == 'tool_execution_end' and request.research_binding is not None:
                    # Even after the capture budget is full, an admitted ID
                    # cannot alias a later different observation.
                    previous = record['research_call_hashes'].get(payload['tool_call_id'])
                    if previous is not None and previous != sha256(json.dumps(
                            event.get('result', {}), ensure_ascii=False).encode()).hexdigest():
                        raise ValueError('native observation call identity changed content')
                details = event.get('result', {}).get('details', {})
                if (request.research_binding is not None and kind == 'tool_execution_end'
                        and details.get('capability') == 'agent_task_progress' and details.get('ok') is True):
                    from jsonschema import Draft202012Validator
                    progress = details.get('result')
                    Draft202012Validator(request.to_document()['research_binding']['progress_tool_schema']).validate(progress)
                    payload['task_progress'] = progress
                graph_binding = (request.research_binding is not None
                    and request.research_binding.get('graph_schema') == 'capstone-enterprise-graph/2')
                if kind == 'tool_execution_end' and graph_binding and (payload['tool_name'] in {
                        'read', 'bash', 'edit', 'write', 'grep', 'find', 'ls', 'agent_task_return'}
                        or payload['tool_name'] in self.capability.get('data_gateway', {}).get('catalog', {}).get('tools', {})):
                    guard = record.get('graph_events')
                    action = guard.action_for_call(payload['tool_call_id'], payload['tool_name'], required=False) if guard is not None else None
                    capture = capture_direct_observation if adaptive and action is None else capture_graph_observation
                    capture(payload['tool_call_id'], payload['tool_name'], event.get('result', {}),
                            is_error=event.get('isError') is True)
                if kind == 'tool_execution_end' and not graph_binding and len(sources) < limits.context_references:
                    body = json.dumps(event.get('result', {}), ensure_ascii=False).encode()
                    digest = sha256(body).hexdigest()
                    observation_id = 'observation-' + str(len(sources)) + '-' + digest
                    self.storage.observation(request.task_id, observation_id, body)
                    source_kind = 'native_tool_observation'
                    metadata = {'tool_name': payload['tool_name'], 'tool_call_id': payload['tool_call_id'],
                                'output_sha256': digest}
                    if activity:
                        metadata['activity'] = activity
                    details = event.get('result', {}).get('details', {})
                    if payload['tool_name'].startswith('data_gateway_') and not payload.get('is_error'):
                        self.verify_gateway_observation(request, payload['tool_call_id'], payload['tool_name'], event['result'])
                    issued = details.get('native_research_source')
                    if request.research_binding is not None and isinstance(issued, dict):
                        expected_ref = ('native-observation:' + request.task_id + ':'
                            + sha256(payload['tool_call_id'].encode()).hexdigest())
                        allowed_sources = ({'read', 'bash', 'edit', 'write', 'grep', 'find', 'ls'}
                            if request.research_binding.get('graph_schema') == 'capstone-enterprise-graph/2'
                            else {'read', 'bash', 'edit', 'write', 'agent_delegate'})
                        if (payload['tool_name'] not in allowed_sources and not payload['tool_name'].startswith('data_gateway_')
                                or issued != {'task_id': request.task_id, 'tool_call_id': payload['tool_call_id'],
                                              'source_ref': expected_ref}):
                            raise ValueError('native observation source identity changed')
                        metadata['source_ref'] = expected_ref
                        with self._lock:
                            previous = record['research_call_hashes'].get(payload['tool_call_id'])
                            if previous is not None and previous != digest:
                                raise ValueError('native observation call identity changed content')
                            record['research_call_hashes'][payload['tool_call_id']] = digest
                            record['research_sources'].append({'task_id': request.task_id,
                                'parent_attempt_id': request.parent_attempt_id, 'source_ref': expected_ref,
                                'observation_sha256': digest})
                        if request.research_binding.get('graph_schema') == 'capstone-enterprise-graph/2':
                            context = record.get('graph_context')
                            guard = record.get('graph_events')
                            if context is None or guard is None:
                                raise ValueError('graph observation has no host context')
                            context.admit_observation(expected_ref, observation_id, digest,
                                action_id=guard.action_for_call(payload['tool_call_id'], payload['tool_name']))
                    if details.get('kind') == 'external_gateway_observation':
                        self.verify_gateway_observation(request, payload['tool_call_id'], payload['tool_name'], event['result'])
                        source_kind = 'external_gateway_observation'
                        metadata.update(catalog_revision=details['catalog_revision'],
                            tool_schema_sha256=details['tool_schema_sha256'], gateway_output_sha256=details['output_sha256'])
                    if details.get('kind') == 'external_mcp_observation':
                        role = 'direct_pi' if request.entrypoint == 'direct' else 'delegated_pi'
                        receipt = self.capability.get('resource_profiles', {}).get(role, {}).get('load_receipt', {})
                        store = getattr(self._run, 'resources', None)
                        if store is not None and request.resource_profile is not None:
                            receipt = store.accepted(role, request.resource_profile['revision'])['load_receipt']
                        content = event['result']['content']
                        def invalid_constant(_value):
                            raise ValueError('external MCP observation is not strict JSON')
                        json.loads(content[0]['text'], parse_constant=invalid_constant)
                        if (details.get('task_id') != request.task_id
                                or details.get('parent_attempt_id') != request.parent_attempt_id
                                or details.get('tool') != payload['tool_name']
                                or details.get('descriptor_sha256') != receipt.get('descriptor_sha256')
                                or details.get('tool_schema_sha256') != receipt.get('tool_schema_hashes', {}).get(payload['tool_name'])
                                or details.get('output_sha256') != sha256(content[0]['text'].encode()).hexdigest()):
                            raise ValueError('external MCP observation identity changed')
                        source_kind = 'external_mcp_observation'
                        metadata.update(descriptor_sha256=details['descriptor_sha256'],
                            tool_schema_sha256=details['tool_schema_sha256'], mcp_output_sha256=details['output_sha256'])
                    sources.append({'source_id': observation_id, 'task_id': request.task_id,
                        'parent_attempt_id': request.parent_attempt_id, 'kind': source_kind, 'metadata': metadata})
            elif kind == 'message_update':
                change = event.get('assistantMessageEvent', {})
                if change.get('type') == 'text_delta':
                    payload = {'type': 'assistant_delta', 'text': str(change.get('delta', ''))}
                elif change.get('type') == 'thinking_delta' and isinstance(change.get('delta'), str):
                    # Only the SDK's displayable stream delta enters this channel.
                    # Completed thinking blocks, signatures and replay metadata do not.
                    payload = {'type': 'assistant_thinking_delta', 'text': change['delta']}
            if (payload is not None and (kind == 'tool_execution_end'
                    or kind == 'enterprise_graph_child_tool' and event.get('activity') == 'end')
                    and payload.get('tool_name') in {'data_gateway_get_network_topology_view', 'data_gateway_open_network_model_view'}
                    and payload.get('is_error') is not True):
                # Verification is mandatory even when the observation capture
                # budget is full. Only the optional display projection can fail
                # open; a forged gateway receipt must still stop execution.
                result = event.get('result', {})
                arguments = self.verify_gateway_observation(request, payload['tool_call_id'], payload['tool_name'], result,
                    include_arguments=True)
                if payload['tool_name'] == 'data_gateway_open_network_model_view':
                    source_view = _electrical_view_from_verified_result(result, arguments)
                else:
                    from .grid_source_topology import source_view_from_gateway_result
                    source_view = source_view_from_gateway_result(result, arguments)
                if source_view is not None:
                    payload = {**payload, 'source_view': source_view}
            if payload is not None:
                if payload.get('type') == 'assistant_delta':
                    thinking_buffer.flush()
                    text_buffer.push(payload['text'])
                elif payload.get('type') == 'assistant_thinking_delta':
                    text_buffer.flush()
                    thinking_buffer.push(payload['text'])
                else:
                    text_buffer.flush()
                    thinking_buffer.flush()
                    publish(payload)
        status, answer, usage = 'completed', '', {}
        public_failure = None
        try:
            if request.research_binding is not None:
                mirror = self.research_mirror(request.task_id)
                while not mirror.ready.wait(.02):
                    if cancelled():
                        raise InterruptedError('research bootstrap was not confirmed')
            try:
                answer, usage = self._run(request, cancelled, emit)
            finally:
                if not cancelled():
                    text_buffer.flush()
                    thinking_buffer.flush()
        except InterruptedError as error:
            usage = getattr(error, 'saved_usage', usage)
            status = 'cancelled' if record['cancel'].is_set() else 'failed'
            if status == 'failed':
                public_failure = {'code': 'native_execution_error', 'phase': 'execution'}
        except Exception as error:
            usage = getattr(error, 'saved_usage', usage)
            status = 'failed'
            # Private receipt only: no error message, traceback, arguments or
            # environment. The operator can locate the failed setup phase.
            failure: dict = {'schema': 'capstone-pi-private-failure/1', 'task_id': request.task_id,
                       'phase': 'task_runner', 'exception_type': type(error).__name__[:64]}
            # Only fixed runtime messages map to private codes. Never persist
            # arbitrary exception text from tools, providers or user files.
            reason = {'General Pi frame exceeds bounds': 'rpc_frame_too_large',
                      'General Pi ended before completion': 'rpc_process_ended',
                      'General Pi rejected request': 'rpc_request_rejected',
                      'General Pi did not complete': 'model_turn_incomplete',
                      'General Pi task deadline exceeded': 'task_deadline_exceeded',
                      'General Pi answer is invalid': 'rpc_answer_invalid',
                      'native observation call identity changed content': 'observation_identity_conflict',
                      'native observation source identity changed': 'observation_source_invalid'}.get(str(error))
            if reason is not None:
                failure['reason_code'] = reason
            elif isinstance(error, ModuleNotFoundError):
                failure['reason_code'] = 'runtime_dependency_missing'
            elif str(error) in {'research branch requires an accepted owner',
                    'research branch progress is invalid', 'research branch identity is invalid',
                    'research branch review mode is invalid', 'research branch task metadata is invalid',
                    'research branch does not belong to the committed parent action',
                    'research branch parent tool call was not observed', 'research branch identity changed',
                    'research branch terminal changed', 'research branch result is invalid',
                    'research branch error is invalid', 'research branch tool activity is invalid'}:
                failure['reason_code'] = 'research_branch_invalid'
            elif str(error) in {'model_context_limit', 'model_rate_limit', 'model_authentication',
                                'model_transport', 'model_output_invalid', 'model_output_rejected',
                                'invalid_research_runtime','invalid_phase','research_checkpoint_rejected',
                                'research_update_not_confirmed','research_deadline','continuation_no_progress','task_goal_blocked'}:
                failure['reason_code'] = str(error)
            if isinstance(error, OSError) and type(error.errno) is int:
                failure['errno'] = error.errno
            public_failure = {'code': {
                'runtime_dependency_missing': 'native_runtime_dependency_missing',
                'research_branch_invalid': 'native_research_branch_invalid',
                'task_deadline_exceeded': 'native_task_deadline',
                'model_context_limit': 'native_model_context_limit',
                'model_rate_limit': 'native_model_rate_limit',
                'model_authentication': 'native_model_authentication',
                'model_transport': 'native_transport_failed',
                'model_output_invalid': 'native_model_output_invalid',
                'model_output_rejected': 'native_model_output_rejected',
                'model_turn_incomplete': 'native_model_turn_incomplete',
                'rpc_frame_too_large': 'native_response_too_large',
                'invalid_research_runtime': 'native_research_runtime_invalid',
                'invalid_phase': 'native_research_runtime_invalid',
                'research_checkpoint_rejected': 'native_research_checkpoint_failed',
                'research_update_not_confirmed': 'native_research_checkpoint_failed',
                'research_deadline': 'native_task_deadline',
                'continuation_no_progress': 'native_continuation_no_progress',
                'task_goal_blocked': 'native_goal_blocked',
            }.get(str(failure.get('reason_code', '')), 'native_execution_error'), 'phase': 'execution'}
            if isinstance(error, CapacityExceeded):
                public_failure = {'code': 'native_capacity_exceeded', 'phase': 'execution',
                                  'capacity': error.to_document()}
            try:
                self.storage._write(self.storage.root / 'failures' / (request.task_id + '.json'),
                                    json.dumps(failure).encode())
            except (OSError, CapacityExceeded):
                pass  # Keep the original failure; initial replay guard remains.
        if cancelled():
            status = 'cancelled' if record['cancel'].is_set() else 'failed'
            answer = ''
            public_failure = ({'code': 'native_task_deadline', 'phase': 'execution'}
                              if status == 'failed' else None)
        if record.get('capacity_failure') is not None:
            status, answer = 'failed', ''
            public_failure = {'code': 'native_capacity_exceeded', 'phase': 'execution',
                              'capacity': record['capacity_failure']}
        workspace = self.root / 'tasks' / request.task_id
        persisted = False
        saved_artifacts = []
        try:
            # Files written before failure or cancellation remain process output,
            # with the real terminal status; they are never promoted to delivery.
            presentation = None
            if status == 'completed' and request.research_binding is not None:
                mirror = record.get('research')
                owner = request.research_binding.get('cycle_owner')
                if mirror is not None and mirror.ready.is_set() and owner is not None:
                    from .native_product_roles import delivery_presentation, graph_delivery_presentation
                    from .native_research_bridge import read_json
                    view = read_json(mirror.root / 'view.json', maximum=mirror.limits['research_response_bytes'])
                    if request.research_binding.get('graph_schema') == 'capstone-enterprise-graph/2':
                        presentation = graph_delivery_presentation(view, task_id=request.task_id,
                            attempt_id=request.parent_attempt_id, binding=request.to_document()['research_binding'])
                    else:
                        presentation = delivery_presentation(view, task_id=request.task_id,
                            attempt_id=request.parent_attempt_id, owner=owner)
            artifacts = collect_artifacts(workspace, request.task_id, request.parent_attempt_id, presentation=presentation)
            self.storage.artifacts(request.task_id, workspace, artifacts)
            if record.get('graph_context') is not None:
                artifacts.extend(record['graph_context'].artifacts(presentation))
            saved_artifacts = artifacts
            result = PiTaskResult.from_document({'schema': 'capstone-pi-task-result/2' if public_failure else 'capstone-pi-task-result/1',
                'task_id': request.task_id, 'parent_attempt_id': request.parent_attempt_id,
                'executor_identity': self.identity, 'status': status, 'answer': answer,
                'sources': sources, 'artifacts': artifacts, 'usage': usage,
                **({'failure': public_failure} if public_failure else {})}, request).to_document()
            self._save(request, result)
            persisted = True
        except (OSError, ValueError, TypeError) as error:
            result = {'schema': 'capstone-pi-task-result/2', 'task_id': request.task_id,
                'parent_attempt_id': request.parent_attempt_id, 'executor_identity': self.identity,
                'status': 'failed', 'answer': '', 'sources': [],
                'artifacts': getattr(error, 'saved_artifacts', saved_artifacts), 'usage': usage,
                'failure': {'code': 'native_artifact_persistence_failed', 'phase': 'persistence'}}
            cause = error.__cause__ if error.__cause__ is not None else error
            if isinstance(cause, CapacityExceeded):
                result['failure'] = {'code': 'native_capacity_exceeded', 'phase': 'persistence',
                                     'capacity': cause.to_document()}
            try:
                self._save(request, result)
            except (OSError, CapacityExceeded):
                pass  # Initial accepted receipt remains an unknown-outcome replay guard.
        finally:
            if persisted:
                shutil.rmtree(workspace, ignore_errors=True)
        with self._lock:
            record['status'], record['result'] = result['status'], result

    def read(self, task_id: str, after: int | None = None) -> dict:
        with self._lock:
            item = self._tasks[task_id]
            if after is not None:
                if after < 0 or after > item.get('event_sequence', 0):
                    raise ValueError('event acknowledgement is invalid')
                item['events'] = [event for event in item['events']
                                  if int(event['event_id'].removeprefix('event-')) > after]
            document = {key: item[key] for key in ('status', 'events', 'result')}
            if after is not None:
                document['event_cursor'] = item.get('event_sequence', 0)
            return json.loads(json.dumps(document))

    def cancel(self, task_id: str) -> None:
        with self._lock:
            self._tasks[task_id]['cancel'].set()

    def interrupt_capacity(self, task_id: str, error: CapacityExceeded) -> None:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is not None:
                record['capacity_failure'] = error.to_document()
                record['cancel'].set()


class NativeTaskRunner:
    """Pi uses a task UID; host secrets remain in a different root process."""
    def __init__(self, *, root: Path, config_root: Path, command: tuple[str, ...],
                 model: str, relay_origin: str, network_policy=None, gateway=None) -> None:
        if os.geteuid() != 0 or os.name != 'posix':
            raise RuntimeError('General Pi requires its isolated Linux container')
        self.root, self.config_root, self.command = root, config_root, command
        self.model, self.relay_origin = model, relay_origin
        from .native_environment import environment_context
        self.environment_context = environment_context()
        self.network_policy = network_policy
        self.gateway = gateway
        self.gateway_publication = gateway.publication() if gateway else {'available': False, 'reason': 'not_configured'}
        self._lock = threading.Lock()
        self.relay = ProviderRelay()
        self.grants = self.relay.grants
        root.mkdir(mode=0o711, parents=True, exist_ok=True)
        (root / 'tasks').mkdir(mode=0o711, exist_ok=True)
        self.resources = None
        resource_config = config_root.parent
        if (resource_config / 'agent-resources.json').is_file():
            from .native_resources import NativeResourceStore
            self.resources = NativeResourceStore(resource_config, root / 'profiles')

    def bind_research_reader(self, reader):
        self._research_reader = reader

    def bind_graph_context_provider(self, provider):
        self._graph_context_provider = provider

    def bind_diagnosis_provider(self, provider):
        self._diagnosis_provider = provider

    def bind_resource_staging(self, staging):
        self._resource_staging = staging

    def __call__(self, request, cancelled, emit, *, inventory_only=False):
        with self._lock:
            counter = self.root / 'receipts' / 'next-uid'
            uid = int(counter.read_text()) if counter.exists() else 10000
            if uid >= 2**31 - 1:
                raise RuntimeError('General Pi task identities exhausted')
            counter.write_text(str(uid + 1))
            counter.chmod(0o600)
            grant = secrets.token_urlsafe(32)
            self.relay.register(request.task_id, grant, time.monotonic() + request.timeout_seconds)
        workspace = task_workspace(self.root / 'tasks', request.task_id)
        inputs = workspace.parent / ('.inputs-' + workspace.name)
        process = None
        try:
            role = 'direct_pi' if request.entrypoint == 'direct' else 'delegated_pi'
            document = request.to_document()
            context = {'messages': document['messages'], 'dependency_results': document['dependency_results']}
            # Host-owned status of this allocated execution, not a global task
            # inventory and not state inferred from the research controller.
            context['execution_state'] = {'source': 'native_task_runner',
                'task_id': request.task_id, 'parent_attempt_id': request.parent_attempt_id,
                'task_status': 'running', 'scope': 'current_native_task_only',
                'observed_at_ms': int(time.time() * 1000),
                'operating_system_processes_observed': False, 'other_tasks_observed': False}
            if request.business_context is not None:
                context['business_context'] = request.business_context.to_document()
            task_input = document.get('input', {'kind': 'text', 'text': request.instruction})
            sdk_config = {'sdk': str(Path(self.command[1]).with_name('index.js')),
                          'input': task_input, 'skillName': None, 'settings': {}, 'allowedSkills': [],
                          'contextFiles': [], 'mcp': None, 'inventoryOnly': inventory_only,
                          'context': context,
                          'deadlineAt': int((time.time() + request.timeout_seconds) * 1000),
                          'adapter_sha256': sha256(b''.join((Path(__file__).parent / name).read_bytes()
                              for name in ('bounded_mcp.py', 'resources/general-sdk.mjs', 'resources/general-mcp.mjs'))).hexdigest()}
            if self.resources is not None:
                accepted = document.get('resource_profile', {
                    'profile_id': role, 'revision': self.resources.profiles[role].revision})
                if accepted['profile_id'] != role:
                    raise ValueError('native resource profile role changed')
                sdk_config.update(self.resources.task_config(role, accepted['revision'], workspace=workspace,
                                                            request=request, inventory_only=inventory_only))
                if sdk_config['mcp']:
                    sdk_config['interpreter'] = str(Path(sdk_config['mcp']['install']) / 'venv/bin/python')
            elif task_input['kind'] != 'text':
                raise ValueError('native skills require an accepted resource profile')
            if self.environment_context:
                # Trusted build capabilities also belong to isolated executors.
                # Keep them separate from parent history and source grants.
                sdk_config['runtimeEnvironment'] = self.environment_context
                sdk_config.setdefault('contextFiles', []).append({
                    'path': 'verified-programming-environment', 'content': self.environment_context})
            if request.native_context is not None:
                from .native_task_context import checked_native_context, resolve_research_policy
                native = checked_native_context(request.native_context)
                sdk_config['applicationPolicy'] = native['policy']
                if native.get('systematic_diagnosis'):
                    diagnosis = self._diagnosis_provider(request, workspace, uid)
                    sdk_config['diagnosisContextPath'] = str(diagnosis.root)
                from .data_gateway_relay import research_gateway_tools
                gateway_tools = research_gateway_tools(native, self.gateway.publication() if self.gateway else {})
                admitted_gateway = gateway_tools.intersection(native['policy']['allowed_tools'])
                if admitted_gateway and self.gateway is not None:
                    self.gateway.bind(request.task_id, request.parent_attempt_id)
                    sdk_config['dataGateway'] = {'url': self.relay_origin + '/data-gateway/' + request.task_id,
                        'grant': grant, 'taskId': request.task_id, 'catalog': self.gateway.publication()['catalog']}
                    sdk_config.setdefault('contextFiles', []).append({'path': 'registered-production-data',
                        'content': 'Application-authorized data_gateway_ tools provide production data through a protected service. '
                        'Choose the published tool that directly answers the current instruction. Discover capabilities or services only when the needed operation is unknown. '
                        'For an inventory request, use summary/default arguments and answer from the returned list; do not add readiness audits, topology loading, sample opening or model builds unless requested. '
                        'When discover_network_models is admitted, a model-list request needs that inventory once with default detail=false, not a broader service investigation. '
                        'For a requested electrical source view, use the discovered model_ref with open_network_model_view and source_node_breaker. '
                        'If it returns preparing, query only its returned preparation_ref with get_network_model_job, then reopen after success. Do not poll without a bounded wait or retry failed preparation. '
                        'Read groups first at the model root; select a returned station/device target and open its local view with parent_view_ref and expected_model_revision. '
                        'Never prefetch all network devices or reconstruct a full network just to open a diagram. Preserve exact view_ref, model_revision, selection_ref and source_snapshot_ref on reads. '
                        'Use refresh_source only when the current instruction asks to refresh source data. Captured content is fixed; source transaction consistency may remain unverified. '
                        'A ready source view supports display, not power-flow readiness or Authority results. Calculation views require an admitted artifact and exact model mapping; do not invent one or build through this research adapter. '
                        'Registered scopes, built artifacts and calculation readiness are distinct claims. Preserve the returned distinction instead of trying extra operations to certify a list. '
                        'For actual data analysis, discover the needed exact objects, metrics, sources and time coverage. '
                        'These explicit data grants do not enable arbitrary external web lookup. Preserve status, gaps, provenance and calculation. '
                        'Use prepare_data_query before execute_data_query and retain its returned validation fingerprint. '
                        'Do not guess units, source IDs, joins, availability or missing values. '
                        'Save retrieved data and analysis as named task products when needed for subsequent analysis. '
                        'The gateway owns all backend selection. Only published tools in the current grant are enabled; inventory admission does not grant model inspection, build or artifact access.'})
                sdk_config['selectedTaskRecords'] = native['selected_task_records']
                sdk_config['selectedTaskMaterials'] = native.get('materials', [])
                sdk_config['researchSources'] = sorted({
                    *('material:' + item['material_id'] + ':' + item['sha256'] for item in native.get('materials', [])),
                    *(f"resource:{item['resource_id']}:{item['version']}:{item['sha256']}"
                      for item in native.get('resource_manifests', [])),
                })
                origins = {item['resource_id']: item for item in native.get('resource_origins', [])}
                sdk_config['selectedResourceFiles'] = [{**resource,
                    'source_path':str(self._resource_staging.source(request.task_id, resource)),
                    **({'source_artifact': origins[resource['resource_id']]} if resource['resource_id'] in origins else {})}
                    for resource in native.get('resource_manifests', [])]
                if native.get('material_notices'):
                    sdk_config.setdefault('contextFiles', []).append({'path': 'session-material-status',
                        'content': 'These user-supplied file names were not staged; do not claim to have read them: '
                            + json.dumps(native['material_notices'], ensure_ascii=False)})
                sdk_config['context']['records_truncated'] = native['records_truncated']
                sdk_config['context']['selected_task_source'] = native['selected_task_source']
                sdk_config['appendSystemPrompt'] = [*sdk_config.get('appendSystemPrompt', []), native['policy']['system_policy']]
                from .native_research_bridge import CYCLE_CONTROL_TOOLS, SPLIT_CYCLE_CONTROL_TOOLS, LEGACY_CYCLE_CONTROL_TOOLS, GRAPH_CONTROL_TOOLS
                control_tools = set(native['policy']['allowed_tools']).intersection(set(CYCLE_CONTROL_TOOLS) | set(GRAPH_CONTROL_TOOLS))
                if control_tools:
                    publication = resolve_research_policy(native['policy']['system_policy'])
                    expected_controls = (GRAPH_CONTROL_TOOLS if publication is not None and publication.graph_schema
                        else LEGACY_CYCLE_CONTROL_TOOLS if publication is not None and publication.application_version == '1.1.0'
                        else SPLIT_CYCLE_CONTROL_TOOLS)
                    if publication is None or control_tools != set(expected_controls):
                        raise ValueError('native research control interface is inconsistent')
                    from enterprise_research import ResearchPolicy
                    sdk_config['researchGuidance'] = ResearchPolicy(publication.pack_version, variant=publication.variant).progress_guidance()
                    selected_runtime = sdk_config.get('settings', {}).get('researchRuntime')
                    sdk_config['researchRuntime'] = json.loads(json.dumps(selected_runtime or {}))
                    sdk_config['researchRuntime']['deliveryReview'] = {
                        **sdk_config['researchRuntime'].get('deliveryReview', {}), 'enabled': publication.delivery_review}
                    sdk_config['researchRuntime']['gracefulExecutionClosure'] = publication.graceful_execution_closure
                    sdk_config['researchRuntime']['explicitSubtaskPlanning'] = publication.explicit_subtask_planning
                    sdk_config['researchRuntime']['batchReadyInvestigations'] = publication.batch_ready_investigations
                    if publication.graph_schema:
                        if document.get('research_binding', {}).get('graph_schema') != publication.graph_schema:
                            raise ValueError('graph policy and protected binding differ')
                        sdk_config['researchRuntime']['graphSchema'] = publication.graph_schema
                        sdk_config['researchRuntime']['isolatedTaskExecution'] = publication.isolated_task_execution
                        sdk_config['researchRuntime']['goalDrivenExecution'] = publication.goal_driven_execution
                        sdk_config['researchRuntime']['lightweightTaskNodes'] = publication.lightweight_task_nodes
                        sdk_config['researchRuntime']['adaptiveAgentLoop'] = publication.adaptive_agent_loop
                        if publication.work_edition:
                            if document.get('research_binding', {}).get('graph_work_edition') != publication.work_edition:
                                raise ValueError('graph work policy and protected binding differ')
                            sdk_config['researchRuntime']['graphWorkEdition'] = publication.work_edition
                            sdk_config['researchRuntime']['graphWorkStartedAt'] = native['graph_work']['started_at_ms']
                            work = publication.work_policy()
                            if not publication.goal_driven_execution:
                                work.update(sdk_config['researchRuntime'].get('graphWork', {}))
                            if (set(work) != set(publication.work_policy()) or work.get('schema') != publication.work_edition
                                    or work.get('mode') not in {'off', 'usable_draft'}
                                    or any(type(work.get(key)) is not int or work[key] <= 0 for key in
                                        ('target_seconds', 'integration_reserve_seconds', 'child_wrapup_seconds'))
                                    or work['target_seconds'] <= work['integration_reserve_seconds'] + work['child_wrapup_seconds']):
                                raise ValueError('selected graph work envelope is invalid')
                            sdk_config['researchRuntime']['graphWork'] = work
                        else:
                            # Old selected publications never acquire a new work contract from settings.
                            for key in ('graphWork', 'graphWorkEdition', 'graphWorkStartedAt'):
                                sdk_config['researchRuntime'].pop(key, None)
                        sdk_config['researchRuntime']['graphLimits'] = {
                            'maxNodes': limits.research_question_count, 'maxItems': limits.research_finding_count,
                            'maxText': limits.research_summary_chars, 'maxExecutions': limits.research_note_count,
                            'snapshotBytes': limits.research_snapshot_bytes, 'publicBytes': limits.event_bytes,
                            'resultBytes': limits.event_bytes}
            if self.network_policy is not None:
                from .native_network_policy import execution_policy
                state = self.network_policy.state()
                if not state['enforced']:
                    raise RuntimeError('network enforcement is not ready')
                previous = sdk_config.get('applicationPolicy', {})
                effective = execution_policy(previous, external_access=state['external_access'])
                if previous:
                    sdk_config['applicationPolicy'] = effective
                prompts = sdk_config.get('appendSystemPrompt', [])
                sdk_config['appendSystemPrompt'] = [p for p in prompts if p != previous.get('system_policy')]
                sdk_config['appendSystemPrompt'].append(effective['system_policy'])
                emit({'type': 'network_policy', **state})
            if request.research_binding is not None:
                mirror = self._research_reader(request.task_id)
                if not mirror.ready.is_set():
                    raise RuntimeError('research view is not ready')
                sdk_config['researchChannelPath'] = str(mirror.root)
                sdk_config['researchTaskId'] = request.task_id
                owner = document['research_binding'].get('cycle_owner')
                if owner is not None:
                    sdk_config['researchOwner'] = owner
                    sdk_config['researchAttemptId'] = request.parent_attempt_id
                    sdk_config.setdefault('researchSources', [])
                if document['research_binding'].get('graph_schema') == 'capstone-enterprise-graph/2':
                    context_host = self._graph_context_provider(request, workspace, uid)
                    sdk_config['graphContextPath'] = str(context_host.root)
            launch_options = {}
            if sdk_config.get('selectedResourceFiles'):
                inputs = task_workspace(self.root / 'inputs', request.task_id)
                launch_options['input_directory'] = inputs
            argv, environment = native_pi_launch(command=self.command, workspace=workspace,
                config_root=self.config_root, model=self.model,
                relay_url=self.relay_origin + '/provider/' + request.task_id, relay_token=grant,
                context_extension=Path(__file__).parent / 'resources' / 'general-context.mjs',
                sdk_config=sdk_config, **launch_options)
            for path in [workspace, *workspace.rglob('*')]:
                os.chown(path, uid, uid)
            for path in [inputs, *inputs.rglob('*')]:
                os.chown(path, 0, uid)
                path.chmod(0o550 if path.is_dir() else 0o440)
            if request.research_binding is not None:
                # Pi can publish only requests. State and receipts stay host-owned.
                mirror = self._research_reader(request.task_id)
                mirror.root.parent.chmod(0o711)
                for path in [mirror.root, *mirror.root.rglob('*')]:
                    os.chown(path, 0, uid)
                    path.chmod(0o550 if path.is_dir() else 0o440)
                (mirror.root / 'requests').chmod(0o700)
                os.chown(mirror.root / 'requests', uid, uid)
            role_options = ({'required_tools': ('agent_research_plan', 'agent_research_record', 'agent_research_assess',
                'agent_research_revise', 'agent_research_finish'),
                'forbidden_tools': ('read', 'bash', 'write', 'edit', 'agent_delegate')}
                if (sdk_config.get('researchRuntime', {}).get('isolatedTaskExecution')
                    and not sdk_config.get('researchRuntime', {}).get('adaptiveAgentLoop')) else {})
            process = GeneralPiProcess(argv, environment, workspace, uid=uid, **role_options)
            answer = process.run(request.instruction, timeout=request.timeout_seconds,
                                 cancelled=cancelled, on_event=emit, inventory_only=inventory_only)
            return answer, ({'native_tools': process.tools, 'inventory': process.inventory} if inventory_only else process.usage)
        except Exception as error:
            if process is not None:
                setattr(error, 'saved_usage', process.usage)
            raise
        finally:
            try:
                if process is not None:
                    process.stop()
            finally:
                with self._lock:
                    self.relay.revoke(request.task_id)
                if self.gateway:
                    self.gateway.revoke(request.task_id)
                shutil.rmtree(inputs, ignore_errors=True)
                if hasattr(self, '_resource_staging'):
                    self._resource_staging.remove(request.task_id)

    def verify_tools(self, identity):
        task_id = 'readiness-' + secrets.token_hex(8)
        request = PiTaskRequest.from_document({'schema': 'capstone-pi-task/1', 'task_id': task_id,
            'parent_attempt_id': task_id, 'entrypoint': 'direct', 'instruction': 'Readiness',
            'messages': [], 'dependency_results': [], 'executor_identity': identity, 'timeout_seconds': 15})
        try:
            checked = self(request, lambda: False, lambda _: None, inventory_only=True)[1]
            self.builtin_tools = checked['inventory'].get('builtin_tools', [])
            return checked['native_tools']
        finally:
            shutil.rmtree(self.root / 'tasks' / task_id, ignore_errors=True)

    def verify_resources(self, identity):
        if self.resources is None:
            return {}
        result = {}
        for role in ('direct_pi', 'delegated_pi'):
            task_id = 'resources-' + secrets.token_hex(8)
            request = PiTaskRequest.from_document({'schema': 'capstone-pi-task/1', 'task_id': task_id,
                'parent_attempt_id': task_id, 'entrypoint': 'direct' if role == 'direct_pi' else 'delegated',
                'instruction': 'Readiness', 'messages': [], 'dependency_results': [],
                'executor_identity': identity, 'timeout_seconds': 90})
            try:
                inventory = self(request, lambda: False, lambda _: None, inventory_only=True)[1]['inventory']
                if inventory['adapter_sha256'] != sha256(b''.join((Path(__file__).parent / name).read_bytes()
                        for name in ('bounded_mcp.py', 'resources/general-sdk.mjs', 'resources/general-mcp.mjs'))).hexdigest():
                    raise ValueError('native adapter publication changed')
                profile = self.resources.confirm_loaded(role, inventory)
                result[role] = {**profile.to_document(),
                    'load_receipt': self.resources.accepted(role, profile.revision)['load_receipt']}
            finally:
                shutil.rmtree(self.root / 'tasks' / task_id, ignore_errors=True)
        return result


def make_server(host: GeneralPiHost, *, control_token: str, address: tuple[str, int],
                runner: NativeTaskRunner | None = None, upstream: str | None = None,
                provider_key: str | None = None, network_policy=None):
    if not control_token:
        raise ValueError('General Pi control authentication is required')
    from .grid_source_topology import GridSourceProvider, GridSourceError, REQUEST_BYTES
    source_provider = GridSourceProvider(getattr(runner or host._run, 'gateway', None))
    from .grid_electrical_view import ElectricalViewProvider, ElectricalViewError
    electrical_provider = ElectricalViewProvider(getattr(runner or host._run, 'gateway', None))
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self._request_started=time.monotonic()
            self.connection.settimeout(limits.native_server_wait_seconds)

        def request_timeout(self):
            try:
                observe_capacity('native_server_wait_seconds',math.ceil(time.monotonic()-self._request_started),
                                 phase='native_http_request')
            except CapacityExceeded as error:
                return self.send_json(408,{'error':'capacity_exceeded','capacity':error.to_document()})
            return self.send_json(408,{'error':'request_timeout'})

        def log_message(self, format, *args):
            pass

        def send_json(self, status, document):
            data = json.dumps(document).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def authorized(self):
            return secrets.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + control_token)

        def source_error(self, error):
            code = str(error)
            status = 409 if code == 'grid_source_view_changed' else 400 if code == 'grid_source_request_invalid' else 503
            return self.send_json(status, {'error': code})

        def do_GET(self):
            if self.path == '/health/ready':
                return self.send_json(200, {'identity': host.identity, 'capability': host.capability})
            if not self.authorized():
                return self.send_json(401, {'error': 'unauthorized'})
            try:
                if self.path == '/grid-sources':
                    return self.send_json(200, source_provider.catalog())
                if self.path == '/grid-sources/data-gateway/electrical/models':
                    try:
                        return self.send_json(200, run_http(electrical_provider.models()))
                    except ElectricalViewError as error:
                        return self.send_json(error.status, {'error': error.code})
                if self.path == '/grid-sources/data-gateway/scopes':
                    return self.send_json(200, run_http(source_provider.scopes()))
                if self.path == '/network-policy':
                    if network_policy is None:
                        return self.send_json(503, {'error': 'network_policy_unavailable'})
                    return self.send_json(200, network_policy.state())
                parts = self.path.split('/')
                if len(parts) == 5 and parts[1] == 'tasks' and parts[3] == 'artifacts':
                    data = host.read_artifact(parts[2], parts[4])
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/octet-stream')
                    self.send_header('Content-Length', str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                if not self.path.startswith('/tasks/'):
                    raise KeyError()
                path = urlsplit(self.path)
                query = parse_qs(path.query)
                after = int(query['after'][0]) if 'after' in query else None
                self.send_json(200, host.read(path.path.removeprefix('/tasks/'), after))
            except GridSourceError as error:
                self.source_error(error)
            except TimeoutError:
                self.request_timeout()
            except CapacityExceeded as error:
                if error.mode=='debug':
                    return self.send_json(400,{'error':'capacity_exceeded','capacity':error.to_document()})
                self.send_json(404,{'error':'task_not_found'})
            except (KeyError, OSError, ValueError):
                self.send_json(404, {'error': 'task_not_found'})

        def do_DELETE(self):
            if not self.authorized():
                return self.send_json(401, {'error': 'unauthorized'})
            try:
                task_id = self.path.removeprefix('/tasks/')
                host.cancel(task_id)
                self.send_json(200, {'task_id': task_id, 'status': 'cancellation_requested'})
            except KeyError:
                self.send_json(404, {'error': 'task_not_found'})

        def do_POST(self):
            if self.path.startswith('/data-gateway/'):
                return self.relay_data_gateway()
            if self.path.startswith('/provider/'):
                return self.relay_provider()
            if not self.authorized():
                return self.send_json(401, {'error': 'unauthorized'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                parts = self.path.split('/')
                electrical_routes = {f'/grid-sources/data-gateway/electrical/{name}': getattr(electrical_provider, name)
                                     for name in ('open', 'read', 'job')}
                if self.path in electrical_routes:
                    try:
                        if not 0 < length <= REQUEST_BYTES:
                            raise ElectricalViewError('grid_electrical_request_invalid')
                        try:
                            document = json.loads(self.rfile.read(length))
                        except (ValueError, UnicodeDecodeError):
                            raise ElectricalViewError('grid_electrical_request_invalid') from None
                        return self.send_json(200, run_http(electrical_routes[self.path](document)))
                    except ElectricalViewError as error:
                        return self.send_json(error.status, {'error': error.code})
                if self.path in {'/grid-sources/data-gateway/resolve-scope', '/grid-sources/data-gateway/topology'}:
                    if not 0 < length <= REQUEST_BYTES:
                        raise GridSourceError('grid_source_request_invalid')
                    try:
                        document = json.loads(self.rfile.read(length))
                    except (ValueError, UnicodeDecodeError):
                        raise GridSourceError('grid_source_request_invalid') from None
                    operation = (source_provider.topology if self.path.endswith('/topology')
                                 else source_provider.resolve_scope)
                    return self.send_json(200, run_http(operation(document)))
                if self.path == '/network-policy':
                    if network_policy is None:
                        return self.send_json(503, {'error': 'network_policy_unavailable'})
                    if not 0 < length <= 128:
                        raise ValueError('invalid network policy request')
                    document = json.loads(self.rfile.read(length))
                    if not isinstance(document, dict) or set(document) != {'external_access'}:
                        raise ValueError('invalid network policy request')
                    if type(document['external_access']) is not bool:
                        raise ValueError('external_access must be a boolean')
                    try:
                        with host._lock:
                            # A full audit disk must never prevent closing egress.
                            if document['external_access'] is False:
                                network_policy.set_external_access(False)
                            host.record_network_policy('requested', document)
                            state = network_policy.set_external_access(document['external_access'])
                            host.record_network_policy('applied', state)
                    except (subprocess.SubprocessError, OSError, RuntimeError):
                        return self.send_json(503, {'error': 'network_policy_apply_failed'})
                    return self.send_json(200, state)
                if self.path == '/inputs':
                    if not 0 < length <= limits.upload_chunk_max_bytes * 2:
                        raise ValueError('resource part request exceeds bounds')
                    return self.send_json(200, host.resource_staging.control(json.loads(self.rfile.read(length))))
                if len(parts) == 4 and parts[1] == 'tasks' and parts[3] == 'research':
                    # Bootstrap/acknowledge carry a full committed research
                    # view; pending batches carry research request records.
                    if not 0 < length <= max(limits.research_request_bytes, limits.research_response_bytes):
                        raise ValueError()
                    try:
                        return self.send_json(200, host.research_control(parts[2], json.loads(self.rfile.read(length))))
                    except RuntimeError:
                        return self.send_json(409, {'error': 'research_owner_conflict'})
                    except ValueError as error:
                        if str(error) == 'research transport file changed':
                            return self.send_json(400, {'error': 'research_transport_file_changed'})
                        raise
                if self.path != '/tasks' or not 0 < length <= limits.native_task_bytes:
                    raise ValueError()
                request = PiTaskRequest.from_document(json.loads(self.rfile.read(length)))
                host.submit(request)
                self.send_json(202, {'task_id': request.task_id})
            except GridSourceError as error:
                self.source_error(error)
            except TimeoutError:
                self.request_timeout()
            except CapacityExceeded as error:
                return self.send_json(400,{'error':'capacity_exceeded','capacity':error.to_document()})
            except (ValueError, KeyError):
                self.send_json(400, {'error': 'invalid_task'})
            except (RuntimeError, OSError):
                self.send_json(503, {'error': 'executor_capacity'})

        def relay_data_gateway(self):
            from .data_gateway_mcp import GatewayError
            gateway = getattr(runner, 'gateway', None)
            parts = self.path.split('/')
            if runner is None or gateway is None or len(parts) != 3 or not parts[2]:
                return self.send_json(404, {'error': 'gateway_unavailable'})
            task_id = parts[2]
            grant = self.headers.get('Authorization', '').removeprefix('Bearer ')
            try:
                lease = runner.relay.acquire(task_id, grant, self.connection)
            except PermissionError:
                return self.send_json(401, {'error': 'unauthorized'})
            except CapacityExceeded as error:
                if error.mode == 'debug':
                    host.interrupt_capacity(task_id, error)
                    runner.relay.revoke(task_id)
                return self.send_json(503, {'error': 'capacity_exceeded', 'capacity': error.to_document()})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= limits.mcp_frame_bytes:
                    raise GatewayError('gateway_request_invalid')
                document = json.loads(self.rfile.read(length))
                async def forward():
                    lease.loop, lease.task = asyncio.get_running_loop(), asyncio.current_task()
                    if lease.cancelled.is_set():
                        raise asyncio.CancelledError()
                    async with asyncio.timeout(max(.001, lease.deadline - time.monotonic())):
                        return await gateway.call(task_id, document)
                self.send_json(200, run_http(forward()))
            except GatewayError as error:
                self.send_json(400, {'error': str(error)})
            except CapacityExceeded as error:
                if error.mode == 'debug':
                    host.interrupt_capacity(task_id, error)
                    runner.relay.revoke(task_id)
                self.send_json(503, {'error': 'capacity_exceeded', 'capacity': error.to_document()})
            except (ValueError, OSError, TimeoutError, asyncio.CancelledError, CancelledError):
                self.close_connection = True
            finally:
                runner.relay.release(lease)

        def relay_provider(self):
            # A task gets a revocable relay grant, never the Provider credential.
            parts = self.path.split('/')
            if (runner is None or upstream is None or not provider_key or len(parts) != 5
                    or parts[3:] != ['chat', 'completions']):
                return self.send_json(404, {'error': 'relay_not_found'})
            try:
                authorization = self.headers.get('Authorization', '')
                grant = authorization.removeprefix('Bearer ') if authorization.startswith('Bearer ') else ''
                lease = runner.relay.acquire(parts[2], grant, self.connection)
            except PermissionError:
                return self.send_json(401, {'error': 'unauthorized'})
            except CapacityExceeded as error:
                if error.mode == 'debug':
                    host.interrupt_capacity(parts[2], error)
                    runner.relay.revoke(parts[2])
                return self.send_json(400 if error.mode == 'debug' else 503,
                    {'error': 'capacity_exceeded', 'capacity': error.to_document()})
            except RuntimeError:
                return self.send_json(503, {'error': 'relay_capacity_reached'})
            try:
                self.connection.settimeout(0.2)
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= limits.provider_request_bytes:
                    raise ValueError()
                body = self.rfile.read(length)
                document = json.loads(body)
                if document.get('model') != runner.model:
                    raise ValueError()
                target = urlsplit(upstream)
                if target.hostname is None or target.scheme not in {'http', 'https'}:
                    raise ValueError()
                run_http(forward_provider(self, lease, upstream, body, provider_key))
            except CapacityExceeded as error:
                if error.mode == 'debug':
                    host.interrupt_capacity(parts[2], error)
                    runner.relay.revoke(parts[2])
                self.send_json(400 if error.mode == 'debug' else 503,
                    {'error': 'capacity_exceeded', 'capacity': error.to_document()})
            except (ValueError, OSError, httpx.HTTPError, asyncio.CancelledError, CancelledError):
                self.close_connection = True
            finally:
                runner.relay.release(lease)
    class BoundedServer(ThreadingHTTPServer):
        maximum = limits.native_server_connections
        slots = threading.BoundedSemaphore(maximum)
        def process_request(self, request, client_address):
            if not self.slots.acquire(blocking=False):
                error = CapacityExceeded('native_server_connections', self.maximum + 1,
                    self.maximum, 'native_http_accept', mode=current_capacity().mode)
                body = json.dumps({'error': 'capacity_exceeded', 'capacity': error.to_document()}).encode()
                try:
                    assert isinstance(request, socket.socket)
                    request.settimeout(1)
                    request.sendall(b'HTTP/1.1 503 Service Unavailable\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: '
                        + str(len(body)).encode() + b'\r\n\r\n' + body)
                except OSError:
                    pass
                self.close_request(request)
                return
            try:
                super().process_request(request, client_address)
            except BaseException:
                self.slots.release()
                raise
        def process_request_thread(self, request, client_address):
            try:
                super().process_request_thread(request, client_address)
            finally:
                self.slots.release()
    return BoundedServer(address, Handler)


def main():
    initialize_capacity(environment=os.environ)
    if os.environ.get('CAPSTONE_GENERAL_SANDBOX') != 'container':
        raise RuntimeError('General Pi service must run in the isolated container')
    config = Path('/opt/general/configs/runtime/general-pi')
    root = Path('/var/lib/general-pi')
    providers = json.loads(Path('/opt/general/llm-providers.json').read_bytes())['providers']
    provider = providers[os.environ['CAPSTONE_PUBLIC_PROVIDER']]
    if (provider['auth']['kind'] != 'api_key_env'
            or provider['compatibility_profile'] == 'anthropic-messages'):
        raise ValueError('General Pi relay requires an API-key chat-completions transport')
    key = os.environ[provider['auth']['default_env']]
    port = int(os.environ.get('PORT', '8790'))
    from .native_network_policy import NativeNetworkPolicy, InternalEndpoint
    endpoints = json.loads(os.environ.get('CAPSTONE_NATIVE_INTERNAL_ENDPOINTS', '[]'))
    if not isinstance(endpoints, list) or len(endpoints) > 64:
        raise ValueError('invalid internal network configuration')
    network_policy = NativeNetworkPolicy(relay_port=port,
        internal_endpoints=tuple(InternalEndpoint(**item) for item in endpoints))
    # No task (including resource inventory) may start before enforcement.
    network_policy.start()
    from .data_gateway_relay import load_container_gateway
    gateway, gateway_publication = load_container_gateway(
        os.environ.get('CAPSTONE_DATA_GATEWAY_CONNECTION_FILE'), config.parent / 'data-gateway.json')
    # Accepted native configuration belongs to its role profile. Engine and
    # fixed dispatch changes remain bound by executor_revision below.
    revision = sha256(b'capstone-general-sdk/2:isolated-uid:fixed-relay:fixed-mcp'
                      + current_capacity().fingerprint.encode())
    from .native_environment import environment_context
    revision.update((environment_context() or '').encode())
    revision.update(json.dumps(gateway_publication, sort_keys=True).encode())
    lock = json.loads(Path('/opt/general/pi-runtime.lock.json').read_bytes())
    identity = {'engine': 'pi', 'model': os.environ['CAPSTONE_PUBLIC_MODEL'],
                'provider': os.environ['CAPSTONE_PUBLIC_PROVIDER'],
                'pi_commit': lock['source']['commit'], 'config_revision': revision.hexdigest(),
                'runtime_lock_sha256': sha256(Path('/opt/general/pi-runtime.lock.json').read_bytes()).hexdigest(),
                'executor_revision': sha256(b''.join((Path(__file__).parent / name).read_bytes()
                    for name in ('general_pi_server.py', 'general_pi_executor.py', 'general_pi_storage.py', 'general_pi_relay.py', 'native_network_policy.py', 'bounded_http_loop.py', 'pi_delegation.py', 'business_context.py', 'request_intent.py', 'native_task_context.py', 'native_diagnosis.py',
                                 'native_resources.py', 'runtime_resources.py', 'resource_installation.py', 'general_pi_resource_seed.py', 'bounded_mcp.py', 'native_environment.py', 'data_gateway_mcp.py', 'data_gateway_relay.py', 'grid_source_topology.py', 'grid_electrical_view.py', 'resources/gateway-electrical-view-v1.schema.json', 'resources/general-data-gateway.mjs',
                                 'progress.py', 'stream_progress.py', 'resource_manifest.py', 'native_resource_staging.py',
                                 'native_research_bridge.py', 'native_graph_context.py', 'native_graph_events.py',
                                 'native_product_roles.py', 'continuation_resources.py', 'resources/general-research.mjs', 'resources/research-guidance.mjs',
                                 'application_capacity.py', 'resources/application-capacity.json', 'resources/runtime-limits.mjs',
                                 'resources/research-tools.mjs', 'resources/execution-guidance.mjs', 'resources/model-request-capture.mjs',
                                 'resources/general-context.mjs', 'resources/general-sdk.mjs', 'resources/systematic-diagnosis.mjs', 'resources/general-mcp.mjs', 'resources/task-record-tools.mjs',
                                 'resources/enterprise-research-runtime.mjs', 'resources/enterprise-cycle-contract.mjs',
                                 'resources/enterprise-cycle-state.mjs', 'resources/enterprise-graph-contract.mjs',
                                 'resources/enterprise-graph-state.mjs', 'resources/enterprise-graph-runtime.mjs', 'resources/task-goal-state.mjs', 'resources/task-node-return.mjs', 'resources/research-context-window.mjs',
                                 'resources/graph-context-client.mjs', 'resources/research-products.mjs', 'resources/delivery-review.mjs', 'resources/product-path-policy.json', 'resources/research-policy-catalog.json',
                                 'resources/managed-subagents.mjs', 'resources/delegation-tool.mjs', 'resources/delegation-scheduler.mjs'))
                    + b''.join(path.relative_to(Path(__file__).parent).as_posix().encode() + path.read_bytes()
                        for directory in ('research-runtime', 'subagents')
                        for path in sorted((Path(__file__).parent / 'resources' / directory).rglob('*.mjs')))).hexdigest()}
    runner = NativeTaskRunner(root=root, config_root=config,
        command=('node', '/opt/pi/packages/coding-agent/dist/cli.js'), model=identity['model'],
        relay_origin=f'http://127.0.0.1:{port}', network_policy=network_policy, gateway=gateway)
    runner.gateway_publication = gateway_publication
    host = GeneralPiHost(root=root, identity=identity, run_task=runner)
    host.record_network_policy('startup_default', network_policy.state())
    host.capability['native_tools'] = runner.verify_tools(identity)
    host.capability['native_builtin_tools'] = runner.builtin_tools
    host.capability['resource_profiles'] = runner.verify_resources(identity)
    server = make_server(host, control_token=os.environ['CAPSTONE_GENERAL_CONTROL_TOKEN'],
        address=('0.0.0.0', port), runner=runner, upstream=provider['base_url'], provider_key=key,
        network_policy=network_policy)
    server.serve_forever()


if __name__ == '__main__':
    main()
