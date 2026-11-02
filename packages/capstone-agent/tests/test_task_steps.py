import pytest

from capstone_agent.task_steps import TaskStepTracker


@pytest.mark.parametrize('native',[False,True])
def test_debug_progress_capacity_escapes_before_pydantic_rejection(native):
    from capstone_agent.application_capacity import initialize_capacity,current_capacity,CapacityExceeded
    from capstone_agent.task_steps import NativeStepTracker
    previous=current_capacity()
    try:
        initialize_capacity({'research_progress_chars':4},mode='debug')
        tracker=NativeStepTracker(prefix='native',objective_steps=True) if native else TaskStepTracker()
        event={'type':'tool_execution_start','toolName':'agent_task_progress','toolCallId':'oversized',
               'args':{'kind':'goal','text':'too long','step_id':'inspect','phase':'started'}}
        with pytest.raises(CapacityExceeded) as caught:
            if native:
                event.update(tool_name='agent_task_progress',tool_call_id='oversized')
                tracker.annotate(event)
            else:tracker.annotate(event)
        assert caught.value.mode=='debug'
        assert caught.value.dimension=='research_progress_chars'
    finally:initialize_capacity(previous)


def test_objective_response_time_accumulates_parent_boundaries_through_public_pipeline():
    from capstone_agent.task_steps import NativeStepTracker
    from capstone_agent.execution_stages import ExecutionStages
    from capstone_agent.harness import normalize_runtime_event

    now = [0.0]
    native = NativeStepTracker(prefix='native', objective_steps=True)
    native.tracker.clock = lambda: now[0]
    stages = ExecutionStages(clock=lambda: now[0])

    def project(event):
        annotated = native.annotate(event)
        public = (normalize_runtime_event(annotated, runtime_mode='capstone')
                  if event['type'] == 'runtime_action' else
                  {'event_type': 'runtime_event', 'visibility': 'public', 'payload': annotated})
        return stages.annotate(public)['payload']

    def cycle(step, phase, **extra):
        return project({'type': 'enterprise_cycle_progress', 'action_id': 'action-' + step,
            'progress': {'step_id': step, 'phase': phase, 'text': step, **extra}})

    # Initial planning has no accepted objective owner. It cannot be assigned
    # retroactively to the objective created by its control tool.
    project({'type': 'runtime_action', 'phase': 'started'})
    now[0] = 1
    project({'type': 'runtime_action', 'phase': 'response_completed'})
    assert 'response_ms' not in cycle('p1', 'started')['task_step']
    project({'type': 'runtime_action', 'phase': 'completed'})
    project({'type': 'runtime_action', 'phase': 'started'})
    now[0] = 3
    first = project({'type': 'runtime_action', 'phase': 'response_completed'})
    assert first['task_step']['response_ms'] == 2000
    project({'type': 'tool_execution_start', 'tool_name': 'bash', 'tool_call_id': 'read'})
    now[0] = 103
    project({'type': 'tool_execution_end', 'tool_name': 'bash', 'tool_call_id': 'read', 'is_error': False})
    project({'type': 'runtime_action', 'phase': 'completed'})
    project({'type': 'runtime_action', 'phase': 'started'})
    now[0] = 104
    project({'type': 'runtime_action', 'phase': 'started', 'subordinate': True})
    now[0] = 105
    project({'type': 'runtime_action', 'phase': 'response_completed', 'subordinate': True})
    now[0] = 106
    second = project({'type': 'runtime_action', 'phase': 'response_completed'})
    assert second['task_step']['response_ms'] == 5000
    # The committed next objective may start before the assess tool returns.
    assess = {'tool_name': 'agent_research_assess', 'tool_call_id': 'assess'}
    project({'type': 'tool_execution_start', **assess})
    assert cycle('p1', 'settled', outcome='met')['task_step']['response_ms'] == 5000
    assert 'response_ms' not in cycle('p2', 'started')['task_step']
    project({'type': 'tool_execution_end', **assess, 'is_error': False})
    project({'type': 'runtime_action', 'phase': 'completed'})
    project({'type': 'runtime_action', 'phase': 'started'})
    now[0] = 110
    third = project({'type': 'runtime_action', 'phase': 'response_completed'})
    assert third['task_step']['id'] == 'native.p2'
    assert third['task_step']['response_ms'] == 4000
    assert stages.steps['native.p1']['response_ms'] == 5000
    assert third['task_step']['status'] == 'running'


