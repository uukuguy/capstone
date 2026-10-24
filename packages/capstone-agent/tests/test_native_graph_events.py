"""Private graph frames retain the exact committed execution owner."""
from copy import deepcopy

import pytest


def fixture():
    from capstone_agent.native_graph_events import NativeGraphEvents
    owner = {'thread_id': 't', 'work_id': 'w', 'research_id': 'r', 'goal_revision': 1}
    action = {'id': 'execute:abc', 'owner': owner, 'attempt_id': 'attempt',
              'step_id': 'A', 'kind': 'execute', 'execution_revision': 1}
    progress = {'type': 'enterprise_graph_progress', 'owner': owner,
                'attempt_id': 'attempt', 'task_id': 'task',
                'checkpoint': {'ref': 'checkpoint', 'revision': 1},
                'graph': {'nodes': [{'id': 'A', 'execution': 'delegated'}], 'actions': [action]}}
    guard = NativeGraphEvents(owner=owner, attempt_id='attempt', task_id='task')
    guard.admit_progress(progress)
    base = {key: progress[key] for key in ('owner', 'attempt_id', 'task_id', 'checkpoint')}
    base.update(action_id=action['id'], step_id='A')
    return guard, base


def test_binding_requires_exact_checkpoint_and_never_rebinds_a_call():
    guard, base = fixture()
    binding = {**base, 'type': 'enterprise_graph_tool_binding',
               'tool_call_id': 'call', 'tool_name': 'read'}
    assert guard.admit(binding) == binding
    assert guard.action_for_call('call', 'read') == 'execute:abc'
    for change in ({'step_id': 'B'}, {'attempt_id': 'foreign'},
                   {'checkpoint': {'ref': 'missing', 'revision': 1}},
                   {'tool_name': 'bash'}):
        with pytest.raises(ValueError):
            guard.admit({**binding, **change})


def test_child_public_projection_drops_private_native_results():
    guard, base = fixture()
    guard.admit({**base, 'type': 'enterprise_graph_child_started', 'child_id': 'A'})
    guard.admit({**base, 'type': 'enterprise_graph_tool_binding',
                 'tool_call_id': 'call', 'tool_name': 'read'})
    event = {**base, 'type': 'enterprise_graph_child_tool', 'child_id': 'A',
             'tool_call_id': 'call', 'tool_name': 'read', 'activity': 'end',
             'result': {'private': '/private/data'}, 'args': {'secret': 'value'}, 'is_error': False}
    public = guard.admit(event)
    assert 'result' not in public and 'args' not in public
    assert public['tool_call_id'] == 'call'
    changed = deepcopy(event)
    changed['child_id'] = 'B'
    with pytest.raises(ValueError): guard.admit(changed)


@pytest.mark.parametrize('duration', [0, 2710.25])
def test_child_tool_preserves_native_execution_duration(duration):
    guard, base = fixture()
    guard.admit({**base, 'type': 'enterprise_graph_child_started', 'child_id': 'A'})
    guard.admit({**base, 'type': 'enterprise_graph_tool_binding', 'tool_call_id': 'call', 'tool_name': 'bash'})
    event = {**base, 'type': 'enterprise_graph_child_tool', 'child_id': 'A',
             'tool_call_id': 'call', 'tool_name': 'bash', 'activity': 'end', 'execution_ms': duration}
    assert guard.admit(event)['execution_ms'] == duration


@pytest.mark.parametrize('duration', [-1, float('inf'), True, '12'])
def test_child_tool_rejects_invalid_native_execution_duration(duration):
    guard, base = fixture()
    guard.admit({**base, 'type': 'enterprise_graph_child_started', 'child_id': 'A'})
    guard.admit({**base, 'type': 'enterprise_graph_tool_binding', 'tool_call_id': 'call', 'tool_name': 'bash'})
    with pytest.raises(ValueError):
        guard.admit({**base, 'type': 'enterprise_graph_child_tool', 'child_id': 'A',
                     'tool_call_id': 'call', 'tool_name': 'bash', 'activity': 'end', 'execution_ms': duration})


