"""Engine-neutral request recognition contracts, with no execution authority.

Documents contain bounded JSON projections only. Serialized storage makes the
entire input immutable; each exported document is a fresh defensive copy.
Capability references describe needs and never enable or authorize a capability.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import json
import math
import time
from typing import Protocol, runtime_checkable


REQUEST_SCHEMA = "capstone-intent-request/1"
DECISION_SCHEMA = "capstone-intent-decision/1"
MAX_DOCUMENT_BYTES = 262_144
# Leave room for the Turn plan envelope in the 64 KiB public ledger event.
MAX_DECISION_BYTES = 32_768
MAX_ITEMS = 256
MAX_GOALS = 32
MAX_TEXT = 65_536
OPERATIONS = frozenset({
    "answer", "rewrite", "catalog_lookup", "external_lookup", "business_read", "business_execute",
})
RELATIONSHIPS = frozenset({"independent", "continuation", "supplement", "unclear"})


def _text(value: object, name: str, *, limit: int = MAX_TEXT, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{name} must be nonempty text of at most {limit} characters")


def _integer(value: object, name: str) -> None:
    if type(value) is not int or not 0 <= value <= 2**63 - 1:
        raise ValueError(f"{name} must be a nonnegative integer")


def _fields(document: object, required: set[str], optional: set[str] | frozenset[str] = frozenset()) -> dict:
    if type(document) is not dict or not required <= document.keys() or document.keys() - required - optional:
        raise ValueError("document fields do not match the intent contract")
    return document


def _items(value: object, name: str, *, limit: int = MAX_ITEMS) -> list:
    if type(value) is not list or len(value) > limit:
        raise ValueError(f"{name} must be a list of at most {limit} items")
    return value


def _json_value(value: object, depth: int = 0) -> None:
    if depth > 16:
        raise ValueError("intent document is too deeply nested")
    if value is None or type(value) is bool:
        return
    if type(value) is str:
        if len(value) > MAX_TEXT:
            raise ValueError("intent text exceeds the limit")
        return
    if type(value) is int:
        if abs(value) > 2**63 - 1:
            raise ValueError("intent integer exceeds the limit")
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) is list:
        for item in _items(value, "JSON array"):
            _json_value(item, depth + 1)
        return
    if type(value) is dict and len(value) <= MAX_ITEMS:
        for key, item in value.items():
            _text(key, "JSON key", limit=256)
            _json_value(item, depth + 1)
        return
    raise ValueError("intent documents must contain bounded finite JSON values")


def _canonical(document: dict, limit: int) -> str:
    _json_value(document)
    try:
        serialized = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        size = len(serialized.encode("utf-8"))
    except (ValueError, TypeError, UnicodeError) as exc:
        raise ValueError("invalid intent JSON document") from exc
    if size > limit:
        raise ValueError("intent document exceeds the byte limit")
    return serialized


def _parse(serialized: str, limit: int) -> dict:
    def unique_fields(pairs: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate intent JSON field")
            result[key] = value
        return result
    if type(serialized) is not str:
        raise ValueError("intent JSON must be text")
    try:
        if len(serialized) > limit or len(serialized.encode("utf-8")) > limit:
            raise ValueError("intent JSON exceeds the byte limit")
        value = json.loads(serialized, object_pairs_hook=unique_fields)
    except (UnicodeError, RecursionError, json.JSONDecodeError) as exc:
        raise ValueError("invalid intent JSON") from exc
    if type(value) is not dict:
        raise ValueError("intent JSON must be an object")
    return value


def _identities(entries: object, key: str) -> set[str]:
    identities = set()
    for entry in _items(entries, key):
        if type(entry) is not dict or key not in entry:
            raise ValueError(f"{key} is required")
        identity = entry[key]
        _text(identity, key, limit=256)
        if identity in identities:
            raise ValueError(f"duplicate {key}")
        identities.add(identity)
    return identities


@dataclass(frozen=True, slots=True, init=False)
class IntentRequest:
    _document_json: str = field(repr=False)

    def __init__(self, document: dict) -> None:
        serialized = _canonical(document, MAX_DOCUMENT_BYTES)
        value = _fields(json.loads(serialized), {
            "schema", "thread_id", "turn_id", "attempt_id", "instruction", "history_cutoff",
            "messages", "objects", "capabilities", "mode_hint",
        }, {"history_truncated"})
        if value["schema"] != REQUEST_SCHEMA:
            raise ValueError("unsupported intent request schema")
        for key in ("thread_id", "turn_id", "attempt_id"):
            _text(value[key], key, limit=256)
        _text(value["instruction"], "instruction")
        _integer(value["history_cutoff"], "history_cutoff")
        if "history_truncated" in value and type(value["history_truncated"]) is not bool:
            raise ValueError("history_truncated must be a boolean")
        _text(value["mode_hint"], "mode_hint", limit=256, nullable=True)
        _identities(value["messages"], "message_id")
        for message in value["messages"]:
            _fields(message, {"message_id", "role", "content", "turn_id", "attempt_id", "model_context_id", "status"},
                    {"thread_id", "event_seq"})
            if type(message["role"]) is not str or message["role"] not in {"user", "assistant"}:
                raise ValueError("history role must be user or assistant")
            _text(message["content"], "message content")
            _text(message["turn_id"], "message turn_id", limit=256)
            for key in ("attempt_id", "model_context_id"):
                _text(message[key], key, limit=256, nullable=True)
            _text(message["status"], "message status", limit=256)
            if message["status"] not in {"completed", "failed", "cancelled", "interrupted"}:
                raise ValueError("history message must have a terminal status")
            if message["role"] == "assistant" and message["status"] != "completed":
                raise ValueError("history assistant message must be completed")
            if "thread_id" in message and message["thread_id"] != value["thread_id"]:
                raise ValueError("history message belongs to a different thread")
            if "event_seq" in message:
                _integer(message["event_seq"], "message event_seq")
                if message["event_seq"] > value["history_cutoff"]:
                    raise ValueError("history message exceeds the cutoff")
        _identities(value["objects"], "object_id")
        object_metadata = {"model_id", "model_revision", "implementation_family", "display_name"}
        for entry in value["objects"]:
            _fields(entry, {"object_id"}, object_metadata)
            for key in object_metadata & entry.keys():
                _text(entry[key], f"object {key}", limit=256)
        _identities(value["capabilities"], "capability_id")
        for capability in value["capabilities"]:
            _fields(capability, {"capability_id", "available", "enabled"}, {
                "display_name", "description", "registered", "implementation_families",
            })
            for key in ("available", "enabled"):
                if type(capability.get(key)) is not bool:
                    raise ValueError(f"capability {key} must be a boolean")
            if "registered" in capability and type(capability["registered"]) is not bool:
                raise ValueError("capability registered must be a boolean")
            for key, limit in (("display_name", 256), ("description", 8192)):
                if key in capability:
                    _text(capability[key], f"capability {key}", limit=limit)
            if "implementation_families" in capability:
                for family in _items(capability["implementation_families"], "implementation families", limit=32):
                    _text(family, "implementation family", limit=256)
        object.__setattr__(self, "_document_json", serialized)

    @classmethod
    def from_document(cls, document: dict) -> IntentRequest:
        return cls(document)

    @classmethod
    def from_json(cls, serialized: str) -> IntentRequest:
        return cls.from_document(_parse(serialized, MAX_DOCUMENT_BYTES))

    def to_document(self) -> dict:
        return json.loads(self._document_json)

    @property
    def request_id(self) -> str:
        return self.to_document()["attempt_id"]


@dataclass(frozen=True, slots=True, init=False)
class IntentDecision:
    """Ordered goals with explicit dependencies and conservative legacy order.

    ``depends_on=[]`` makes a goal independent. If ``depends_on`` is absent,
    the goal depends on every preceding goal for legacy document compatibility.
    Only prior goal identities are valid; this excludes forward edges and cycles.
    """

    _document_json: str = field(repr=False)

    def __init__(self, document: dict, request: IntentRequest) -> None:
        if not isinstance(request, IntentRequest):
            raise ValueError("decision requires a validated intent request")
        serialized = _canonical(document, MAX_DECISION_BYTES)
        value = _fields(json.loads(serialized), {
            "schema", "attempt_id", "history_cutoff", "relationship", "goals", "clarification",
        })
        source = request.to_document()
        if value["schema"] != DECISION_SCHEMA:
            raise ValueError("unsupported intent decision schema")
        _integer(value["history_cutoff"], "history_cutoff")
        if value["attempt_id"] != source["attempt_id"] or value["history_cutoff"] != source["history_cutoff"]:
            raise ValueError("intent decision does not match its request identity and cutoff")
        if type(value["relationship"]) is not str or value["relationship"] not in RELATIONSHIPS:
            raise ValueError("invalid intent relationship")
        _text(value["clarification"], "clarification", limit=8192, nullable=True)
        goals = _items(value["goals"], "goals", limit=MAX_GOALS)
        if not goals:
            raise ValueError("intent decision must contain a goal")
        _identities(goals, "goal_id")
        allowed = {
            "message_refs": _identities(source["messages"], "message_id"),
            "object_refs": _identities(source["objects"], "object_id"),
            "capability_refs": _identities(source["capabilities"], "capability_id"),
        }
        prior_goals: set[str] = set()
        for goal in goals:
            _fields(goal, {"goal_id", "description", "operation", "message_refs", "object_refs",
                           "capability_refs", "missing_requirements"}, {"depends_on"})
            if "depends_on" in goal:
                dependencies = _items(goal["depends_on"], "goal dependencies", limit=MAX_GOALS)
                for dependency in dependencies:
                    _text(dependency, "goal dependency", limit=256)
                    if dependency not in prior_goals:
                        raise ValueError("intent dependencies must reference prior goals")
                if len(set(dependencies)) != len(dependencies):
                    raise ValueError("duplicate intent dependency")
            _text(goal["description"], "goal description", limit=8192)
            if type(goal["operation"]) is not str or goal["operation"] not in OPERATIONS:
                raise ValueError("invalid intent operation")
            for key, identities in allowed.items():
                refs = _items(goal[key], key)
                for ref in refs:
                    _text(ref, key, limit=256)
                    if ref not in identities:
                        raise ValueError(f"unknown intent {key} reference")
                if len(set(refs)) != len(refs):
                    raise ValueError(f"duplicate intent {key} reference")
            for requirement in _items(goal["missing_requirements"], "missing requirements", limit=32):
                _text(requirement, "missing requirement", limit=2048)
            prior_goals.add(goal["goal_id"])
        object.__setattr__(self, "_document_json", serialized)

    @classmethod
    def from_document(cls, document: dict, request: IntentRequest) -> IntentDecision:
        return cls(document, request)

    @classmethod
    def from_json(cls, serialized: str, request: IntentRequest) -> IntentDecision:
        return cls.from_document(_parse(serialized, MAX_DECISION_BYTES), request)

    def to_document(self) -> dict:
        return json.loads(self._document_json)

    @property
    def requires_business(self) -> bool:
        return any(goal["operation"] in {"business_read", "business_execute"}
                   for goal in self.to_document()["goals"])

    @property
    def execution_goals(self) -> tuple[dict, ...]:
        """Return defensive goal copies whose requirements and dependencies hold.

        This projection describes readiness only. Capability authorization and
        authority admission remain application and Domain Pack responsibilities.
        A global clarification blocks execution of every goal.
        """
        document = self.to_document()
        if document["clarification"] is not None:
            return ()
        prior_goals: list[str] = []
        executable: set[str] = set()
        ready: list[dict] = []
        for goal in document["goals"]:
            dependencies = goal.get("depends_on", prior_goals)
            if not goal["missing_requirements"] and all(ref in executable for ref in dependencies):
                ready.append(goal)
                executable.add(goal["goal_id"])
            prior_goals.append(goal["goal_id"])
        return tuple(ready)


@dataclass(frozen=True, slots=True)
class IntentEngineIdentity:
    engine: str
    model: str
    config_revision: str

    def __post_init__(self) -> None:
        for key in ("engine", "model", "config_revision"):
            _text(getattr(self, key), key, limit=256)

    def to_document(self) -> dict:
        return {"schema": "capstone-intent-engine/1", "engine": self.engine,
                "model": self.model, "config_revision": self.config_revision}


@dataclass(frozen=True, slots=True)
class NodeControl:
    """A monotonic deadline and application cancellation/lease check callback."""

    check: Callable[[], None]
    deadline: float

    def __post_init__(self) -> None:
        if not callable(self.check):
            raise ValueError("node control check must be callable")
        if type(self.deadline) not in {int, float} or not math.isfinite(self.deadline):
            raise ValueError("node control deadline must be finite")

    def checkpoint(self) -> None:
        if time.monotonic() >= self.deadline:
            raise TimeoutError("intent recognition deadline expired")
        self.check()
        if time.monotonic() >= self.deadline:
            raise TimeoutError("intent recognition deadline expired")


@runtime_checkable
class IntentRecognizer(Protocol):
    @property
    def identity(self) -> IntentEngineIdentity: ...

    def recognize(self, request: IntentRequest, control: NodeControl) -> IntentDecision: ...