def test_objective_response_measurements_ignore_incomplete_or_repeated_boundaries():
    now = [0.0]
    tracker = TaskStepTracker(clock=lambda: now[0])
    tracker.cycle_progress({'step_id': 'p1', 'phase': 'started', 'text': 'Inspect'})
    tracker.annotate({'type': 'runtime_action', 'phase': 'started'})
    now[0] = 1
    tracker.annotate({'type': 'runtime_action', 'phase': 'started'})
    now[0] = 2
    result = tracker.annotate({'type': 'runtime_action', 'phase': 'response_completed'})
    assert result['task_step']['response_ms'] == 2000
    now[0] = 10
    tracker.annotate({'type': 'runtime_action', 'phase': 'response_completed'})
    tracker.annotate({'type': 'runtime_action', 'phase': 'completed'})
    tracker.annotate({'type': 'runtime_action', 'phase': 'started'})
    now[0] = 20
    tracker.annotate({'type': 'runtime_action', 'phase': 'interrupted'})
    tracker.annotate({'type': 'runtime_action', 'phase': 'response_completed'})
    assert tracker.steps['p1']['response_ms'] == 2000
    tracker.cycle_progress({'step_id': 'p1', 'phase': 'settled', 'text': 'Inspect', 'outcome': 'partial'})
    tracker.cycle_progress({'step_id': 'p2', 'phase': 'started', 'text': 'Repair'})
    tracker.annotate({'type': 'runtime_action', 'phase': 'started'})
    now[0] = 30
    tracker.annotate({'type': 'runtime_action', 'phase': 'interrupted'})
    assert 'response_ms' not in tracker.steps['p2']


def test_response_owner_is_fixed_at_start_even_if_committed_step_changes():
    now = [0.0]
    tracker = TaskStepTracker(clock=lambda: now[0])
    tracker.cycle_progress({'step_id': 'p1', 'phase': 'started', 'text': 'Inspect'})
    tracker.annotate({'type': 'runtime_action', 'phase': 'started'})
    now[0] = 1
    tracker.cycle_progress({'step_id': 'p1', 'phase': 'settled', 'text': 'Inspect', 'outcome': 'met'})
    tracker.cycle_progress({'step_id': 'p2', 'phase': 'started', 'text': 'Compare'})
    now[0] = 2
    observed = tracker.annotate({'type': 'runtime_action', 'phase': 'response_completed'})
    assert observed['task_step']['id'] == 'p1'
    assert observed['task_step']['status'] == 'completed'
    assert observed['task_step']['response_ms'] == 2000
    assert 'response_ms' not in tracker.steps['p2']
    assert tracker.active == 'p2'


def test_next_native_step_records_actual_failed_step_without_claiming_replanning():
    from capstone_agent.task_steps import RuntimeStepTracker
    tracker = RuntimeStepTracker()
    tracker.annotate({'type': 'runtime_action', 'phase': 'started'})
    tracker.annotate({'type': 'tool_execution_start', 'toolName': 'domain_query', 'toolCallId': 'one'})
    tracker.annotate({'type': 'tool_execution_end', 'toolName': 'domain_query', 'toolCallId': 'one', 'ok': False})
    tracker.annotate({'type': 'runtime_action', 'phase': 'completed'})
    continuation = tracker.annotate({'type': 'runtime_action', 'phase': 'started'})
    assert continuation['task_step']['after_failed_steps'] == ['runtime-1']
    assert 'replanned' not in continuation['task_step']
    tracker.annotate({'type': 'runtime_action', 'phase': 'completed'})
    following = tracker.annotate({'type': 'runtime_action', 'phase': 'started'})
    assert not following['task_step'].get('after_failed_steps')


