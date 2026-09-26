"""Domain-neutral application context contracts.

The application context is deliberately smaller than any domain's state model.
It owns lifecycle and lineage metadata while preserving domain state as an
opaque, binding-qualified envelope.  Values crossing this boundary are JSON
values and are frozen recursively so a caller cannot mutate an accepted
snapshot through an alias to its input object.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from hashlib import sha256
from typing import Any, Literal, TypeAlias

from pydantic import ConfigDict, Field, field_validator, model_validator

from capability_agent.trajectory.canonical import canonical_json_bytes
from capability_agent.trajectory.events import StrictFrozenModel


APPLICATION_CONTEXT_SCHEMA = "application-context/1.0"
APPLICATION_CONTEXT_EVENT_SCHEMA = "application-context-event/1.0"
PORTABLE_ID_PATTERN = re.compile(r"^[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$")


class ContextModelError(ValueError):
    """Raised when a context model contains an unsafe JSON value."""


class _FrozenDict(dict[str, Any]):
    """A JSON-compatible mapping that rejects all in-place mutations."""

    def _immutable(self, *args: object, **kwargs: object) -> None:
        raise TypeError("mapping is immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    __ior__ = _immutable  # type: ignore[assignment]
    clear = _immutable
    pop = _immutable
    popitem = _immutable  # type: ignore[assignment]
    setdefault = _immutable  # type: ignore[assignment]
    update = _immutable  # type: ignore[assignment]


def _freeze_json(value: Any, *, label: str = "context", max_depth: int = 64) -> Any:
    """Validate and recursively freeze a JSON value.

    Only exact JSON scalar types, ordinary mappings with string keys, and
    list/tuple containers are accepted.  The active-container set detects
    cycles without rejecting repeated references to independent containers.
    """

    try:
        return _freeze_json_value(value, label=label, active=set(), depth=0, max_depth=max_depth)
    except ContextModelError:
        raise
    except Exception:
        raise ContextModelError(f"{label} contains an unsafe JSON value") from None


def _freeze_json_value(
    value: Any,
    *,
    label: str,
    active: set[int],
    depth: int,
    max_depth: int,
) -> Any:
    if depth > max_depth:
        raise ContextModelError(f"{label} nesting exceeds the supported depth")
    if isinstance(value, Mapping):
        identity = id(value)
        if identity in active:
            raise ContextModelError(f"{label} contains a container cycle")
        active.add(identity)
        try:
            frozen: dict[str, Any] = {}
            for key, item in value.items():
                if type(key) is not str:
                    raise ContextModelError(f"{label} mapping keys must be strings")
                frozen[key] = _freeze_json_value(
                    item,
                    label=label,
                    active=active,
                    depth=depth + 1,
                    max_depth=max_depth,
                )
            return _FrozenDict(frozen)
        finally:
            active.remove(identity)
    if isinstance(value, list | tuple):
        identity = id(value)
        if identity in active:
            raise ContextModelError(f"{label} contains a container cycle")
        active.add(identity)
        try:
            return tuple(
                _freeze_json_value(
                    item,
                    label=label,
                    active=active,
                    depth=depth + 1,
                    max_depth=max_depth,
                )
                for item in value
            )
        finally:
            active.remove(identity)
    if value is None or type(value) in {str, bool, int}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ContextModelError(f"{label} float values must be finite")
        return value
    raise ContextModelError(f"{label} contains an unsupported JSON value")


def _freeze_model_json_fields(model: Any, fields: tuple[str, ...], *, label: str) -> None:
    for field_name in fields:
        value = getattr(model, field_name)
        if value is not None:
            object.__setattr__(
                model,
                field_name,
                _freeze_json(value, label=f"{label}.{field_name}"),
            )


class _ContextModel(StrictFrozenModel):
    """Strict immutable Pydantic base for context-owned models."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        hide_input_in_errors=True,
    )


