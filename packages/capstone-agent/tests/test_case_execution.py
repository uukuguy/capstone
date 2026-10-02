from __future__ import annotations

import pytest
from typing import Literal
from dataclasses import replace

from capstone_agent.case_definition import CaseDefinition, CaseStepDefinition
from capstone_agent.case_execution import (
    CaseExecution,
    CaseStepState,
    ExecutionStatus,
    PinnedCaseContext,
    SequentialBatchExecutor,
    StepOutcome,
)


def execution_fixture(status: ExecutionStatus = "waiting_step") -> CaseExecution:
    return CaseExecution(
        case_execution_id="exec-1",
        thread_id="thread-1",
        run_id="run-1",
        case_id="case-1",
        case_revision="case:sha256:revision",
        strategy_id="sequential_batch",
        strategy_version=1,
        context=PinnedCaseContext(
            model_context_id="context-1",
            model_id="model-1",
            model_revision="model-revision-1",
            selection_revision="selection-revision-1",
        ),
        steps=(
            CaseStepState(
                ordinal=1,
                turn_id="turn-1",
                latest_attempt_id="attempt-1",
                status="running",
                answer=None,
                result_refs=(),
                evidence_refs=(),
                duration_ms=None,
                error_code=None,
            ),
            CaseStepState(
                ordinal=2,
                turn_id=None,
                latest_attempt_id=None,
                status="pending",
                answer=None,
                result_refs=(),
                evidence_refs=(),
                duration_ms=None,
                error_code=None,
            ),
        ),
        status=status,
        current_step=1,
    )


def definitions() -> tuple[CaseStepDefinition, ...]:
    return (
        CaseStepDefinition(1, "First", "first instruction", "digest-1"),
        CaseStepDefinition(2, "Second", "second instruction", "digest-2"),
    )


def _case_definition(case_id: str, steps: tuple[CaseStepDefinition, ...]) -> CaseDefinition:
    return CaseDefinition(
        case_id=case_id,
        case_version="1",
        case_revision=f"revision-{case_id}",
        display_name=case_id,
        description="test case",
        model_ids=("model-1",),
        steps=steps,
    )


def test_strategy_waits_for_committed_step() -> None:
    execution = execution_fixture()
    decision = SequentialBatchExecutor(definitions()).advance(execution, StepOutcome.running())
    assert decision.next_step is None
    assert decision.execution == execution


def test_successful_step_advances_to_next_definition() -> None:
    execution = execution_fixture()
    decision = SequentialBatchExecutor(definitions()).advance(
        execution,
        StepOutcome.completed(
            attempt_id="attempt-1",
            answer="first answer",
            result_refs=("result-1",),
            evidence_refs=("evidence-1",),
            duration_ms=17,
        ),
    )
    assert decision.next_step == definitions()[1]
    assert decision.execution.status == "waiting_step"
    assert decision.execution.current_step == 2
    assert decision.execution.steps[0].status == "completed"
    assert decision.execution.steps[0].answer == "first answer"
    assert decision.execution.steps[0].latest_attempt_id == "attempt-1"
    assert decision.execution.steps[1].status == "pending"


def test_final_success_completes_execution() -> None:
    execution = SequentialBatchExecutor(definitions()).advance(
        execution_fixture(),
        StepOutcome.completed(attempt_id="attempt-1", answer="first answer"),
    ).execution.with_current_step(2, turn_id="turn-2", attempt_id="attempt-2")
    decision = SequentialBatchExecutor(definitions()).advance(
        execution,
        StepOutcome.completed(attempt_id="attempt-2", answer="second answer"),
    )
    assert decision.next_step is None
    assert decision.execution.status == "completed"
    assert decision.execution.current_step is None
    assert decision.execution.steps[0] == execution.steps[0]
    assert decision.execution.steps[1].status == "completed"


@pytest.mark.parametrize("phase", ["failed", "cancelled", "interrupted"])
def test_terminal_non_success_blocks_without_handoff(phase: Literal["failed", "cancelled", "interrupted"]) -> None:
    execution = execution_fixture()
    outcome = StepOutcome(
        status=phase,
        attempt_id="attempt-1",
        answer="partial answer",
        result_refs=("partial-result",),
        evidence_refs=("partial-evidence",),
        error_code="attempt_failed",
    )
    decision = SequentialBatchExecutor(definitions()).advance(execution, outcome)
    assert decision.next_step is None
    assert decision.execution.status == "blocked"
    step = decision.execution.steps[0]
    assert step.status == phase
    assert step.answer is None
    assert step.result_refs == ()
    assert step.evidence_refs == ()


