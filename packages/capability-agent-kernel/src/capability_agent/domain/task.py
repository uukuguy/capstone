"""Neutral, bounded task resolution and conclusion contracts."""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Protocol, Callable, Mapping


def _text(value, limit, *, empty=False):
    if not isinstance(value, str) or len(value) > limit or (not empty and not value.strip()):
        raise ValueError("invalid task contract text")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate task contract key")
        result[key] = value
    return result


def _depth(value, depth=0):
    if depth > 8:
        raise ValueError("task requirement is too deep")
    if isinstance(value, dict):
        for key, child in value.items():
            _text(key, 128)
            _depth(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            _depth(child, depth + 1)


def _goal_id(value):
    _text(value, 64)
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", value):
        raise ValueError("invalid task goal identity")


@dataclass(frozen=True, slots=True)
class ResolvedTaskGoal:
    goal_id: str
    status: str
    requirement_json: str
    reason: str = ""
    binding_id: str = ""
    execution_required: bool = True

    def __post_init__(self):
        _goal_id(self.goal_id)
        _text(self.status, 32)
        _text(self.reason, 2048, empty=True)
        _text(self.binding_id, 128, empty=True)
        _text(self.requirement_json, 32768)
        if type(self.execution_required) is not bool:
            raise ValueError("invalid execution requirement flag")
        if self.status not in {"ready", "unsupported", "clarification", "uncertified", "general"}:
            raise ValueError("invalid task resolution status")
        try:
            document = json.loads(self.requirement_json, object_pairs_hook=_pairs)
            canonical = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
            _depth(document)
        except (RecursionError, TypeError, ValueError):
            raise ValueError("invalid bounded task requirement") from None
        if len(canonical.encode()) > 32768 or not isinstance(document, dict):
            raise ValueError("invalid bounded task requirement")
        object.__setattr__(self, "requirement_json", canonical)

    @property
    def requirement(self):
        return json.loads(self.requirement_json)

    def to_document(self):
        return {"goal_id": self.goal_id, "status": self.status, "requirement_json": self.requirement_json,
                "reason": self.reason, "binding_id": self.binding_id, "execution_required": self.execution_required}

    @classmethod
    def from_document(cls, document):
        if not isinstance(document, dict) or set(document) != set(cls.__dataclass_fields__):
            raise ValueError("invalid task resolution fields")
        return cls(**document)


@dataclass(frozen=True, slots=True)
class TaskConclusion:
    goal_id: str
    status: str
    text: str
    result_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    context_ref: str = ""
    revision_ref: str = ""
    scenario: str = ""

    def __post_init__(self):
        _goal_id(self.goal_id)
        _text(self.status, 32)
        _text(self.text, 8192)
        for name in ("context_ref", "revision_ref", "scenario"):
            _text(getattr(self, name), 512, empty=True)
        for name in ("result_refs", "evidence_refs"):
            values = getattr(self, name)
            if not isinstance(values, (list, tuple)) or len(values) > 128:
                raise ValueError("invalid conclusion references")
            for value in values:
                _text(value, 512)
            if len(set(values)) != len(values):
                raise ValueError("duplicate conclusion references")
            object.__setattr__(self, name, tuple(values))
        if self.status not in {"supported", "partial", "unresolved", "unsupported", "clarification", "general", "uncertified"}:
            raise ValueError("invalid conclusion status")
        if self.status == "general" and (self.result_refs or self.evidence_refs or self.context_ref or self.revision_ref or self.scenario):
            raise ValueError("general response cannot claim Authority binding")
        if self.status == "uncertified" and (self.result_refs or self.evidence_refs or self.context_ref or self.revision_ref or self.scenario):
            raise ValueError("uncertified goal cannot claim Authority coverage")
        if not self.goal_id or len(self.text) > 8192 or len(self.result_refs) > 128 or len(self.evidence_refs) > 128:
            raise ValueError("invalid bounded conclusion")

    def to_document(self):
        return {name: list(value) if isinstance(value, tuple) else value for name in self.__dataclass_fields__ for value in (getattr(self, name),)}

    @classmethod
    def from_document(cls, document):
        if not isinstance(document, dict) or set(document) != set(cls.__dataclass_fields__):
            raise ValueError("invalid task conclusion fields")
        return cls(**document)


class DomainTaskProvider(Protocol):
    schema: str
    schema_document: Mapping[str, object]

    def required_capabilities(self, payload: object) -> tuple[str, ...]: ...

    def authorizes_context(self, task: ResolvedTaskGoal, authority: object, context_ref: str, revision_ref: str) -> bool: ...

    def render_conclusion(self, conclusion: TaskConclusion, *, language: str, scale: str) -> str: ...

    def validate_semantic_binding(self, task: ResolvedTaskGoal, *, semantic_goal: Mapping[str, object],
                                  answer_policy: Mapping[str, str]) -> None: ...

    def resolve(self, goal_id: str, payload: object, *, context_ref: str, revision_ref: str,
                invoke: Callable[[str, dict[str, object]], dict[str, object]],
                semantic_goal: Mapping[str, object] | None = None,
                answer_policy: Mapping[str, str] | None = None) -> ResolvedTaskGoal: ...

    def conclude(self, task: ResolvedTaskGoal, *, authority: object, result_refs: tuple[str, ...],
                 evidence_refs: tuple[str, ...]) -> TaskConclusion: ...