class CoreContext(_ContextModel):
    """Lifecycle state owned by the application Kernel."""

    input: Mapping[str, Any] = Field(default_factory=dict)
    runtime: Mapping[str, Any] = Field(default_factory=dict)
    questions: tuple[Mapping[str, Any], ...] = ()
    turns: tuple[Mapping[str, Any], ...] = ()
    active_turn: Mapping[str, Any] | None = None
    decisions: tuple[Mapping[str, Any], ...] = ()
    diagnostics: tuple[Mapping[str, Any], ...] = ()
    consumed_refs: tuple[str, ...] = ()
    produced_refs: tuple[str, ...] = ()
    result_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    answer_lifecycle: Mapping[str, Any] = Field(default_factory=dict)

    @field_validator(
        "input",
        "runtime",
        "questions",
        "turns",
        "active_turn",
        "decisions",
        "diagnostics",
        "consumed_refs",
        "produced_refs",
        "result_refs",
        "evidence_refs",
        "answer_lifecycle",
        mode="before",
    )
    @classmethod
    def validate_json_values(cls, value: Any) -> Any:
        if value is None:
            return value
        return _freeze_json(value, label="core")

    @model_validator(mode="after")
    def freeze_values(self) -> "CoreContext":
        _freeze_model_json_fields(
            self,
            (
                "input",
                "runtime",
                "questions",
                "turns",
                "active_turn",
                "decisions",
                "diagnostics",
                "consumed_refs",
                "produced_refs",
                "result_refs",
                "evidence_refs",
                "answer_lifecycle",
            ),
            label="core",
        )
        return self


class DomainStateEnvelope(_ContextModel):
    """Opaque state owned by one declared application binding."""

    schema_id: str = Field(min_length=1)
    revision: int = Field(default=0, ge=0)
    state: Mapping[str, Any] = Field(default_factory=dict)

    @field_validator("state", mode="before")
    @classmethod
    def validate_state_value(cls, value: Any) -> Any:
        if value is None:
            return value
        return _freeze_json(value, label="domain state")

    @model_validator(mode="after")
    def freeze_values(self) -> "DomainStateEnvelope":
        object.__setattr__(self, "state", _freeze_json(self.state, label="domain state"))
        return self


EventType: TypeAlias = Literal[
    "analysis.started",
    "analysis.completed",
    "analysis.failed",
    "application.started",
    "application.completed",
    "application.failed",
    "application.instruction.accepted",
    "turn.started",
    "turn.completed",
    "turn.failed",
    "tool.observation.recorded",
    "tool.failed",
    "result.registered",
    "evidence.registered",
    "fact.verified",
    "decision.recorded",
    "diagnostic.recorded",
    "audit.diagnostic.recorded",
    "limitation.recorded",
    "limitation.resolved",
    "reference.consumed",
    "reference.produced",
    "answer.started",
    "answer.submitted",
    "answer.rejected",
    "domain.state.projected",
]


class ContextEventDraft(_ContextModel):
    """A validated, closed-set context transition request."""

    event_type: EventType
    binding_id: str | None = None
    turn_id: str | None = Field(default=None, min_length=1)
    capability: str | None = Field(default=None, min_length=1)
    trace_sequence: int | None = Field(default=None, ge=1)
    timestamp: str | None = Field(default=None, min_length=1)
    payload: Mapping[str, Any] = Field(default_factory=dict)

    @field_validator("payload", mode="before")
    @classmethod
    def validate_payload_value(cls, value: Any) -> Any:
        if value is None:
            return value
        return _freeze_json(value, label="context event payload")

    @field_validator("binding_id")
    @classmethod
    def validate_binding_id(cls, value: str | None) -> str | None:
        if value is not None and not PORTABLE_ID_PATTERN.fullmatch(value):
            raise ValueError("binding_id must be a portable identifier")
        return value

    @model_validator(mode="after")
    def freeze_values(self) -> "ContextEventDraft":
        object.__setattr__(
            self,
            "payload",
            _freeze_json(self.payload, label="context event payload"),
        )
        return self


