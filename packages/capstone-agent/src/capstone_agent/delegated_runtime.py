"""Application-owned general tasks and ordered business goal execution."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from hashlib import sha256
import json
import time
from typing import Any, cast
from .application_capacity import CapacityExceeded, limits, observe_capacity

from .harness import AdmittedAttemptAnswer, HarnessRuntime, terminal_payload_for_admission, HarnessRuntimeConfigurationError
from .pi_delegation import GeneralPiExecutor, PiTaskRequest, PiTaskResult, PiHTTPFailure, PiTransportTimeout
from .business_context import BusinessContext
from .request_intent import IntentDecision, IntentRequest, NodeControl
from .thread_service import AttemptClaim
from .turn_router import TurnPlan
from .business_goal_dependency import AdmittedBusinessGoalDependency, business_dependencies_for_claim
from .thread_network import normalize_thread_network_projection

BUSINESS_OPERATIONS = frozenset({'business_read', 'business_execute'})
SHORTENED_NOTICE = '\n\n[Reply shortened. Complete task results are retained in the saved records.]'


def child_failure_code(error: BaseException) -> str:
    """Keep diagnostic categories, never arbitrary exception text or credentials."""
    if isinstance(error, CapacityExceeded):
        return 'native_capacity_exceeded'
    if isinstance(error, PiHTTPFailure):
        return 'native_executor_http_rejected'
    known = {
        'Pi transport deadline expired; task state is unknown': 'native_transport_timeout',
        'Pi executor transport failed; task state may be unknown': 'native_transport_failed',
        'Pi task deadline expired': 'native_task_deadline',
        'Pi response exceeds byte bounds': 'native_response_too_large',
        'Pi event history exceeds bounds': 'native_event_history_limit',
        'Pi event identity changed': 'native_event_identity_changed',
        'research response is invalid': 'native_research_response_invalid',
        'research observation source is not task-bound': 'native_research_source_invalid',
    }
    if str(error) in known:
        return known[str(error)]
    if isinstance(error, InterruptedError):
        return 'native_parent_cancelled'
    if isinstance(error, TimeoutError):
        return 'native_deadline_exceeded'
    if isinstance(error, ValueError):
        return 'native_contract_rejected'
    if isinstance(error, GoalReceiptPersistenceError):
        return 'native_receipt_persistence_failed'
    return 'native_execution_error'


def json_document(value):
    """Copy the executor's immutable JSON containers into storage containers."""
    if isinstance(value, Mapping):
        return {key: json_document(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_document(item) for item in value]
    return value


class DelegatedRuntime:
    runtime_name = 'pi'

    def __init__(self, claim: AttemptClaim, executor: GeneralPiExecutor | None,
                 business_factory, *, direct: bool = False):
        self._claim, self._executor, self._business = claim, executor, business_factory
        if claim.turn_plan is None or not isinstance(claim.turn_plan.intent_resources, Mapping):
            raise ValueError('delegation requires a frozen Turn plan')
        if not direct and (claim.turn_plan.intent_request is None or claim.turn_plan.intent_decision is None):
            raise ValueError('delegation requires a validated intent decision')
        self._plan: TurnPlan = claim.turn_plan
        self._resources = cast(Mapping[str, Any], self._plan.intent_resources)
        self._request = self._plan.intent_request
        self._decision = self._plan.intent_decision
        self._direct = direct
        self.runtime_mode = 'pi_reference' if direct else 'capstone'
        self._active: HarnessRuntime | None = None
        self._active_task: str | None = None
        self._artifact_store = None
        self._general_results: dict[str, PiTaskResult] = {}
        self._business_admissions: list[AdmittedAttemptAnswer] = []
        self._business_answers: dict[str, str] = {}
        self._business_dependencies: dict[str, AdmittedBusinessGoalDependency] = {}
        self._network_projection_requested = False
        self._network_projection: dict | None = None
        self._network_projection_refs: tuple[str, ...] = ()
        self.network_projection_failure_code = 'projection_unavailable'
        self._business_started: set[str] = set()
        self._statuses: dict[str, str] = {}
        self._research_bridge = None

    def bind_research(self, bridge):
        if self._research_bridge is not None:
            raise ValueError('research controller is already bound')
        self._research_bridge = bridge

    def start(self):
        return None

    @property
    def network_projection_enabled(self) -> bool:
        return self._network_projection_requested

    def network_projection(self, claim, result_refs, evidence_refs, tool_events):
        del tool_events
        if (claim.model_context != self._claim.model_context or
            not set(self._network_projection_refs).issubset((*result_refs, *evidence_refs))):
            self.network_projection_failure_code = 'projection_invalid'
            return None
        return json_document(self._network_projection)

    def _capture_network_projection(self, runtime, scoped, admission, events):
        hook = getattr(runtime, 'network_projection', None)
        if not getattr(runtime, 'network_projection_enabled', False) or not callable(hook):
            return
        self._network_projection_requested = True
        self._network_projection_refs = (*admission.result_refs, *admission.evidence_refs)
        try:
            value = hook(scoped, admission.result_refs, admission.evidence_refs, tuple(events))
            self._network_projection = normalize_thread_network_projection(value, scoped,
                self._network_projection_refs) if value is not None else None
            self.network_projection_failure_code = ('projection_invalid' if value is not None
                else getattr(runtime, 'network_projection_failure_code', 'projection_unavailable'))
        except Exception:
            self._network_projection = None
            self.network_projection_failure_code = 'projection_source_unavailable'

    def stop(self):
        if self._active is not None:
            self._active.stop()
        if self._active_task is not None and self._executor is not None:
            self._executor.cancel(self._active_task)

    def _emit(self, on_event, payload, *, visibility='diagnostic'):
        try:
            on_event({'event_type': 'runtime_event', 'runtime_mode': self.runtime_mode,
                      'visibility': visibility, 'payload': payload})
        except Exception as error:
            raise GoalReceiptPersistenceError('goal receipt could not be saved') from error

    def _general_task(self, goal, dependencies, control, on_event):
        resources = self._resources
        if self._direct:
            frozen = resources['resources']['general_executor']
            instruction, messages = resources['instruction'], resources['messages']
            context_document = resources.get('business_context')
        else:
            frozen = resources['general_executor']
            assert self._request is not None
            document = self._request.to_document()
            instruction = goal.get('instruction_excerpt', document['instruction'])
            messages = [message for message in document['messages'] if message['message_id'] in goal['message_refs']]
            context_document = resources.get('business_contexts', {}).get(goal['goal_id'])
        if self._executor is None or frozen is None:
            raise HarnessRuntimeConfigurationError('general Pi executor is unavailable')
        parent = frozen['original_attempt_id']
        task_id = 'pi-' + sha256((parent + '\0' + goal['goal_id']).encode()).hexdigest()
        # Historical text stays historical. No Authority resources or internal
        # model projection cross the general execution contract.
        messages = [{**item, 'model_context_id': ''} for item in messages]
        for dependency in dependencies:
            if dependency not in self._business_answers:
                continue
            text = ('Current task dependency: application-admitted business answer text. '
                    'No Authority evidence is transferred.\n' + self._business_answers[dependency])
            observe_capacity('delegation_dependency_bytes', len(text.encode()), 'delegation_dependency')
            messages.append({'message_id': 'dep-' + sha256((parent + '\0' + dependency).encode()).hexdigest(),
                'role': 'assistant', 'content': text.encode()[:limits.delegation_dependency_bytes].decode('utf-8', errors='ignore'),
                'turn_id': self._claim.attempt.turn_id, 'attempt_id': parent,
                'model_context_id': '', 'status': 'completed'})
        observe_capacity('delegation_history_count', len(messages), 'delegation_history')
        observe_capacity('delegation_history_bytes', sum(len(item['content'].encode()) for item in messages), 'delegation_history')
        while len(messages) > limits.delegation_history_count or sum(len(item['content'].encode()) for item in messages) > limits.delegation_history_bytes:
            messages.pop(0)
        from .thread_products import render_product_context
        product_context = render_product_context((resources.get('submission') or {}).get('_product_context', []))
        if product_context:
            product_message = {'message_id': 'product-' + sha256((parent + '\0product-context').encode()).hexdigest(),
                'role': 'user', 'content': product_context, 'turn_id': self._claim.attempt.turn_id,
                'attempt_id': parent, 'model_context_id': '', 'status': 'completed'}
            observe_capacity('delegation_history_count', len(messages) + 1, 'delegation_products')
            observe_capacity('delegation_history_bytes', sum(len(item['content'].encode()) for item in messages) + len(product_context.encode()), 'delegation_products')
            while messages and (len(messages) >= limits.delegation_history_count or
                    sum(len(item['content'].encode()) for item in messages) + len(product_context.encode()) > limits.delegation_history_bytes):
                messages.pop(0)
            messages.append(product_message)
        context = None if context_document is None else BusinessContext.from_document(context_document)
        submission = resources.get('submission')
        selected_input = (submission if submission and submission['input']['kind'] == 'skill_invocation'
                          and (self._direct or goal.get('uses_selected_skill')) else None)
        task_fields = {}
        if context is not None:
            if 'capstone-pi-task/2' in frozen['capability'].get('task_schemas', ()):
                role = 'direct_pi' if self._direct else 'delegated_pi'
                accepted_profile = frozen['capability'].get('resource_profiles', {}).get(role)
                task_fields = {'business_context': context, 'resource_profile': {
                    'profile_id': role,
                    'revision': (accepted_profile['revision'] if accepted_profile is not None
                                 else frozen['identity']['config_revision'])},
                    'input': {'kind': 'text', 'text': instruction}}
                if selected_input is not None:
                    if selected_input['resource_profile']['profile_id'] != role:
                        raise HarnessRuntimeConfigurationError('selected skill execution role changed')
                    task_fields['resource_profile'] = selected_input['resource_profile']
                    task_fields['input'] = {**selected_input['input'], 'text': instruction}
            elif context.to_document()['selection']['state'] != 'none':
                raise HarnessRuntimeConfigurationError('general Pi task schema does not support required context')
        if selected_input is not None and 'input' not in task_fields:
            raise HarnessRuntimeConfigurationError('general Pi task schema does not support selected skill')
        request = PiTaskRequest(task_id, parent, 'direct' if self._direct else 'delegated',
            instruction, tuple(messages), tuple(self._general_results[identity].to_document()
                for identity in dependencies if identity in self._general_results),
            frozen['identity'], frozen['timeout_seconds'],
            native_context=resources.get('native_context'),
            research_binding=None if self._research_bridge is None else self._research_bridge.binding,
            **task_fields)
        self._emit(on_event, {'task_id': task_id, 'goal_id': goal['goal_id'],
            'parent_attempt_id': parent, 'child_status': 'started',
            'executor_identity': frozen['identity'], 'entrypoint': request.entrypoint})

        from .task_steps import NativeStepTracker
        from .native_research_bridge import CYCLE_CONTROL_TOOLS
        steps = NativeStepTracker(prefix=task_id, objective_steps=bool(set(CYCLE_CONTROL_TOOLS).intersection(
            resources.get('native_context', {}).get('policy', {}).get('allowed_tools', ()))))
        stream_text = self._direct or (self._decision is not None
            and len(self._decision.to_document()['goals']) == 1)
        transfers = self._incremental_artifact_transfers(on_event, control)

        def native(event):
            control.checkpoint()
            kind = event.get('type', event.get('event', 'unknown'))
            if kind == 'native_artifact_captured':
                self._publish_captured_artifact(event, request, transfers)
                return
            if kind == 'assistant_thinking_delta':
                if event.get('text') == '':
                    return
                from .harness import normalize_runtime_event
                thinking = normalize_runtime_event({'type': 'assistant_thinking_delta',
                    'text': event.get('text'), 'task_id': task_id}, runtime_mode=self.runtime_mode)
                try:
                    on_event(thinking)
                except Exception as error:
                    raise GoalReceiptPersistenceError('thinking event could not be saved') from error
                return
            delta = event.get('text') if kind in {'text_delta', 'assistant_delta'} else None
            update = event.get('assistantMessageEvent')
            if isinstance(update, Mapping) and update.get('type') == 'text_delta':
                delta = update.get('delta')
            if stream_text and isinstance(delta, str):
                # The text event is the replay record. A second metadata-only
                # event for the same chunk carries no additional observation.
                steps.annotate(event)
                on_event({'event_type': 'assistant_process_delta', 'runtime_mode': self.runtime_mode,
                    'visibility': 'diagnostic', 'payload': {'text': delta[:16384]}})
                return
            event = steps.annotate(event)
            if event.get('type') == 'runtime_action':
                from .harness import normalize_runtime_event
                on_event(normalize_runtime_event(event, runtime_mode=self.runtime_mode))
                return
            # General tools are host observations. They never become semantic
            # tool events and never contribute result/evidence references.
            kind = event.get('type', event.get('event', 'unknown'))
            tool_name = event.get('tool_name', event.get('toolName'))
            tool_call_id = event.get('tool_call_id', event.get('toolCallId'))
            public_tool = kind in {'tool_execution_start', 'tool_execution_end'} and (
                isinstance(tool_name, str) and bool(tool_name) and isinstance(tool_call_id, str) and bool(tool_call_id))
            research_branch = kind in {'delegation_child_started', 'delegation_child_tool', 'delegation_child_finished', 'delegation_child_response'}
            research_graph_event = kind in {'enterprise_graph_tool_binding', 'enterprise_graph_child_started',
                'enterprise_graph_child_tool', 'enterprise_graph_child_response_started', 'enterprise_graph_child_response', 'enterprise_graph_child_finished'}
            llm_pool_call = event.get('llm_pool_call')
            pool_progress = isinstance(llm_pool_call, Mapping)
            model_request_pool = event.get('model_request_pool')
            model_progress = isinstance(model_request_pool, Mapping)
            source_view = None
            if (kind == 'tool_execution_end' or kind == 'enterprise_graph_child_tool' and event.get('activity') == 'end'):
                if (tool_name in {'data_gateway_get_network_topology_view', 'data_gateway_open_network_model_view'} and isinstance(tool_call_id, str)
                        and tool_call_id and event.get('is_error') is not True
                        and event.get('task_id', task_id) == task_id
                        and event.get('attempt_id', parent) == parent):
                    from .grid_source_topology import checked_source_view_request, GridSourceError
                    try:
                        if tool_name == 'data_gateway_open_network_model_view':
                            from .grid_electrical_view import checked_electrical_descriptor
                            source_view = checked_electrical_descriptor(event.get('source_view'))
                        else:
                            source_view = checked_source_view_request(event.get('source_view'))
                    except (GridSourceError, ValueError):
                        pass  # Optional presentation metadata cannot block the task.
            self._emit(on_event, {'task_id': task_id, 'goal_id': goal['goal_id'],
                'native_type': 'model_request_pool' if model_progress else 'llm_pool_call' if pool_progress else kind if isinstance(kind, str) else 'unknown',
                **({'model_request_pool':dict(model_request_pool)} if model_progress else {}),
                **({'llm_pool_call':dict(llm_pool_call)} if pool_progress else {}),
                **({'transport': {key: value[:64] for key in ('operation', 'transport_phase')
                    if isinstance((value := event.get(key)), str)}} if kind in {'transport_interrupted', 'transport_restored'} else {}),
                **({'tool_name': tool_name[:256]} if isinstance(tool_name, str) else {}),
                **({'tool_call_id': tool_call_id[:256]} if isinstance(tool_call_id, str) else {}),
                **({'task_progress': event['task_progress']} if isinstance(event.get('task_progress'), Mapping) else {}),
                **({'source_view': source_view} if source_view is not None else {}),
                **({'research_cycle': {key: event[key] for key in
                    ('owner', 'attempt_id', 'action_id', 'checkpoint', 'progress') if key in event}}
                    if kind == 'enterprise_cycle_progress' else {}),
                **({'research_graph': {key: event[key] for key in
                    ('type', 'owner', 'attempt_id', 'task_id', 'action_id', 'checkpoint', 'graph', 'events', 'control')
                    if key in event}} if kind == 'enterprise_graph_progress' else {}),
                **({'research_graph_event': {key: event[key] for key in
                    ('type', 'owner', 'attempt_id', 'task_id', 'action_id', 'step_id', 'checkpoint',
                     'tool_call_id', 'tool_name', 'child_id', 'activity', 'tool_activity', 'is_error',
                     'execution_ms', 'response_number', 'response_ms', 'tool_call_ids', 'tool_requests', 'response_text', 'stop_reason', 'usage', 'status', 'result_summary', 'model_responses', 'turns')
                    if key in event}} if research_graph_event else {}),
                **({'research_branch': {key: event[key] for key in ('type', 'subordinate', 'owner', 'attempt_id',
                    'parent_action_id', 'parent_step_id', 'parent_tool_call_id', 'child_id', 'title', 'questions',
                    'expected_outputs', 'checkpoint', 'status', 'result_summary', 'error', 'response_number', 'response_ms',
                    'activity', 'tool_activity', 'tool_name', 'tool_call_id', 'is_error') if key in event}} if research_branch else {}),
                **{key: event[key] for key in ('task_step', 'task_steps', 'task_step_id', 'task_step_number',
                    'step_tool_number', 'task_step_error', 'runtime_step_tracking') if key in event},
                **({'activity': {key: value[:limit] for key, limit in
                    (('operation', 241), ('output_excerpt', 601), ('warning', 241))
                    if isinstance((value := cast(Mapping, event.get('activity')).get(key)), str)}}
                    if isinstance(event.get('activity'), Mapping) else {}),
                **({'is_error': event['is_error']} if type(event.get('is_error')) is bool else {})},
                visibility='public' if public_tool or research_branch or research_graph_event or pool_progress or model_progress or kind in {
                    'enterprise_cycle_progress', 'enterprise_graph_progress'} else 'diagnostic')
        self._active_task = task_id
        try:
            manifests = resources.get('native_context', {}).get('resource_manifests', ())
            if manifests:
                stage = getattr(self._executor, 'stage_resources', None)
                if not callable(stage) or self._claim.resource_reader is None:
                    raise HarnessRuntimeConfigurationError('resource acquisition transport is unavailable')
                stage_events = getattr(self._executor, 'stage_resources_with_events', None)
                if callable(stage_events):
                    stage_events(task_id, manifests, self._claim.resource_reader, control, native)
                else:
                    stage(task_id, manifests, self._claim.resource_reader, control)
            if self._research_bridge is None:
                result = self._executor.execute(request, control, native)
            else:
                execute = getattr(self._executor, 'execute_with_research', None)
                if not callable(execute):
                    raise HarnessRuntimeConfigurationError('research control transport is unavailable')
                result = cast(PiTaskResult, execute(request, control, native, self._research_bridge))
            result = PiTaskResult.from_document(result.to_document(), request)
            control.checkpoint()
        except BaseException as error:
            transfers.close()
            cancelled = True
            try:
                retained = self._executor.cancel(task_id)
                if retained is not None:
                    retained = PiTaskResult.from_document(retained.to_document(), request)
                    self._publish_artifacts(retained, request, on_event)
            except Exception:
                cancelled = False
                error.add_note('Child cancellation was not confirmed; task state is unknown')
            self._emit(on_event, {'task_id': task_id, 'goal_id': goal['goal_id'],
                'parent_attempt_id': parent, 'child_status': 'cancelled' if isinstance(error, InterruptedError) else 'failed',
                'cancellation_confirmed': cancelled, 'failure_code': child_failure_code(error),
                **({'transport_failure': dict(error.diagnostic)}
                   if isinstance(error, (PiHTTPFailure, PiTransportTimeout)) else {}),
                **({'failure': {'code':'native_capacity_exceeded','phase':error.phase or 'execution',
                    'capacity':error.to_document()}} if isinstance(error, CapacityExceeded) else {}),
                'timeout_seconds': request.timeout_seconds})
            raise
        finally:
            transfers.close()
            self._active_task = None
            if steps.tracker.active is not None:
                from .harness import normalize_runtime_event
                on_event(normalize_runtime_event(steps.annotate(
                    {'type': 'runtime_action', 'phase': 'interrupted'}), runtime_mode=self.runtime_mode))
        self._general_results[goal['goal_id']] = result
        document = result.to_document()
        try:
            self._publish_artifacts(result, request, on_event, control)
        except Exception:
            self._emit(on_event, {'task_id': task_id, 'goal_id': goal['goal_id'],
                'parent_attempt_id': parent, 'child_status': 'failed',
                'failure_code': 'native_artifact_persistence_failed',
                'executor_status': result.status})
            raise
        self._emit(on_event, {'task_id': task_id, 'goal_id': goal['goal_id'],
            'parent_attempt_id': parent, 'child_status': result.status,
            **({'failure_code': result.failure['code'], 'failure_phase': result.failure['phase'],
                'failure': dict(result.to_document()['failure']),
                'timeout_seconds': request.timeout_seconds} if result.failure is not None else {}),
            'executor_identity': document['executor_identity'], 'usage': bounded_metadata(document['usage'])})
        if result.failure is not None:
            capacity=result.to_document()['failure'].get('capacity')
            if isinstance(capacity,dict) and capacity.get('mode')=='debug':
                raise CapacityExceeded(capacity['dimension'],capacity['actual'],capacity['limit'],
                                       capacity['phase'],mode='debug')
        # Separate receipts stay below the Thread event bound even when a
        # result has many sources. These are external identities, not evidence.
        for kind in ('sources', 'artifacts'):
            for reference in document[kind]:
                metadata = reference['metadata']
                reference = {**reference, 'metadata': bounded_metadata(metadata),
                    'metadata_sha256': sha256(json.dumps(metadata, ensure_ascii=False,
                        sort_keys=True, separators=(',', ':')).encode()).hexdigest()}
                self._emit(on_event, {'goal_id': goal['goal_id'], 'external_reference_kind': kind,
                                      'reference': reference})
        return result.status, result.answer

    def bind_artifact_store(self, objects):
        self._artifact_store = objects

    def _publish_artifacts(self, result, request, on_event, control=None):
        from .native_artifact_projection import project_native_artifacts
        if control is not None:
            # Model execution has returned. Persist its files under a separate
            # bounded transfer window; keep the same cancellation/lease callback.
            # Reuse the configured task timeout, without renewing model execution.
            control = NodeControl(control.check, time.monotonic() + request.timeout_seconds)
        artifacts = project_native_artifacts(self._claim, result, expected_parent_attempt_id=request.parent_attempt_id)
        self._publish_artifact_descriptors(artifacts, result.task_id, on_event, control)

    def _incremental_artifact_transfers(self, on_event, control):
        from .incremental_artifact_transfers import IncrementalArtifactTransfers
        from .native_artifact_projection import retain_native_artifact
        def transfer(artifact, check):
            def guard():
                check()
                control.checkpoint()
            guard()
            if self._artifact_store is not None:
                retain_native_artifact(self._artifact_store, self._executor, artifact, check=guard)
            guard()
            on_event({'event_type':'native_artifact_published', 'runtime_mode':self.runtime_mode,
                'visibility':'public', 'payload':{'artifact':artifact}})
        return IncrementalArtifactTransfers(transfer, maximum=limits.artifact_count)

    def _publish_captured_artifact(self, event, request, transfers):
        from .native_artifact_projection import project_native_artifact_capture
        artifacts = project_native_artifact_capture(self._claim, request, event)
        for artifact in artifacts:
            transfers.submit(artifact)

    def _publish_artifact_descriptors(self, artifacts, task_id, on_event, control=None):
        from .native_artifact_projection import retain_native_artifact
        from .pi_delegation import PiArtifactTransportUnavailable
        for artifact in artifacts:
            if self._artifact_store is not None:
                interrupted, delay = False, 0.1
                while True:
                    if control is not None:
                        control.checkpoint()
                    try:
                        retain_native_artifact(self._artifact_store, self._executor, artifact)
                        break
                    except PiArtifactTransportUnavailable:
                        # Cancellation cleanup preserves available process files,
                        # but must not enter a new task-lifetime retry loop.
                        if control is None:
                            raise
                        if not interrupted:
                            self._emit(on_event, {'task_id': task_id,
                                'transport': {'operation': 'artifact_transfer'},
                                'child_status': 'transport_interrupted'})
                        interrupted = True
                        until = time.monotonic() + delay
                        while time.monotonic() < until:
                            control.checkpoint()
                            time.sleep(min(0.025, max(0, until - time.monotonic())))
                        delay = min(2, delay * 2)
                if interrupted:
                    self._emit(on_event, {'task_id': task_id,
                        'transport': {'operation': 'artifact_transfer'},
                        'child_status': 'transport_restored'})
            on_event({'event_type': 'native_artifact_published', 'runtime_mode': self.runtime_mode,
                      'visibility': 'public', 'payload': {'artifact': artifact}})

    def _business_goal(self, goal, dependencies, control, on_event, heartbeat):
        plan = self._plan
        assert self._request is not None and self._decision is not None
        source = self._request.to_document()
        refs = set(goal['message_refs'])
        source['messages'] = [message for message in source['messages'] if message['message_id'] in refs]
        source['objects'] = [item for item in source['objects'] if item['object_id'] in goal['object_refs']
                             or item['object_id'] == self._claim.model_context_id]
        source['capabilities'] = [item for item in source['capabilities']
                                  if item['capability_id'] in goal['capability_refs']]
        source['instruction'] = goal.get('instruction_excerpt', source['instruction'])
        if 'context_selection' in source:
            available_objects = {item['object_id'] for item in source['objects']}
            source['context_selection'] = {key: [ref for ref in refs if ref in available_objects and
                (key == 'exclude_refs' or ref in goal['object_refs'])] for key, refs in source['context_selection'].items()}
        if not goal.get('uses_selected_skill'):
            source.pop('selected_skill', None)
        request = IntentRequest.from_document(source)
        decision = self._decision.to_document()
        decision['goals'] = [{**goal, 'depends_on': []}]
        checked = IntentDecision.from_document(decision, request)
        resources = dict(self._resources)
        observations = tuple(self._general_results[identity] for identity in dependencies
                             if identity in self._general_results)
        resources['external_observations'] = observations
        resources['resolved_goal_dependencies'] = tuple(dependencies)
        resources['business_goal_dependencies'] = tuple(self._business_dependencies[identity]
            for identity in dependencies if identity in self._business_dependencies)
        executor = self._resources.get('general_executor')
        resources['delegation_parent_attempt_id'] = (executor['original_attempt_id']
            if executor else self._claim.attempt.attempt_id)
        resources.pop('general_executor', None)
        # Only historical resources named by this business goal are prepared.
        visible = {message['attempt_id'] for message in source['messages']}
        resources['prior_results'] = [item for item in resources.get('prior_results', ())
                                      if item['attempt_id'] in visible]
        scoped = replace(self._claim, instruction=source['instruction'],
            prior_results=tuple(ref for ref in self._claim.prior_results if ref.attempt_id in visible),
            turn_plan=replace(plan, intent_request=request, intent_decision=checked,
                              intent_resources=resources))
        admitted_dependencies = business_dependencies_for_claim(scoped)
        events = [event for item in admitted_dependencies for event in item['tool_receipts']]
        result_refs = [ref for item in admitted_dependencies for ref in item['admission']['result_refs']]
        evidence_refs = [ref for item in admitted_dependencies for ref in item['admission']['evidence_refs']]

        def emit(event):
            control.checkpoint()
            payload = event.get('payload', {})
            if event.get('event_type') == 'tool_completed':
                events.append(payload)
            for key, collection in (('result_refs', result_refs), ('evidence_refs', evidence_refs)):
                collection.extend(ref for ref in payload.get(key, ()) if isinstance(ref, str))
            try:
                on_event(event)
            except Exception as error:
                raise GoalReceiptPersistenceError('business event could not be saved') from error
        control.checkpoint()
        runtime = self._business(scoped)
        self._active = runtime
        self._business_started.add(goal['goal_id'])
        try:
            runtime.start()
            answer = runtime.prompt(scoped.instruction, on_event=emit,
                correlation_id=self._claim.attempt.attempt_id, on_heartbeat=heartbeat)
            control.checkpoint()
            admit = getattr(runtime, 'admit_attempt', None)
            try:
                admitted = None if not callable(admit) else admit(scoped, answer,
                    tuple(dict.fromkeys(result_refs)), tuple(dict.fromkeys(evidence_refs)), tuple(events))
            except Exception as error:
                raise BusinessAdmissionError('business answer admission failed') from error
            if (not isinstance(admitted, AdmittedAttemptAnswer) or
                not set(admitted.result_refs).issubset(result_refs) or
                not set(admitted.evidence_refs).issubset(evidence_refs) or
                not (admitted.mode == 'authority_backed' or
                     (admitted.mode == 'offline_information' and admitted.assurance == 'deterministic_information'
                      and 'current_model_observation_verified' in admitted.diagnostic_codes))):
                raise BusinessAdmissionError('business answer admission failed')
            self._business_admissions.append(admitted)
            self._business_answers[goal['goal_id']] = admitted.answer
            self._business_dependencies[goal['goal_id']] = AdmittedBusinessGoalDependency(
                self._claim.attempt.attempt_id, goal['goal_id'], self._claim.professional_context.id,
                tuple(goal['capability_refs']), admitted, tuple(events))
            self._capture_network_projection(runtime, scoped, admitted, events)
            return 'completed', admitted.answer
        finally:
            runtime.stop()
            self._active = None

    def prompt(self, question, *, on_event, correlation_id=None, on_heartbeat=None):
        del question, correlation_id
        heartbeat = on_heartbeat or (lambda: None)
        frozen = self._resources
        general = frozen['resources']['general_executor'] if self._direct else frozen.get('general_executor')
        timeout = limits.delegation_task_seconds if general is None else general['timeout_seconds']
        control = NodeControl(heartbeat, time.monotonic() + timeout)
        goals: list[dict] = ([dict(goal_id='direct', operation='answer', depends_on=[], missing_requirements=[])]
            if self._direct else cast(IntentDecision, self._decision).to_document()['goals'])
        if self._direct and frozen.get('decision', {}).get('clarification_required') is True:
            self._statuses['direct'] = 'blocked'
            return self._bounded_reply([frozen['decision']['clarification']], {0}, on_event)
        answers, prior = [], []
        protected: set[int] = set()
        for goal in goals:
            control.checkpoint()
            identity = goal['goal_id']
            dependencies = goal.get('depends_on', list(prior))
            prior.append(identity)
            if (self._decision is not None and self._decision.needs_clarification) or goal['missing_requirements'] or any(
                self._statuses.get(ref) != 'completed' for ref in dependencies
            ):
                label = 'Business task' if goal['operation'] in BUSINESS_OPERATIONS else 'General task'
                status, answer = 'blocked', f"{label} was not executed: prerequisites are not complete."
            else:
                try:
                    if goal['operation'] in BUSINESS_OPERATIONS:
                        status, answer = self._business_goal(goal, dependencies, control, on_event, heartbeat)
                    elif goal['operation'] == 'catalog_lookup':
                        from .catalog_answer import complete_catalog_answer
                        answer = complete_catalog_answer('', '', self._claim.application_catalog,
                                                         full_catalog_requested=True)
                        status = 'completed' if answer is not None else 'capability_unavailable'
                        answer = answer or 'The application catalog is unavailable.'
                    else:
                        status, answer = self._general_task(goal, dependencies, control, on_event)
                except (BusinessAdmissionError, GoalReceiptPersistenceError, HarnessRuntimeConfigurationError):
                    raise
                except Exception as error:
                    if isinstance(error,CapacityExceeded) and error.mode=='debug':
                        raise
                    control.checkpoint()  # Parent cancellation and deadline stay fatal.
                    status, answer = 'failed', 'A task failed. Its result is unavailable.'
            self._statuses[identity] = status
            if self._plan.source == 'native_conversation' and status != 'completed':
                raise RuntimeError('native conversation did not complete')
            self._emit(on_event, {'goal_id': identity, 'goal_status': status,
                                  'operation': goal['operation']})
            if status == 'failed':
                answer = 'A task failed. Its result is unavailable.'
            if len(goals) > 1 and status == 'completed':
                label = 'Business result' if goal['operation'] in BUSINESS_OPERATIONS else 'General result (external observation)'
                answer = f'{label}:\n{answer}'
            if goal['operation'] in BUSINESS_OPERATIONS or status != 'completed':
                protected.add(len(answers))
            answers.append(answer or 'A task requires clarification.')
        if not any(status == 'completed' for status in self._statuses.values()):
            clarification = None if self._decision is None else self._decision.to_document()['clarification']
            if clarification:
                return self._bounded_reply([clarification], {0}, on_event)
        return self._bounded_reply(answers, protected, on_event)

    def _bounded_reply(self, answers: list[str], protected: set[int], on_event) -> str:
        admission = self.admit_attempt(self._claim, 'Pending response.', (), (), ())

        def fits(text):
            payload = terminal_payload_for_admission(admission, answer=text)
            return len(text) <= limits.delegation_answer_chars and len(json.dumps(payload, ensure_ascii=False,
                allow_nan=False, sort_keys=True).encode()) <= limits.delegation_reply_bytes

        full = '\n\n'.join(answers)
        observe_capacity('delegation_answer_chars', len(full), 'delegation_reply')
        observe_capacity('delegation_reply_bytes', len(json.dumps(
            terminal_payload_for_admission(admission, answer=full), ensure_ascii=False,
            allow_nan=False, sort_keys=True).encode()), 'delegation_reply')
        if fits(full):
            return full
        pieces = [answer if ordinal in protected else '' for ordinal, answer in enumerate(answers)]

        def render():
            return '\n\n'.join(piece for piece in pieces if piece) + SHORTENED_NOTICE

        if not fits(render()):
            # If professional text itself exceeds the public payload budget,
            # retain its full admitted receipt before making a visible excerpt.
            for dependency in self._business_dependencies.values():
                document = dependency.to_document()
                serialized = json.dumps(document, ensure_ascii=False, allow_nan=False, sort_keys=True)
                digest = sha256(serialized.encode()).hexdigest()
                chunks = [serialized[index:index + 4096] for index in range(0, len(serialized), 4096)]
                for ordinal, chunk in enumerate(chunks):
                    self._emit(on_event, {'business_answer_receipt': digest,
                        'goal_id': document['goal_id'], 'chunk_index': ordinal,
                        'chunk_count': len(chunks), 'content': chunk})
            pieces = [''] * len(answers)
        if not fits(render()):
            # Never discard admitted references or result projections to make
            # room. An impossible metadata envelope is an admission failure.
            raise BusinessAdmissionError('admitted metadata exceeds the parent payload budget')
        for ordinal in [*sorted(protected), *(index for index in range(len(answers)) if index not in protected)]:
            if pieces[ordinal]:
                continue
            low, high = 0, len(answers[ordinal])
            while low < high:
                middle = (low + high + 1) // 2
                pieces[ordinal] = answers[ordinal][:middle]
                if fits(render()):
                    low = middle
                else:
                    high = middle - 1
            pieces[ordinal] = answers[ordinal][:low]
        return render()

    def admit_attempt(self, claim, answer, result_refs, evidence_refs, tool_events):
        del claim, tool_events
        if self._business_admissions:
            refs = tuple(dict.fromkeys(ref for item in self._business_admissions for ref in item.result_refs))
            evidence = tuple(dict.fromkeys(ref for item in self._business_admissions for ref in item.evidence_refs))
            mode, assurance = ('authority_backed', 'lineage_verified') if evidence else ('offline_information', 'deterministic_information')
            codes = tuple(dict.fromkeys(code for item in self._business_admissions for code in item.diagnostic_codes))
            projections: dict[str, Mapping[str, object]] = {}
            for admitted in self._business_admissions:
                for item in admitted.result_projections:
                    identity = item.get('result_id')
                    if not isinstance(identity, str) or not identity:
                        raise BusinessAdmissionError('admitted result projection identity is invalid')
                    if identity in projections and projections[identity] != item:
                        raise BusinessAdmissionError('admitted result projections conflict')
                    projections[identity] = item
            return AdmittedAttemptAnswer(answer, mode, assurance, refs, evidence, codes, tuple(projections.values()))
        if self._business_started or result_refs or evidence_refs:
            raise BusinessAdmissionError('professional execution has no admitted result')
        from .harness import AdmittedPartialGoalAnswer
        business = [] if self._decision is None else [goal['goal_id'] for goal in self._decision.to_document()['goals']
                                           if goal['operation'] in BUSINESS_OPERATIONS]
        if business:
            completed = tuple(identity for identity, result in self._general_results.items() if result.status == 'completed')
            if not completed and self._plan.route == 'ordinary':
                return AdmittedAttemptAnswer(answer, 'limited', 'limited',
                    diagnostic_codes=('business_goals_not_executed',))
            return AdmittedPartialGoalAnswer(answer, 'limited', 'limited',
                diagnostic_codes=('business_goals_not_executed',),
                completed_general_goal_ids=completed, unexecuted_business_goal_ids=tuple(business))
        if any(status != 'completed' for status in self._statuses.values()):
            return AdmittedAttemptAnswer(answer, 'limited', 'limited')
        return AdmittedAttemptAnswer(answer, 'offline_information', 'general_knowledge')


class BusinessAdmissionError(ValueError):
    """Professional admission failure must never become general output."""


class GoalReceiptPersistenceError(RuntimeError):
    """Required receipt persistence failure remains fatal for the Attempt."""


def bounded_metadata(metadata: Mapping) -> dict:
    """Keep receipt projections small; the executor retains the full result."""
    result = {}
    for key, value in list(metadata.items())[:32]:
        if isinstance(value, str):
            result[key] = value[:256]
        elif value is None or type(value) in {bool, int, float}:
            result[key] = value
    return result