def test_tool_failure_requires_exact_existing_binding_and_immutable_status():
    guard, base = fixture()
    binding = {**base, 'type': 'enterprise_graph_tool_binding', 'tool_call_id': 'call', 'tool_name': 'read'}
    failure = {**binding, 'type': 'enterprise_graph_tool_failure', 'status': 'cancelled'}
    with pytest.raises(ValueError): guard.admit(failure)
    assert guard.action_for_call('unknown', 'read', required=False) is None
    guard.admit(binding)
    assert guard.admit(failure) == failure
    assert guard.admit(failure) == failure
    assert guard.failures == {'call': 'cancelled'}
    for change in ({'status': 'completed'}, {'status': 'failed'}, {'tool_name': 'bash'},
                   {'checkpoint': {'ref': 'other', 'revision': 1}}):
        with pytest.raises(ValueError): guard.admit({**failure, **change})


def test_old_action_events_keep_the_original_checkpoint_after_sibling_progress():
    guard, base = fixture()
    guard.admit({**base, 'type': 'enterprise_graph_child_started', 'child_id': 'A'})
    guard.admit_progress({'checkpoint': {'ref': 'next', 'revision': 2},
                         'graph': {'nodes': [], 'actions': []}})
    event = {**base, 'type': 'enterprise_graph_child_finished', 'child_id': 'A',
             'status': 'completed', 'result_summary': 'Native execution returned.'}
    assert guard.admit(event)['action_id'] == base['action_id']
    assert 'model_responses' not in guard.admit(event)
    with pytest.raises(ValueError): guard.admit({**event, 'status': 'failed'})


def test_graph_child_usage_counts_once_and_missing_receipt_stays_unknown():
    from capstone_agent.general_pi_executor import _NativeUsage
    usage = _NativeUsage()
    started = {'type': 'enterprise_graph_child_started', 'action_id': 'execute:A'}
    usage.observe(started)
    assert usage.summary()['child_model_responses'] is None
    finished = {**started, 'type': 'enterprise_graph_child_finished', 'status': 'completed',
                'usage': [{'input': 7, 'output': 3, 'cost': None}], 'model_responses': 1, 'turns': 1}
    usage.observe(finished)
    usage.observe(finished)
    assert usage.summary()['child_input'] == 7
    assert usage.summary()['child_model_responses'] == 1
    usage.observe({'type': 'enterprise_graph_child_started', 'action_id': 'execute:B'})
    assert usage.summary()['child_input'] is None


def test_model_round_preserves_start_and_exact_multiple_tool_associations():
    guard, base = fixture()
    child = {**base, 'child_id': 'A'}
    guard.admit({**child, 'type': 'enterprise_graph_child_started'})
    started = {**child, 'type': 'enterprise_graph_child_response_started', 'response_number': 1}
    assert guard.admit(started) == started
    response = {**child, 'type': 'enterprise_graph_child_response', 'response_number': 1,
                'response_ms': 12, 'tool_call_ids': ['call:one', 'call:two'], 'stop_reason': 'toolUse',
                'tool_requests': [{'id': 'call:one', 'name': 'read'}, {'id': 'call:two', 'name': 'bash', 'operation': 'python analyze.py'}],
                'response_text': 'Inspect supplied files.'}
    assert guard.admit(response) == response
    assert guard.admit({**response, 'response_number': 2, 'tool_call_ids': [], 'tool_requests': [], 'stop_reason': 'stop'})['tool_call_ids'] == []
    for ids in [['duplicate', 'duplicate'], ['x' * 129], [None], 'not-a-list']:
        with pytest.raises(ValueError):
            guard.admit({**response, 'response_number': 3, 'tool_call_ids': ids})


def test_unknown_pricing_is_valid_public_usage():
    guard, base = fixture()
    guard.admit({**base, 'type': 'enterprise_graph_child_started', 'child_id': 'A'})
    event = {**base, 'type': 'enterprise_graph_child_response', 'child_id': 'A',
             'response_number': 1, 'response_ms': 12, 'usage': {'input': 7, 'cost': None}}
    assert guard.admit(event)['usage']['cost'] is None


def test_private_graph_handles_do_not_enter_public_activity():
    from capstone_agent.native_graph_events import public_graph_activity
    root = '/var/lib/general-pi/tasks/.contexts/task'
    activity = {'operation': f"python -c read('{root}/results/abc')",
                'output_excerpt': f'Loaded {root}/observations/def', 'other': 'ignored'}
    public = public_graph_activity(activity, (root,))
    assert set(public) == {'operation', 'output_excerpt'}
    assert '.contexts' not in str(public) and root not in str(public)
    assert 'results/abc' not in str(public) and 'observations/def' not in str(public)
    assert 'python -c' in public['operation']


