"""Application intent node followed by bounded runtime resource selection."""
from __future__ import annotations

from collections.abc import Callable, Mapping
import math
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
from typing import TYPE_CHECKING
from typing import cast

from .harness import HarnessPiClient, HarnessRuntime, PiPromptSession, HarnessRuntimeConfigurationError
from .request_intent import IntentDecision, IntentRecognizer, IntentRequest, NodeControl
from .thread_service import AttemptClaim, PriorResultReference
from .turn_router import ResearchTurnRouter, RouterConfig, TurnPlan, routing_input_for_claim
from .pi_delegation import GeneralPiExecutor
from .business_context import BusinessContext, business_context_for, unversioned_object_refs
from .context_selection import (ContextSelectionRequest, ContextSelectionDecision,
                                ContextSelector, selected_business_context)

_LEGACY = object()
UNSCOPED_DOMAIN_GAP = '当前没有已启用的领域计算能力。这项计算不能交给通用执行器。'
DOMAIN_EXECUTOR_UNAVAILABLE = '当前领域执行器不可用。这项计算不能交给通用执行器。'
DOMAIN_EXECUTOR_UNREGISTERED = '当前领域执行器没有注册。这项计算不能交给通用执行器。'
DOMAIN_RUNTIME_REQUIRES_MODEL = '领域运行时还不能在没有模型资源时启动。这项计算不能交给通用执行器。'
_DOMAIN_GAPS = frozenset({
    UNSCOPED_DOMAIN_GAP, DOMAIN_EXECUTOR_UNAVAILABLE, DOMAIN_EXECUTOR_UNREGISTERED,
})
_BUSINESS = frozenset({'business_read', 'business_execute'})

if TYPE_CHECKING:
    from .pi_intent import NativeConversationPiSessionBuilder
    from .thread_application import ThreadApplicationAssembly


def intent_request_for_claim(claim: AttemptClaim, general_capability: Mapping | None = None) -> IntentRequest:
    history = claim.conversation_context.to_document()
    messages, history_objects = history['messages'], history.get('objects', [])
    if not isinstance(messages, list) or not isinstance(history_objects, list):
        raise ValueError('conversation projection is invalid')
    context = claim.professional_context
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
    if claim.submission is not None:
        objects = claim.submission['objects']
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
        **({'context_selection': claim.submission['context_selection']} if claim.submission is not None else {}),
        **({'selected_skill': {**claim.submission['resource_profile'],
            'skill_id': claim.submission['input']['skill_id'], 'skill_version': claim.submission['input']['skill_version']}}
            if claim.submission is not None and claim.submission['input']['kind'] == 'skill_invocation'
                and claim.attempt.runtime_mode != 'pi_reference' else {}),
    })


def bind_unscoped_business(document: dict, capabilities: list[dict], *, execute_here: bool) -> tuple[dict, str | None]:
    """Keep a business calculation off general-pi and bind it to a published domain capability.

    An open model is not required. A missing or unavailable domain executor stays
    on the goal as a recorded gap. Exactly one ready family can be handed to that
    family's worker when this process cannot run the domain itself.
    """
    catalog = {entry['capability_id']: entry for entry in capabilities
               if isinstance(entry, Mapping) and isinstance(entry.get('capability_id'), str)}
    goals = []
    families: list[str] = []
    conflict = False
    for goal in document['goals']:
        if goal['operation'] not in _BUSINESS:
            goals.append(goal)
            continue
        refs = [ref for ref in goal['capability_refs'] if ref != 'general-pi']
        ready, published_unavailable = [], False
        for ref in refs:
            entry = catalog.get(ref)
            if not isinstance(entry, Mapping):
                continue
            if entry.get('enabled') is True and entry.get('available') is True:
                ready.append(ref)
            elif entry.get('enabled') is True:
                published_unavailable = True
        missing = [item for item in goal['missing_requirements'] if item not in _DOMAIN_GAPS]
        if not ready:
            gap = DOMAIN_EXECUTOR_UNAVAILABLE if published_unavailable else UNSCOPED_DOMAIN_GAP
            if gap not in missing:
                missing.append(gap)
            goals.append({**goal, 'capability_refs': [], 'missing_requirements': missing})
            continue
        goal_families = []
        for ref in ready:
            raw = catalog[ref].get('implementation_families', [])
            if isinstance(raw, list):
                goal_families.extend(item for item in raw if isinstance(item, str) and item)
        unique = list(dict.fromkeys(goal_families))
        if execute_here:
            goals.append({**goal, 'capability_refs': ready, 'missing_requirements': missing})
            continue
        if len(unique) == 1:
            families.append(unique[0])
            goals.append({**goal, 'capability_refs': ready, 'missing_requirements': missing})
            continue
        conflict = True
        if DOMAIN_EXECUTOR_UNREGISTERED not in missing:
            missing.append(DOMAIN_EXECUTOR_UNREGISTERED)
        goals.append({**goal, 'capability_refs': [], 'missing_requirements': missing})
    chosen = list(dict.fromkeys(families))
    if execute_here or conflict or len(chosen) != 1:
        if not execute_here and len(chosen) > 1:
            rewritten = []
            for goal in goals:
                if goal['operation'] not in _BUSINESS or goal['missing_requirements']:
                    rewritten.append(goal)
                    continue
                missing = list(goal['missing_requirements'])
                if DOMAIN_EXECUTOR_UNREGISTERED not in missing:
                    missing.append(DOMAIN_EXECUTOR_UNREGISTERED)
                rewritten.append({**goal, 'capability_refs': [], 'missing_requirements': missing})
            goals = rewritten
        return {**document, 'goals': goals}, None
    return {**document, 'goals': goals}, chosen[0]


