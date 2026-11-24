"""Host-owned execution of ordered, deterministic validation rules."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Generic, Literal, TypeVar

T = TypeVar("T")
Status = Literal["accepted", "corrected", "rejected"]


class Stage(str, Enum):
    ANSWER_ADMISSION = "answer_check"
    ANSWER_PRESENTATION = "answer_presentation"


@dataclass(frozen=True, slots=True)
class Decision(Generic[T]):
    value: T
    status: Status = "accepted"
    code: str | None = None
    count: int | None = None

    @classmethod
    def accepted(cls, value: T) -> "Decision[T]":
        return cls(value)

    @classmethod
    def corrected(cls, value: T, code: str, *, count: int | None = None) -> "Decision[T]":
        return cls(value, "corrected", code, count)

    @classmethod
    def rejected(cls, value: T, code: str) -> "Decision[T]":
        return cls(value, "rejected", code)


@dataclass(frozen=True, slots=True)
class Rule(Generic[T]):
    rule_id: str
    version: int
    check: Callable[[T], Decision[T]]


@dataclass(frozen=True, slots=True)
class RuleObservation:
    stage: Stage
    rule_id: str
    version: int
    status: Status
    code: str
    count: int | None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {"stage": self.stage.value, "rule_id": self.rule_id,
                   "rule_version": self.version, "status": self.status, "code": self.code}
        return payload if self.count is None else {**payload, "count": self.count}


@dataclass(frozen=True, slots=True)
class RulePipeline(Generic[T]):
    stage: Stage
    rules: tuple[Rule[T], ...]

    def __post_init__(self) -> None:
        if len({rule.rule_id for rule in self.rules}) != len(self.rules):
            raise ValueError("Duplicate validation rule identifier in stage")

    def run(self, value: T, *, observe: Callable[[RuleObservation], None]) -> Decision[T]:
        outcome = Decision.accepted(value)
        for rule in self.rules:
            decision = rule.check(outcome.value)
            if decision.status == "accepted":
                outcome = Decision(decision.value, outcome.status, outcome.code, outcome.count)
                continue
            if decision.status not in {"corrected", "rejected"} or not decision.code:
                raise ValueError("Invalid validation rule decision")
            observe(RuleObservation(self.stage, rule.rule_id, rule.version,
                                    decision.status, decision.code, decision.count))
            if decision.status == "rejected":
                return decision
            outcome = decision
        return outcome
