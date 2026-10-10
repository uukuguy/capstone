from __future__ import annotations

import hashlib
from dataclasses import replace
from typing import Any, Mapping

import pytest

from capstone_agent.case_definition import CaseCatalog, CaseDefinition, CaseStepDefinition
from capstone_agent.case_execution import CaseExecution, PinnedCaseContext, SequentialBatchExecutor
from capstone_agent.case_service import CaseExecutionService
from capstone_agent.thread_application_transition import (
    ApplicationEvent,
    ThreadApplicationTransition,
)
from capstone_agent.thread_commands import ThreadCommandFactory
from capstone_agent.thread_service import InMemoryThreadService


def _catalog() -> CaseCatalog:
    return CaseCatalog(
        (
            CaseDefinition(
                case_id="case_demo",
                case_version="1",
                case_revision="case:sha256:demo",
                display_name="Demo case",
                description="A deterministic case for the command boundary.",
                model_ids=("ieee39",),
                steps=(
                    CaseStepDefinition(
                        1,
                        "First",
                        "inspect the network",
                        hashlib.sha256(b"inspect the network").hexdigest(),
                    ),
                    CaseStepDefinition(
                        2,
                        "Second",
                        "summarize the result",
                        hashlib.sha256(b"summarize the result").hexdigest(),
                    ),
                ),
            ),
        ),
    )


def _thread_service(
    *,
    model_id: str = "ieee39",
    last_event_seq: int = 0,
    current_attempt: dict[str, str] | None = None,
) -> InMemoryThreadService:
    return InMemoryThreadService.from_document(
        {
            "schema": "capstone-thread-snapshot/1",
            "thread_id": "thr_case",
            "run": {"run_id": "run_case", "state": "open"},
            "active_model_context": {
                "id": "ctx_ieee39",
                "model_id": model_id,
                "model_revision": "model-rev-7",
                "implementation_family": "pandapower",
                "selection_revision": "sel-3",
            },
            "active_grid_page_id": "page_ieee39",
            "current_attempt": current_attempt,
            "last_event_seq": last_event_seq,
            "base_event_seq": 0,
        },
    )


def _service(
    *,
    model_id: str = "ieee39",
    current_attempt: dict[str, str] | None = None,
) -> CaseExecutionService:
    return CaseExecutionService(
        _catalog(),
        _thread_service(model_id=model_id, current_attempt=current_attempt),
    )


def start_command(case_id: str, seq: int, **payload: Any) -> Mapping[str, object]:
    return ThreadCommandFactory("thr_case", "run_case").start_case_execution(
        case_id,
        expected_event_seq=seq,
        command_id="cmd_case_start",
        idempotency_key="idem_case_start",
        **payload,
    )


@pytest.fixture
def case_service() -> CaseExecutionService:
    return _service()


def test_start_case_pins_current_context(case_service: CaseExecutionService) -> None:
    receipt = case_service.submit_command(start_command("case_demo", seq=0))

    assert receipt.status == "accepted"
    execution = case_service.reconcile("thr_case")
    assert execution is not None
    snapshot = case_service.thread_service.snapshot("thr_case")
    assert execution.context.model_context_id == snapshot.active_model_context.id
    assert execution.context.model_revision == snapshot.active_model_context.model_revision
    assert execution.context.selection_revision == snapshot.active_model_context.selection_revision
    assert execution.case_revision == "case:sha256:demo"
    assert execution.steps[0].status == "running"


def test_duplicate_start_is_idempotent(case_service: CaseExecutionService) -> None:
    command = start_command("case_demo", seq=0)

    first = case_service.submit_command(command)
    second = case_service.submit_command(command)

    assert second == first
    assert len(case_service.thread_service.read_events("thr_case", 0).events) == 3


def test_duplicate_start_replays_after_case_service_restart() -> None:
    thread_service = _thread_service()
    first_service = CaseExecutionService(_catalog(), thread_service)
    command = start_command("case_demo", seq=0)

    first = first_service.submit_command(command)
    restarted = CaseExecutionService(_catalog(), thread_service)

    assert restarted.submit_command(command) == first


