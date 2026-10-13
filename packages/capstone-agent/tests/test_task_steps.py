from capstone_agent.task_steps import TaskStepTracker


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
    assert 'verified' not in finished['task_step']


def test_runtime_step_does_not_turn_goal_into_an_action():
    from capstone_agent.task_steps import RuntimeStepTracker
    tracker = RuntimeStepTracker()
    assert 'task_step' not in tracker.annotate(progress('goal', 'started', '本轮目标'))
    assert 'task_step' not in tracker.annotate({'type': 'tool_execution_start', 'toolName': 'grid_check', 'toolCallId': 'one'})


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