@pytest.mark.parametrize("phase", ["failed", "cancelled", "interrupted"])
def test_blocked_attempt_cannot_complete_without_retry(
    phase: Literal["failed", "cancelled", "interrupted"],
) -> None:
    execution = execution_fixture()
    executor = SequentialBatchExecutor(definitions())
    blocked = executor.advance(execution, StepOutcome(status=phase, attempt_id="attempt-1")).execution
    with pytest.raises(ValueError, match="retry|attempt"):
        executor.advance(blocked, StepOutcome.completed(attempt_id="attempt-1", answer="late"))


def test_running_attempt_cannot_be_overwritten() -> None:
    with pytest.raises(ValueError, match="running"):
        execution_fixture().with_current_step(1, turn_id="turn-new", attempt_id="attempt-new")


def test_retry_must_use_a_new_attempt_id() -> None:
    executor = SequentialBatchExecutor(definitions())
    blocked = executor.advance(
        execution_fixture(), StepOutcome.failed(attempt_id="attempt-1")
    ).execution
    with pytest.raises(ValueError, match="new Attempt"):
        blocked.with_current_step(1, turn_id="turn-1", attempt_id="attempt-1")


def test_executor_definitions_are_immutable_and_fully_pinned() -> None:
    first = definitions()
    second = (
        CaseStepDefinition(1, "Different", "different instruction", "digest-x"),
        CaseStepDefinition(2, "Second", "second instruction", "digest-2"),
    )
    executor = SequentialBatchExecutor(first)
    execution = executor.create_execution(
        _case_definition("case-1", first),
        execution_fixture().context,
        case_execution_id="exec-created",
        thread_id="thread-1",
        run_id="run-1",
    )
    with pytest.raises(ValueError, match="definition"):
        executor.create_execution(
            _case_definition("case-1", second),
            execution_fixture().context,
            case_execution_id="exec-other",
            thread_id="thread-1",
            run_id="run-1",
        )
    with pytest.raises(ValueError, match="definition"):
        executor.advance(
            replace(execution, case_revision="revision-other"),
            StepOutcome.completed(attempt_id="attempt-1"),
        )


def test_durable_non_completed_step_cannot_retain_outputs() -> None:
    with pytest.raises(ValueError, match="non-completed"):
        CaseStepState(
            ordinal=1,
            turn_id="turn-1",
            latest_attempt_id="attempt-1",
            status="running",
            answer="stale",
            result_refs=(),
            evidence_refs=(),
            duration_ms=None,
            error_code=None,
        )


def test_terminal_execution_rejects_unrelated_outcome_attempt() -> None:
    execution = SequentialBatchExecutor(definitions()).advance(
        execution_fixture(), StepOutcome.completed(attempt_id="attempt-1")
    ).execution.with_current_step(2, turn_id="turn-2", attempt_id="attempt-2")
    completed = SequentialBatchExecutor(definitions()).advance(
        execution, StepOutcome.completed(attempt_id="attempt-2")
    ).execution
    with pytest.raises(ValueError, match="attempt"):
        SequentialBatchExecutor(definitions()).advance(
            completed, StepOutcome.completed(attempt_id="unrelated")
        )
    with pytest.raises(ValueError, match="attempt"):
        SequentialBatchExecutor(definitions()).advance(
            completed, StepOutcome.completed(attempt_id="attempt-1")
        )


def test_completed_step_is_immutable_and_terminal_attempt_must_match() -> None:
    execution = execution_fixture()
    completed = SequentialBatchExecutor(definitions()).advance(
        execution,
        StepOutcome.completed(attempt_id="attempt-1", answer="answer"),
    ).execution
    with pytest.raises(ValueError, match="attempt"):
        SequentialBatchExecutor(definitions()).advance(
            completed,
            StepOutcome.completed(attempt_id="other-attempt", answer="changed"),
        )
    advanced = SequentialBatchExecutor(definitions()).advance(
        completed.with_current_step(2, turn_id="turn-2", attempt_id="attempt-2"),
        StepOutcome.completed(attempt_id="attempt-2", answer="second"),
    )
    assert advanced.execution.steps[0] == completed.steps[0]


def test_execution_document_round_trip_is_bounded() -> None:
    execution = execution_fixture()
    restored = CaseExecution.from_document(execution.to_document())
    assert restored == execution
    document = execution.to_document()
    document["steps"][0]["result_refs"] = ["x" * 513]
    with pytest.raises(ValueError, match="result"):
        CaseExecution.from_document(document)
