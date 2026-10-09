"""Application-owned general tasks and ordered business goal execution."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from hashlib import sha256
import json
import time
from typing import Any, cast

from .harness import AdmittedAttemptAnswer, HarnessRuntime, terminal_payload_for_admission, HarnessRuntimeConfigurationError
from .pi_delegation import GeneralPiExecutor, PiTaskRequest, PiTaskResult
from .business_context import BusinessContext
from .request_intent import IntentDecision, IntentRequest, NodeControl
from .thread_service import AttemptClaim
from .turn_router import TurnPlan
from .business_goal_dependency import AdmittedBusinessGoalDependency, business_dependencies_for_claim
from .thread_network import normalize_thread_network_projection

BUSINESS_OPERATIONS = frozenset({'business_read', 'business_execute'})
PARENT_PAYLOAD_BUDGET = 64 * 1024 - 2048
SHORTENED_NOTICE = '\n\n[Reply shortened. Complete task results are retained in the saved records.]'


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

    def _emit(self, on_event, payload):
        try:
            on_event({'event_type': 'runtime_event', 'runtime_mode': self.runtime_mode,
                      'visibility': 'diagnostic', 'payload': payload})
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
            messages.append({'message_id': 'dep-' + sha256((parent + '\0' + dependency).encode()).hexdigest(),
                'role': 'assistant', 'content': text.encode()[:2048].decode('utf-8', errors='ignore'),
                'turn_id': self._claim.attempt.turn_id, 'attempt_id': parent,
                'model_context_id': '', 'status': 'completed'})
        while len(messages) > 32 or sum(len(item['content'].encode()) for item in messages) > 32768:
            messages.pop(0)
        context = None if context_document is None else BusinessContext.from_document(context_document)
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
            elif context.to_document()['selection']['state'] != 'none':
                raise HarnessRuntimeConfigurationError('general Pi task schema does not support required context')
        request = PiTaskRequest(task_id, parent, 'direct' if self._direct else 'delegated',
            instruction, tuple(messages), tuple(self._general_results[identity].to_document()
                for identity in dependencies if identity in self._general_results),
            frozen['identity'], frozen['timeout_seconds'], **task_fields)
        self._emit(on_event, {'task_id': task_id, 'goal_id': goal['goal_id'],
            'parent_attempt_id': parent, 'child_status': 'started',
            'executor_identity': frozen['identity'], 'entrypoint': request.entrypoint})

        def native(event):
            control.checkpoint()
            # General tools are host observations. They never become semantic
            # tool events and never contribute result/evidence references.
            kind = event.get('type', event.get('event', 'unknown'))
            self._emit(on_event, {'task_id': task_id, 'goal_id': goal['goal_id'],
                'native_type': kind if isinstance(kind, str) else 'unknown',
                **({'tool_name': event['toolName'][:256]} if isinstance(event.get('toolName'), str) else {})})
            if self._direct or (self._decision is not None and len(self._decision.to_document()['goals']) == 1):
                delta = event.get('text') if kind in {'text_delta', 'assistant_delta'} else None
                update = event.get('assistantMessageEvent')
                if isinstance(update, Mapping) and update.get('type') == 'text_delta':
                    delta = update.get('delta')
                if isinstance(delta, str):
                    on_event({'event_type': 'assistant_text_delta', 'runtime_mode': self.runtime_mode,
                              'visibility': 'public', 'payload': {'text': delta[:16384]}})
        self._active_task = task_id
        try:
            result = self._executor.execute(request, control, native)
            result = PiTaskResult.from_document(result.to_document(), request)
            control.checkpoint()
        except BaseException as error:
            cancelled = True
            try:
                self._executor.cancel(task_id)
            except Exception:
                cancelled = False
                error.add_note('Child cancellation was not confirmed; task state is unknown')
            self._emit(on_event, {'task_id': task_id, 'goal_id': goal['goal_id'],
                'parent_attempt_id': parent, 'child_status': 'cancelled' if isinstance(error, InterruptedError) else 'failed',
                'cancellation_confirmed': cancelled})
            raise
        finally:
            self._active_task = None
        self._general_results[goal['goal_id']] = result
        document = result.to_document()
        self._emit(on_event, {'task_id': task_id, 'goal_id': goal['goal_id'],
            'parent_attempt_id': parent, 'child_status': result.status,
            'executor_identity': document['executor_identity'], 'usage': bounded_metadata(document['usage'])})
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
                self._claim.attempt.attempt_id, goal['goal_id'], self._claim.model_context_id,
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
        timeout = 600 if general is None else general['timeout_seconds']
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
                except Exception:
                    control.checkpoint()  # Parent cancellation and deadline stay fatal.
                    status, answer = 'failed', 'A task failed. Its result is unavailable.'
            self._statuses[identity] = status
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
            return len(text) <= 64000 and len(json.dumps(payload, ensure_ascii=False,
                allow_nan=False, sort_keys=True).encode()) <= PARENT_PAYLOAD_BUDGET

        full = '\n\n'.join(answers)
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