def test_start_replays_a_persisted_created_case_after_crash_window() -> None:
    thread_service = _thread_service()
    definition = _catalog().get("case_demo", "1")
    command = start_command("case_demo", seq=0)
    snapshot = thread_service.snapshot("thr_case")
    context = PinnedCaseContext(
        model_context_id=snapshot.active_model_context.id,
        model_id=snapshot.active_model_context.model_id,
        model_revision=snapshot.active_model_context.model_revision,
        selection_revision=snapshot.active_model_context.selection_revision,
    )
    execution = SequentialBatchExecutor(definition).create_execution(
        definition,
        context,
        case_execution_id=_execution_id(command),
        thread_id=snapshot.thread_id,
        run_id=snapshot.run.run_id,
    )
    service = CaseExecutionService(_catalog(), thread_service)
    thread_service.apply_application_transition(
        service._created_transition(command, execution, definition),
    )

    restarted = CaseExecutionService(_catalog(), thread_service)
    receipt = restarted.submit_command(command)

    assert receipt.status == "accepted"
    recovered = restarted.reconcile("thr_case")
    assert recovered is not None
    assert recovered.steps[0].status == "running"
    assert thread_service.snapshot("thr_case").current_attempt is not None


def test_cancel_case_commits_after_the_attempt_cancel_events(
    case_service: CaseExecutionService,
) -> None:
    case_service.submit_command(start_command("case_demo", seq=0))
    execution = case_service.reconcile("thr_case")
    assert execution is not None
    snapshot = case_service.thread_service.snapshot("thr_case")
    command = ThreadCommandFactory("thr_case", "run_case").cancel_case_execution(
        execution.case_execution_id,
        expected_event_seq=snapshot.last_event_seq,
        command_id="cmd_case_cancel",
        idempotency_key="idem_case_cancel",
    )

    receipt = case_service.submit_command(command)

    assert receipt.status == "accepted"
    cancelled = case_service.reconcile("thr_case")
    assert cancelled is not None
    assert cancelled.status == "cancelled"
    assert case_service.submit_command(command) == receipt


def test_start_rejects_a_case_that_does_not_support_the_current_model() -> None:
    service = _service(model_id="other_model")

    receipt = service.submit_command(start_command("case_demo", seq=0))

    assert receipt.status == "rejected"
    assert receipt.rejection == "case_model_mismatch"


def test_start_rejects_a_busy_thread() -> None:
    service = _service(
        current_attempt={
            "turn_id": "turn_existing",
            "attempt_id": "attempt_existing",
            "phase": "running",
            "target_model_context_id": "ctx_ieee39",
        },
    )

    receipt = service.submit_command(start_command("case_demo", seq=0))

    assert receipt.status == "rejected"
    assert receipt.rejection == "thread_busy"


def test_start_rejects_a_stale_cursor() -> None:
    service = _service()
    command = start_command("case_demo", seq=0)
    service.submit_command(command)

    stale = dict(command)
    stale.update({
        "command_id": "cmd_case_start_stale",
        "idempotency_key": "idem_case_start_stale",
        "expected_event_seq": 0,
    })
    receipt = service.submit_command(stale)

    assert receipt.status == "rejected"
    assert receipt.rejection == "stale_event_seq"


def test_active_case_locks_model_and_profile_switches(case_service: CaseExecutionService) -> None:
    case_service.submit_command(start_command("case_demo", seq=0))
    command = ThreadCommandFactory("thr_case", "run_case").switch_model(
        "ieee39",
        expected_event_seq=case_service.thread_service.snapshot("thr_case").last_event_seq,
        command_id="cmd_switch",
        idempotency_key="idem_switch",
    )

    receipt = case_service.thread_service.submit_command(command)

    assert receipt.status == "rejected"
    assert receipt.rejection == "case_context_locked"


def test_active_case_blocks_ordinary_turns(case_service: CaseExecutionService) -> None:
    case_service.submit_command(start_command("case_demo", seq=0))
    snapshot = case_service.thread_service.snapshot("thr_case")
    command = ThreadCommandFactory("thr_case", "run_case").send_ordinary(
        "interleave",
        expected_event_seq=snapshot.last_event_seq,
        command_id="cmd_interleave",
        idempotency_key="idem_interleave",
    )

    receipt = case_service.thread_service.submit_command(command)

    assert receipt.status == "rejected"
    assert receipt.rejection == "case_execution_active"


