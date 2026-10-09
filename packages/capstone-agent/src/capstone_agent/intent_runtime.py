"""Application intent node followed by bounded runtime resource selection."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from hashlib import sha256
import json
from typing import TYPE_CHECKING
from typing import cast

from .harness import HarnessPiClient, HarnessRuntime, PiPromptSession, HarnessRuntimeConfigurationError
from .request_intent import IntentDecision, IntentRecognizer, IntentRequest, NodeControl
from .thread_service import AttemptClaim, PriorResultReference
from .turn_router import RouterConfig, TurnPlan, routing_input_for_claim
from .pi_delegation import GeneralPiExecutor
from .business_context import BusinessContext, business_context_for
from .context_selection import (ContextSelectionRequest, ContextSelectionDecision,
                                ContextSelector, selected_business_context)

_LEGACY = object()

if TYPE_CHECKING:
    from .pi_intent import NativeConversationPiSessionBuilder
    from .thread_application import ThreadApplicationAssembly


def intent_request_for_claim(claim: AttemptClaim, general_capability: Mapping | None = None) -> IntentRequest:
    history = claim.conversation_context.to_document()
    messages, history_objects = history['messages'], history.get('objects', [])
    if not isinstance(messages, list) or not isinstance(history_objects, list):
        raise ValueError('conversation projection is invalid')
    context = claim.model_context
    enabled = {f"{pid}@{version}" for pid, version in context.enabled_profiles}
    catalog = claim.application_catalog or {}
    capabilities: list[dict] = []
    profiles = catalog.get('profiles', [])
    for profile in profiles if isinstance(profiles, list) else []:
        if not isinstance(profile, Mapping):
            continue
        pid, version = profile.get('profile_id'), profile.get('profile_version')
        if not isinstance(pid, str) or not isinstance(version, str):
            continue
        identity = f'{pid}@{version}'
        families = profile.get('implementation_families', [])
        capabilities.append({'capability_id': identity,
            'display_name': profile.get('display_name', pid),
            'enabled': identity in enabled,
            'available': context.implementation_family in families,
            'implementation_families': families})
    known = {item['capability_id'] for item in capabilities}
    for identity in sorted(enabled - known):
        capabilities.append({'capability_id': identity, 'enabled': True,
                             'available': True})
    if general_capability is not None:
        general_entry = {key: general_capability[key] for key in
            ('capability_id', 'display_name', 'description', 'enabled', 'available')
            if key in general_capability}
        general_entry['description'] = (
            str(general_entry.get('description', 'Isolated general Pi executor.')) +
            ' Operations: ' + ', '.join(general_capability.get('operations', ())) +
            '. Native tools: ' + ', '.join(general_capability.get('native_tools', ())) +
            '. Exact retrieval sources are discovered by the child agent. '
            'Business model reads and calculations require Domain Pack capabilities.')[:8192]
        capabilities.append(general_entry)
    objects = [{'object_id': context.id, 'model_id': context.model_id,
                'model_revision': context.model_revision,
                'implementation_family': context.implementation_family}]
    objects.extend(item for item in history_objects if item['object_id'] != context.id)
    known_objects = {item['object_id'] for item in objects}
    for identity in dict.fromkeys(message['model_context_id'] for message in messages):
        if identity and identity not in known_objects:
            objects.append({'object_id': identity})
            known_objects.add(identity)
    return IntentRequest.from_document({
        'schema': 'capstone-intent-request/1', 'thread_id': claim.thread_id,
        'turn_id': claim.attempt.turn_id, 'attempt_id': claim.attempt.attempt_id,
        'instruction_message_id': claim.attempt.attempt_id + ':user',
        'instruction': claim.instruction, 'history_cutoff': history['history_cutoff'],
        'history_truncated': history['truncated'],
        'messages': messages,
        'objects': objects,
        'capabilities': capabilities,
        'mode_hint': {'send_ordinary': 'ordinary', 'send_professional': 'professional'}.get(claim.kind),
    })


def context_selection_request_for_claim(claim: AttemptClaim) -> ContextSelectionRequest:
    """Project public identities and history; no Domain Pack catalog leaves the host."""
    source = intent_request_for_claim(claim).to_document()
    objects = []
    for item in source['objects']:
        revision = item.get('model_revision')
        version = None if revision is None else 'sha256:' + sha256(json.dumps({
            'workspace_id': source['thread_id'], 'object_id': item['object_id'], 'revision': revision},
            sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
        objects.append({'object_id': item['object_id'],
            'display_name': item.get('display_name', item.get('model_id', item['object_id'])),
            'kind': 'model', 'version': version,
            'relation': 'current' if item['object_id'] == claim.model_context.id else 'historical',
            'source': {'kind': 'workspace', 'workspace_id': source['thread_id'],
                'message_refs': [message['message_id'] for message in source['messages']
                    if message['model_context_id'] == item['object_id']]}})
    return ContextSelectionRequest.from_document({'schema': 'capstone-context-selection-request/1',
        'workspace_id': source['thread_id'], 'current_object_id': claim.model_context.id,
        **{key: source[key] for key in ('turn_id', 'attempt_id', 'instruction_message_id',
            'instruction', 'history_cutoff', 'history_truncated', 'messages')}, 'objects': objects})


class IntentRuntimeFactory:
    """Keep recognition interchangeable while enforcing application permissions."""

    supports_frozen_intent_decision = True

    def __init__(self, business_factory: Callable[[AttemptClaim], HarnessRuntime],
                 recognizer_factory: Callable[[], IntentRecognizer],
                 ordinary_session_factory: Callable[[AttemptClaim, IntentDecision], PiPromptSession],
                 *, general_executor: GeneralPiExecutor | None | object = _LEGACY,
                 general_timeout_seconds: float = 600,
                 context_selector_factory: Callable[[], ContextSelector] | None = None):
        self._business = business_factory
        self._recognizer = recognizer_factory
        self._ordinary = ordinary_session_factory
        self._general = general_executor
        self._context_selector = context_selector_factory
        if not 1 <= general_timeout_seconds <= 3600:
            raise ValueError('general task timeout is invalid')
        self._general_timeout = general_timeout_seconds

    def _general_resources(self, claim: AttemptClaim) -> dict | None:
        if self._general is _LEGACY or self._general is None:
            return None
        executor = cast(GeneralPiExecutor, self._general)
        # Export fresh JSON; private origins and control tokens are not resources.
        from .delegated_runtime import json_document
        return {'identity': json_document(executor.identity),
                'capability': json_document(executor.capability),
                'original_attempt_id': claim.attempt.attempt_id,
                'timeout_seconds': self._general_timeout}

    @property
    def rollback_selection_on_failure(self) -> bool:
        return bool(getattr(self._business, 'rollback_selection_on_failure', False))

    def plan_intent(self, claim: AttemptClaim, control: NodeControl,
                    freeze: Callable[[AttemptClaim, dict], dict], *,
                    freeze_decision: Callable[[AttemptClaim, dict | None], dict | None] | None = None) -> TurnPlan:
        control.checkpoint()
        general = self._general_resources(claim)
        if claim.attempt.runtime_mode == 'pi_reference':
            if (general is None or general['capability'].get('enabled') is not True
                or general['capability'].get('available') is not True):
                raise HarnessRuntimeConfigurationError('general Pi executor is unavailable')
            return self._plan_direct(claim, control, freeze, freeze_decision, general)
        recognizer = self._recognizer()
        identity = recognizer.identity.to_document()
        request_document = intent_request_for_claim(claim, None if general is None else general['capability']).to_document()
        visible_attempts = {message['attempt_id'] for message in request_document['messages']
                            if message['status'] == 'completed'}
        resources = {'application_catalog': claim.application_catalog,
                     'current_object_id': claim.model_context.id,
                     'prior_results': [{'result_ref': ref.result_ref, 'evidence_refs': list(ref.evidence_refs),
                                        'capability_id': ref.capability_id, 'attempt_id': ref.attempt_id}
                                       for ref in claim.prior_results if ref.attempt_id in visible_attempts]}
        resources['general_executor'] = general
        frozen = freeze(claim, {'request': request_document,
                               'engine_identity': identity, 'resources': resources})
        if frozen['engine_identity'] != identity:
            raise HarnessRuntimeConfigurationError('intent configuration changed since original Attempt')
        self._check_general_configuration(general, frozen['resources'])
        request_doc = dict(frozen['request'])
        request_doc['attempt_id'] = claim.attempt.attempt_id
        if 'instruction_message_id' in request_doc:
            request_doc['instruction_message_id'] = claim.attempt.attempt_id + ':user'
        request = IntentRequest.from_document(request_doc)
        saved = None if freeze_decision is None else freeze_decision(claim, None)
        if saved is None:
            decision = recognizer.recognize(request, control)
        else:
            decision = IntentDecision.from_document(_rebind_decision(saved, claim.attempt.attempt_id), request)
        # A pluggable engine cannot bypass request binding or grant permission.
        decision = IntentDecision.from_document(decision.to_document(), request)
        control.checkpoint()
        document = decision.to_document()
        capabilities = {entry['capability_id']: entry for entry in request_doc['capabilities']}
        executable = decision.execution_goals
        executable_ids = {goal['goal_id'] for goal in executable}
        for goal in document['goals']:
            if (self._general is not _LEGACY and len(document['goals']) > 1
                and 'instruction_excerpt' not in goal):
                raise ValueError('mixed goal requires a source excerpt')
            if goal['goal_id'] not in executable_ids:
                continue
            for ref in goal['capability_refs']:
                entry = capabilities[ref]
                if goal['operation'] in {'business_read', 'business_execute', 'external_lookup'} and (
                    entry.get('enabled') is not True or entry.get('available') is not True
                ):
                    if general is not None and ref == general['capability']['capability_id']:
                        raise HarnessRuntimeConfigurationError('general Pi executor is unavailable')
                    raise ValueError('intent requested a disabled or unavailable capability')
            if goal['operation'] in {'business_read', 'business_execute'} and not goal['capability_refs']:
                raise ValueError('business intent has no authorized capability')
            general_id = None if general is None else general['capability']['capability_id']
            if goal['operation'] in {'business_read', 'business_execute'} and general_id in goal['capability_refs']:
                raise ValueError('business execution requires a domain capability')
            if goal['operation'] == 'external_lookup' and general is None:
                raise HarnessRuntimeConfigurationError('general Pi executor is unavailable')
            if goal['operation'] not in {'business_read', 'business_execute', 'catalog_lookup'} and self._general is not _LEGACY:
                if general is None or general['capability'].get('enabled') is not True or general['capability'].get('available') is not True:
                    raise HarnessRuntimeConfigurationError('general Pi executor is unavailable')
                if goal['operation'] not in general['capability'].get('operations', ()):
                    raise HarnessRuntimeConfigurationError('general Pi operation is unavailable')
                if any(ref != general_id for ref in goal['capability_refs']):
                    raise ValueError('general execution cannot use domain capabilities')
            if goal['operation'] in {'business_read', 'business_execute'} and any(
                ref != claim.model_context.id for ref in goal['object_refs']
            ):
                raise ValueError('business execution requires the active model context')
        if freeze_decision is not None:
            stored = freeze_decision(claim, document)
            if stored is None:
                raise ValueError('accepted intent decision was not saved')
            decision = IntentDecision.from_document(_rebind_decision(stored, claim.attempt.attempt_id), request)
        # Project from the original accepted identities. Retry message rebinding
        # must not alter the task snapshot or its public content identity.
        original = IntentRequest.from_document(frozen['request'])
        original_decision = IntentDecision.from_document(
            _rebind_decision(decision.to_document(), frozen['request']['attempt_id']), original)
        execution_resources = dict(frozen['resources'])
        if self._general is not _LEGACY:
            # Blocked goals retain unresolved references in the accepted decision.
            # Only ready goals need a version-bound context for child execution.
            execution_resources['business_contexts'] = {goal['goal_id']: business_context_for(
                original, original_decision, goal_id=goal['goal_id'],
                current_object_id=execution_resources.get('current_object_id', original.to_document()['objects'][0]['object_id'])
            ).to_document() for goal in original_decision.execution_goals
                if goal['operation'] not in {'business_read', 'business_execute', 'catalog_lookup'}}
        return TurnPlan(
            turn_id=claim.attempt.turn_id, attempt_id=claim.attempt.attempt_id,
            route='professional' if any(goal['operation'] in {'business_read', 'business_execute'}
                                        for goal in executable) else 'ordinary',
            source=recognizer.identity.engine, plan_revision='turn-intent-v1',
            capability_hint=None, context_snapshot=routing_input_for_claim(claim).context_snapshot,
            router_config=RouterConfig(mode='semantic', model=recognizer.identity.model,
                                       schema='capstone-intent-decision/1'),
            intent_decision=decision, intent_engine=identity, intent_request=request,
            intent_resources=execution_resources,
        )

    def _plan_direct(self, claim, control, freeze, freeze_decision, general):
        if self._context_selector is None:
            raise HarnessRuntimeConfigurationError('direct Pi context selector is unavailable')
        selector = self._context_selector()
        identity = selector.identity.to_document()
        frozen = freeze(claim, {'entrypoint': 'direct',
            'request': context_selection_request_for_claim(claim).to_document(),
            'engine_identity': identity, 'resources': {'general_executor': general}})
        self._check_general_configuration(general, frozen['resources'])
        # Existing accepted /1 direct tasks can still recover their exact inputs.
        if 'request' not in frozen:
            return TurnPlan(claim.attempt.turn_id, claim.attempt.attempt_id,
                'ordinary', 'direct_pi', 'turn-direct-pi-v1', None, {}, intent_resources=frozen)
        if frozen['engine_identity'] != identity:
            raise HarnessRuntimeConfigurationError('context selection configuration changed since original Attempt')
        request = ContextSelectionRequest.from_document(frozen['request'])
        accepted = None if freeze_decision is None else freeze_decision(claim, None)
        if accepted is None:
            decision = ContextSelectionDecision.from_document(selector.select(request, control).to_document(), request)
            context = selected_business_context(request, decision)
            accepted = {'decision': decision.to_document(), 'business_context': context.to_document()}
            control.checkpoint()
            if freeze_decision is not None:
                accepted = freeze_decision(claim, accepted)
                if accepted is None:
                    raise ValueError('accepted context selection was not saved')
        if set(accepted) != {'decision', 'business_context'}:
            raise ValueError('frozen context selection fields are invalid')
        decision = ContextSelectionDecision.from_document(accepted['decision'], request)
        context = BusinessContext.from_document(accepted['business_context'])
        if context != selected_business_context(request, decision):
            raise ValueError('frozen context selection snapshot does not match its decision')
        source = request.to_document()
        execution = {**frozen, **accepted, 'instruction': source['instruction'],
            'messages': [item for item in source['messages'] if item['message_id'] in decision.to_document()['message_refs']]}
        return TurnPlan(claim.attempt.turn_id, claim.attempt.attempt_id,
            'ordinary', 'direct_pi', 'turn-direct-pi-v2', None, {},
            intent_engine=identity, intent_resources=execution)

    @staticmethod
    def _check_general_configuration(current: dict | None, resources: Mapping) -> None:
        previous = resources.get('general_executor')
        if (current is None) != (previous is None):
            raise HarnessRuntimeConfigurationError('general Pi configuration changed since original Attempt')
        if current is not None:
            if not isinstance(previous, Mapping) or any(current[key] != previous.get(key)
                for key in ('identity', 'timeout_seconds')):
                raise HarnessRuntimeConfigurationError('general Pi configuration changed since original Attempt')
            # New catalog publication changes new acceptance. The host resolves
            # an old accepted revision against its retained private snapshot.
            current_capability = {key: value for key, value in current['capability'].items() if key != 'resource_profiles'}
            previous_capability = {key: value for key, value in previous['capability'].items() if key != 'resource_profiles'}
            if current_capability != previous_capability:
                raise HarnessRuntimeConfigurationError('general Pi configuration changed since original Attempt')

    def __call__(self, claim: AttemptClaim) -> HarnessRuntime:
        plan = claim.turn_plan
        if plan is not None and plan.source == 'direct_pi':
            from .delegated_runtime import DelegatedRuntime
            resources = plan.intent_resources
            if not isinstance(resources, Mapping) or not isinstance(resources.get('resources'), Mapping):
                raise HarnessRuntimeConfigurationError('frozen direct execution resources are unavailable')
            self._check_general_configuration(self._general_resources(claim), cast(Mapping, resources['resources']))
            return DelegatedRuntime(claim, cast(GeneralPiExecutor, self._general), self._business, direct=True)
        if plan is None or plan.intent_decision is None:
            # Registered scripted Cases have an existing deterministic plan.
            if claim.kind in {'send_auto', 'send_ordinary', 'send_professional'}:
                raise ValueError('intent decision is required before runtime preparation')
            return self._business(claim)
        resources = plan.intent_resources
        if not isinstance(resources, Mapping):
            raise ValueError('frozen execution resources are unavailable')
        prior = resources.get('prior_results', [])
        if not isinstance(prior, list):
            raise ValueError('frozen result resources are invalid')
        catalog = resources.get('application_catalog')
        if catalog is not None and not isinstance(catalog, Mapping):
            raise ValueError('frozen application catalog is invalid')
        claim = replace(claim, prior_results=tuple(PriorResultReference(
            item['result_ref'], tuple(item['evidence_refs']), item['capability_id'], item['attempt_id']
        ) for item in prior), application_catalog=catalog)
        if self._general is not _LEGACY:
            from .delegated_runtime import DelegatedRuntime
            self._check_general_configuration(self._general_resources(claim), resources)
            return DelegatedRuntime(claim, cast(GeneralPiExecutor | None, self._general), self._business)
        if plan.route == 'professional':
            return self._business(claim)
        session = self._ordinary(claim, plan.intent_decision)
        return HarnessPiClient(session, admission=getattr(session, 'admit_attempt', None))

    def sweep_idle(self) -> int:
        sweep = getattr(self._business, 'sweep_idle', None)
        return cast(Callable[[], int], sweep)() if callable(sweep) else 0

    def close(self) -> None:
        close = getattr(self._business, 'close', None)
        if callable(close):
            close()


def with_intent_runtime(assembly: ThreadApplicationAssembly,
                        builder_factory: Callable[[], NativeConversationPiSessionBuilder],
                        *, general_executor: GeneralPiExecutor | None = None,
                        general_timeout_seconds: float = 600) -> ThreadApplicationAssembly:
    """Install semantic preparation in a registered hosted application."""
    from .harness import HarnessRuntimeRegistry
    from .pi_intent import PiIntentRecognizer
    from .context_selection import PiContextSelector

    def recognizer() -> IntentRecognizer:
        builder = builder_factory()
        return PiIntentRecognizer(builder.build_intent, builder.identity)

    def ordinary(claim: AttemptClaim, decision: IntentDecision) -> PiPromptSession:
        builder = builder_factory()
        if claim.turn_plan is None or builder.identity.to_document() != dict(claim.turn_plan.intent_engine or {}):
            raise HarnessRuntimeConfigurationError('intent configuration changed before execution')
        return builder.build_execution(claim, decision)

    def context_selector() -> ContextSelector:
        builder = builder_factory()
        return PiContextSelector(builder.build_context_selection, builder.identity)

    factory = IntentRuntimeFactory(assembly.runtime_factory, recognizer, ordinary,
        general_executor=general_executor, general_timeout_seconds=general_timeout_seconds,
        context_selector_factory=context_selector)
    registry = HarnessRuntimeRegistry()
    registry.register('pi', factory)
    return replace(assembly, runtime_factory=factory, runtime_registry=registry, runtime_name='pi')


def _rebind_decision(document: dict, attempt_id: str) -> dict:
    """Preserve accepted goals; only the current user message identity changes."""
    original = document['attempt_id']
    return {**document, 'attempt_id': attempt_id, 'goals': [{**goal,
        'message_refs': [attempt_id + ':user' if identity == original + ':user' else identity
                         for identity in goal['message_refs']]}
        for goal in document['goals']]}
