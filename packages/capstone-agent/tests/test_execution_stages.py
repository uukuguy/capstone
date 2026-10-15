from capstone_agent.execution_stages import ExecutionStages


def action(phase, status='running', identity='runtime-1'):
    return {'event_type': 'runtime_action', 'runtime_mode': 'capstone', 'visibility': 'public',
        'payload': {'phase': phase, 'task_step': {'id': identity, 'number': 1,
            'title': '检查条件', 'status': status}}}


def test_stages_cover_preparation_execution_transition_and_finalization():
    now = [0.0]
    stages = ExecutionStages(preparation_seconds=4, clock=lambda: now[0])
    now[0] = 3
    first = stages.annotate(action('started'))
    assert first['payload']['task_steps'][0]['duration_ms'] == 7000
    assert first['payload']['task_step']['number'] == 2
    now[0] = 6
    stages.annotate(action('completed', 'completed'))
    now[0] = 6.1
    closing = stages.begin_finalization()
    assert closing['payload']['task_steps'][0]['duration_ms'] == 3100
    now[0] = 8
    final = stages.finish()
    assert final[0]['duration_ms'] == 1900
    assert sum(step['duration_ms'] for step in stages.steps.values()) == 12000


def test_host_numbers_tool_parent_and_preserves_response_time():
    stages = ExecutionStages(preparation_seconds=0)
    stages.annotate(action('started'))
    event = {'event_type': 'tool_completed', 'runtime_mode': 'capstone', 'payload': {
        'task_step_id': 'runtime-1', 'task_step_number': 1, 'step_tool_number': 2,
        'task_step': {'id': 'runtime-1', 'number': 1, 'title': '检查条件', 'status': 'running', 'response_ms': 1700}}}
    result = stages.annotate(event)
    assert result['payload']['task_step_number'] == 2
    assert result['payload']['step_tool_number'] == 2
    assert result['payload']['task_step']['response_ms'] == 1700


def test_recovery_returns_to_execution_without_merging_verification_and_model_work():
    now = [0.0]
    stages = ExecutionStages(preparation_seconds=0, clock=lambda: now[0])
    stages.annotate(action('started'))
    now[0] = 2
    stages.annotate(action('completed', 'completed'))
    stages.begin_finalization()
    now[0] = 3
    resumed = stages.annotate(action('started', identity='runtime-2'))
    assert resumed['payload']['task_steps'][0]['title'] == '核验与结果整理'
    assert resumed['payload']['task_steps'][0]['duration_ms'] == 1000
    assert resumed['payload']['task_step']['number'] == 4


def test_unframed_runtime_uses_the_recorded_prompt_entry_boundary():
    now = [0.0]
    stages = ExecutionStages(preparation_seconds=4, clock=lambda: now[0])
    now[0] = 3
    stages.mark_execution_entry()
    now[0] = 5
    finalizing = stages.begin_finalization()
    assert [step['duration_ms'] for step in finalizing['payload']['task_steps']] == [7000, 2000]
    now[0] = 6
    assert stages.finish()[0]['duration_ms'] == 1000
