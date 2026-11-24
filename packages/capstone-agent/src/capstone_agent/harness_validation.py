"""Host-owned execution of ordered, deterministic validation rules."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from hashlib import sha256
from importlib.resources import files
from inspect import getsourcefile
import json
from pathlib import Path
import re
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
    source: bytes | None = None

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
    bundle = RuleBundle(doc["version"], sha256(raw).hexdigest(), tuple(rules), target, raw)
    bundle.pipeline()
    return bundle


_REPLAY_LIMIT = 4_000_000


@lru_cache(maxsize=64)
def _source_digest(path: str) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def _processor_identity(bundle: RuleBundle) -> list[list[str]]:
    identity = [['engine', _source_digest(__file__)]]
    for rule in bundle.rules:
        path = getsourcefile(rule.check)
        if path is None:
            raise ValueError('Validation handler source is unavailable')
        identity.append([rule.rule_id, _source_digest(path)])
    return identity


def _replay_key(thread_id: str, attempt_id: str, digest: str) -> str:
    if (any(not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value) for value in (thread_id, attempt_id))
            or not re.fullmatch(r'[a-f0-9]{64}', digest)):
        raise ValueError('Invalid validation replay identity')
    return f'diagnostics/validation/{thread_id}/{attempt_id}/{digest}.json'


def archive_rule_input(objects, thread_id: str, attempt_id: str,
                       bundle: RuleBundle[T], value: T, *, answer_limit: int | None = None) -> str:
    if bundle.source is None or sha256(bundle.source).hexdigest() != bundle.digest:
        raise ValueError('Validation bundle source is unavailable')
    body = json.dumps({'schema': 'capstone-validation-replay/1', 'target': bundle.target,
                       'bundle': bundle.source.decode(), 'processors': _processor_identity(bundle),
                       'answer_limit': answer_limit, 'input': value},
                      ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
    if len(body) > _REPLAY_LIMIT:
        raise ValueError('Validation replay input exceeds its size limit')
    digest = sha256(body).hexdigest()
    objects.put(_replay_key(thread_id, attempt_id, digest), body, 'application/json')
    return digest


def replay_rule_input(objects, thread_id: str, attempt_id: str, digest: str,
                      bundle: RuleBundle[T], *, candidate: RuleBundle[T] | None = None,
                      observe: Callable[[RuleObservation], None] = lambda _: None,
                      accept_correction: Callable[[T], bool] | None = None) -> Decision[T]:
    """Run trusted installed rules on a private archived input without changing delivery."""
    body = objects.get(_replay_key(thread_id, attempt_id, digest), _REPLAY_LIMIT)
    if len(body) > _REPLAY_LIMIT or sha256(body).hexdigest() != digest:
        raise ValueError('Validation replay digest mismatch')
    archived = json.loads(body)
    if (archived['schema'] != 'capstone-validation-replay/1'
            or archived['target'] != bundle.target
            or archived['bundle'].encode() != bundle.source
            or archived['processors'] != _processor_identity(bundle)
            or candidate is not None and candidate.target != bundle.target):
        raise ValueError('Validation replay bundle mismatch')
    pipeline = (candidate or bundle).pipeline()
    if accept_correction is None and archived['answer_limit'] is not None:
        limit = archived['answer_limit']
        accept_correction = lambda value: isinstance(value, str) and bool(value.strip()) and len(value.encode()) <= limit
    return pipeline.run(archived['input'], observe=observe, accept_correction=accept_correction)