def test_purpose_on_business_call_is_saved_without_a_progress_tool():
    from capstone_agent.task_steps import RuntimeStepTracker
    tracker = RuntimeStepTracker()
    tracker.annotate({'type': 'runtime_action', 'phase': 'started'})
    tracker.annotate({'type': 'tool_execution_start', 'toolName': 'agent_task_progress', 'toolCallId': 'goal',
        'args': {'kind': 'goal', 'text': '完整任务目标', 'purpose': '完整任务目标', 'refs': []}})
    tracker.annotate({'type': 'runtime_action', 'phase': 'response_completed', 'response_kind': 'tools'})
    call = tracker.annotate({'type': 'tool_execution_start', 'toolName': 'domain_query', 'toolCallId': 'one',
        'args': {'execution_purpose': '读取结果并核验约束', 'dataset': 'lines'}})
    assert call['task_step']['title'] == '读取结果并核验约束'
    assert call['task_step_id'] == 'runtime-1'
    tracker.annotate({'type': 'tool_execution_start', 'toolName': 'agent_task_progress', 'toolCallId': 'note',
        'args': {'kind': 'observation', 'text': '阶段观察', 'purpose': '冗长观察描述', 'refs': []}})
    tracker.annotate({'type': 'tool_execution_start', 'toolName': 'domain_query', 'toolCallId': 'two'})
    end = tracker.annotate({'type': 'runtime_action', 'phase': 'completed'})
    assert end['task_step']['title'] == '读取结果并核验约束'


def test_runtime_steps_follow_native_boundaries_without_model_completion():
    from capstone_agent.task_steps import RuntimeStepTracker
    now = [0.0]
    tracker = RuntimeStepTracker(clock=lambda: now[0])
    started = tracker.annotate({'type': 'runtime_action', 'phase': 'started'})
    assert started['task_step']['number'] == 1
    now[0] = 2.0
    tracker.annotate({'type': 'runtime_action', 'phase': 'response_completed', 'response_kind': 'tools'})
    child = tracker.annotate({'type': 'tool_execution_start', 'toolName': 'grid_check', 'toolCallId': 'one'})
    assert child['task_step_id'] == started['task_step']['id']
    now[0] = 3.0
    tracker.annotate({'type': 'tool_execution_end', 'toolName': 'grid_check', 'toolCallId': 'one', 'ok': False})
    finished = tracker.annotate({'type': 'runtime_action', 'phase': 'completed'})
    assert finished['task_step']['duration_ms'] == 3000
    assert finished['task_step']['response_ms'] == 2000
    assert finished['task_step']['status'] == 'completed'
    assert finished['task_step']['title'] == '组织工具调用'
    assert tracker.response_seconds == {}, 'runtime tracker must not also accumulate objective timing'
    assert 'verified' not in finished['task_step']


def test_response_timing_records_first_public_text_and_usage_without_inventing_purpose():
    from capstone_agent.task_steps import RuntimeStepTracker
    now = [0.0]
    tracker = RuntimeStepTracker(clock=lambda: now[0])
    start = tracker.annotate({'type': 'runtime_action', 'phase': 'started'})
    assert start['task_step']['title'] == '模型响应'
    now[0] = 1
    tracker.annotate({'type': 'assistant_process_delta', 'text': 'public'})
    now[0] = 2
    tracker.annotate({'type': 'assistant_process_delta', 'text': 'more public'})
    now[0] = 3
    end = tracker.annotate({'type': 'runtime_action', 'phase': 'response_completed', 'response_kind': 'text', 'usage': {'input': 9000, 'output': 200}})
    assert end['task_step']['first_text_ms'] == 1000
    assert end['task_step']['response_ms'] == 3000
    assert end['task_step']['usage'] == {'input': 9000, 'output': 200}


def test_runtime_step_does_not_turn_goal_into_an_action():
    from capstone_agent.task_steps import RuntimeStepTracker
    tracker = RuntimeStepTracker()
    assert 'task_step' not in tracker.annotate(progress('goal', 'started', '本轮目标'))
    assert 'task_step' not in tracker.annotate({'type': 'tool_execution_start', 'toolName': 'grid_check', 'toolCallId': 'one'})


def test_native_step_annotations_survive_public_normalization():
    from capstone_agent.task_steps import RuntimeStepTracker
    from capstone_agent.harness import normalize_runtime_event
    now = [0.0]
    tracker = RuntimeStepTracker(clock=lambda: now[0])
    start = normalize_runtime_event(tracker.annotate({'type': 'runtime_action', 'phase': 'started'}), runtime_mode='capstone')
    assert start['payload']['task_step']['status'] == 'running'
    now[0] = 2.0
    end = normalize_runtime_event(tracker.annotate({'type': 'runtime_action', 'phase': 'completed'}), runtime_mode='capstone')
    assert end['payload']['task_step']['duration_ms'] == 2000
    assert end['payload']['task_step']['status'] == 'completed'