def test_active_case_blocks_generic_retry_new_attempt_after_step_failure(
    case_service: CaseExecutionService,
) -> None:
    case_service.submit_command(start_command("case_demo", seq=0))
    failed_attempt_id = _finish_current_attempt(case_service, phase="failed")
    snapshot = case_service.thread_service.snapshot("thr_case")
    command = ThreadCommandFactory("thr_case", "run_case").retry_new_attempt(
        expected_event_seq=snapshot.last_event_seq,
        command_id="cmd_generic_retry",
        idempotency_key="idem_generic_retry",
        attempt_id=failed_attempt_id,
    )

    receipt = case_service.thread_service.submit_command(command)

    assert receipt.status == "rejected"
    assert receipt.rejection == "case_execution_active"


@pytest.mark.parametrize(
    ("payload_update", "command_id", "idempotency_key"),
    [
        ({}, "cmd_forged_step_missing_context", "idem_forged_step_missing_context"),
        (
            {
                "case_context": {
                    "model_context_id": "ctx_other",
                    "model_id": "ieee39",
                    "model_revision": "model-rev-7",
                    "selection_revision": "sel-3",
                },
            },
            "cmd_forged_step_wrong_context",
            "idem_forged_step_wrong_context",
        ),
    ],
)
def test_forged_case_step_auto_command_cannot_bypass_active_case_lock(
    case_service: CaseExecutionService,
    payload_update: dict[str, Any],
    command_id: str,
    idempotency_key: str,
) -> None:
    case_service.submit_command(start_command("case_demo", seq=0))
    _finish_current_attempt(case_service, phase="failed")
    execution = case_service.reconcile("thr_case")
    assert execution is not None
    snapshot = case_service.thread_service.snapshot("thr_case")
    command = ThreadCommandFactory("thr_case", "run_case").send_auto(
        "forged step",
        expected_event_seq=snapshot.last_event_seq,
        command_id=command_id,
        idempotency_key=idempotency_key,
    )
    command["payload"].update({
        "case_execution_id": execution.case_execution_id,
        "step_ordinal": 1,
        **payload_update,
    })

    receipt = case_service.thread_service.submit_command(command)

    assert receipt.status == "rejected"
    assert receipt.rejection == "case_execution_active"


def test_forged_case_step_with_deterministic_identity_still_requires_trusted_instruction(
    case_service: CaseExecutionService,
) -> None:
    definition = _catalog().get("case_demo", "1")
    execution, context = _store_created_case_state(case_service, definition)
    command_id, idempotency_key = _step_identity(execution.case_execution_id, 1)
    snapshot = case_service.thread_service.snapshot("thr_case")
    command = ThreadCommandFactory("thr_case", "run_case").send_auto(
        "forged step",
        expected_event_seq=snapshot.last_event_seq,
        command_id=command_id,
        idempotency_key=idempotency_key,
    )
    command["payload"].update({
        "case_execution_id": execution.case_execution_id,
        "step_ordinal": 1,
        "case_context": context.to_document(),
        "step_instruction_digest": hashlib.sha256(b"forged step").hexdigest(),
    })

    receipt = case_service.thread_service.submit_command(command)

    assert receipt.status == "rejected"
    assert receipt.rejection == "case_execution_active"


def test_rejected_case_command_survives_restart_and_reserves_command_id() -> None:
    thread_service = _thread_service(model_id="other_model")
    first_service = CaseExecutionService(_catalog(), thread_service)
    command = start_command("case_demo", seq=0)

    first = first_service.submit_command(command)
    restarted = CaseExecutionService(_catalog(), thread_service)
    second = restarted.submit_command(command)
    reused_id = dict(command)
    reused_id.update({
        "idempotency_key": "idem_case_start_after_restart",
    })

    assert first.status == "rejected"
    assert first.rejection == "case_model_mismatch"
    assert second == first
    assert restarted.submit_command(reused_id).rejection == "command_id_conflict"


def test_case_projection_uses_registered_case_and_step_titles() -> None:
    service = CaseExecutionService(_catalog(), _thread_service(model_id="ieee39"))
    receipt = service.submit_command(start_command("case_demo", seq=0))
    assert receipt.status == "accepted"

    projection = service.thread_service.snapshot("thr_case").case_execution_snapshot

    assert projection is not None
    assert projection.display_name == "Demo case"
    assert tuple(step.title for step in projection.steps) == ("First", "Second")


