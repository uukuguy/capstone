from capstone_agent.execution_stages import ExecutionStages


def test_native_takeover_batch_preserves_limited_old_step_and_global_numbers():
    stages = ExecutionStages()
    stages.annotate(action('started', identity='native.narrative'))
    old = {'id': 'native.narrative', 'number': 1, 'title': 'Initial data profile',
           'status': 'limited', 'finish_reason': 'Committed research took over; no completion was confirmed.'}
    incoming = action('started', identity='native.p1')
    incoming['payload']['task_steps'] = [old]
    result = stages.annotate(incoming)['payload']
    assert len(result['task_steps']) == 1
    assert result['task_steps'][0]['id'] == old['id']
    assert result['task_steps'][0]['status'] == 'limited'
    assert result['task_steps'][0]['finish_reason'] == old['finish_reason']
    assert result['task_steps'][0]['number'] == 2
    assert result['task_step']['id'] == 'native.p1' and result['task_step']['number'] == 3
    assert stages.steps['native.narrative']['status'] == 'limited'
    assert incoming['payload']['task_steps'] == [old], 'do not mutate original tracker event'


def test_first_seen_native_terminal_batch_merges_preparation_without_dropping_either():
    stages = ExecutionStages()
    incoming = action('started', identity='native.p1')
    incoming['payload']['task_steps'] = [{'id': 'native.narrative', 'number': 1,
        'title': 'Initial data profile', 'status': 'limited', 'finish_reason': 'Research took over.'}]
    payload = stages.annotate(incoming)['payload']
    previous = {step['id']: step for step in payload['task_steps']}
    assert set(previous) == {'task-preparation', 'native.narrative'}
    assert previous['task-preparation']['status'] == 'completed'
    assert previous['native.narrative']['status'] == 'limited'
    assert previous['native.narrative']['number'] == 2
    assert payload['task_step']['number'] == 3
    late = stages.annotate({'event_type': 'runtime_event', 'payload': {
        'task_step': {'id': 'native.narrative', 'title': 'Initial data profile', 'status': 'limited'},
        'task_step_id': 'native.narrative', 'task_step_number': 1}})['payload']
    assert late['task_step']['status'] == 'limited' and late['task_step_number'] == 2
    assert stages.active == 'native.p1'


def test_interrupted_startup_does_not_invent_execution_or_verification():
    stages = ExecutionStages()
    stages.mark_execution_entry()
    steps = stages.finish(interrupted=True)
    assert len(stages.steps) == 1
    assert steps[0]['id'] == 'task-preparation'
    assert steps[0]['finish_reason'] == 'interrupted'


def test_partial_research_outcome_survives_next_step_and_finalization():
    stages = ExecutionStages()
    stages.annotate(action('started', identity='analysis'))
    result = stages.annotate(action('settled', 'partial', identity='analysis'))
    assert result['payload']['task_step']['status'] == 'partial'
    repair = stages.annotate(action('started', identity='repair'))
    assert repair['payload']['task_steps'][0]['status'] == 'partial'
    stages.annotate(action('settled', 'failed', identity='repair'))
    assert stages.finish(interrupted=True)[0]['status'] == 'failed'


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