def test_action_purpose_is_model_recorded_and_not_inferred_from_tools():
    from capstone_agent.task_steps import RuntimeStepTracker
    tracker = RuntimeStepTracker()
    tracker.annotate({'type': 'runtime_action', 'phase': 'started'})
    event = {'type': 'tool_execution_start', 'toolName': 'agent_task_progress', 'toolCallId': 'progress',
        'args': {'kind': 'goal', 'text': '检查求解条件', 'purpose': '检查约束与求解条件', 'refs': []}}
    described = tracker.annotate(event)
    assert described['task_step']['title'] == '检查约束与求解条件'
    child = tracker.annotate({'type': 'tool_execution_start', 'toolName': 'grid_check', 'toolCallId': 'one'})
    assert child['task_step_id'] == described['task_step']['id']
    ended = tracker.annotate({'type': 'runtime_action', 'phase': 'completed'})
    assert ended['task_step']['title'] == '检查约束与求解条件'


def progress(step, phase, text):
    return {"type": "tool_result", "event": "tool_result", "tool_name": "agent_task_progress",
        "capability": "agent_task_progress", "ok": True,
        "result": {"kind": "goal", "text": text, "refs": [], "step_id": step, "phase": phase}}


def test_host_numbers_steps_and_binds_tools_at_start():
    now = [0.0]
    tracker = TaskStepTracker(clock=lambda: now[0])
    started = tracker.annotate(progress("inspect", "started", "检查拓扑"))
    assert started["task_step"]["number"] == 1
    child = tracker.annotate({"type": "tool_execution_start", "toolName": "grid_context_get", "toolCallId": "call-one"})
    assert child["task_step_id"] == "inspect"
    assert child["step_tool_number"] == 1
    tracker.annotate({"type": "tool_execution_end", "toolName": "grid_context_get", "toolCallId": "call-one", "ok": True})
    now[0] = 2.5
    finished = tracker.annotate(progress("inspect", "completed", "拓扑检查结束"))
    assert finished["task_step"]["duration_ms"] == 2500
    assert finished["task_step"]["title"] == "检查拓扑"
    second = tracker.annotate(progress("solve", "started", "计算故障场景"))
    assert second["task_step"]["number"] == 2
    late = tracker.annotate({"type": "tool_execution_end", "toolName": "grid_context_get", "toolCallId": "call-one", "ok": True})
    assert late["task_step_id"] == "inspect"


def test_unscoped_tools_are_not_assigned_to_invented_steps():
    tracker = TaskStepTracker()
    event = {"type": "tool_execution_start", "toolName": "grid_context_get", "toolCallId": "call-one"}
    assert "task_step_id" not in tracker.annotate(event)


def test_native_objective_transition_rejection_remains_visible():
    from capstone_agent.task_steps import NativeStepTracker
    tracker = NativeStepTracker(prefix='attempt', objective_steps=True)
    def start(identity):
        return {'type': 'tool_execution_start', 'tool_name': 'agent_task_progress',
            'tool_call_id': identity, 'args': {'kind': 'goal', 'text': identity,
                'refs': [], 'step_id': identity, 'phase': 'started'}}
    tracker.annotate(start('analyze'))
    rejected = tracker.annotate(start('deliver'))
    assert rejected['task_step_error']
    assert tracker.tracker.active == 'analyze'
    assert tracker.tracker.steps['analyze']['status'] == 'running'
    assert 'deliver' not in tracker.tracker.steps
    child = tracker.annotate({'type': 'tool_execution_start', 'tool_name': 'bash',
        'tool_call_id': 'check'})
    assert child['task_step_id'] == 'attempt.analyze'


def test_committed_cycle_preserves_partial_result_and_starts_repair():
    from capstone_agent.task_steps import NativeStepTracker
    tracker = NativeStepTracker(prefix='attempt', objective_steps=True)
    def cycle(identity, phase, outcome=None):
        record = {'step_id': identity, 'phase': phase, 'text': identity}
        if outcome is not None:
            record['outcome'] = outcome
        return tracker.annotate({'type': 'enterprise_cycle_progress', 'progress': record})
    assert cycle('analyze', 'started')['task_step']['status'] == 'running'
    tracker.annotate({'type': 'tool_execution_start', 'tool_name': 'bash', 'tool_call_id': 'one'})
    tracker.annotate({'type': 'tool_execution_end', 'tool_name': 'bash', 'tool_call_id': 'one', 'is_error': False})
    assert cycle('analyze', 'settled', 'partial')['task_step']['status'] == 'partial'
    assert cycle('repair', 'started')['task_step']['number'] == 2
    replay = cycle('analyze', 'settled', 'partial')
    assert 'task_step_error' not in replay
    assert tracker.tracker.active == 'repair'
    assert cycle('analyze', 'started')['task_step']['status'] == 'partial'
    late = tracker.annotate({'type': 'tool_execution_end', 'tool_name': 'bash', 'tool_call_id': 'one', 'is_error': False})
    assert late['task_step_id'] == 'attempt.analyze'
    assert late['task_step']['status'] == 'partial'
    assert cycle('repair', 'settled', 'met')['task_step']['status'] == 'completed'


