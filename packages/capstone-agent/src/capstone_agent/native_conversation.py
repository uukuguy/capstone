"""Application-owned native conversation binding over the existing Pi host."""
import json
from typing import cast
from collections.abc import Mapping

from .general_executor_composition import _resource_profiles


def executor_binding(executor, *, session_type: str | None = None, profile_version: str | None = None, _policy_variant='default') -> dict:
    from .delegated_runtime import json_document
    capability = cast(dict, json_document(executor.capability))
    identity = cast(dict, json_document(executor.identity))
    if (not identity or capability.get('capability_id') != 'general-pi'
            or capability.get('enabled') is not True or capability.get('available') is not True
            or 'answer' not in capability.get('operations', ())):
        raise ValueError('native conversation executor is unavailable')
    if 'capstone-native-context/1' not in capability.get('native_context_schemas', ()):
        raise ValueError('native conversation context contract is unavailable')
    _resource_profiles(capability.get('resource_profiles', {}))
    if 'delegated_pi' not in capability.get('resource_profiles', {}):
        raise ValueError('native conversation resource profile is unavailable')
    from .enterprise_application import resolve_native_profile
    from .native_pack_preparation import PiNativeBindingPreparer
    from capability_agent.domain.profile import NativeDomainRuntimeProfile
    from pathlib import Path
    supported = 'capstone-research-bridge/1' in capability.get('research_bridge_schemas', ())
    review_supported = 'capstone-delivery-review/1' in capability.get('delivery_review_schemas', ())
    from .native_task_context import registered_research_policy
    supported_policies = capability.get('research_policy_profiles', [])
    research_version = next((version for version in ('1.9.0', '1.8.0', '1.7.0', '1.6.0', '1.5.0', '1.4.0')
                             if registered_research_policy(version).capability() in supported_policies), '1.3.0') if review_supported else '1.2.0'
    graph_supported = 'capstone-enterprise-graph/2' in capability.get('research_graph_schemas', ())
    for graph_version in ('1.10.0', '1.11.0', '1.12.0', '1.13.0', '1.14.0', '1.15.0', '1.16.0', '1.17.0', '1.18.0'):
        if graph_supported and registered_research_policy(graph_version).capability() in supported_policies:
            research_version = graph_version
    version = profile_version or (research_version if supported and session_type in {None, 'enterprise-research'} else '1.0.0')
    if version in {'1.10.0', '1.11.0', '1.12.0', '1.13.0', '1.14.0', '1.15.0', '1.16.0', '1.17.0', '1.18.0'} and not graph_supported:
        raise ValueError('research graph protocol is unavailable on this executor')
    if version in {'1.3.0', '1.4.0', '1.5.0', '1.6.0', '1.7.0', '1.8.0', '1.9.0'} and not review_supported:
        raise ValueError('independent delivery review is unavailable')
    if version in {'1.4.0', '1.5.0', '1.6.0', '1.7.0', '1.8.0', '1.9.0', '1.10.0', '1.11.0', '1.12.0', '1.13.0', '1.14.0', '1.15.0', '1.16.0', '1.17.0', '1.18.0'} and registered_research_policy(version).capability() not in supported_policies:
        raise ValueError('research policy profile is unavailable on this executor')
    profile = resolve_native_profile(session_type, version, policy_variant=_policy_variant)
    native_bindings = [item for item in profile.domains if isinstance(item.profile, NativeDomainRuntimeProfile)]
    if len(native_bindings) != 1:
        raise ValueError('conversation execution requires one selected native executor binding')
    binding = native_bindings[0]
    if version in {'1.1.0', '1.2.0', '1.3.0', '1.4.0', '1.5.0', '1.6.0', '1.7.0', '1.8.0', '1.9.0', '1.10.0', '1.11.0', '1.12.0', '1.13.0', '1.14.0', '1.15.0', '1.16.0', '1.17.0', '1.18.0'} and not supported:
        raise ValueError('research control transport is unavailable')
    if not isinstance(binding.profile, NativeDomainRuntimeProfile):
        raise ValueError('native application selected an incompatible binding')
    class NativeCredentials:
        scope_id = 'isolated'
        credentials: Mapping[str, str] = {}
    prepared = PiNativeBindingPreparer(executor).prepare(binding=binding, profile=binding.profile,
        workspace=Path('.'), credentials=NativeCredentials())
    if prepared.receipt.resource_revision != capability['resource_profiles']['delegated_pi']['revision']:
        raise ValueError('native resource preparation identity changed')
    prepared.close()
    # Optional retrieval is not an application grant merely because the host
    # supports it. The base conversation has no external lookup permission.
    capability['operations'] = [item for item in capability['operations'] if item in {'answer', 'rewrite'}]
    result = {'schema': 'capstone-native-conversation/1',
            'application_profile': {'profile_id': profile.manifest.application_id,
                                    'profile_version': profile.manifest.version},
            'binding_id': binding.binding_id, 'identity': identity, 'capability': capability}
    if version in {'1.1.0', '1.2.0', '1.3.0', '1.4.0', '1.5.0', '1.6.0', '1.7.0', '1.8.0', '1.9.0', '1.10.0', '1.11.0', '1.12.0', '1.13.0', '1.14.0', '1.15.0', '1.16.0', '1.17.0', '1.18.0'}:
        from hashlib import sha256
        pack = binding.profile
        guides = []
        for item in pack.guide_provider.load():
            resource_id = item['resource_id']
            if not isinstance(resource_id, str):
                raise ValueError('native Pack guide identity is invalid')
            guides.append(dict(pack.guide_provider.open(resource_id)))
        result['pack_bindings'] = [{'binding_id': binding.binding_id, 'pack_id': pack.manifest.domain_id,
            'pack_version': pack.manifest.version,
            'policy_sha256': sha256(pack.policy_provider.load().encode()).hexdigest(),
            'guides_sha256': sha256(json.dumps(guides, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
            'resource_profile_id': prepared.receipt.resource_profile_id,
            'resource_revision': prepared.receipt.resource_revision}]
    return result


def binding_for_session(binding: Mapping | None, session_type: str | None) -> dict:
    """Select host-published organization; session labels retain entry defaults."""
    from types import SimpleNamespace
    if binding is None:
        raise ValueError('native conversation executor is unavailable')
    if session_type not in {None, 'general-chat', 'enterprise-research'}:
        raise ValueError('native session type is not registered')
    capability = binding['capability']
    from .native_task_context import registered_research_policy
    # The current incremental organizer can answer without constructing a task
    # graph, then plan useful work on a later turn. Older publications retain
    # their explicit presets; persisted Attempts still use validate_binding.
    shared = ('capstone-research-bridge/1' in capability.get('research_bridge_schemas', ())
              and 'capstone-enterprise-graph/2' in capability.get('research_graph_schemas', ())
              and registered_research_policy('1.18.0').capability()
              in capability.get('research_policy_profiles', ()))
    selected = 'enterprise-research' if shared else session_type
    return executor_binding(SimpleNamespace(identity=binding['identity'], capability=binding['capability']),
                            session_type=selected)


def validate_binding(value: object) -> dict:
    if not isinstance(value, Mapping):
        raise ValueError('native conversation binding is invalid')
    governed = value.get('application_profile') in (
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
        {'profile_id': 'enterprise-research', 'profile_version': '1.18.0'})
    fields = {'schema', 'application_profile', 'binding_id', 'identity', 'capability'}
    if governed:
        fields.add('pack_bindings')
    if (set(value) != fields
            or value['schema'] != 'capstone-native-conversation/1'
            or value['application_profile'] not in (
                {'profile_id': 'enterprise-research', 'profile_version': '1.0.0'},
                {'profile_id': 'general-chat', 'profile_version': '1.0.0'},
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
        {'profile_id': 'enterprise-research', 'profile_version': '1.18.0'})
            or value['binding_id'] != ('research-methods' if governed
                                        else 'native-conversation')):
        raise ValueError('native conversation binding is invalid')
    from types import SimpleNamespace
    from .native_task_context import research_policy_for_binding
    entry = research_policy_for_binding(value) if governed else None
    checked = executor_binding(SimpleNamespace(identity=value['identity'], capability=value['capability']),
                               session_type=value['application_profile']['profile_id'],
                               profile_version=value['application_profile']['profile_version'],
                               _policy_variant=entry.variant if entry else 'default')
    if checked != value:
        raise ValueError('native conversation binding is inconsistent')
    return json.loads(json.dumps(checked))


class NativeResearchRuntime:
    """Bind the existing ordinary runtime to the same durable Work research."""
    def __init__(self, runtime, claim, root, *, governed=False):
        from .attempt_research import AttemptResearch
        self._runtime, self._claim = runtime, claim
        self._completed = False
        self._governed = governed
        allowed_refs = set()
        if governed:
            resources = claim.turn_plan.intent_resources
            allowed_refs.update('material:' + item['material_id'] + ':' + item['sha256']
                for item in resources['native_context'].get('materials', ()))
            allowed_refs.update(f"resource:{item['resource_id']}:{item['version']}:{item['sha256']}"
                for item in resources['native_context'].get('resource_manifests', ()))
        self._research = AttemptResearch(root, thread_id=claim.thread_id, run_id=claim.run_id,
            attempt_id=claim.attempt.attempt_id, task_context=claim.task_context,
            is_active=lambda: False, admit_reference=lambda ref: ref in allowed_refs)
        if governed:
            from hashlib import sha256
            from .native_research_bridge import WorkerResearchBridge, SourceReceiptCache, read_json
            state = self._research.controller.read()
            referenced = set() if state is None else set(state.condition_refs)
            if state is not None:
                for record in (*state.claims, *state.notes):
                    referenced.update(record.refs)
            cache = SourceReceiptCache(self._research.store.workspace.core_path / 'native-source-receipts.json',
                {'thread_id': claim.thread_id, 'work_id': claim.task_context.binding.work_id,
                 'research_id': self._research.research_id}, referenced=referenced)
            allowed_refs.update(cache.records)
            def admit_sources(records):
                cache.accept(records)
                allowed_refs.update(record['source_ref'] for record in records)
            parent = claim.turn_plan.intent_resources['general_executor']['original_attempt_id']
            binding = read_json(self._research.channel.root / 'binding.json')
            binding.update(attempt_id=parent, turn_id='turn-' + sha256(
                json.dumps((claim.thread_id, claim.run_id, parent)).encode()).hexdigest()[:48])
            if claim.task_context is not None:
                binding['cycle_owner'] = {**claim.task_context.binding.to_document(),
                                          'goal_revision': claim.task_context.goal_revision}
            if claim.turn_plan.intent_resources['general_executor'].get('application_profile') in (
                    {'profile_id': 'enterprise-research', 'profile_version': '1.10.0'},
                    {'profile_id': 'enterprise-research', 'profile_version': '1.11.0'},
                    {'profile_id': 'enterprise-research', 'profile_version': '1.12.0'},
        {'profile_id': 'enterprise-research', 'profile_version': '1.13.0'},
        {'profile_id': 'enterprise-research', 'profile_version': '1.14.0'},
        {'profile_id': 'enterprise-research', 'profile_version': '1.15.0'},
        {'profile_id': 'enterprise-research', 'profile_version': '1.16.0'},
        {'profile_id': 'enterprise-research', 'profile_version': '1.17.0'},
        {'profile_id': 'enterprise-research', 'profile_version': '1.18.0'}):
                binding['graph_schema'] = 'capstone-enterprise-graph/2'
                if claim.turn_plan.intent_resources['general_executor']['application_profile']['profile_version'] in {'1.12.0', '1.13.0', '1.14.0', '1.15.0', '1.16.0', '1.17.0', '1.18.0'}:
                    binding['graph_work_edition'] = 'capstone-graph-work/1'
            self._bridge = WorkerResearchBridge(self._research.channel,
                owner_id=sha256(claim.lease_token.encode()).hexdigest(), producer_binding=binding,
                admit_sources=admit_sources)
            runtime.bind_research(self._bridge)

    def __getattr__(self, name):
        return getattr(self._runtime, name)

    def bind_attempt_guard(self, check, terminal_phase=None):
        self._check = check
        self._research.bind_active_check(check, terminal_phase)

    def start(self):
        return self._runtime.start()

    def prompt(self, question, *, on_event, correlation_id=None, on_heartbeat=None):
        if not self._check():
            raise InterruptedError('native conversation cancelled')
        if self._governed:
            self._bridge.on_commit = lambda: on_event({'event_type': 'research_state_updated',
                'runtime_mode': self._runtime.runtime_mode, 'visibility': 'public',
                'payload': self._research.current_projection()})
        answer = self._runtime.prompt(question, correlation_id=correlation_id,
                                      on_event=on_event, on_heartbeat=on_heartbeat)
        if not self._check():
            raise InterruptedError('native conversation cancelled')
        if self._governed:
            self._completed = True
            return answer
        state = self._research.controller.read()
        from .application_capacity import limits
        notes = [] if state is None else [note.model_dump(mode='json') for note in state.notes][-(limits.research_note_count - 1):]
        note_limit = limits.research_text_chars
        note_prefix = 'Assistant reply excerpt (general knowledge; full reply is in the Attempt record):\n'
        notes.append({'note_id': self._claim.attempt.attempt_id,
            'text': note_prefix + answer[:note_limit - len(note_prefix)],
            'refs': []})
        goal = question if state is None else state.goal
        goal_limit = limits.research_goal_chars
        if len(goal) > goal_limit:
            goal_prefix = 'Task request excerpt (full request is in the Attempt record):\n'
            goal = goal_prefix + goal[:goal_limit - len(goal_prefix)]
        self._research.controller.update({'request_id': self._claim.attempt.attempt_id,
            'expected_revision': 0 if state is None else state.revision,
            'changes': {'goal': goal, 'notes': notes}})
        projection = self._research.current_projection()
        on_event({'event_type': 'research_state_updated', 'runtime_mode': self._runtime.runtime_mode,
                  'visibility': 'public', 'payload': projection})
        self._completed = True
        return answer

    def stop(self):
        try:
            self._runtime.stop()
        finally:
            self._research.close(failed=not self._completed)