def test_retry_rejects_a_target_that_is_not_the_blocked_case_step(
    case_service: CaseExecutionService,
) -> None:
    case_service.submit_command(start_command("case_demo", seq=0))
    execution = case_service.reconcile("thr_case")
    assert execution is not None
    blocked = replace(
        execution,
        status="blocked",
        steps=(
            replace(execution.steps[0], status="failed", error_code="attempt_failed"),
            execution.steps[1],
        ),
    )
    _store_case_state(case_service, blocked)
    snapshot = case_service.thread_service.snapshot("thr_case")
    command = ThreadCommandFactory("thr_case", "run_case").retry_case_step(
        blocked.case_execution_id,
        step_ordinal=1,
        failed_attempt_id="wrong_attempt",
        expected_event_seq=snapshot.last_event_seq,
        command_id="cmd_retry",
        idempotency_key="idem_retry",
    )

    receipt = case_service.submit_command(command)

    assert receipt.status == "rejected"
    assert receipt.rejection == "case_retry_target_mismatch"


def _store_case_state(service: CaseExecutionService, execution: CaseExecution) -> None:
    snapshot = service.thread_service.snapshot(execution.thread_id)
    service.thread_service.apply_application_transition(
        ThreadApplicationTransition(
            command={
                "schema": "capstone-command/1",
                "command_id": "cmd_case_state_test",
                "idempotency_key": "idem_case_state_test",
                "thread_id": execution.thread_id,
                "run_id": execution.run_id,
                "kind": "case_state_test",
                "expected_event_seq": snapshot.last_event_seq,
                "payload": {},
            },
            state={
                "case_execution": execution.to_document(),
                "context_locked": execution.status in {"created", "running", "waiting_step"},
            },
            events=(ApplicationEvent("case_state_test", {"case_execution_id": execution.case_execution_id}),),
        ),
    )


def _finish_current_attempt(service: CaseExecutionService, *, phase: str) -> str:
    claim = service.thread_service.claim_attempt("case-worker", lease_seconds=30)
    assert claim is not None
    service.thread_service.finish_attempt(claim, phase=phase, payload={"reason": "test"})
    return claim.attempt.attempt_id


def _store_created_case_state(
    service: CaseExecutionService,
    definition: CaseDefinition,
) -> tuple[CaseExecution, PinnedCaseContext]:
    snapshot = service.thread_service.snapshot("thr_case")
    context = PinnedCaseContext(
        model_context_id=snapshot.active_model_context.id,
        model_id=snapshot.active_model_context.model_id,
        model_revision=snapshot.active_model_context.model_revision,
        selection_revision=snapshot.active_model_context.selection_revision,
    )
    execution = SequentialBatchExecutor(definition).create_execution(
        definition,
        context,
        case_execution_id="case_exec_crash_window",
        thread_id=snapshot.thread_id,
        run_id=snapshot.run.run_id,
    )
    service.thread_service.apply_application_transition(
        ThreadApplicationTransition(
            command={
                "schema": "capstone-command/1",
                "command_id": "cmd_case_crash_window",
                "idempotency_key": "idem_case_crash_window",
                "thread_id": execution.thread_id,
                "run_id": execution.run_id,
                "kind": "case_state_test",
                "expected_event_seq": snapshot.last_event_seq,
                "payload": {},
            },
            state={
                "case_execution": execution.to_document(),
                "context_locked": True,
                "case_step_instruction_digests": [
                    {
                        "ordinal": step.ordinal,
                        "instruction_digest": step.instruction_digest,
                    }
                    for step in definition.steps
                ],
            },
            events=(ApplicationEvent("case_state_test", {"case_execution_id": execution.case_execution_id}),),
        ),
    )
    return execution, context


def _step_identity(execution_id: str, ordinal: int) -> tuple[str, str]:
    suffix = hashlib.sha256(f"{execution_id}:{ordinal}".encode()).hexdigest()[:24]
    return f"case_step_{suffix}", f"case_step_idem_{suffix}"


def _execution_id(command: Mapping[str, object]) -> str:
    raw = f"{command['thread_id']}:{command['run_id']}:{command['command_id']}".encode()
    return "case_exec_" + hashlib.sha256(raw).hexdigest()[:24]
