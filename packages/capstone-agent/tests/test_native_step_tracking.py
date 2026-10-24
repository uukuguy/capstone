from capstone_agent.task_steps import NativeStepTracker


def test_native_steps_share_runtime_tracker_and_bind_work_records():
    tracker = NativeStepTracker(prefix='native-task')
    start = tracker.annotate({'type': 'runtime_action', 'phase': 'started'})
    tracker.annotate({'type': 'runtime_action', 'phase': 'response_completed', 'response_kind': 'tools'})
    tool = tracker.annotate({'type': 'tool_execution_start', 'tool_name': 'bash', 'tool_call_id': 'read'})
    progress = tracker.annotate({'type': 'tool_execution_end', 'tool_name': 'agent_task_progress',
        'tool_call_id': 'purpose', 'is_error': False, 'task_progress': {
            'kind': 'goal', 'purpose': '检查资料覆盖和缺失', 'text': '核对上传数据', 'refs': []}})
    assert tool['task_step_id'] == start['task_step']['id']
    assert progress['task_step']['title'] == '检查资料覆盖和缺失'
    assert progress['runtime_step_tracking'] is True
    tracker.annotate({'type': 'tool_execution_end', 'tool_name': 'bash', 'tool_call_id': 'read', 'is_error': True})
    tracker.annotate({'type': 'runtime_action', 'phase': 'completed'})
    following = tracker.annotate({'type': 'runtime_action', 'phase': 'started'})
    assert following['task_step']['after_failed_steps'] == [start['task_step']['id']]
    assert following['task_step']['id'] != start['task_step']['id']


def test_native_failed_progress_does_not_rename_step():
    tracker = NativeStepTracker(prefix='native-task')
    tracker.annotate({'type': 'runtime_action', 'phase': 'started'})
    failed = tracker.annotate({'type': 'tool_execution_end', 'tool_name': 'agent_task_progress',
        'tool_call_id': 'bad', 'is_error': True, 'task_progress': {
            'kind': 'goal', 'purpose': '未成功记录的目的', 'text': '不采用', 'refs': []}})
    assert failed.get('task_step', {}).get('title') != '未成功记录的目的'
def test_research_objective_spans_model_turns_and_multiple_tools():
    from capstone_agent.task_steps import NativeStepTracker
    tracker = NativeStepTracker(prefix='research-task', objective_steps=True)
    assert 'task_step' not in tracker.annotate({'type':'runtime_action','phase':'started'})
    start = tracker.annotate({'type':'tool_execution_start','tool_name':'agent_task_progress',
        'tool_call_id':'begin','args':{'kind':'goal','text':'检查来源并核对统计口径',
        'step_id':'source-check','phase':'started'}})
    assert start['task_step']['id'] == 'research-task.source-check'
    for index in range(3):
        tracker.annotate({'type':'runtime_action','phase':'started'})
        child = tracker.annotate({'type':'tool_execution_start','tool_name':'read','tool_call_id':str(index)})
        assert child['task_step_id'] == 'research-task.source-check'
        tracker.annotate({'type':'tool_execution_end','tool_name':'read','tool_call_id':str(index),'is_error':False})
        assert 'task_step' not in tracker.annotate({'type':'runtime_action','phase':'completed'})
    end = tracker.annotate({'type':'tool_execution_end','tool_name':'agent_task_progress',
        'tool_call_id':'end','is_error':False,'task_progress':{'kind':'observation',
        'text':'来源与口径核对结束','step_id':'source-check','phase':'completed'}})
    assert end['task_step']['status'] == 'completed'
    assert len(tracker.tracker.steps) == 1

