"""Immutable Case execution state and the M6 sequential strategy.

The objects in this module are application state only.  They do not execute
Turns or talk to an authority; callers persist the returned state and dispatch
the returned next step through the public Thread APIs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any, Literal, Self

from .case_definition import CaseDefinition, CaseStepDefinition


OutcomeStatus = Literal["running", "completed", "failed", "cancelled", "interrupted"]
ExecutionStatus = Literal[
    "created", "running", "waiting_step", "blocked", "completed", "cancelled"
]
StepStatus = Literal[
    "pending", "running", "completed", "failed", "cancelled", "interrupted"
]

_OUTCOME_STATUSES = frozenset({"running", "completed", "failed", "cancelled", "interrupted"})
_EXECUTION_STATUSES = frozenset(
    {"created", "running", "waiting_step", "blocked", "completed", "cancelled"}
)
_STEP_STATUSES = frozenset(
    {"pending", "running", "completed", "failed", "cancelled", "interrupted"}
)
_MAX_ID_CHARS = 256
_MAX_REVISION_CHARS = 512
_MAX_ANSWER_CHARS = 65536
_MAX_ERROR_CHARS = 256
_MAX_REF_CHARS = 512
_MAX_REFS = 128
_MAX_STEPS = 32


def _text(value: Any, *, field: str, max_chars: int = _MAX_ID_CHARS, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > max_chars or (not allow_empty and not value.strip()):
        raise ValueError(f"{field} is invalid")
    return value


def _optional_text(value: Any, *, field: str, max_chars: int) -> str | None:
    if value is None:
        return None
    return _text(value, field=field, max_chars=max_chars)


def _refs(value: Sequence[str], *, field: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > _MAX_REFS:
        raise ValueError(f"{field} is invalid")
    result: list[str] = []
    for index, ref in enumerate(value):
        result.append(_text(ref, field=f"{field}[{index}]", max_chars=_MAX_REF_CHARS))
    if len(set(result)) != len(result):
        raise ValueError(f"{field} contains duplicates")
    return tuple(result)


def _mapping(value: Any, *, field: str, fields: set[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    unknown = set(value) - fields
    missing = fields - set(value)
    if unknown or missing:
        details = ", ".join(sorted(unknown or missing))
        raise ValueError(f"{field} has invalid fields: {details}")
    return value


def _duration(value: Any, *, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > 86_400_000:
        raise ValueError(f"{field} is invalid")
    return value


@dataclass(frozen=True, slots=True)
class PinnedCaseContext:
    """Model and profile selection revisions captured at Case start."""

    model_context_id: str
    model_id: str
    model_revision: str
    selection_revision: str

    def __post_init__(self) -> None:
        _text(self.model_context_id, field="model_context_id")
        _text(self.model_id, field="model_id")
        _text(self.model_revision, field="model_revision", max_chars=_MAX_REVISION_CHARS)
        _text(self.selection_revision, field="selection_revision", max_chars=_MAX_REVISION_CHARS)

    def to_document(self) -> dict[str, str]:
        return {
            "model_context_id": self.model_context_id,
            "model_id": self.model_id,
            "model_revision": self.model_revision,
            "selection_revision": self.selection_revision,
        }

    @classmethod
    def from_document(cls, value: Any) -> Self:
        document = _mapping(
            value,
            field="context",
            fields={"model_context_id", "model_id", "model_revision", "selection_revision"},
        )
        return cls(
            model_context_id=document["model_context_id"],
            model_id=document["model_id"],
            model_revision=document["model_revision"],
            selection_revision=document["selection_revision"],
        )


@dataclass(frozen=True, slots=True)
class CaseStepState:
    """Durable state for one ordered Case step."""

    ordinal: int
    turn_id: str | None
    latest_attempt_id: str | None
    status: StepStatus
    answer: str | None
    result_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    duration_ms: int | None
    error_code: str | None

    def __post_init__(self) -> None:
        if isinstance(self.ordinal, bool) or not isinstance(self.ordinal, int) or not 1 <= self.ordinal <= _MAX_STEPS:
            raise ValueError("ordinal is invalid")
        _optional_text(self.turn_id, field="turn_id", max_chars=_MAX_ID_CHARS)
        _optional_text(self.latest_attempt_id, field="latest_attempt_id", max_chars=_MAX_ID_CHARS)
        if self.status not in _STEP_STATUSES:
            raise ValueError("status is invalid")
        _optional_text(self.answer, field="answer", max_chars=_MAX_ANSWER_CHARS)
        if not isinstance(self.result_refs, tuple):
            raise ValueError("result_refs must be a tuple")
        if not isinstance(self.evidence_refs, tuple):
            raise ValueError("evidence_refs must be a tuple")
        _refs(self.result_refs, field="result_refs")
        _refs(self.evidence_refs, field="evidence_refs")
        _duration(self.duration_ms, field="duration_ms")
        _optional_text(self.error_code, field="error_code", max_chars=_MAX_ERROR_CHARS)
        if self.status != "completed" and (
            self.answer is not None or self.result_refs or self.evidence_refs
        ):
            raise ValueError("non-completed step cannot retain answer or references")

    def to_document(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "turn_id": self.turn_id,
            "latest_attempt_id": self.latest_attempt_id,
            "status": self.status,
            "answer": self.answer,
            "result_refs": list(self.result_refs),
            "evidence_refs": list(self.evidence_refs),
            "duration_ms": self.duration_ms,
            "error_code": self.error_code,
        }

    @classmethod
    def from_document(cls, value: Any) -> Self:
        document = _mapping(
            value,
            field="step",
            fields={
                "ordinal", "turn_id", "latest_attempt_id", "status", "answer",
                "result_refs", "evidence_refs", "duration_ms", "error_code",
            },
        )
        raw_result_refs = document["result_refs"]
        raw_evidence_refs = document["evidence_refs"]
        if not isinstance(raw_result_refs, list) or not isinstance(raw_evidence_refs, list):
            raise ValueError("step references are invalid")
        return cls(
            ordinal=document["ordinal"],
            turn_id=document["turn_id"],
            latest_attempt_id=document["latest_attempt_id"],
            status=document["status"],
            answer=document["answer"],
            result_refs=tuple(raw_result_refs),
            evidence_refs=tuple(raw_evidence_refs),
            duration_ms=document["duration_ms"],
            error_code=document["error_code"],
        )


@dataclass(frozen=True, slots=True)
class CaseExecution:
    """Immutable application state for one Case run."""

    case_execution_id: str
    thread_id: str
    run_id: str
    case_id: str
    case_revision: str
    strategy_id: str
    strategy_version: int
    context: PinnedCaseContext
    steps: tuple[CaseStepState, ...]
    status: ExecutionStatus
    current_step: int | None

    def __post_init__(self) -> None:
        for name in ("case_execution_id", "thread_id", "run_id", "case_id", "strategy_id"):
            _text(getattr(self, name), field=name)
        _text(self.case_revision, field="case_revision", max_chars=_MAX_REVISION_CHARS)
        if isinstance(self.strategy_version, bool) or not isinstance(self.strategy_version, int) or self.strategy_version < 1:
            raise ValueError("strategy_version is invalid")
        if not isinstance(self.context, PinnedCaseContext):
            raise ValueError("context is invalid")
        if not isinstance(self.steps, tuple) or not 1 <= len(self.steps) <= _MAX_STEPS:
            raise ValueError("steps are invalid")
        expected = tuple(range(1, len(self.steps) + 1))
        if tuple(step.ordinal for step in self.steps) != expected:
            raise ValueError("steps must have contiguous ordinals")
        if self.status not in _EXECUTION_STATUSES:
            raise ValueError("status is invalid")
        if self.current_step is not None and (
            isinstance(self.current_step, bool)
            or not isinstance(self.current_step, int)
            or not 1 <= self.current_step <= len(self.steps)
        ):
            raise ValueError("current_step is invalid")
        if self.status in {"completed", "cancelled"} and self.current_step is not None:
            raise ValueError("terminal execution cannot have a current step")

    def to_document(self) -> dict[str, Any]:
        return {
            "case_execution_id": self.case_execution_id,
            "thread_id": self.thread_id,
            "run_id": self.run_id,
            "case_id": self.case_id,
            "case_revision": self.case_revision,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "context": self.context.to_document(),
            "steps": [step.to_document() for step in self.steps],
            "status": self.status,
            "current_step": self.current_step,
        }

    @classmethod
    def from_document(cls, value: Any) -> Self:
        document = _mapping(
            value,
            field="case_execution",
            fields={
                "case_execution_id", "thread_id", "run_id", "case_id", "case_revision",
                "strategy_id", "strategy_version", "context", "steps", "status", "current_step",
            },
        )
        raw_steps = document["steps"]
        if not isinstance(raw_steps, list):
            raise ValueError("steps are invalid")
        return cls(
            case_execution_id=document["case_execution_id"],
            thread_id=document["thread_id"],
            run_id=document["run_id"],
            case_id=document["case_id"],
            case_revision=document["case_revision"],
            strategy_id=document["strategy_id"],
            strategy_version=document["strategy_version"],
            context=PinnedCaseContext.from_document(document["context"]),
            steps=tuple(CaseStepState.from_document(step) for step in raw_steps),
            status=document["status"],
            current_step=document["current_step"],
        )

    def with_current_step(self, ordinal: int, *, turn_id: str | None, attempt_id: str | None) -> Self:
        """Return a copy with a newly dispatched step attempt."""
        if self.current_step != ordinal:
            raise ValueError("current step does not match ordinal")
        if not turn_id or not attempt_id:
            raise ValueError("turn_id and attempt_id are required")
        current = self.steps[ordinal - 1]
        if current.status == "completed":
            raise ValueError("completed step is immutable")
        if current.status == "running":
            raise ValueError("running attempt cannot be overwritten")
        if current.latest_attempt_id == attempt_id:
            raise ValueError("retry requires a new Attempt")
        steps = list(self.steps)
        steps[ordinal - 1] = replace(
            current,
            turn_id=turn_id,
            latest_attempt_id=attempt_id,
            status="running",
            answer=None,
            result_refs=(),
            evidence_refs=(),
            duration_ms=None,
            error_code=None,
        )
        return replace(self, steps=tuple(steps), status="waiting_step")


@dataclass(frozen=True, slots=True)
class StepOutcome:
    """A worker's observation of the current Attempt."""

    status: OutcomeStatus
    attempt_id: str
    answer: str | None = None
    result_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    duration_ms: int | None = None
    error_code: str | None = None

    def __post_init__(self) -> None:
        if self.status not in _OUTCOME_STATUSES:
            raise ValueError("status is invalid")
        if self.status == "running":
            if self.attempt_id and len(self.attempt_id) > _MAX_ID_CHARS:
                raise ValueError("attempt_id is invalid")
        else:
            _text(self.attempt_id, field="attempt_id")
        _optional_text(self.answer, field="answer", max_chars=_MAX_ANSWER_CHARS)
        if not isinstance(self.result_refs, tuple) or not isinstance(self.evidence_refs, tuple):
            raise ValueError("outcome references must be tuples")
        _refs(self.result_refs, field="result_refs")
        _refs(self.evidence_refs, field="evidence_refs")
        _duration(self.duration_ms, field="duration_ms")
        _optional_text(self.error_code, field="error_code", max_chars=_MAX_ERROR_CHARS)
        if self.status != "completed" and (self.answer is not None or self.result_refs or self.evidence_refs):
            object.__setattr__(self, "answer", None)
            object.__setattr__(self, "result_refs", ())
            object.__setattr__(self, "evidence_refs", ())

    @classmethod
    def running(cls, attempt_id: str = "") -> Self:
        return cls(status="running", attempt_id=attempt_id)

    @classmethod
    def completed(
        cls,
        attempt_id: str,
        answer: str | None = None,
        result_refs: tuple[str, ...] = (),
        evidence_refs: tuple[str, ...] = (),
        duration_ms: int | None = None,
    ) -> Self:
        return cls("completed", attempt_id, answer, result_refs, evidence_refs, duration_ms)

    @classmethod
    def failed(
        cls,
        attempt_id: str,
        error_code: str | None = None,
        duration_ms: int | None = None,
    ) -> Self:
        return cls("failed", attempt_id, duration_ms=duration_ms, error_code=error_code)

    @classmethod
    def cancelled(
        cls,
        attempt_id: str,
        error_code: str | None = None,
        duration_ms: int | None = None,
    ) -> Self:
        return cls("cancelled", attempt_id, duration_ms=duration_ms, error_code=error_code)

    @classmethod
    def interrupted(
        cls,
        attempt_id: str,
        error_code: str | None = None,
        duration_ms: int | None = None,
    ) -> Self:
        return cls("interrupted", attempt_id, duration_ms=duration_ms, error_code=error_code)

    def to_document(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "attempt_id": self.attempt_id,
            "answer": self.answer,
            "result_refs": list(self.result_refs),
            "evidence_refs": list(self.evidence_refs),
            "duration_ms": self.duration_ms,
            "error_code": self.error_code,
        }

    @classmethod
    def from_document(cls, value: Any) -> Self:
        document = _mapping(
            value,
            field="step_outcome",
            fields={
                "status", "attempt_id", "answer", "result_refs", "evidence_refs",
                "duration_ms", "error_code",
            },
        )
        raw_result_refs = document["result_refs"]
        raw_evidence_refs = document["evidence_refs"]
        if not isinstance(raw_result_refs, list) or not isinstance(raw_evidence_refs, list):
            raise ValueError("outcome references are invalid")
        return cls(
            status=document["status"],
            attempt_id=document["attempt_id"],
            answer=document["answer"],
            result_refs=tuple(raw_result_refs),
            evidence_refs=tuple(raw_evidence_refs),
            duration_ms=document["duration_ms"],
            error_code=document["error_code"],
        )