def test_cycle_settlement_waits_for_tools_and_narration_cannot_override_it():
    from capstone_agent.task_steps import NativeStepTracker
    tracker = NativeStepTracker(prefix='attempt', objective_steps=True)
    tracker.annotate({'type': 'enterprise_cycle_progress', 'progress': {
        'step_id': 'inspect', 'phase': 'started', 'text': 'Inspect sources'}})
    tracker.annotate({'type': 'tool_execution_start', 'tool_name': 'bash', 'tool_call_id': 'one'})
    tracker.annotate({'type': 'tool_execution_end', 'tool_name': 'agent_task_progress',
        'tool_call_id': 'narration', 'is_error': False, 'task_progress': {
            'kind': 'goal', 'text': 'Done', 'refs': [], 'step_id': 'inspect', 'phase': 'completed'}})
    assert tracker.tracker.steps['inspect']['status'] == 'running'
    pending = tracker.annotate({'type': 'enterprise_cycle_progress', 'progress': {
        'step_id': 'inspect', 'phase': 'settled', 'outcome': 'failed', 'text': 'Source check failed'}})
    assert pending['task_step']['status'] == 'running'
    blocked = tracker.annotate({'type': 'enterprise_cycle_progress', 'progress': {
        'step_id': 'next', 'phase': 'started', 'text': 'Next objective'}})
    assert 'unfinished tool calls' in blocked['task_step_error']
    assert tracker.tracker.active == 'inspect' and 'next' not in tracker.tracker.steps
    settled = tracker.annotate({'type': 'tool_execution_end', 'tool_name': 'bash',
        'tool_call_id': 'one', 'is_error': True})
    assert settled['task_step']['status'] == 'failed'


def test_unsettled_objective_rejection_explains_reason_and_preserves_state():
    tracker = TaskStepTracker()
    tracker.cycle_progress({'step_id': 'first', 'phase': 'started', 'text': 'First objective'})
    blocked = tracker.cycle_progress({'step_id': 'next', 'phase': 'started', 'text': 'Next objective'})
    assert 'before the current step has a committed settlement' in blocked['task_step_error']
    assert tracker.active == 'first' and set(tracker.steps) == {'first'}


@pytest.mark.parametrize('outcome,status', [('met', 'completed'), ('partial', 'partial'), ('failed', 'failed')])
@pytest.mark.parametrize('control_tool', ['agent_research_cycle', 'agent_research_plan', 'agent_research_record', 'agent_research_assess'])
def test_live_cycle_assessment_starts_next_objective_before_its_tool_end(outcome, status, control_tool):
    """Live seq 72, 74, 75, 76: one CAS emits settle+start before tool end."""
    from capstone_agent.task_steps import NativeStepTracker
    from capstone_agent.execution_stages import ExecutionStages
    tracker = NativeStepTracker(prefix='attempt', objective_steps=True)
    stages = ExecutionStages()
    def project(event):
        native = tracker.annotate(event)
        return stages.annotate({'event_type': 'runtime_event', 'visibility': 'public', 'payload': native})['payload']
    project({'type': 'enterprise_cycle_progress', 'action_id': 'cycle-profile', 'progress': {
        'step_id': 'source-profile', 'phase': 'started', 'text': '确认资料口径与覆盖'}})
    assessment = {'tool_name': control_tool, 'tool_call_id': 'assessment-call'}
    before = project({'type': 'tool_execution_start', **assessment})
    pending = project({'type': 'enterprise_cycle_progress', 'action_id': 'cycle-profile', 'progress': {
        'step_id': 'source-profile', 'phase': 'settled', 'text': '确认资料口径与覆盖',
        'outcome': outcome, 'result_summary': '资料检查已保存。'}})
    assert pending['task_step']['status'] == status
    following = project({'type': 'enterprise_cycle_progress', 'action_id': 'cycle-prices', 'progress': {
        'step_id': 'price-analysis', 'phase': 'started', 'text': '量化价格与负电价分布'}})
    assert 'task_step_error' not in following
    assert following['task_step']['id'] == 'attempt.price-analysis'
    assert tracker.tracker.active == 'price-analysis'
    replay = project({'type': 'enterprise_cycle_progress', 'action_id': 'cycle-profile', 'progress': {
        'step_id': 'source-profile', 'phase': 'settled', 'text': '确认资料口径与覆盖', 'outcome': outcome}})
    assert 'task_step_error' not in replay
    assert replay['task_step']['status'] == status
    assert tracker.tracker.active == 'price-analysis'
    after = project({'type': 'tool_execution_end', **assessment, 'is_error': False})
    assert after['task_step_id'] == before['task_step_id'] == 'attempt.source-profile'
    assert after['task_step']['status'] == status
    assert after['task_step']['result_summary'] == '资料检查已保存。'
    assert tracker.tracker.active == 'price-analysis'
    assert stages.active == 'attempt.price-analysis'
    assert stages.steps['attempt.source-profile']['status'] == status
    next_tool = project({'type': 'tool_execution_start', 'tool_name': 'bash', 'tool_call_id': 'prices'})
    assert next_tool['task_step_id'] == 'attempt.price-analysis'
    assert len(tracker.tracker.steps) == 2


