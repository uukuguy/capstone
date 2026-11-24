"""Host-owned execution of ordered, deterministic validation rules."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from hashlib import sha256
from importlib.resources import files
import json
from typing import Generic, Literal, TypeVar

T = TypeVar("T")
Status = Literal["accepted", "corrected", "rejected"]


class Stage(str, Enum):
    ANSWER_ADMISSION = "answer_check"
    ANSWER_PRESENTATION = "answer_presentation"
    RESULT_PRESENTATION = "result_presentation"


_TARGET_STAGES = {"answer.text": Stage.ANSWER_PRESENTATION, "result.table": Stage.RESULT_PRESENTATION}


@lru_cache(maxsize=1)
def published_rule_bundle_bytes() -> bytes:
    return files("capstone_agent").joinpath("resources", "harness-rules.json").read_bytes()


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
    action: Literal["correct", "report"] = "correct"


@dataclass(frozen=True, slots=True)
class RuleObservation:
    stage: Stage
    rule_id: str
    version: int
    status: str
    code: str
    count: int | None
    target: str | None = None
    bundle_version: int | None = None
    bundle_sha256: str | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {"stage": self.stage.value, "rule_id": self.rule_id,
                   "rule_version": self.version, "status": self.status, "code": self.code}
        if self.count is not None:
            payload["count"] = self.count
        if self.target is not None:
            payload["target"] = self.target
        if self.bundle_version is not None:
            payload.update(rule_bundle_version=self.bundle_version, rule_bundle_sha256=self.bundle_sha256)
        return payload


@dataclass(frozen=True, slots=True)
class RulePipeline(Generic[T]):
    stage: Stage
    rules: tuple[Rule[T], ...]
    target: str | None = None
    bundle_version: int | None = None
    bundle_sha256: str | None = None

    def __post_init__(self) -> None:
        if len({rule.rule_id for rule in self.rules}) != len(self.rules):
            raise ValueError("Duplicate validation rule identifier in stage")

    def run(self, value: T, *, observe: Callable[[RuleObservation], None],
            accept_correction: Callable[[T], bool] | None = None) -> Decision[T]:
        outcome = Decision.accepted(value)
        for rule in self.rules:
            try:
                decision = rule.check(outcome.value)
                if not isinstance(decision, Decision) or decision.status not in {
                    "accepted", "corrected", "rejected",
                } or (decision.status != "accepted" and not decision.code):
                    raise ValueError("Invalid validation rule decision")
            except Exception:
                observe(self._observation(rule, "rule_error", "validation_rule_error"))
                continue
            if decision.status == "accepted":
                continue
            corrects = decision.status == "corrected" and rule.action == "correct"
            if corrects and accept_correction is not None and not accept_correction(decision.value):
                observe(self._observation(rule, "finding", "correction_outside_contract"))
                continue
            observe(self._observation(
                rule, "corrected" if corrects else "finding", decision.code, decision.count
            ))
            if corrects:
                outcome = decision
        return outcome

    def _observation(self, rule: Rule[T], status: str, code: str,
                     count: int | None = None) -> RuleObservation:
        return RuleObservation(self.stage, rule.rule_id, rule.version, status, code, count,
                               self.target, self.bundle_version, self.bundle_sha256)


@dataclass(frozen=True, slots=True)
class RuleBundle(Generic[T]):
    version: int
    digest: str
    rules: tuple[Rule[T], ...]
    target: str = "answer.text"

    def pipeline(self) -> RulePipeline[T]:
        return RulePipeline(_TARGET_STAGES[self.target], self.rules,
                            self.target, self.version, self.digest)


def load_rule_bundle(raw: bytes, handlers: dict[str, Callable[[T], Decision[T]]], *,
                     target: str = "answer.text") -> RuleBundle[T]:
    if len(raw) > 64_000:
        raise ValueError("Validation rule bundle exceeds its size limit")
    doc = json.loads(raw)
    if (not isinstance(doc, dict) or set(doc) != {"schema", "version", "rules"}
            or doc["schema"] != "capstone-harness-rules/1"
            or type(doc["version"]) is not int or doc["version"] < 1
            or not isinstance(doc["rules"], list) or len(doc["rules"]) > 64):
        raise ValueError("Invalid validation rule bundle")
    rules: list[Rule[T]] = []
    identifiers = set()
    for entry in doc["rules"]:
        if (not isinstance(entry, dict) or set(entry) - {
                "id", "version", "stage", "target", "handler", "action", "enabled",
        } or not isinstance(entry.get("id"), str) or not 0 < len(entry["id"]) <= 128
                or type(entry.get("version")) is not int or entry["version"] < 1
                or not isinstance(entry.get("target"), str) or entry["target"] not in _TARGET_STAGES
                or entry.get("stage") != _TARGET_STAGES[entry["target"]].value
                or not isinstance(entry.get("handler"), str)
                or entry.get("action") not in ("correct", "report")
                or (entry["target"] == "result.table" and entry["action"] != "report")
                or type(entry.get("enabled", True)) is not bool):
            raise ValueError("Invalid validation rule")
        if entry["id"] in identifiers:
            raise ValueError("Duplicate validation rule identifier in bundle")
        identifiers.add(entry["id"])
        if entry["target"] != target:
            continue
        if entry["handler"] not in handlers:
            raise ValueError("Unknown validation rule handler")
        if entry.get("enabled", True):
            rules.append(Rule(entry["id"], entry["version"], handlers[entry["handler"]], entry["action"]))
    bundle = RuleBundle(doc["version"], sha256(raw).hexdigest(), tuple(rules), target)
    bundle.pipeline()
    return bundle