class ContextEvent(_ContextModel):
    """Durable context event with revision and state-hash lineage."""

    schema_version: Literal["application-context-event/1.0"] = APPLICATION_CONTEXT_EVENT_SCHEMA
    run_id: str = Field(min_length=1)
    sequence: int = Field(ge=1)
    event_type: EventType
    binding_id: str | None = None
    turn_id: str | None = Field(default=None, min_length=1)
    capability: str | None = Field(default=None, min_length=1)
    trace_sequence: int | None = Field(default=None, ge=1)
    timestamp: str | None = Field(default=None, min_length=1)
    payload: Mapping[str, Any] = Field(default_factory=dict)
    previous_revision: int = Field(ge=0)
    previous_state_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    next_revision: int = Field(ge=1)
    next_state_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("payload", mode="before")
    @classmethod
    def validate_payload_value(cls, value: Any) -> Any:
        if value is None:
            return value
        return _freeze_json(value, label="context event payload")

    @field_validator("binding_id")
    @classmethod
    def validate_binding_id(cls, value: str | None) -> str | None:
        if value is not None and not PORTABLE_ID_PATTERN.fullmatch(value):
            raise ValueError("binding_id must be a portable identifier")
        return value

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, value: str) -> str:
        if not PORTABLE_ID_PATTERN.fullmatch(value):
            raise ValueError("run_id must be a portable identifier")
        return value

    @model_validator(mode="after")
    def validate_lineage_and_freeze(self) -> "ContextEvent":
        if self.sequence != self.next_revision:
            raise ValueError("event sequence must equal next_revision")
        if self.next_revision != self.previous_revision + 1:
            raise ValueError("event revisions must advance by one")
        object.__setattr__(
            self,
            "payload",
            _freeze_json(self.payload, label="context event payload"),
        )
        return self


class ApplicationContext(_ContextModel):
    """Materialized generic application state for one run."""

    schema_version: Literal["application-context/1.0"] = APPLICATION_CONTEXT_SCHEMA
    run_id: str = Field(min_length=1)
    revision: int = Field(ge=0)
    state_hash: str = Field(default="", pattern=r"^(?:[0-9a-f]{64})?$")
    status: Literal["initializing", "running", "completed", "failed"]
    core: CoreContext = Field(default_factory=CoreContext)
    domains: Mapping[str, DomainStateEnvelope] = Field(default_factory=dict)

    @field_validator("domains", mode="before")
    @classmethod
    def validate_domains_value(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        try:
            return dict(value.items())
        except Exception:
            raise ContextModelError("context domains contains an unsafe mapping") from None

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, value: str) -> str:
        if not PORTABLE_ID_PATTERN.fullmatch(value):
            raise ValueError("run_id must be a portable identifier")
        return value

    @model_validator(mode="after")
    def validate_domains_and_freeze(self) -> "ApplicationContext":
        domains: dict[str, DomainStateEnvelope] = {}
        for binding_id, envelope in self.domains.items():
            if not isinstance(binding_id, str) or not PORTABLE_ID_PATTERN.fullmatch(binding_id):
                raise ValueError("domain binding identifiers must be portable")
            if not isinstance(envelope, DomainStateEnvelope):
                raise TypeError("domain state must use DomainStateEnvelope")
            domains[binding_id] = envelope
        object.__setattr__(self, "domains", _FrozenDict(domains))
        return self

    @classmethod
    def initial(
        cls,
        *,
        run_id: str,
        domains: Mapping[str, str | DomainStateEnvelope],
        core: CoreContext | Mapping[str, Any] | None = None,
        status: Literal["initializing", "running", "completed", "failed"] = "initializing",
    ) -> "ApplicationContext":
        envelopes: dict[str, DomainStateEnvelope] = {}
        try:
            domain_items = tuple(domains.items())
        except Exception:
            raise ContextModelError("context domains contains an unsafe mapping") from None
        for binding_id, value in domain_items:
            if isinstance(value, str):
                value = DomainStateEnvelope(schema_id=value)
            elif not isinstance(value, DomainStateEnvelope):
                raise TypeError("domains must map binding IDs to schema IDs or envelopes")
            if value.revision != 0:
                raise ValueError("initial domain state revisions must be zero")
            envelopes[binding_id] = value
        core_model = (
            core
            if isinstance(core, CoreContext)
            else CoreContext.model_validate({} if core is None else core)
        )
        context = cls(
            run_id=run_id,
            revision=0,
            state_hash="",
            status=status,
            core=core_model,
            domains=envelopes,
        )
        return context.model_copy(update={"state_hash": canonical_state_hash(context)})


def canonical_state_hash(context: ApplicationContext) -> str:
    """Hash the canonical context while excluding its self-referential hash."""

    payload = context.model_dump(mode="json")
    payload.pop("state_hash", None)
    return sha256(canonical_json_bytes(payload)).hexdigest()


__all__ = [
    "APPLICATION_CONTEXT_EVENT_SCHEMA",
    "APPLICATION_CONTEXT_SCHEMA",
    "ApplicationContext",
    "ContextEvent",
    "ContextEventDraft",
    "ContextModelError",
    "CoreContext",
    "DomainStateEnvelope",
    "EventType",
    "PORTABLE_ID_PATTERN",
    "canonical_state_hash",
]