def test_private_handle_filter_runs_before_activity_clipping():
    from capstone_agent.native_graph_events import project_graph_tool_activity
    root = '/var/lib/general-pi/tasks/.contexts/task'
    event = {'args': {'command': 'x' * 220 + ' ' + root + '/results/abc'},
             'result': {'content': [{'type': 'text', 'text': 'x' * 590 + ' ' + root + '/results/abc'}]}}
    public = project_graph_tool_activity(event, (root,))
    assert '/var' not in public['operation'] and '.contexts' not in str(public)
    assert '/var' not in public['output_excerpt']


@pytest.mark.parametrize('binary', ['PAR1\x00\x01payload', 'plain\x00text', '\x02not-text', 'x' * 600 + '\x00'])
def test_graph_public_nontext_preview_is_fixed_bounded_and_idempotent(binary):
    from capstone_agent.native_graph_events import public_graph_activity, project_graph_tool_activity
    from hashlib import sha256
    import json
    event = {'args': {'command': 'inspect\x00file'},
             'result': {'content': [{'type': 'text', 'text': binary}]}, 'is_error': False}
    original = json.dumps(event, ensure_ascii=False).encode()
    expected = '非文本工具输出，预览已省略。'
    assert public_graph_activity({'output_excerpt': binary}) == {'output_excerpt': expected}
    public = project_graph_tool_activity(event)
    if '\x00' in binary[:600] or binary.startswith('\x02'):
        assert public['output_excerpt'] == expected
    assert '\x00' not in public['operation'] and '\\u0000' in public['operation']
    assert public_graph_activity(public) == public
    assert sha256(json.dumps(event, ensure_ascii=False).encode()).digest() == sha256(original).digest()


def test_child_preview_filters_binary_but_keeps_success_identity_and_raw_result():
    guard, base = fixture()
    guard.admit({**base, 'type': 'enterprise_graph_child_started', 'child_id': 'A'})
    guard.admit({**base, 'type': 'enterprise_graph_tool_binding', 'tool_call_id': 'call', 'tool_name': 'bash'})
    event = {**base, 'type': 'enterprise_graph_child_tool', 'child_id': 'A', 'activity': 'end',
             'tool_call_id': 'call', 'tool_name': 'bash', 'is_error': False,
             'result': {'content': [{'type': 'text', 'text': 'PAR1\x00binary'}]}}
    original = deepcopy(event)
    public = guard.admit(event)
    assert public['tool_activity']['output_excerpt'] == '非文本工具输出，预览已省略。'
    assert public['is_error'] is False and public['action_id'] == base['action_id']
    assert event == original


def test_public_text_and_existing_ansi_whitespace_semantics_stay_unchanged():
    from capstone_agent.native_graph_events import public_graph_activity, project_graph_tool_activity
    from capstone_agent.progress import project_native_tool_activity
    text = '中文 **结果**\n第二行\t值\r\n\x1b[32mOK\x1b[0m'
    assert public_graph_activity({'operation': text, 'output_excerpt': text}) == {'operation': text, 'output_excerpt': text}
    event = {'args': {'command': text}, 'result': {'content': [{'type': 'text', 'text': text}]}}
    assert project_graph_tool_activity(event) == project_native_tool_activity(event)
    public = public_graph_activity({'operation': '\x00' * 240})
    assert '\x00' not in public['operation'] and len(public['operation']) <= 241


def test_binary_preview_does_not_bypass_native_frame_capacity(monkeypatch):
    from capstone_agent import application_capacity as capacity
    guard, base = fixture()
    guard.admit({**base, 'type': 'enterprise_graph_child_started', 'child_id': 'A'})
    guard.admit({**base, 'type': 'enterprise_graph_tool_binding', 'tool_call_id': 'call', 'tool_name': 'bash'})
    monkeypatch.setattr(capacity, '_current', capacity._profile({'event_bytes': 1024}))
    event = {**base, 'type': 'enterprise_graph_child_tool', 'child_id': 'A', 'activity': 'end',
             'tool_call_id': 'call', 'tool_name': 'bash', 'is_error': False,
             'result': {'content': [{'type': 'text', 'text': '\x00' * 2048}]}}
    with pytest.raises(capacity.CapacityExceeded, match='graph_native_event'):
        guard.admit(event)
