"""Session presets select registered, consumed native policy bindings."""
from types import SimpleNamespace

import pytest

from capstone_agent.enterprise_application import resolve_native_profile
from capstone_agent.native_conversation import binding_for_session, executor_binding, validate_binding
from capstone_agent.native_task_context import checked_native_context, native_context_for
from test_enterprise_normal_chat import native_executor


def test_native_intent_policy_is_a_file_for_a_pack_manifest(tmp_path):
    from capstone_agent.native_hosted_worker import native_intent_policy_path
    profile = resolve_native_profile('enterprise-research', '1.20.0')
    assert not hasattr(profile.domains[0].profile.manifest, 'system_policy_path')
    path = native_intent_policy_path(profile, tmp_path)
    assert path.is_file()
    assert path.read_text(encoding='utf-8') == profile.application_policy.load()


def test_native_recognizer_binds_each_attempt_model_selection(tmp_path, monkeypatch):
    from pathlib import Path
    from capstone_agent import native_hosted_worker, runtime, pi_intent
    from capstone_agent.request_intent import IntentEngineIdentity
    from capstone_agent.workbench_llm_profiles import ProfileRegistry
    root = Path(__file__).resolve().parents[3]
    environment = {'CAPSTONE_RUNTIME_PROFILE': 'capstone-workbench-v1',
        'CAPSTONE_WORKBENCH_PRESET': 'intranet', 'CAPSTONE_PUBLIC_PROVIDER': 'openai-compatible'}
    monkeypatch.setattr(native_hosted_worker, 'application_root', lambda: root)
    monkeypatch.setattr(runtime, 'build_runtime_host', lambda *args, **kwargs: None)
    capabilities = []

    class Builder:
        def __init__(self, *, resolved_llm, **kwargs):
            capabilities.append(kwargs.get('model_reasoning'))
            self.identity = IntentEngineIdentity(engine='pi', model=resolved_llm.config.model,
                config_revision='sha256:' + 'a' * 64)
        def build_intent(self, request, control):
            raise AssertionError('test must not start a model request')

    monkeypatch.setattr(pi_intent, 'NativeConversationPiSessionBuilder', Builder)
    factory = native_hosted_worker.build_native_unscoped_recognizer(tmp_path, environment)
    registry = ProfileRegistry(environment=environment)
    qwen = registry.freeze('intranet-qwen-flash-next-8013')
    dsv4 = registry.freeze('intranet-dsv4-18804')
    assert factory.for_attempt(SimpleNamespace(submission={'llm_selection': qwen})).identity.model == 'Qwen3.8-Flash-Next'
    assert capabilities[-1] is None
    assert factory.for_attempt(SimpleNamespace(submission={'llm_selection': dsv4})).identity.model == 'dsv4'
    assert capabilities[-1] is True

    environment.update(CAPSTONE_RECOGNITION_PROVIDER='openai',
        CAPSTONE_RECOGNITION_MODEL='recognition-only',
        CAPSTONE_RECOGNITION_BASE_URL='http://127.0.0.1:19999/v1',
        CAPSTONE_RECOGNITION_API_KEY_ENV='RECOGNITION_TEST_KEY', RECOGNITION_TEST_KEY='test-only')
    override = native_hosted_worker.build_native_unscoped_recognizer(tmp_path, environment)
    assert override.for_attempt(SimpleNamespace(submission={'llm_selection': dsv4})).identity.model == 'recognition-only'
    assert capabilities[-1] is None


@pytest.mark.parametrize('profile,version,expected', [
    ('enterprise-research', '1.1.0', {'agent_research_cycle'}),
    ('enterprise-research', '1.2.0', {'agent_research_plan', 'agent_research_record', 'agent_research_assess'}),
    ('enterprise-research', '1.0.0', set()), ('general-chat', '1.0.0', set()),
    ('general-chat', '1.2.0', set()), ('unregistered', '1.2.0', set()),
])
def test_cycle_tools_follow_accepted_profile_version(profile, version, expected):
    from capstone_agent.native_research_bridge import CYCLE_CONTROL_TOOLS, research_tools_for_profile
    selected = set(research_tools_for_profile(profile, version))
    assert selected.intersection(CYCLE_CONTROL_TOOLS) == expected
    assert ('agent_delegate' in selected) == bool(expected)


@pytest.mark.parametrize('version,expected', [
    ('1.1.0', {'agent_research_cycle'}),
    ('1.2.0', {'agent_research_plan', 'agent_research_record', 'agent_research_assess'}),
])
def test_native_context_freezes_only_selected_cycle_interface(version, expected):
    from capstone_agent.native_research_bridge import CYCLE_CONTROL_TOOLS
    from test_research_policy_compatibility import registered_binding
    binding = registered_binding(version)
    claim = SimpleNamespace(submission=None, selected_task_reader=None)
    context = native_context_for(claim, binding)
    assert set(context['policy']['allowed_tools']).intersection(CYCLE_CONTROL_TOOLS) == expected
    assert context['policy']['external_lookup_enabled'] is False
    assert checked_native_context(context) == context