def test_first_committed_cycle_takes_over_unsettled_narrative_without_losing_tools():
    from capstone_agent.task_steps import NativeStepTracker
    tracker = NativeStepTracker(prefix='task', objective_steps=True)
    tracker.annotate({'type': 'tool_execution_start', 'tool_name': 'agent_task_progress',
        'tool_call_id': 'narrative', 'args': {'kind': 'goal', 'text': 'Initial data profile',
            'step_id': 'data-profile', 'phase': 'started'}})
    tracker.annotate({'type': 'tool_execution_start', 'tool_name': 'bash', 'tool_call_id': 'in-flight'})
    tracker.annotate({'type': 'tool_execution_start', 'tool_name': 'agent_research_cycle', 'tool_call_id': 'plan'})
    taken = tracker.annotate({'type': 'enterprise_cycle_progress', 'progress': {
        'step_id': 'p1', 'phase': 'started', 'text': 'Inspect actual source coverage'}})
    assert 'task_step_error' not in taken
    assert taken['task_step']['id'] == 'task.p1'
    assert taken['task_step']['title'] == 'Inspect actual source coverage'
    assert taken['task_step']['number'] == 2
    prior = taken['task_steps'][0]
    assert prior['id'] == 'task.data-profile' and prior['status'] == 'limited'
    assert '接管' in prior['finish_reason']
    assert tracker.tracker.pending == {'in-flight', 'plan'}
    late = tracker.annotate({'type': 'tool_execution_end', 'tool_name': 'bash',
        'tool_call_id': 'in-flight', 'is_error': False})
    assert late['task_step_id'] == 'task.data-profile'
    assert late['task_step']['status'] == 'limited'
    assert tracker.tracker.active == 'p1'
    tracker.annotate({'type': 'tool_execution_end', 'tool_name': 'agent_research_cycle',
        'tool_call_id': 'plan', 'is_error': False})
    new_tool = tracker.annotate({'type': 'tool_execution_start', 'tool_name': 'read', 'tool_call_id': 'p1-read'})
    assert new_tool['task_step_id'] == 'task.p1'
    tracker.annotate({'type': 'tool_execution_end', 'tool_name': 'read', 'tool_call_id': 'p1-read', 'is_error': False})
    assert tracker.annotate({'type': 'enterprise_cycle_progress', 'progress': {
        'step_id': 'p1', 'phase': 'settled', 'outcome': 'met', 'text': 'Coverage checked'}})['task_step']['status'] == 'completed'
    following = tracker.annotate({'type': 'enterprise_cycle_progress', 'progress': {
        'step_id': 'p2', 'phase': 'started', 'text': 'Compare admitted observations'}})
    assert following['task_step']['id'] == 'task.p2' and following['task_step']['number'] == 3
    replay = tracker.annotate({'type': 'enterprise_cycle_progress', 'progress': {
        'step_id': 'p1', 'phase': 'started', 'text': 'Inspect actual source coverage'}})
    assert replay['task_step']['status'] == 'completed'
    assert tracker.tracker.active == 'p2'
    assert 'task_steps' not in replay