@dataclass(frozen=True, slots=True)
class StrategyDecision:
    execution: CaseExecution
    next_step: CaseStepDefinition | None


class CaseExecutionStrategy:
    """Protocol-like base for pure Case execution strategies."""

    strategy_id = "sequential_batch"
    strategy_version = 1

    def advance(self, execution: CaseExecution, outcome: StepOutcome) -> StrategyDecision:
        raise NotImplementedError


@dataclass(frozen=True, slots=True, init=False)
class SequentialBatchExecutor(CaseExecutionStrategy):
    """Advance one ordered Case step after its terminal Attempt is committed."""

    _definitions: tuple[CaseStepDefinition, ...] = field(init=False, repr=False, compare=False)
    _case_id: str | None = field(init=False, repr=False, compare=False)
    _case_revision: str | None = field(init=False, repr=False, compare=False)

    def __init__(
        self,
        definition: CaseDefinition | Sequence[CaseStepDefinition] | None = None,
        *,
        steps: Sequence[CaseStepDefinition] | None = None,
        case_definition: CaseDefinition | None = None,
    ) -> None:
        supplied = [item for item in (definition, steps, case_definition) if item is not None]
        if len(supplied) > 1:
            raise ValueError("provide one step definition source")
        if steps is not None:
            definition = steps
        elif case_definition is not None:
            definition = case_definition
        pinned_case_id: str | None = None
        pinned_case_revision: str | None = None
        if isinstance(definition, CaseDefinition):
            definitions = tuple(definition.steps)
            pinned_case_id = definition.case_id
            pinned_case_revision = definition.case_revision
        elif definition is None:
            definitions = ()
        else:
            definitions = tuple(definition)
        if len(definitions) > _MAX_STEPS or any(not isinstance(step, CaseStepDefinition) for step in definitions):
            raise ValueError("step definitions are invalid")
        if definitions and tuple(step.ordinal for step in definitions) != tuple(range(1, len(definitions) + 1)):
            raise ValueError("step definitions must have contiguous ordinals")
        object.__setattr__(self, "_definitions", definitions)
        object.__setattr__(self, "_case_id", pinned_case_id)
        object.__setattr__(self, "_case_revision", pinned_case_revision)

    def create_execution(
        self,
        definition: CaseDefinition,
        context: PinnedCaseContext,
        *,
        case_execution_id: str,
        thread_id: str,
        run_id: str,
    ) -> CaseExecution:
        """Create the bounded initial state; Turn creation remains a caller concern."""
        if not isinstance(definition, CaseDefinition):
            raise ValueError("CaseDefinition is required")
        definition_steps = tuple(definition.steps)
        if self._definitions and self._definitions != definition_steps:
            raise ValueError("strategy definitions do not match CaseDefinition")
        if self._case_id is not None and (
            self._case_id != definition.case_id or self._case_revision != definition.case_revision
        ):
            raise ValueError("strategy CaseDefinition is already pinned")
        if not self._definitions:
            object.__setattr__(self, "_definitions", definition_steps)
        object.__setattr__(self, "_case_id", definition.case_id)
        object.__setattr__(self, "_case_revision", definition.case_revision)
        steps = tuple(
            CaseStepState(
                ordinal=step.ordinal,
                turn_id=None,
                latest_attempt_id=None,
                status="pending",
                answer=None,
                result_refs=(),
                evidence_refs=(),
                duration_ms=None,
                error_code=None,
            )
            for step in definition.steps
        )
        return CaseExecution(
            case_execution_id=case_execution_id,
            thread_id=thread_id,
            run_id=run_id,
            case_id=definition.case_id,
            case_revision=definition.case_revision,
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            context=context,
            steps=steps,
            status="created",
            current_step=1,
        )

    def advance(self, execution: CaseExecution, outcome: StepOutcome) -> StrategyDecision:
        if self._case_id is None or self._case_revision is None or not self._definitions:
            raise ValueError("CaseDefinition and ordered step definitions must be pinned before advance")
        if execution.strategy_id != self.strategy_id or execution.strategy_version != self.strategy_version:
            raise ValueError("execution strategy is not supported")
        if self._definitions and tuple(step.ordinal for step in execution.steps) != tuple(
            step.ordinal for step in self._definitions
        ):
            raise ValueError("step definitions do not match execution")
        if self._case_id is not None and (
            execution.case_id != self._case_id or execution.case_revision != self._case_revision
        ):
            raise ValueError("execution CaseDefinition does not match pinned definition")
        if outcome.status == "running":
            return StrategyDecision(execution, None)
        if execution.status in {"completed", "cancelled"}:
            terminal_attempt_id = next(
                (step.latest_attempt_id for step in reversed(execution.steps) if step.latest_attempt_id),
                None,
            )
            if outcome.attempt_id != terminal_attempt_id:
                raise ValueError("terminal outcome attempt does not match execution")
            return StrategyDecision(execution, None)
        if execution.current_step is None:
            raise ValueError("execution has no current step")
        index = execution.current_step - 1
        current = execution.steps[index]
        if current.status == "completed":
            if outcome.status == "completed" and current.latest_attempt_id == outcome.attempt_id:
                return StrategyDecision(execution, None)
            raise ValueError("completed step is immutable or attempt does not match")
        if current.status in {"failed", "cancelled", "interrupted"}:
            raise ValueError("retry requires a new Attempt")
        if current.latest_attempt_id != outcome.attempt_id:
            raise ValueError("terminal outcome attempt does not match current step")
        updated = replace(
            current,
            status=outcome.status,
            answer=outcome.answer if outcome.status == "completed" else None,
            result_refs=outcome.result_refs if outcome.status == "completed" else (),
            evidence_refs=outcome.evidence_refs if outcome.status == "completed" else (),
            duration_ms=outcome.duration_ms,
            error_code=outcome.error_code,
        )
        steps = list(execution.steps)
        steps[index] = updated
        if outcome.status != "completed":
            return StrategyDecision(replace(execution, steps=tuple(steps), status="blocked"), None)
        next_ordinal = execution.current_step + 1
        if next_ordinal > len(steps):
            return StrategyDecision(
                replace(execution, steps=tuple(steps), status="completed", current_step=None),
                None,
            )
        next_step = self._step_definition(next_ordinal)
        return StrategyDecision(
            replace(execution, steps=tuple(steps), status="waiting_step", current_step=next_ordinal),
            next_step,
        )

    def _step_definition(self, ordinal: int) -> CaseStepDefinition:
        if not self._definitions:
            raise ValueError("step definitions are required to advance")
        try:
            return self._definitions[ordinal - 1]
        except IndexError as exc:
            raise ValueError("step definition does not match execution") from exc


__all__ = [
    "CaseExecution",
    "CaseExecutionStrategy",
    "CaseStepState",
    "PinnedCaseContext",
    "SequentialBatchExecutor",
    "StepOutcome",
    "StrategyDecision",
]
