from __future__ import annotations

import hashlib

from capstone_agent.case_definition import CaseCatalog, CaseDefinition, CaseStepDefinition
from capstone_agent.case_service import CaseExecutionService
from capstone_agent.thread_commands import ThreadCommandFactory
from capstone_agent.thread_service import InMemoryThreadService


def _catalog() -> CaseCatalog:
    steps = tuple(
        CaseStepDefinition(
            ordinal,
            f"Step {ordinal}",
            f"perform step {ordinal}",
            hashlib.sha256(f"perform step {ordinal}".encode()).hexdigest(),
        )
        for ordinal in range(1, 4)
    )
    return CaseCatalog((CaseDefinition(
        case_id="recovery_case", case_version="1", case_revision="case:sha256:recovery",
        display_name="Recovery case", description="recovery fixture", model_ids=("ieee39",), steps=steps,
    ),))


def _service() -> CaseExecutionService:
    return CaseExecutionService(_catalog(), InMemoryThreadService.from_document({
        "schema": "capstone-thread-snapshot/1", "thread_id": "thr_recovery",
        "run": {"run_id": "run_recovery", "state": "open"},
        "active_model_context": {
            "id": "ctx_ieee39", "model_id": "ieee39", "model_revision": "rev-1",
            "implementation_family": "pandapower", "selection_revision": "sel-1",
        },
        "active_grid_page_id": "page_ieee39", "current_attempt": None,
        "last_event_seq": 0, "base_event_seq": 0,
    }))


def _start(service: CaseExecutionService):
    return service.submit_command(ThreadCommandFactory("thr_recovery", "run_recovery").start_case_execution(
        "recovery_case", expected_event_seq=0, command_id="start_recovery", idempotency_key="start_recovery",
    ))


def _finish(service: CaseExecutionService, phase: str):
    claim = service.thread_service.claim_attempt("recovery-worker", lease_seconds=30)
    assert claim is not None
    service.thread_service.finish_attempt(claim, phase=phase, payload={
        "answer": "answer" if phase == "completed" else None,
        "result_refs": ["result:1"] if phase == "completed" else [],
        "evidence_refs": ["evidence:1"] if phase == "completed" else [],
    })
    return claim.attempt.attempt_id


def start_and_finish_step(service: CaseExecutionService, phase: str):
    """Small fixture helper shared by recovery scenarios."""
    if service.reconcile("thr_recovery") is None:
        _start(service)
    _finish(service, phase)
    execution = service.reconcile("thr_recovery")
    assert execution is not None
    return execution


def case_service_from_same_postgres() -> CaseExecutionService:
    """Return a fresh service over the same fixture store seam.

    The in-memory test store keeps this helper offline; Postgres contract tests
    can replace it with a fixture backed by the same DSN.
    """
    return _service()


def count_step_turns(service: CaseExecutionService, ordinal: int) -> int:
    events = service.thread_service.read_events("thr_recovery", 0).events
    return sum(
        1
        for event in events
        if event.event_type == "command_accepted"
        and isinstance(event.payload, dict)
        and event.payload.get("kind") == "send_auto"
        and isinstance(event.payload.get("payload"), dict)
        and event.payload["payload"].get("step_ordinal") == ordinal
    )


def test_reconcile_advances_only_after_committed_terminal_attempt() -> None:
    service = _service()
    assert _start(service).status == "accepted"
    first = service.reconcile("thr_recovery")
    assert first is not None and first.steps[0].status == "running"
    service.reconcile("thr_recovery")
    assert service.thread_service.snapshot("thr_recovery").current_attempt is not None
    _finish(service, "completed")
    advanced = service.reconcile("thr_recovery")
    assert advanced is not None and advanced.steps[0].status == "completed"
    assert advanced.steps[1].status == "running"
    assert advanced.steps[2].status == "pending"


def test_failed_attempt_blocks_and_retry_reuses_turn_with_new_attempt() -> None:
    service = _service()
    _start(service)
    failed_attempt = _finish(service, "failed")
    blocked = service.reconcile("thr_recovery")
    assert blocked is not None and blocked.status == "blocked"
    assert blocked.steps[0].status == "failed"
    snapshot = service.thread_service.snapshot("thr_recovery")
    retry = ThreadCommandFactory("thr_recovery", "run_recovery").retry_case_step(
        blocked.case_execution_id, step_ordinal=1, failed_attempt_id=failed_attempt,
        expected_event_seq=snapshot.last_event_seq, command_id="retry_recovery", idempotency_key="retry_recovery",
    )
    receipt = service.submit_command(retry)
    assert receipt.status == "accepted" and receipt.target is not None
    resumed = service.reconcile("thr_recovery")
    assert resumed is not None and resumed.steps[0].status == "running"
    assert resumed.steps[0].turn_id == blocked.steps[0].turn_id
    assert resumed.steps[0].latest_attempt_id != failed_attempt


def test_cancelled_and_interrupted_attempts_block() -> None:
    for phase in ("cancelled", "interrupted"):
        service = _service()
        _start(service)
        _finish(service, phase)
        execution = service.reconcile("thr_recovery")
        assert execution is not None and execution.status == "blocked"
        assert execution.steps[0].status == phase


def test_restart_recovers_after_step_turn_commit_before_application_transition() -> None:
    service = _service()
    _start(service)
    _finish(service, "completed")
    original = service.thread_service.apply_application_transition
    crashed = False

    def crash_once(transition):
        nonlocal crashed
        if transition.command["kind"] == "case_step_started" and not crashed:
            crashed = True
            raise RuntimeError("simulated process crash")
        return original(transition)

    service.thread_service.apply_application_transition = crash_once
    try:
        service.reconcile("thr_recovery")
    except RuntimeError:
        pass
    service.thread_service.apply_application_transition = original
    recovered = service.reconcile("thr_recovery")
    assert recovered is not None
    assert recovered.steps[1].status == "running"
    assert recovered.steps[1].turn_id is not None