def test_first_cycle_can_take_over_after_narrative_tools_already_finished():
    from capstone_agent.task_steps import NativeStepTracker
    tracker = NativeStepTracker(prefix='task', objective_steps=True)
    tracker.annotate({'type': 'tool_execution_start', 'tool_name': 'agent_task_progress',
        'tool_call_id': 'narrative', 'args': {'kind': 'goal', 'text': 'Initial profile',
            'step_id': 'data-profile', 'phase': 'started'}})
    taken = tracker.annotate({'type': 'enterprise_cycle_progress', 'progress': {
        'step_id': 'p1', 'phase': 'started', 'text': 'Inspect sources'}})
    assert taken['task_steps'][0]['status'] == 'limited'
    assert taken['task_step']['status'] == 'running'


def test_first_cycle_reusing_narrative_id_keeps_distinct_history_and_inflight_owner():
    from capstone_agent.task_steps import NativeStepTracker
    tracker = NativeStepTracker(prefix='task', objective_steps=True)
    tracker.annotate({'type': 'tool_execution_start', 'tool_name': 'agent_task_progress',
        'tool_call_id': 'narrative', 'args': {'kind': 'goal', 'text': 'Narrative preparation',
            'step_id': 'inspect', 'phase': 'started'}})
    tracker.annotate({'type': 'tool_execution_start', 'tool_name': 'read', 'tool_call_id': 'old-read'})
    accepted = tracker.annotate({'type': 'enterprise_cycle_progress', 'action_id': 'cycle-inspect', 'progress': {
        'step_id': 'inspect', 'phase': 'started', 'text': 'Committed source inspection'}})
    assert accepted['task_steps'][0]['id'] == 'task.inspect'
    assert accepted['task_steps'][0]['status'] == 'limited'
    new_id = accepted['task_step']['id']
    assert new_id != 'task.inspect'
    assert accepted['task_step']['title'] == 'Committed source inspection'
    for kind in ('delegation_child_started', 'delegation_child_tool', 'delegation_child_finished'):
        branch = {'type': kind, 'parent_action_id': 'cycle-inspect', 'parent_step_id': 'inspect'}
        projected = tracker.annotate(branch)
        assert projected['parent_step_id'] == new_id
        assert branch['parent_step_id'] == 'inspect'
        assert 'task_step' not in projected and 'task_step_id' not in projected
        assert tracker.tracker.active == tracker.cycle_step_ids['inspect']
        assert len(tracker.tracker.steps) == 2
    late = tracker.annotate({'type': 'tool_execution_end', 'tool_name': 'read', 'tool_call_id': 'old-read', 'is_error': False})
    assert late['task_step_id'] == 'task.inspect' and late['task_step']['status'] == 'limited'
    new = tracker.annotate({'type': 'tool_execution_start', 'tool_name': 'read', 'tool_call_id': 'new-read'})
    assert new['task_step_id'] == new_id
    tracker.annotate({'type': 'tool_execution_end', 'tool_name': 'read', 'tool_call_id': 'new-read', 'is_error': False})
    settled = tracker.annotate({'type': 'enterprise_cycle_progress', 'progress': {
        'step_id': 'inspect', 'phase': 'settled', 'outcome': 'met', 'text': 'Checked'}})
    assert settled['task_step']['id'] == new_id and settled['task_step']['status'] == 'completed'


def test_child_branch_requires_observed_committed_parent_action():
    from capstone_agent.task_steps import NativeStepTracker
    tracker = NativeStepTracker(prefix='task', objective_steps=True)
    with pytest.raises(ValueError, match='parent action'):
        tracker.annotate({'type': 'delegation_child_started', 'parent_action_id': 'unknown',
                          'parent_step_id': 'inspect'})


def test_first_committed_synthesis_update_can_take_over_narrative():
    from capstone_agent.task_steps import NativeStepTracker
    tracker = NativeStepTracker(prefix='task', objective_steps=True)
    tracker.annotate({'type': 'tool_execution_start', 'tool_name': 'agent_task_progress',
        'tool_call_id': 'narrative', 'args': {'kind': 'goal', 'text': 'Preparation',
            'step_id': 'prepare', 'phase': 'started'}})
    accepted = tracker.annotate({'type': 'enterprise_cycle_progress', 'progress': {
        'step_id': 'synthesize', 'phase': 'updated', 'text': 'Compare admitted inputs'}})
    assert accepted['task_steps'][0]['status'] == 'limited'
    assert accepted['task_step']['id'] == 'task.synthesize'
    assert accepted['task_step']['status'] == 'running'