def _one_general_task(document: dict) -> dict:
    return {**document, 'goals': [{
        'goal_id': 'task',
        'description': 'Complete the current instruction with the general executor.',
        'operation': 'answer',
        'message_refs': [],
        'object_refs': [],
        'capability_refs': ['general-pi'],
        'missing_requirements': [],
        'depends_on': [],
    }]}


def keep_general_task(document: dict, capabilities: list[dict], instruction: str) -> dict:
    """Keep the lightweight chain as the only execution of this instruction.

    A configured Domain Pack is called through the tools on that chain. It is
    not a second attempt. A pack that is not available does not withhold the
    instruction or reject the turn.
    """
    del instruction
    catalog = {entry['capability_id']: entry for entry in capabilities
               if isinstance(entry, Mapping) and isinstance(entry.get('capability_id'), str)}
    general = catalog.get('general-pi')
    if not isinstance(general, Mapping) or general.get('enabled') is not True or general.get('available') is not True:
        return document
    operations = set(general.get('operations') or ()) | {'answer', 'rewrite', 'external_lookup'}
    goals = []
    business = False
    changed = False
    for goal in document['goals']:
        if goal['operation'] in _BUSINESS:
            business = True
            continue
        operation = goal['operation']
        if operation not in operations and operation != 'catalog_lookup':
            changed = True
            goals.append({**goal, 'operation': 'answer', 'capability_refs': ['general-pi'], 'missing_requirements': []})
            continue
        goals.append(goal)
    if business or (changed and not goals):
        return _one_general_task(document)
    return {**document, 'goals': goals}


def _published_model_objects(claim: AttemptClaim, existing: list) -> list:
    """Append published catalog models. An open model is not required to name one.

    Identifiers come from the catalog. This does not choose a case. A model
    marked unavailable is omitted. No revision is attached: domain tools open
    the registered model, and a general projection must not treat the identity
    as an already opened workspace object.
    """
    published = list(existing) if isinstance(existing, list) else []
    known = {item['object_id'] for item in published
             if isinstance(item, Mapping) and isinstance(item.get('object_id'), str)}
    catalog = claim.application_catalog if isinstance(claim.application_catalog, Mapping) else {}
    models = catalog.get('models', [])
    for model in models if isinstance(models, list) else []:
        if len(published) >= 200 or not isinstance(model, Mapping) or model.get('available') is False:
            continue
        identity = model.get('model_id')
        if not isinstance(identity, str) or not identity.strip() or len(identity) > 256 or identity in known:
            continue
        entry = {'object_id': identity, 'model_id': identity}
        display_name = model.get('display_name')
        if isinstance(display_name, str) and display_name.strip():
            entry['display_name'] = display_name[:256]
        family = model.get('implementation_family')
        if isinstance(family, str) and family.strip():
            entry['implementation_family'] = family[:256]
        published.append(entry)
        known.add(identity)
    return published


def _general_contexts(request, decision, current_object_id=None) -> dict:
    """Project general goals that already have a version. Catalog identities stay out."""
    contexts = {}
    for goal in decision.execution_goals:
        if goal['operation'] in {'business_read', 'business_execute', 'catalog_lookup'}:
            continue
        if unversioned_object_refs(request, goal):
            continue
        contexts[goal['goal_id']] = business_context_for(
            request, decision, goal_id=goal['goal_id'], current_object_id=current_object_id).to_document()
    return contexts


def _heavy_instruction(claim: AttemptClaim) -> bool:
    """Choose reasoning depth from explicit controls; never discard context."""
    submission = claim.submission or {}
    if claim.kind == 'send_professional' or submission.get('deep_research') is True:
        return True
    raw = submission.get('input')
    if isinstance(raw, Mapping) and raw.get('kind') == 'skill_invocation':
        return True
    selection = submission.get('context_selection')
    refs = selection.get('include_refs') if isinstance(selection, Mapping) else None
    return isinstance(refs, list) and bool(refs)


def _recognize(recognizer, request: IntentRequest, control: NodeControl, thinking_level: str):
    try:
        recognizer.thinking_level = thinking_level
    except (AttributeError, TypeError):
        pass
    return recognizer.recognize(request, control)


