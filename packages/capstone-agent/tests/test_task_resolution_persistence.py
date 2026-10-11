from dataclasses import replace
import pytest
from capability_agent.domain.task import ResolvedTaskGoal
from capstone_agent.task_recognition import accept_task
from capstone_agent.task_resolution import accept_resolution, resolution_payload
from capstone_agent.task_understanding import recognize_decision
from capstone_agent.thread_service import InMemoryThreadService, PostgresThreadService
from test_task_recognition import proposal
from test_thread_postgres import postgres_thread_service, _snapshot, _command


def exercise(service, thread_id, reopen):
    if isinstance(service, PostgresThreadService):
        service.create_thread(_snapshot(thread_id))
    service.submit_command(_command(thread_id))
    claim = service.claim_attempt("worker", 30)
    claim = accept_task(service, claim, lambda bound, **kwargs: recognize_decision(bound.task_request, proposal(), recognizer="controlled"), on_heartbeat=lambda: None)
    goal = ResolvedTaskGoal("overview", "ready", '{"object_indices":[1,2]}', binding_id="grid")
    resolved = accept_resolution(service, claim, lambda task: (goal,))
    with pytest.raises(Exception, match="immutable"):
        service.append_runtime_event(claim, event_type="task_requirements_resolved",
                                     payload=resolution_payload(claim.task_request, (replace(goal, requirement_json='{"object_indices":[3]}'),)))
    snapshot = service.finish_attempt(resolved, phase="failed", payload={"error_code": "controlled_failure"})
    if isinstance(service, PostgresThreadService):
        service.compact_before(thread_id, snapshot.last_event_seq)
    else:
        service.compact_before(snapshot.last_event_seq)
    service = reopen(service)
    service.submit_command({"schema": "capstone-command/1", "command_id": "retry", "idempotency_key": "retry", "thread_id": thread_id,
        "run_id": "run_test_001", "kind": "retry_new_attempt", "expected_event_seq": snapshot.last_event_seq,
        "payload": {"attempt_id": claim.attempt.attempt_id}})
    replay = service.claim_attempt("worker2", 30)
    assert replay.task_resolutions == (goal,)
    assert replay.task_resolution_route == "professional"
    assert accept_resolution(service, replay, lambda task: pytest.fail("retry must reuse resolved objects")) == replay


def test_memory_resolution_is_immutable_across_retry_and_compaction():
    exercise(InMemoryThreadService(_snapshot("memory_resolution")), "memory_resolution", lambda service: service)


def test_postgres_resolution_is_immutable_across_restart_retry_and_compaction(postgres_thread_service):
    service, thread_id = postgres_thread_service
    exercise(service, thread_id, lambda previous: PostgresThreadService(previous.dsn))


def test_resolution_persistence_failure_stops_before_execution():
    service = InMemoryThreadService(_snapshot("resolution_failure"))
    service.submit_command(_command("resolution_failure"))
    claim = service.claim_attempt("worker", 30)
    claim = accept_task(service, claim, lambda bound, **kwargs: recognize_decision(bound.task_request, proposal(), recognizer="controlled"), on_heartbeat=lambda: None)
    class FailedStore:
        def append_runtime_event(self, *args, **kwargs):
            raise RuntimeError("required ledger unavailable")
    with pytest.raises(RuntimeError, match="required ledger"):
        accept_resolution(FailedStore(), claim, lambda task: (ResolvedTaskGoal("overview", "general", "{}"),))


@pytest.mark.parametrize("fail", [False, True])
def test_typed_conclusion_write_is_required_before_terminal_answer(fail):
    from capability_agent.domain.task import TaskConclusion
    from capstone_agent.harness import HarnessAttemptRunner, HarnessPiClient, AdmittedAttemptAnswer
    service = InMemoryThreadService(_snapshot("conclusion_write"))
    command = _command("conclusion_write")
    command["kind"] = "send_professional"
    service.submit_command(command)
    claim = service.claim_attempt("worker", 30)
    claim = accept_task(service, claim, lambda bound, **kwargs: recognize_decision(bound.task_request, proposal(), recognizer="controlled"), on_heartbeat=lambda: None)
    claim = accept_resolution(service, claim, lambda task: (ResolvedTaskGoal("overview", "unsupported", "{}", "Not registered.", execution_required=False),))
    original_append = service.append_runtime_event
    def append(*args, **kwargs):
        if fail and kwargs.get("event_type") == "task_goal_conclusions":
            raise RuntimeError("required conclusion ledger failed")
        return original_append(*args, **kwargs)
    service.append_runtime_event = append
    class Session:
        def start(self): pass
        def stop(self): pass
        def prompt_and_wait(self, question, **kwargs): return "Not registered."
    conclusion = TaskConclusion("overview", "unsupported", "Not registered.")
    runtime = HarnessPiClient(Session(), admission=lambda *args: AdmittedAttemptAnswer("Not registered.", "offline_information", "deterministic_information",
        diagnostic_codes=("task_capability_boundary_verified",), goal_conclusions=(conclusion,)))
    result = HarnessAttemptRunner(service, runtime).run(claim)
    assert result.status == ("failed" if fail else "completed")
    if not fail:
        events = service.read_events("conclusion_write", 0).events
        saved = next(event for event in events if event.event_type == "task_goal_conclusions")
        assert saved.payload["request"] == claim.task_request.to_document()
        assert saved.payload["conclusions"] == [conclusion.to_document()]