def test_committed_step_metadata_retains_purpose_and_adds_result_without_extra_step():
    from capstone_agent.task_steps import NativeStepTracker
    tracker = NativeStepTracker(prefix='task', objective_steps=True)
    metadata = {'questions': ['Which source is current?'], 'expected_outputs': ['Compare both sources'],
                'derived_from': ['finding-conflict'], 'next_action_reason': 'Resolve the conflict first.'}
    opened = tracker.annotate({'type': 'enterprise_cycle_progress', 'progress': {
        'step_id': 'resolve', 'phase': 'started', 'text': 'Check source versions', **metadata}})
    assert all(opened['task_step'][key] == value for key, value in metadata.items())
    settled = tracker.annotate({'type': 'enterprise_cycle_progress', 'progress': {
        'step_id': 'resolve', 'phase': 'settled', 'outcome': 'partial', 'text': 'Check source versions',
        **metadata, 'result_summary': 'A current version is not yet identified.'}})
    assert settled['task_step']['title'] == 'Check source versions'
    assert settled['task_step']['result_summary'] == 'A current version is not yet identified.'
    assert settled['task_step']['status'] == 'partial'
    assert len(tracker.tracker.steps) == 1


def test_reported_completion_waits_for_actual_tool_end():
    now = [0.0]
    tracker = TaskStepTracker(clock=lambda: now[0])
    tracker.annotate(progress("inspect", "started", "检查拓扑"))
    tracker.annotate({"type": "tool_execution_start", "toolName": "grid_check", "toolCallId": "call-one"})
    now[0] = 1.0
    reported = tracker.annotate(progress("inspect", "completed", "步骤结束"))
    assert reported["task_step"]["status"] == "running"
    now[0] = 3.0
    actual = tracker.annotate({"type": "tool_execution_end", "toolName": "grid_check", "toolCallId": "call-one", "ok": False})
    assert actual["task_step"]["status"] == "completed"
    assert actual["task_step"]["duration_ms"] == 3000


def test_native_receipt_cannot_invent_host_step_ownership():
    tracker = TaskStepTracker()
    event = {"type": "tool_execution_start", "toolName": "grid_check", "toolCallId": "call-one",
        "task_step_id": "invented", "task_step_number": 99}
    result = tracker.annotate(event)
    assert "task_step_id" not in result


def test_progress_start_binds_parallel_tools_without_waiting_for_its_receipt():
    tracker = TaskStepTracker()
    start = {"type": "tool_execution_start", "toolName": "agent_task_progress", "toolCallId": "progress-start",
        "args": {"kind": "goal", "text": "检查拓扑", "step_id": "inspect", "phase": "started", "refs": []}}
    assert tracker.annotate(start)["task_step"]["number"] == 1
    child = tracker.annotate({"type": "tool_execution_start", "toolName": "grid_check", "toolCallId": "call-one"})
    assert child["task_step_id"] == "inspect"
    tracker.annotate({"type": "tool_execution_end", "toolName": "grid_check", "toolCallId": "call-one", "ok": True})
    tracker.annotate({"type": "tool_execution_start", "toolName": "agent_task_progress", "toolCallId": "progress-end"})
    end = tracker.annotate(progress("inspect", "completed", "检查结束"))
    assert end["task_step"]["status"] == "completed"
def test_failed_model_response_is_not_presented_as_successful_tool_organization():
    from capability_agent.runtime.step_events import project_runtime_action
    from capstone_agent.task_steps import RuntimeStepTracker
    tracker = RuntimeStepTracker()
    tracker.annotate({'type': 'runtime_action', 'phase': 'started'})
    response = project_runtime_action({'type': 'message_end', 'message': {
        'role': 'assistant', 'stopReason': 'error', 'errorMessage': 'PRIVATE',
        'content': [{'type': 'toolCall', 'arguments': {'private': 'PRIVATE'}}],
    }})
    assert response['response_kind'] == 'error'
    assert 'PRIVATE' not in str(response)
    tracker.annotate(response)
    ended = tracker.annotate({'type': 'runtime_action', 'phase': 'completed'})
    assert ended['task_step']['title'] == '模型响应失败'
    assert ended['task_step']['finish_reason'] == 'error'