def _unscoped_capabilities(claim: AttemptClaim, accepted: Mapping) -> list[dict]:
    operations = [item for item in accepted['capability'].get('operations', ()) if isinstance(item, str)]
    capabilities = [{
        'capability_id': 'general-pi', 'display_name': 'General Pi', 'enabled': True, 'available': True,
        'description': (
            'Isolated general Pi executor. Operations: ' + ', '.join(operations) +
            '. Business model reads and calculations require an enabled Domain Pack capability. '
            'A general executor result is not a domain calculation result. '
            'A missing open model does not disable a published domain capability.')[:8192]}]
    catalog = claim.application_catalog if isinstance(claim.application_catalog, Mapping) else {}
    available_families = set()
    models = catalog.get('models', [])
    for model in models if isinstance(models, list) else []:
        if not isinstance(model, Mapping):
            continue
        family = model.get('implementation_family')
        if isinstance(family, str) and family and model.get('available') is not False:
            available_families.add(family)
    profiles = catalog.get('profiles', [])
    seen = {'general-pi'}
    for profile in profiles if isinstance(profiles, list) else []:
        if not isinstance(profile, Mapping):
            continue
        pid, version = profile.get('profile_id'), profile.get('profile_version')
        if not isinstance(pid, str) or not isinstance(version, str):
            continue
        identity = f'{pid}@{version}'
        if identity in seen:
            continue
        seen.add(identity)
        published = profile.get('implementation_families', [])
        published = [item for item in published if isinstance(item, str) and item] if isinstance(published, list) else []
        ready = [item for item in published if item in available_families]
        entry = {'capability_id': identity, 'display_name': pid, 'enabled': True, 'available': bool(ready)}
        display_name = profile.get('display_name')
        if isinstance(display_name, str) and display_name.strip():
            entry['display_name'] = display_name[:256]
        if published:
            entry['implementation_families'] = ready or published
        capabilities.append(entry)
    return capabilities


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
            'relation': 'current' if item['object_id'] == claim.professional_context.id else 'historical',
            'source': {'kind': 'workspace', 'workspace_id': source['thread_id'],
                'message_refs': [message['message_id'] for message in source['messages']
                    if message['model_context_id'] == item['object_id']]}})
    return ContextSelectionRequest.from_document({'schema': 'capstone-context-selection-request/1',
        'workspace_id': source['thread_id'], 'current_object_id': claim.professional_context.id,
        **{key: source[key] for key in ('turn_id', 'attempt_id', 'instruction_message_id',
            'instruction', 'history_cutoff', 'history_truncated', 'messages')}, 'objects': objects,
        **({'context_selection': source['context_selection']} if 'context_selection' in source else {})})


