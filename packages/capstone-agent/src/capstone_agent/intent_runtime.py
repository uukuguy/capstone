"""Application intent node followed by bounded runtime resource selection."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import TYPE_CHECKING
from typing import cast

from .harness import HarnessPiClient, HarnessRuntime, PiPromptSession
from .request_intent import IntentDecision, IntentRecognizer, IntentRequest, NodeControl
from .thread_service import AttemptClaim, PriorResultReference
from .turn_router import RouterConfig, TurnPlan, routing_input_for_claim

if TYPE_CHECKING:
    from .pi_intent import NativeConversationPiSessionBuilder
    from .thread_application import ThreadApplicationAssembly


def intent_request_for_claim(claim: AttemptClaim) -> IntentRequest:
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


class IntentRuntimeFactory:
    """Keep recognition interchangeable while enforcing application permissions."""

    def __init__(self, business_factory: Callable[[AttemptClaim], HarnessRuntime],
                 recognizer_factory: Callable[[], IntentRecognizer],
                 ordinary_session_factory: Callable[[AttemptClaim, IntentDecision], PiPromptSession]):
        self._business = business_factory
        self._recognizer = recognizer_factory
        self._ordinary = ordinary_session_factory

    @property
    def rollback_selection_on_failure(self) -> bool:
        return bool(getattr(self._business, 'rollback_selection_on_failure', False))

    def plan_intent(self, claim: AttemptClaim, control: NodeControl,
                    freeze: Callable[[AttemptClaim, dict], dict]) -> TurnPlan:
        control.checkpoint()
        recognizer = self._recognizer()
        identity = recognizer.identity.to_document()
        request_document = intent_request_for_claim(claim).to_document()
        visible_attempts = {message['attempt_id'] for message in request_document['messages']
                            if message['status'] == 'completed'}
        resources = {'application_catalog': claim.application_catalog,
                     'prior_results': [{'result_ref': ref.result_ref, 'evidence_refs': list(ref.evidence_refs),
                                        'capability_id': ref.capability_id, 'attempt_id': ref.attempt_id}
                                       for ref in claim.prior_results if ref.attempt_id in visible_attempts]}
        frozen = freeze(claim, {'request': request_document,
                               'engine_identity': identity, 'resources': resources})
        if frozen['engine_identity'] != identity:
            raise ValueError('intent configuration changed since original Attempt')
        request_doc = dict(frozen['request'])
        request_doc['attempt_id'] = claim.attempt.attempt_id
        if 'instruction_message_id' in request_doc:
            request_doc['instruction_message_id'] = claim.attempt.attempt_id + ':user'
        request = IntentRequest.from_document(request_doc)
        decision = recognizer.recognize(request, control)
        # A pluggable engine cannot bypass request binding or grant permission.
        decision = IntentDecision.from_document(decision.to_document(), request)
        control.checkpoint()
        document = decision.to_document()
        capabilities = {entry['capability_id']: entry for entry in request_doc['capabilities']}
        executable = decision.execution_goals
        executable_ids = {goal['goal_id'] for goal in executable}
        for goal in document['goals']:
            if goal['goal_id'] not in executable_ids:
                continue
            for ref in goal['capability_refs']:
                entry = capabilities[ref]
                if goal['operation'] in {'business_read', 'business_execute', 'external_lookup'} and (
                    entry.get('enabled') is not True or entry.get('available') is not True
                ):
                    raise ValueError('intent requested a disabled or unavailable capability')
            if goal['operation'] in {'business_read', 'business_execute'} and not goal['capability_refs']:
                raise ValueError('business intent has no authorized capability')
            if goal['operation'] == 'external_lookup' and not goal['capability_refs'] and not goal['missing_requirements']:
                raise ValueError('external lookup has no registered source')
            if goal['operation'] == 'external_lookup':
                # The current catalog contains model profiles, not external sources.
                raise ValueError('external lookup requires a registered external source')
            if goal['operation'] in {'business_read', 'business_execute'} and any(
                ref != claim.model_context.id for ref in goal['object_refs']
            ):
                raise ValueError('business execution requires the active model context')
        return TurnPlan(
            turn_id=claim.attempt.turn_id, attempt_id=claim.attempt.attempt_id,
            route='professional' if any(goal['operation'] in {'business_read', 'business_execute'}
                                        for goal in executable) else 'ordinary',
            source=recognizer.identity.engine, plan_revision='turn-intent-v1',
            capability_hint=None, context_snapshot=routing_input_for_claim(claim).context_snapshot,
            router_config=RouterConfig(mode='semantic', model=recognizer.identity.model,
                                       schema='capstone-intent-decision/1'),
            intent_decision=decision, intent_engine=identity, intent_request=request,
            intent_resources=frozen['resources'],
        )

    def __call__(self, claim: AttemptClaim) -> HarnessRuntime:
        plan = claim.turn_plan
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
                        builder_factory: Callable[[], NativeConversationPiSessionBuilder]) -> ThreadApplicationAssembly:
    """Install semantic preparation in a registered hosted application."""
    from .harness import HarnessRuntimeRegistry
    from .pi_intent import PiIntentRecognizer

    def recognizer() -> IntentRecognizer:
        builder = builder_factory()
        return PiIntentRecognizer(builder.build_intent, builder.identity)

    def ordinary(claim: AttemptClaim, decision: IntentDecision) -> PiPromptSession:
        builder = builder_factory()
        if claim.turn_plan is None or builder.identity.to_document() != dict(claim.turn_plan.intent_engine or {}):
            raise ValueError('intent configuration changed before execution')
        return builder.build_execution(claim, decision)

    factory = IntentRuntimeFactory(assembly.runtime_factory, recognizer, ordinary)
    registry = HarnessRuntimeRegistry()
    registry.register('pi', factory)
    return replace(assembly, runtime_factory=factory, runtime_registry=registry, runtime_name='pi')
