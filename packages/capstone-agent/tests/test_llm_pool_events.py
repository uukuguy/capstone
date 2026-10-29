"""Public pool events are bounded host-bound observations, never research results."""
from copy import deepcopy

import pytest

from capstone_agent.general_pi_server import _checked_llm_pool_call
from capstone_agent.general_pi_executor import _NativeUsage
from capstone_agent.native_llm_pool import LLM_CALL_POOL_POLICY


def event(status='queued', **fields):
    return {'type': 'llm_pool_call', 'schema': LLM_CALL_POOL_POLICY['schema'],
            'parent_tool_call_id': 'submit-a', 'child_id': 'a', 'title': 'Check totals',
            'status': status, 'queued_at_ms': 100, **fields}


def setup():
    return ({'llm_call_pool': deepcopy(LLM_CALL_POOL_POLICY),
             'policy': {'allowed_tools': ['agent_llm_submit']}},
            {'llm_call_pool': deepcopy(LLM_CALL_POOL_POLICY)},
            {'llm_pool_submit_calls': {'submit-a'}, 'llm_pool_bindings': {}})


def test_bound_lifecycle_response_repeats_terminal_replay_and_whitelist():
    native, capability, record = setup()
    assert _checked_llm_pool_call(event(), native, capability, record) == event()
    running = event('running', started_at_ms=110)
    _checked_llm_pool_call(running, native, capability, record)
    response = {**running, 'response_number': 1, 'response_ms': 23}
    _checked_llm_pool_call(response, native, capability, record)
    terminal = event('completed', started_at_ms=110, finished_at_ms=140,
                     usage=[{'input': 2, 'output': 3, 'cacheRead': 0, 'cacheWrite': 0, 'totalTokens': 5}],
                     model_responses=1, turns=1)
    assert _checked_llm_pool_call(terminal, native, capability, record) == terminal
    assert _checked_llm_pool_call(terminal, native, capability, record) == terminal
    for changed in [{**terminal, 'turns': 2}, running, {**terminal, 'title': 'Other'}]:
        with pytest.raises(ValueError):
            _checked_llm_pool_call(changed, native, capability, record)


@pytest.mark.parametrize('change', ['native', 'capability', 'grant', 'parent'])
def test_requires_exact_double_publication_grant_and_observed_submit(change):
    native, capability, record = setup()
    if change == 'native': native['llm_call_pool']['concurrency'] = 2.0
    if change == 'capability': capability['llm_call_pool'] = {}
    if change == 'grant': native['policy']['allowed_tools'] = []
    if change == 'parent': record['llm_pool_submit_calls'] = set()
    with pytest.raises(ValueError):
        _checked_llm_pool_call(event(), native, capability, record)
    assert not record['llm_pool_bindings']


@pytest.mark.parametrize('fields', [
    {'title': 'x' * 121}, {'queued_at_ms': True}, {'status': 'invented'},
    {'usage': [{'input': -1}]}, {'usage': [{'input': '2'}]}, {'input': 'private prompt'},
    {'answer': 'must not publish'}, {'response_ms': float('inf')}, {'finished_at_ms': 99},
])
def test_rejects_unbounded_private_and_malformed_payloads(fields):
    with pytest.raises(ValueError):
        _checked_llm_pool_call(event(**fields), *setup())


def test_child_identity_cannot_move_parent_or_reset_queued_origin():
    native, capability, record = setup()
    _checked_llm_pool_call(event(), native, capability, record)
    record['llm_pool_submit_calls'].add('submit-b')
    for fields in [{'parent_tool_call_id': 'submit-b'}, {'queued_at_ms': 101}, {'title': 'Other'}]:
        with pytest.raises(ValueError):
            _checked_llm_pool_call(event(**fields), native, capability, record)


def test_usage_cannot_precede_completion_and_cancellation_reason_remains_bound():
    native, capability, record = setup()
    with pytest.raises(ValueError):
        _checked_llm_pool_call(event(usage=[{'input': 1}]), native, capability, record)
    _checked_llm_pool_call(event(), native, capability, record)
    _checked_llm_pool_call(event('running', started_at_ms=110), native, capability, record)
    _checked_llm_pool_call(event('cancelling', started_at_ms=110, cancel_reason='timeout'), native, capability, record)
    with pytest.raises(ValueError):
        _checked_llm_pool_call(event('cancelled', started_at_ms=110, finished_at_ms=140,
            cancel_reason='cancelled'), native, capability, record)


