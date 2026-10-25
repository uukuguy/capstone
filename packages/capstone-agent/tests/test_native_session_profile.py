"""Session presets select registered, consumed native policy bindings."""
from types import SimpleNamespace

import pytest

from capstone_agent.enterprise_application import resolve_native_profile
from capstone_agent.native_conversation import binding_for_session, executor_binding, validate_binding
from capstone_agent.native_task_context import checked_native_context, native_context_for
from test_enterprise_normal_chat import native_executor


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
    assert shared['application_profile'] == {'profile_id': 'enterprise-research', 'profile_version': '1.18.0'}
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