class IntentRuntimeFactory:
    """Keep recognition interchangeable while enforcing application permissions."""

    supports_frozen_intent_decision = True

    def __init__(self, business_factory: Callable[[AttemptClaim], HarnessRuntime],
                 recognizer_factory: Callable[[], IntentRecognizer],
                 ordinary_session_factory: Callable[[AttemptClaim, IntentDecision], PiPromptSession],
                 *, general_executor: GeneralPiExecutor | None | object = _LEGACY,
                 general_timeout_seconds: float = 600,
                 application_timeout_seconds: Mapping[str, float] | None = None,
                 context_selector_factory: Callable[[], ContextSelector] | None = None,
                 research_router: ResearchTurnRouter | None = None,
                 native_research_root: Path | None = None,
                 unscoped_intent: bool = False):
        self._business = business_factory
        self._recognizer = recognizer_factory
        self._ordinary = ordinary_session_factory
        self._general = general_executor
        self._context_selector = context_selector_factory
        self._research_router = research_router
        self.native_research_root = native_research_root
        if type(unscoped_intent) is not bool:
            raise ValueError('unscoped intent selection is invalid')
        self._unscoped_intent = unscoped_intent
        if type(general_timeout_seconds) not in {int, float} or not math.isfinite(general_timeout_seconds) or general_timeout_seconds < 1:
            raise ValueError('general task timeout is invalid')
        self._general_timeout = general_timeout_seconds
        self._application_timeouts = dict(application_timeout_seconds or {})
        for timeout in self._application_timeouts.values():
            if type(timeout) not in {int, float} or not math.isfinite(timeout) or timeout < 1:
                raise ValueError('application task timeout is invalid')

    def _recognizer_for_attempt(self, claim: AttemptClaim):
        selected = getattr(self._recognizer, 'for_attempt', None)
        return selected(claim) if callable(selected) else self._recognizer()

    def _general_resources(self, claim: AttemptClaim) -> dict | None:
        if self._general is _LEGACY or self._general is None:
            return None
        executor = cast(GeneralPiExecutor, self._general)
        # Export fresh JSON; private origins and control tokens are not resources.
        from .delegated_runtime import json_document
        capability = cast(dict[str, object], json_document(executor.capability))
        if claim.model_context is None:
            from .native_conversation import executor_binding
            capability = executor_binding(executor)['capability']
        if claim.submission is not None and 'resource_profiles' in claim.submission:
            capability['resource_profiles'] = {role: profile for role, profile in claim.submission['resource_profiles'].items()
                                               if role in {'direct_pi', 'delegated_pi'}}
        return {'identity': json_document(executor.identity),
                'capability': capability,
                'original_attempt_id': claim.attempt.attempt_id,
                'timeout_seconds': self._timeout_for(claim)}

    def _timeout_for(self, claim: AttemptClaim) -> float:
        binding = (claim.submission or {}).get('_native_execution', {})
        profile_id = binding.get('application_profile', {}).get('profile_id')
        return self._application_timeouts.get(profile_id, self._general_timeout)

    @property
    def rollback_selection_on_failure(self) -> bool:
        return bool(getattr(self._business, 'rollback_selection_on_failure', False))

    def plan_intent(self, claim: AttemptClaim, control: NodeControl,
                    freeze: Callable[[AttemptClaim, dict], dict], *,
                    freeze_decision: Callable[[AttemptClaim, dict | None], dict | None] | None = None) -> TurnPlan:
        control.checkpoint()
        if claim.model_context is None:
            # No open model is an execution resource, not a reason to skip understanding.
            # A domain handoff replays the frozen decision on the receiving worker.
            # A runtime without a recognizer keeps the synthetic conversation. A retry
            # frozen before recognition has no engine identity and stays on that snapshot.
            domain = (claim.submission or {}).get('_domain_execution')
            if isinstance(domain, Mapping) and domain.get('role') == 'report':
                return self._plan_domain_report(claim, control, freeze, freeze_decision, domain)
            if isinstance(domain, Mapping) and isinstance(domain.get('implementation_family'), str):
                return self._replay_frozen_domain_execution(claim, control, freeze, freeze_decision)
            if self._unscoped_intent:
                recognized = self._plan_unscoped_research_intent(claim, control, freeze, freeze_decision)
                if recognized is not None:
                    return recognized
            return self._plan_native_conversation(claim, control, freeze, freeze_decision)
        if claim.attempt.runtime_mode != 'pi_reference' and self._research_router is not None:
            selection = (claim.submission or {}).get('context_selection', {})
            if claim.professional_context.id in selection.get('exclude_refs', ()):
                raise HarnessRuntimeConfigurationError('research model is explicitly excluded')
            return self._research_router.plan(routing_input_for_claim(claim))
        general = self._general_resources(claim)
        if claim.attempt.runtime_mode == 'pi_reference':
            if (general is None or general['capability'].get('enabled') is not True
                or general['capability'].get('available') is not True):
                raise HarnessRuntimeConfigurationError('general Pi executor is unavailable')
            return self._plan_direct(claim, control, freeze, freeze_decision, general)
        recognizer = self._recognizer_for_attempt(claim)
        identity = recognizer.identity.to_document()
        request_document = intent_request_for_claim(claim, None if general is None else general['capability']).to_document()
        visible_attempts = {message['attempt_id'] for message in request_document['messages']
                            if message['status'] == 'completed'}
        resources = {'application_catalog': claim.application_catalog,
                     'current_object_id': claim.professional_context.id,
                     'prior_results': [{'result_ref': ref.result_ref, 'evidence_refs': list(ref.evidence_refs),
                                        'capability_id': ref.capability_id, 'attempt_id': ref.attempt_id}
                                       for ref in claim.prior_results if ref.attempt_id in visible_attempts]}
        resources['general_executor'] = general
        resources['submission'] = claim.submission
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
            if goal['operation'] in {'business_read', 'business_execute'} and claim.professional_context.id in request_doc.get('context_selection', {}).get('exclude_refs', []):
                raise ValueError('business execution cannot use the explicitly excluded current object')
            general_id = None if general is None else general['capability']['capability_id']
            if goal['operation'] in {'business_read', 'business_execute'} and general_id in goal['capability_refs']:
                raise ValueError('business execution requires a domain capability')
            if goal['operation'] == 'external_lookup' and general is None:
                raise HarnessRuntimeConfigurationError('general Pi executor is unavailable')
            if goal['operation'] not in {'business_read', 'business_execute', 'catalog_lookup'} and self._general is not _LEGACY:
                if general is None or general['capability'].get('enabled') is not True or general['capability'].get('available') is not True:
                    raise HarnessRuntimeConfigurationError('general Pi executor is unavailable')
                if goal['operation'] not in general['capability'].get('operations', ()):
                    goal['operation'] = 'answer'
                    if general_id is not None:
                        goal['capability_refs'] = [general_id]
                if any(ref != general_id for ref in goal['capability_refs']):
                    raise ValueError('general execution cannot use domain capabilities')
            if goal['operation'] in {'business_read', 'business_execute'} and any(
                ref != claim.professional_context.id for ref in goal['object_refs']
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
            general_goals = [goal for goal in original_decision.execution_goals
                             if goal['operation'] not in {'business_read', 'business_execute', 'catalog_lookup'}]
            current_object_id = execution_resources.get('current_object_id')
            if current_object_id is None and general_goals:
                current_object_id = original.to_document()['objects'][0]['object_id']
            execution_resources['business_contexts'] = _general_contexts(
                original, original_decision, current_object_id)
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

    def _plan_native_conversation(self, claim, control, freeze, freeze_decision):
        """A declared ordinary conversation needs no business intent planner."""
        from .native_conversation import validate_binding, executor_binding
        if self._general is _LEGACY or self._general is None:
            raise HarnessRuntimeConfigurationError('native conversation executor is unavailable')
        accepted = validate_binding((claim.submission or {}).get('_native_execution'))
        current = executor_binding(cast(GeneralPiExecutor, self._general),
                                   session_type=accepted['application_profile']['profile_id'])
        if accepted['identity'] != current['identity']:
            raise HarnessRuntimeConfigurationError('native conversation executor configuration changed')
        history = claim.conversation_context.to_document()
        submission = claim.submission or {}
        request = IntentRequest.from_document({
            'schema': 'capstone-intent-request/1', 'thread_id': claim.thread_id,
            'turn_id': claim.attempt.turn_id, 'attempt_id': claim.attempt.attempt_id,
            'instruction_message_id': claim.attempt.attempt_id + ':user',
            'instruction': claim.instruction, 'history_cutoff': history['history_cutoff'],
            'history_truncated': history['truncated'], 'messages': history['messages'],
            'objects': submission.get('objects', []), 'capabilities': [{
                'capability_id': 'general-pi', 'enabled': True, 'available': True}],
            'mode_hint': 'ordinary',
            **({'context_selection': submission['context_selection']} if 'context_selection' in submission else {}),
            **({'selected_skill': {**submission['resource_profile'],
                'skill_id': submission['input']['skill_id'], 'skill_version': submission['input']['skill_version']}}
                if submission.get('input', {}).get('kind') == 'skill_invocation' else {}),
        })
        general = {'identity': accepted['identity'], 'capability': accepted['capability'],
                   'application_profile': accepted['application_profile'],
                   'original_attempt_id': claim.attempt.attempt_id, 'timeout_seconds': self._timeout_for(claim)}
        resources = {'general_executor': general, 'submission': {key: value for key, value in (claim.submission or {}).items() if key != '_materials'},
                     'application_catalog': None, 'prior_results': []}
        from .native_task_context import native_context_for
        resources['native_context'] = native_context_for(claim, accepted)
        frozen = freeze(claim, {'request': request.to_document(), 'resources': resources})
        if frozen['resources']['general_executor']['identity'] != current['identity']:
            raise HarnessRuntimeConfigurationError('native conversation configuration changed')
        request = IntentRequest.from_document(frozen['request'])
        decision = IntentDecision.from_document({
            'schema': 'capstone-intent-decision/1', 'attempt_id': claim.attempt.attempt_id,
            'history_cutoff': request.to_document()['history_cutoff'], 'relationship': 'continuation',
            'goals': [{'goal_id': 'conversation', 'description': 'Reply to the current user input',
                'operation': 'answer', 'message_refs': [item['message_id'] for item in history['messages']],
                'object_refs': request.to_document().get('context_selection', {}).get('include_refs', []),
                'capability_refs': ['general-pi'], 'missing_requirements': [],
                'depends_on': [], **({'uses_selected_skill': True} if 'selected_skill' in request.to_document() else {})}],
            'clarification': None}, request)
        if freeze_decision is not None:
            saved = freeze_decision(claim, decision.to_document())
            if saved is None:
                raise ValueError('native conversation decision was not saved')
            decision = IntentDecision.from_document(saved, request)
        resources = {**frozen['resources'], 'business_contexts': {
            'conversation': business_context_for(request, decision).to_document()}}
        control.checkpoint()
        return TurnPlan(claim.attempt.turn_id, claim.attempt.attempt_id,
            'ordinary', 'native_conversation', 'turn-native-conversation-v1', None, {},
            intent_request=request, intent_decision=decision, intent_resources=resources)

    def _plan_unscoped_research_intent(self, claim, control, freeze, freeze_decision):
        """Ask for one decision before any general execution when no model is open.

        A retry whose frozen input has no engine identity keeps the synthetic
        conversation that was accepted before this gate existed.
        """
        from .native_conversation import validate_binding, executor_binding
        from .native_task_context import native_context_for
        if self._general is _LEGACY or self._general is None:
            raise HarnessRuntimeConfigurationError('native conversation executor is unavailable')
        accepted = validate_binding((claim.submission or {}).get('_native_execution'))
        current = executor_binding(cast(GeneralPiExecutor, self._general),
                                   session_type=accepted['application_profile']['profile_id'])
        if accepted['identity'] != current['identity']:
            raise HarnessRuntimeConfigurationError('native conversation executor configuration changed')
        recognizer = self._recognizer_for_attempt(claim)
        identity = recognizer.identity.to_document()
        history = claim.conversation_context.to_document()
        submission = claim.submission or {}
        request = IntentRequest.from_document({
            'schema': 'capstone-intent-request/1', 'thread_id': claim.thread_id,
            'turn_id': claim.attempt.turn_id, 'attempt_id': claim.attempt.attempt_id,
            'instruction_message_id': claim.attempt.attempt_id + ':user',
            'instruction': claim.instruction, 'history_cutoff': history['history_cutoff'],
            'history_truncated': history['truncated'], 'messages': history['messages'],
            'objects': _published_model_objects(claim, submission.get('objects', [])),
            'capabilities': _unscoped_capabilities(claim, accepted),
            'mode_hint': {'send_ordinary': 'ordinary', 'send_professional': 'professional'}.get(claim.kind),
            **({'context_selection': submission['context_selection']} if 'context_selection' in submission else {}),
            **({'selected_skill': {**submission['resource_profile'],
                'skill_id': submission['input']['skill_id'], 'skill_version': submission['input']['skill_version']}}
                if submission.get('input', {}).get('kind') == 'skill_invocation' else {}),
        })
        general = {'identity': accepted['identity'], 'capability': accepted['capability'],
                   'application_profile': accepted['application_profile'],
                   'original_attempt_id': claim.attempt.attempt_id, 'timeout_seconds': self._timeout_for(claim)}
        resources = {'general_executor': general,
                     'submission': {key: value for key, value in submission.items() if key != '_materials'},
                     'application_catalog': claim.application_catalog, 'prior_results': []}
        resources['native_context'] = native_context_for(claim, accepted)
        frozen = freeze(claim, {'request': request.to_document(), 'engine_identity': identity, 'resources': resources})
        if 'engine_identity' not in frozen:
            return None
        if frozen['resources']['general_executor']['identity'] != current['identity']:
            raise HarnessRuntimeConfigurationError('native conversation configuration changed')
        if frozen['engine_identity'] != identity:
            raise HarnessRuntimeConfigurationError('intent configuration changed since original Attempt')
        request_doc = dict(frozen['request'])
        request_doc['attempt_id'] = claim.attempt.attempt_id
        if 'instruction_message_id' in request_doc:
            request_doc['instruction_message_id'] = claim.attempt.attempt_id + ':user'
        request = IntentRequest.from_document(request_doc)
        saved = None if freeze_decision is None else freeze_decision(claim, None)
        if saved is None:
            decision = _recognize(recognizer, request, control,
                'medium' if _heavy_instruction(claim) else 'low')
        else:
            decision = IntentDecision.from_document(_rebind_decision(saved, claim.attempt.attempt_id), request)
        execute_here = getattr(self._business, 'domain_execution', True) is not False
        bound, dispatch = bind_unscoped_business(
            decision.to_document(), list(request_doc['capabilities']), execute_here=execute_here)
        bound = keep_general_task(bound, list(request_doc['capabilities']), request_doc['instruction'])
        decision = IntentDecision.from_document(bound, request)
        control.checkpoint()
        document = decision.to_document()
        capabilities = {entry['capability_id']: entry for entry in request_doc['capabilities']}
        executable = decision.execution_goals
        executable_ids = {goal['goal_id'] for goal in executable}
        general_id = general['capability']['capability_id']
        for goal in document['goals']:
            if len(document['goals']) > 1 and 'instruction_excerpt' not in goal:
                raise ValueError('mixed goal requires a source excerpt')
            if goal['goal_id'] not in executable_ids:
                continue
            if goal['operation'] in _BUSINESS:
                if not goal['capability_refs']:
                    raise ValueError('business intent has no authorized capability')
                for ref in goal['capability_refs']:
                    entry = capabilities[ref]
                    if entry.get('enabled') is not True or entry.get('available') is not True or ref == general_id:
                        raise ValueError('business execution requires a domain capability')
                continue
            for ref in goal['capability_refs']:
                entry = capabilities[ref]
                if goal['operation'] == 'external_lookup' and (entry.get('enabled') is not True or entry.get('available') is not True):
                    raise HarnessRuntimeConfigurationError('general Pi executor is unavailable')
            if goal['operation'] == 'external_lookup' and self._general is _LEGACY:
                continue
            if goal['operation'] != 'catalog_lookup':
                if general['capability'].get('enabled') is not True or general['capability'].get('available') is not True:
                    raise HarnessRuntimeConfigurationError('general Pi executor is unavailable')
                if goal['operation'] not in general['capability'].get('operations', ()):
                    goal['operation'] = 'answer'
                    goal['capability_refs'] = [general_id]
                if any(ref != general_id for ref in goal['capability_refs']):
                    raise ValueError('general execution cannot use domain capabilities')
        if freeze_decision is not None:
            stored = freeze_decision(claim, document)
            if stored is None:
                raise ValueError('accepted intent decision was not saved')
            decision = IntentDecision.from_document(_rebind_decision(stored, claim.attempt.attempt_id), request)
        original = IntentRequest.from_document(frozen['request'])
        original_decision = IntentDecision.from_document(
            _rebind_decision(decision.to_document(), frozen['request']['attempt_id']), original)
        execution_resources = dict(frozen['resources'])
        execution_resources['business_contexts'] = _general_contexts(original, original_decision)
        # The lightweight chain keeps the attempt. A ready Domain Pack goal is a
        # tool call inside that chain, not a separate professional execution.
        return TurnPlan(
            turn_id=claim.attempt.turn_id, attempt_id=claim.attempt.attempt_id,
            route='ordinary',
            source=recognizer.identity.engine, plan_revision='turn-intent-v1',
            capability_hint=None, context_snapshot=routing_input_for_claim(claim).context_snapshot,
            router_config=RouterConfig(mode='semantic', model=recognizer.identity.model,
                                       schema='capstone-intent-decision/1'),
            intent_decision=decision, intent_engine=identity, intent_request=request,
            intent_resources=execution_resources)

    def _plan_domain_report(self, claim, control, freeze, freeze_decision, domain):
        """Finish a mixed task from the parent draft and the grid node receipt."""
        del control
        frozen = freeze(claim, None)
        if not isinstance(frozen, Mapping) or 'request' not in frozen or 'engine_identity' not in frozen:
            raise HarnessRuntimeConfigurationError('domain node report is unavailable')
        identity = frozen['engine_identity']
        if not isinstance(identity, Mapping) or not isinstance(identity.get('engine'), str):
            raise HarnessRuntimeConfigurationError('domain node report is unavailable')
        resources = dict(frozen.get('resources') or {})
        request_doc = dict(frozen['request'])
        request_doc['attempt_id'] = claim.attempt.attempt_id
        if 'instruction_message_id' in request_doc:
            request_doc['instruction_message_id'] = claim.attempt.attempt_id + ':user'
        request = IntentRequest.from_document(request_doc)
        saved = None if freeze_decision is None else freeze_decision(claim, None)
        if not isinstance(saved, Mapping):
            raise HarnessRuntimeConfigurationError('domain node report is unavailable')
        decision = IntentDecision.from_document(
            _rebind_decision(dict(saved), claim.attempt.attempt_id), request)
        resources.pop('domain_dispatch_family', None)
        resources['business_contexts'] = _general_contexts(request, decision)
        resources['assemble_domain_report'] = True
        resources['parent_text'] = domain.get('parent_text') or ''
        resources['node_text'] = domain.get('node_text') or ''
        from .domain_node_report import goal_heading
        goals = decision.to_document()['goals']
        resources['report_parent_title'] = goal_heading(goals, business=False, fallback='任务说明')
        resources['report_node_title'] = goal_heading(goals, business=True, fallback='领域计算')
        return TurnPlan(
            turn_id=claim.attempt.turn_id, attempt_id=claim.attempt.attempt_id,
            route='ordinary', source=identity['engine'], plan_revision='turn-intent-v1',
            capability_hint=None, context_snapshot=routing_input_for_claim(claim).context_snapshot,
            router_config=RouterConfig(mode='semantic', model=identity.get('model') or '',
                                       schema='capstone-intent-decision/1'),
            intent_decision=decision, intent_engine=dict(identity), intent_request=request,
            intent_resources=resources)

    def _replay_frozen_domain_execution(self, claim, control, freeze, freeze_decision):
        """Replay a frozen domain decision. Do not recognize or bind the goal again."""
        from .native_conversation import validate_binding, executor_binding
        if self._general is _LEGACY or self._general is None:
            raise HarnessRuntimeConfigurationError('native conversation executor is unavailable')
        accepted = validate_binding((claim.submission or {}).get('_native_execution'))
        current = executor_binding(cast(GeneralPiExecutor, self._general),
                                   session_type=accepted['application_profile']['profile_id'])
        if accepted['identity'] != current['identity']:
            raise HarnessRuntimeConfigurationError('native conversation executor configuration changed')
        frozen = freeze(claim, None)
        if not isinstance(frozen, Mapping) or 'engine_identity' not in frozen or 'request' not in frozen:
            raise HarnessRuntimeConfigurationError('domain execution replay is unavailable')
        resources = frozen.get('resources')
        identity = frozen.get('engine_identity')
        if (not isinstance(resources, Mapping) or not isinstance(identity, Mapping)
                or not isinstance(identity.get('engine'), str) or not isinstance(identity.get('model'), str)):
            raise HarnessRuntimeConfigurationError('domain execution replay is unavailable')
        general = resources.get('general_executor')
        if not isinstance(general, Mapping) or general.get('identity') != current['identity']:
            raise HarnessRuntimeConfigurationError('native conversation executor configuration changed')
        request_doc = dict(frozen['request'])
        request_doc['attempt_id'] = claim.attempt.attempt_id
        if 'instruction_message_id' in request_doc:
            request_doc['instruction_message_id'] = claim.attempt.attempt_id + ':user'
        request = IntentRequest.from_document(request_doc)
        saved = None if freeze_decision is None else freeze_decision(claim, None)
        if not isinstance(saved, Mapping):
            raise HarnessRuntimeConfigurationError('domain execution replay is unavailable')
        decision = IntentDecision.from_document(_rebind_decision(dict(saved), claim.attempt.attempt_id), request)
        control.checkpoint()
        # The frozen input stops before child projections. Rebuild the general
        # excerpt's context from that input so replay can form a typed Pi request.
        original = IntentRequest.from_document(frozen['request'])
        original_decision = IntentDecision.from_document(
            _rebind_decision(dict(saved), frozen['request']['attempt_id']), original)
        execution_resources = {key: value for key, value in resources.items() if key != 'domain_dispatch_family'}
        execution_resources['business_contexts'] = _general_contexts(original, original_decision)
        domain = (claim.submission or {}).get('_domain_execution')
        if isinstance(domain, Mapping) and domain.get('role') == 'node':
            execution_resources['domain_node_only'] = True
            execution_resources['parent_text'] = domain.get('parent_text') or ''
        business = any(goal['operation'] in _BUSINESS for goal in decision.execution_goals)
        return TurnPlan(
            turn_id=claim.attempt.turn_id, attempt_id=claim.attempt.attempt_id,
            route='professional' if business else 'ordinary',
            source=identity['engine'], plan_revision='turn-intent-v1',
            capability_hint=None, context_snapshot=routing_input_for_claim(claim).context_snapshot,
            router_config=RouterConfig(mode='semantic', model=identity['model'],
                                       schema='capstone-intent-decision/1'),
            intent_decision=decision, intent_engine=dict(identity), intent_request=request,
            intent_resources=execution_resources)

    def _plan_direct(self, claim, control, freeze, freeze_decision, general):
        if self._context_selector is None:
            raise HarnessRuntimeConfigurationError('direct Pi context selector is unavailable')
        selector = self._context_selector()
        identity = selector.identity.to_document()
        frozen = freeze(claim, {'entrypoint': 'direct',
            'request': context_selection_request_for_claim(claim).to_document(),
            'engine_identity': identity, 'submission': claim.submission,
            'resources': {'general_executor': general}})
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
            # Gateway publication belongs to the accepted conversation, not the
            # workspace default. The protected host checks its frozen instance
            # and catalog revision before admitting any call.
            scoped = {'resource_profiles', 'data_gateway'}
            current_capability = {key: value for key, value in current['capability'].items() if key not in scoped}
            previous_capability = {key: value for key, value in previous['capability'].items() if key not in scoped}
            if current_capability != previous_capability:
                raise HarnessRuntimeConfigurationError('general Pi configuration changed since original Attempt')

    def __call__(self, claim: AttemptClaim) -> HarnessRuntime:
        plan = claim.turn_plan
        if (claim.attempt.runtime_mode != 'pi_reference' and self._research_router is not None
                and plan is not None and plan.intent_decision is None
                and plan.source in {'agent_loop', 'explicit'}):
            return self._business(claim)
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
            runtime = DelegatedRuntime(claim, cast(GeneralPiExecutor | None, self._general), self._business)
            if (claim.model_context is None and self.native_research_root is not None
                    and not resources.get('assemble_domain_report')):
                from .native_conversation import NativeResearchRuntime
                accepted_submission = cast(Mapping, resources.get('submission') or {})
                accepted_profile = accepted_submission.get('_native_execution', {}).get('application_profile', {})
                return NativeResearchRuntime(runtime, claim, self.native_research_root,
                    governed=accepted_profile in (
                        {'profile_id': 'enterprise-research', 'profile_version': '1.1.0'},
                        {'profile_id': 'enterprise-research', 'profile_version': '1.2.0'},
                        {'profile_id': 'enterprise-research', 'profile_version': '1.3.0'},
                        {'profile_id': 'enterprise-research', 'profile_version': '1.4.0'},
                        {'profile_id': 'enterprise-research', 'profile_version': '1.5.0'},
                        {'profile_id': 'enterprise-research', 'profile_version': '1.6.0'},
                        {'profile_id': 'enterprise-research', 'profile_version': '1.7.0'},
                        {'profile_id': 'enterprise-research', 'profile_version': '1.8.0'},
                        {'profile_id': 'enterprise-research', 'profile_version': '1.9.0'},
                        {'profile_id': 'enterprise-research', 'profile_version': '1.10.0'},
                        {'profile_id': 'enterprise-research', 'profile_version': '1.11.0'},
                        {'profile_id': 'enterprise-research', 'profile_version': '1.12.0'},
                        {'profile_id': 'enterprise-research', 'profile_version': '1.13.0'},
                        {'profile_id': 'enterprise-research', 'profile_version': '1.14.0'},
                        {'profile_id': 'enterprise-research', 'profile_version': '1.15.0'},
                        {'profile_id': 'enterprise-research', 'profile_version': '1.16.0'},
                        {'profile_id': 'enterprise-research', 'profile_version': '1.17.0'},
                        {'profile_id': 'enterprise-research', 'profile_version': '1.18.0'},
                        {'profile_id': 'enterprise-research', 'profile_version': '1.19.0'},
        {'profile_id': 'enterprise-research', 'profile_version': '1.20.0'}))
            return runtime
        if plan.route == 'professional':
            return self._business(claim)
        session = self._ordinary(claim, plan.intent_decision)
        return HarnessPiClient(session, admission=getattr(session, 'admit_attempt', None))

    def prepare_model(self, snapshot) -> None:
        """Keep the wrapped runtime's model preparation independent of intent."""
        prepare = getattr(self._business, 'prepare_model', None)
        if callable(prepare):
            prepare(snapshot)

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
        context_selector_factory=context_selector,
        research_router=assembly.turn_router if isinstance(assembly.turn_router, ResearchTurnRouter) else None)
    registry = HarnessRuntimeRegistry()
    registry.register('pi', factory)
    from .thread_input_catalog import PreparedResourceCatalog
    from .pi_intent import default_config_root
    resources = PreparedResourceCatalog(assembly.capability_context_owner, general_executor, default_config_root().parent)
    return replace(assembly, runtime_factory=factory, runtime_registry=registry, runtime_name='pi',
                   resource_profiles=resources)


def _rebind_decision(document: dict, attempt_id: str) -> dict:
    """Preserve accepted goals; only the current user message identity changes."""
    original = document['attempt_id']
    return {**document, 'attempt_id': attempt_id, 'goals': [{**goal,
        'message_refs': [attempt_id + ':user' if identity == original + ':user' else identity
                         for identity in goal['message_refs']]}
        for goal in document['goals']]}