def test_usage_counts_actual_pool_children_once_and_preserves_missing_observations():
    usage = _NativeUsage()
    usage.observe(event('running', started_at_ms=110))
    assert usage.summary()['child_model_responses'] is None
    result = event('completed', started_at_ms=110, finished_at_ms=140,
        usage=[{'input': 2, 'output': 3, 'cacheRead': 0, 'cacheWrite': 0, 'totalTokens': 5}], model_responses=1, turns=1)
    usage.observe(result);usage.observe(result)
    summary = usage.summary()
    assert summary['child_model_responses'] == 1
    assert summary['child_input'] == 2
    assert summary['child_totalTokens'] == 5
    usage.observe(event('running', child_id='b', started_at_ms=150))
    assert usage.summary()['child_input'] is None


def test_not_started_cancellation_is_zero_work_but_missing_running_usage_is_unknown():
    usage = _NativeUsage()
    usage.observe(event('cancelled', finished_at_ms=110))
    assert usage.summary()['child_input'] == 0
    assert usage.summary()['child_model_responses'] == 0
    usage.observe(event('failed', child_id='b', started_at_ms=110, finished_at_ms=150))
    assert usage.summary()['child_input'] is None


def test_actual_host_admits_only_observed_submit_and_publishes_typed_payload(tmp_path):
    import time
    from capstone_agent.business_context import BusinessContext
    from capstone_agent.general_pi_server import GeneralPiHost
    from capstone_agent.pi_delegation import PiTaskRequest
    from capstone_agent.native_task_context import GENERAL_CHAT_POLICY_TEXT
    native = {'policy': {'schema': 'capstone-conversation-policy/1',
        'system_policy': GENERAL_CHAT_POLICY_TEXT, 'allowed_tools': ['agent_llm_submit'],
        'external_lookup_enabled': False}, 'selected_task_records': [], 'selected_task_source': None,
        'records_truncated': False, 'llm_call_pool': deepcopy(LLM_CALL_POOL_POLICY), 'deep_research': False}
    def run(request, cancelled, emit):
        emit({'type': 'tool_execution_start', 'toolName': 'agent_llm_submit', 'toolCallId': 'submit-a'})
        emit(event())
        emit(event('running', started_at_ms=110))
        emit(event('completed', started_at_ms=110, finished_at_ms=140))
        return 'Useful answer', {}
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=run)
    host.capability.update(llm_call_pool=deepcopy(LLM_CALL_POOL_POLICY), native_tools=['agent_llm_submit'])
    request = PiTaskRequest('pool-events', 'attempt-a', 'direct', 'Explain', (), (), host.identity, 2,
        business_context=BusinessContext.empty('workspace', 0),
        resource_profile={'profile_id': 'direct_pi', 'revision': 'test'},
        input={'kind': 'text', 'text': 'Explain'}, native_context=native)
    host.submit(request)
    deadline = time.monotonic() + 2
    while host.read(request.task_id)['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(.005)
    result = host.read(request.task_id)
    assert result['status'] == 'completed'
    calls = [row['llm_pool_call'] for row in result['events'] if 'llm_pool_call' in row]
    assert [row['status'] for row in calls] == ['queued', 'running', 'completed']
    assert all('research_branch' not in row for row in result['events'])


def test_process_forwards_pool_frames_and_accounts_actual_usage_without_child_answer(tmp_path):
    import json
    import sys
    from capstone_agent.general_pi_executor import GeneralPiProcess
    running = event('running', started_at_ms=110)
    terminal = event('completed', started_at_ms=110, finished_at_ms=140,
        usage=[{'input': 2, 'output': 3, 'cacheRead': 0, 'cacheWrite': 0, 'totalTokens': 5}],
        model_responses=1, turns=1)
    frames = [event(), running, terminal, terminal, {'type': 'agent_end', 'messages': [
        {'role': 'assistant', 'stopReason': 'stop', 'content': [{'type': 'text', 'text': 'Parent answer'}]}]}]
    script = tmp_path / 'pool_frames.py'
    script.write_text('import sys\nsys.stdin.readline()\n' + '\n'.join(
        'print(' + repr(json.dumps(frame)) + ',flush=True)' for frame in frames))
    process = GeneralPiProcess((sys.executable, str(script)), {'PATH': '/usr/bin'}, tmp_path)
    received = []
    assert process.run('task', timeout=5, cancelled=lambda: False, on_event=received.append) == 'Parent answer'
    assert [row for row in received if row['type'] == 'llm_pool_call'] == frames[:-1]
    assert process.usage['child_input'] == 2
    assert process.usage['child_model_responses'] == 1