def test_native_context_accepts_inputs_plus_products_with_a_separate_count_bound():
    import base64
    from hashlib import sha256
    context = native_context_for(SimpleNamespace(submission=None, selected_task_reader=None),
        executor_binding(native_executor()))
    data = b'saved source'
    context['materials'] = [{'schema': 'capstone-thread-material/1',
        'material_id': 'material_' + f'{index:032x}', 'file_name': f'source-{index}.txt',
        'size_bytes': len(data), 'sha256': sha256(data).hexdigest(),
        'content_base64': base64.b64encode(data).decode()} for index in range(8)]
    assert len(checked_native_context(context)['materials']) == 8
    from capstone_agent.application_capacity import limits
    context['materials'] = context['materials'] * (limits.inline_material_count // 8 + 1)
    with pytest.raises(ValueError, match='count bounds'):
        checked_native_context(context)


@pytest.mark.parametrize('session_type', ['general-chat', 'enterprise-research'])
def test_native_session_profile_is_registered_frozen_and_consumed(session_type):
    original = executor_binding(native_executor())
    binding = binding_for_session(original, session_type)
    assert original['application_profile']['profile_id'] == 'enterprise-research'
    assert binding['application_profile'] == {'profile_id': session_type, 'profile_version': '1.0.0'}
    assert validate_binding(binding) == binding
    claim = SimpleNamespace(submission=None, selected_task_reader=None)
    context = native_context_for(claim, binding)
    assert context['policy']['system_policy'] == resolve_native_profile(session_type).application_policy.load()
    assert context['policy']['external_lookup_enabled'] is False
    assert checked_native_context(context) == context
    assert set(context['policy']['allowed_tools']) == {'read', 'bash', 'edit', 'write'}


def test_native_session_presets_have_distinct_consumed_policies_and_reject_unknown():
    assert resolve_native_profile('general-chat').application_policy.load() != resolve_native_profile('enterprise-research').application_policy.load()
    binding = executor_binding(native_executor())
    assert binding_for_session(binding, None) == binding
    with pytest.raises(ValueError):
        binding_for_session(binding, 'unregistered')
    with pytest.raises(ValueError):
        validate_binding({**binding, 'application_profile': {'profile_id': 'general-chat', 'profile_version': 'unknown'}})


def test_current_host_organization_is_available_across_native_session_presets():
    from copy import deepcopy
    from capstone_agent.native_task_context import research_policy_capabilities
    executor = native_executor()
    executor.capability.update({
        'research_bridge_schemas': ['capstone-research-bridge/1'],
        'delivery_review_schemas': ['capstone-delivery-review/1'],
        'research_graph_schemas': ['capstone-enterprise-graph/2'],
        'research_policy_profiles': research_policy_capabilities(),
    })
    original = executor_binding(executor)
    frozen = deepcopy(original)
    shared = binding_for_session(original, 'general-chat')
    assert shared == binding_for_session(original, 'enterprise-research')
    assert shared['application_profile'] == {'profile_id': 'enterprise-research', 'profile_version': '1.20.0'}
    assert validate_binding(shared) == shared
    assert original == frozen
    with pytest.raises(ValueError, match='not registered'):
        binding_for_session(original, 'unregistered')


def test_old_graph_publication_does_not_silently_upgrade_general_chat():
    from capstone_agent.native_task_context import registered_research_policy
    executor = native_executor()
    executor.capability.update({
        'research_bridge_schemas': ['capstone-research-bridge/1'],
        'research_graph_schemas': ['capstone-enterprise-graph/2'],
        'research_policy_profiles': [registered_research_policy('1.10.0').capability()],
    })
    original = executor_binding(executor)
    assert binding_for_session(original, 'general-chat')['application_profile'] == {
        'profile_id': 'general-chat', 'profile_version': '1.0.0'}


@pytest.mark.parametrize('operation', ['binding', 'general_resources'])
def test_native_capability_snapshot_is_read_once_and_refreshed_per_call(operation):
    from copy import deepcopy
    from capstone_agent.native_hosted_worker import native_runtime_factory
    source = native_executor()
    class CountedHost:
        identity = source.identity
        reads = 0
        @property
        def capability(self):
            self.reads += 1
            return source.capability
    host = CountedHost()
    def bind():
        if operation == 'binding':
            return executor_binding(host)['capability']
        claim = SimpleNamespace(model_context=None, submission=None,
            attempt=SimpleNamespace(attempt_id='test-capability-snapshot'))
        return native_runtime_factory(host)._general_resources(claim)['capability']
    first = bind()
    assert host.reads == 1
    original = deepcopy(first)
    source.capability['resource_profiles']['delegated_pi']['revision'] = 'd' * 64
    source.capability['data_gateway'] = {'diagnostic_revision': 'second-publication'}
    second = bind()
    assert host.reads == 2
    assert second['resource_profiles']['delegated_pi']['revision'] == 'd' * 64
    assert second['data_gateway']['diagnostic_revision'] == 'second-publication'
    second['resource_profiles']['delegated_pi']['revision'] = 'e' * 64
    assert source.capability['resource_profiles']['delegated_pi']['revision'] == 'd' * 64
    assert first == original
