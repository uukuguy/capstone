"""Session presets select registered, consumed native policy bindings."""
from types import SimpleNamespace

import pytest

from capstone_agent.enterprise_application import resolve_native_profile
from capstone_agent.native_conversation import binding_for_session, executor_binding, validate_binding
from capstone_agent.native_task_context import checked_native_context, native_context_for
from test_enterprise_normal_chat import native_executor


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
