"""Text-only call pools require an exact application-selected publication."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from capstone_agent.native_conversation import binding_for_session, executor_binding, validate_binding
from capstone_agent.native_task_context import checked_native_context, native_context_for
from test_enterprise_normal_chat import native_executor


POLICY = {'schema': 'capstone-llm-call-pool/1', 'concurrency': 2, 'max_jobs': 12,
          'max_input_chars': 16000, 'max_output_chars': 8000,
          'call_timeout_ms': 120000, 'max_wait_ms': 30000}
TOOLS = {'agent_llm_submit', 'agent_llm_collect', 'agent_llm_cancel'}


def binding(profile='enterprise-research', publication=True):
    executor = native_executor()
    if publication:
        executor.capability = {**executor.capability, 'llm_call_pool': deepcopy(POLICY)}
    return binding_for_session(executor_binding(executor), profile)


def context(selected, choice=False):
    return native_context_for(SimpleNamespace(submission={} if choice is None else {'deep_research': choice},
        selected_task_reader=None), selected)


def test_actual_binding_admits_exact_lightweight_pool_without_extra_execution_grants():
    selected = binding()
    assert validate_binding(selected) == selected
    native = context(selected)
    assert native['llm_call_pool'] == POLICY
    assert set(native['policy']['allowed_tools']) == {'read', 'bash', 'edit', 'write'} | TOOLS
    assert checked_native_context(native) == native


@pytest.mark.parametrize('profile,publication,choice', [
    ('enterprise-research', True, True), ('enterprise-research', True, None),
    ('enterprise-research', False, False), ('general-chat', True, False),
])
def test_pool_is_absent_without_explicit_lightweight_application_selection(profile, publication, choice):
    native = context(binding(profile, publication), choice)
    assert 'llm_call_pool' not in native
    assert not TOOLS.intersection(native['policy']['allowed_tools'])


@pytest.mark.parametrize('mutate', [
    lambda policy: policy.update(concurrency=3), lambda policy: policy.update(concurrency=2.0),
    lambda policy: policy.update(max_jobs=True), lambda policy: policy.update(extra='not-registered'),
    lambda policy: policy.pop('max_wait_ms'),
])
def test_modified_publication_never_activates_pool(mutate):
    selected = binding()
    mutate(selected['capability']['llm_call_pool'])
    native = context(selected)
    assert 'llm_call_pool' not in native
    assert not TOOLS.intersection(native['policy']['allowed_tools'])


@pytest.mark.parametrize('tool', sorted(TOOLS))
def test_tool_grant_without_exact_policy_fails_closed(tool):
    native = context(binding(publication=False))
    native['policy']['allowed_tools'].append(tool)
    with pytest.raises(ValueError, match='pool policy'):
        checked_native_context(native)
    native['llm_call_pool'] = {**POLICY, 'max_wait_ms': 30001}
    with pytest.raises(ValueError, match='pool policy'):
        checked_native_context(native)


def test_registered_policy_and_resource_are_one_exact_contract():
    from capstone_agent.native_llm_pool import LLM_CALL_POOL_POLICY, LLM_CALL_POOL_TOOLS
    assert LLM_CALL_POOL_POLICY == POLICY
    assert set(LLM_CALL_POOL_TOOLS) == TOOLS
    native = context(binding(publication=False))
    native['llm_call_pool'] = deepcopy(POLICY)
    assert checked_native_context(native) == native
    native['llm_call_pool']['concurrency'] = 2.0
    with pytest.raises(ValueError, match='pool policy'):
        checked_native_context(native)
