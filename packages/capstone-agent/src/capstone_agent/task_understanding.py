"""Application-owned semantic task proposals, without completion authority."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
import re


SCHEMA = "capstone-task-understanding/1"
MAX_DECISION_BYTES = 24_576
MAX_INSTRUCTION_CHARS = 16_384
MAX_REFERENCE_CHARS = 512
MAX_HISTORY_CUTOFF = 2**63 - 1
_ID = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")


def _text(value: object, limit: int = 1024, *, empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > limit or (not empty and not value.strip()):
        raise ValueError("task text is invalid")
    return value


def _fields(value: object, names: set[str]) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != names:
        raise ValueError("task fields are invalid")
    return value


def _choice(value: object, options: set[str]) -> str:
    text = _text(value, 64)
    if text not in options:
        raise ValueError("task choice is invalid")
    return text


def _texts(value: object, *, required: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > 16 or (required and not value):
        raise ValueError("task list is invalid")
    result = tuple(_text(item, 512) for item in value)
    if len(set(result)) != len(result):
        raise ValueError("task list contains duplicates")
    return result


@dataclass(frozen=True, slots=True)
class TaskRequest:
    thread_id: str
    turn_id: str
    attempt_id: str
    instruction: str
    history_cutoff: int
    model_context_id: str
    model_id: str
    model_revision: str

    def __post_init__(self) -> None:
        for name in ("thread_id", "turn_id", "attempt_id", "model_context_id", "model_id", "model_revision"):
            _text(getattr(self, name), MAX_REFERENCE_CHARS)
        _text(self.instruction, MAX_INSTRUCTION_CHARS)
        if type(self.history_cutoff) is not int or not 0 <= self.history_cutoff <= MAX_HISTORY_CUTOFF:
            raise ValueError("task history cutoff is invalid")

    def to_document(self) -> dict[str, object]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}

    @classmethod
    def from_document(cls, document: object) -> TaskRequest:
        value = _fields(document, set(cls.__dataclass_fields__))
        cutoff = value["history_cutoff"]
        if type(cutoff) is not int:
            raise ValueError("task history cutoff is invalid")
        return cls(thread_id=_text(value["thread_id"], MAX_REFERENCE_CHARS),
                   turn_id=_text(value["turn_id"], MAX_REFERENCE_CHARS),
                   attempt_id=_text(value["attempt_id"], MAX_REFERENCE_CHARS),
                   instruction=_text(value["instruction"], MAX_INSTRUCTION_CHARS),
                   history_cutoff=cutoff,
                   model_context_id=_text(value["model_context_id"], MAX_REFERENCE_CHARS),
                   model_id=_text(value["model_id"], MAX_REFERENCE_CHARS),
                   model_revision=_text(value["model_revision"], MAX_REFERENCE_CHARS))


@dataclass(frozen=True, slots=True)
class SemanticGoal:
    id: str
    purpose: str
    subject: str
    scope: str
    scenario: str
    change: str | None
    conclusion: str
    measure: str | None
    obligations: tuple[str, ...]
    missing_requirements: tuple[str, ...]

    def __post_init__(self) -> None:
        if not _ID.fullmatch(_text(self.id, 64)):
            raise ValueError("task goal identity is invalid")
        _text(self.purpose)
        _text(self.subject)
        _choice(self.scope, {"unspecified", "subset", "full"})
        _choice(self.scenario, {"none", "baseline", "changed", "contingency", "comparison"})
        _choice(self.conclusion, {"description", "impact", "limit", "comparison", "ranking"})
        if self.change is not None:
            _text(self.change)
        if self.scenario in {"changed", "contingency", "comparison"} and self.change is None:
            raise ValueError("task scenario requirement is missing")
        if self.measure is not None:
            _text(self.measure, 256)
        for name in ("obligations", "missing_requirements"):
            values = getattr(self, name)
            if not isinstance(values, (tuple, list)):
                raise ValueError("task list is invalid")
            object.__setattr__(self, name, _texts(list(values), required=name == "obligations"))

    @classmethod
    def from_document(cls, document: object) -> SemanticGoal:
        value = _fields(document, set(cls.__dataclass_fields__))
        goal_id = _text(value["id"], 64)
        if not _ID.fullmatch(goal_id):
            raise ValueError("task goal identity is invalid")
        scenario = _choice(value["scenario"], {"none", "baseline", "changed", "contingency", "comparison"})
        change = None if value["change"] is None else _text(value["change"], 1024)
        if scenario in {"changed", "contingency", "comparison"} and change is None:
            raise ValueError("task scenario requirement is missing")
        return cls(goal_id, _text(value["purpose"]), _text(value["subject"]),
                   _choice(value["scope"], {"unspecified", "subset", "full"}), scenario, change,
                   _choice(value["conclusion"], {"description", "impact", "limit", "comparison", "ranking"}),
                   None if value["measure"] is None else _text(value["measure"], 256),
                   _texts(value["obligations"], required=True), _texts(value["missing_requirements"]))

    def to_document(self) -> dict[str, object]:
        return {name: list(value) if isinstance(value, tuple) else value
                for name in self.__dataclass_fields__ for value in (getattr(self, name),)}


@dataclass(frozen=True, slots=True)
class AnswerPolicy:
    language: str
    scale: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", _text(self.language, 32)):
            raise ValueError("task language is invalid")
        _choice(self.scale, {"concise", "standard", "detailed"})

    @classmethod
    def from_document(cls, document: object) -> AnswerPolicy:
        value = _fields(document, {"language", "scale"})
        language = _text(value["language"], 32)
        if not re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", language):
            raise ValueError("task language is invalid")
        return cls(language, _choice(value["scale"], {"concise", "standard", "detailed"}))


@dataclass(frozen=True, slots=True)
class TaskUnderstanding:
    request: TaskRequest
    recognizer: str
    goals: tuple[SemanticGoal, ...]
    answer_policy: AnswerPolicy

    def __post_init__(self) -> None:
        if not isinstance(self.request, TaskRequest) or not isinstance(self.answer_policy, AnswerPolicy):
            raise ValueError("task contract is invalid")
        _text(self.recognizer, 256)
        if not isinstance(self.goals, (tuple, list)) or not 1 <= len(self.goals) <= 8:
            raise ValueError("task goal count is invalid")
        if any(not isinstance(goal, SemanticGoal) for goal in self.goals):
            raise ValueError("task goal is invalid")
        if len({goal.id for goal in self.goals}) != len(self.goals):
            raise ValueError("task goal identities are not unique")
        object.__setattr__(self, "goals", tuple(self.goals))
        try:
            size = len(json.dumps(self.to_document(), ensure_ascii=False, allow_nan=False).encode("utf-8"))
        except (TypeError, ValueError, RecursionError):
            raise ValueError("task contract is not bounded JSON") from None
        if size > MAX_DECISION_BYTES:
            raise ValueError("task contract is too large")

    def to_document(self) -> dict[str, object]:
        return {"schema": SCHEMA, "request": self.request.to_document(), "recognizer": self.recognizer,
                "goals": [goal.to_document() for goal in self.goals],
                "answer_policy": {"language": self.answer_policy.language, "scale": self.answer_policy.scale}}

    @classmethod
    def from_document(cls, document: object, *, expected_request: TaskRequest | None = None) -> TaskUnderstanding:
        value = _fields(document, {"schema", "request", "recognizer", "goals", "answer_policy"})
        request = TaskRequest.from_document(value["request"])
        if expected_request is not None and request != expected_request:
            raise ValueError("task request binding does not match")
        return recognize_decision(request, {key: value[key] for key in ("schema", "goals", "answer_policy")},
                                  recognizer=_text(value["recognizer"], 256))


def recognize_decision(request: TaskRequest, proposal: object, *, recognizer: str) -> TaskUnderstanding:
    """Validate model semantics; request references come exclusively from the host."""
    if not isinstance(request, TaskRequest):
        raise ValueError("task request is invalid")
    try:
        encoded = json.dumps(proposal, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, RecursionError):
        raise ValueError("task decision is not bounded JSON") from None
    if len(encoded.encode("utf-8")) > MAX_DECISION_BYTES:
        raise ValueError("task decision is too large")
    value = _fields(proposal, {"schema", "goals", "answer_policy"})
    if value["schema"] != SCHEMA:
        raise ValueError("task schema is invalid")
    items = value["goals"]
    if not isinstance(items, list) or not 1 <= len(items) <= 8:
        raise ValueError("task goal count is invalid")
    goals = tuple(SemanticGoal.from_document(item) for item in items)
    if len({goal.id for goal in goals}) != len(goals):
        raise ValueError("task goal identities are not unique")
    return TaskUnderstanding(request, _text(recognizer, 256), goals, AnswerPolicy.from_document(value["answer_policy"]))
