"""Pure reduction of generic application context events."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import ValidationError

from capability_agent.application.context_models import (
    ApplicationContext,
    ContextEventDraft,
    CoreContext,
    DomainStateEnvelope,
    canonical_state_hash,
)


class ContextTransitionError(RuntimeError):
    """Raised when a context transition violates a Kernel invariant."""


_TERMINAL_STATUSES = frozenset({"completed", "failed"})
_KNOWN_EVENT_TYPES = frozenset(
    {
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
    }
)
_RESERVED_STATE_KEYS = frozenset(
    {
        "core",
        "domains",
        "schema_id",
        "revision",
        "state_hash",
    }
)
_OWNER_KEYS = frozenset(
    {
        "binding_id",
        "owner_binding_id",
        "source_binding_id",
        "target_binding_id",
    }
)
_OWNER_LIST_KEYS = frozenset(
    {
        "binding_ids",
        "owner_binding_ids",
        "source_binding_ids",
        "target_binding_ids",
    }
)
ContextStatus = Literal["initializing", "running", "completed", "failed"]


def initial_context(
    run_id: str,
    domains: Mapping[str, str | DomainStateEnvelope],
    *,
    core: CoreContext | Mapping[str, Any] | None = None,
) -> ApplicationContext:
    """Build the revision-zero context used before the first lifecycle event."""

    return ApplicationContext.initial(run_id=run_id, domains=domains, core=core)


def reduce_context(
    context: ApplicationContext, draft: ContextEventDraft
) -> ApplicationContext:
    """Apply one validated draft and return a new immutable context snapshot."""

    if context.state_hash != canonical_state_hash(context):
        raise ContextTransitionError("context state hash mismatch")
    if context.status in _TERMINAL_STATUSES:
        raise ContextTransitionError("terminal context cannot be mutated")
    if draft.event_type not in _KNOWN_EVENT_TYPES:
        raise ContextTransitionError("unsupported context event type")

    try:
        next_core, next_domains, next_status = _apply_event(context, draft)
        next_context = ApplicationContext(
            run_id=context.run_id,
            revision=context.revision + 1,
            state_hash="",
            status=next_status,
            core=next_core,
            domains=next_domains,
        )
        return next_context.model_copy(
            update={"state_hash": canonical_state_hash(next_context)}
        )
    except ContextTransitionError:
        raise
    except (TypeError, ValueError, ValidationError):
        raise ContextTransitionError("invalid context transition") from None


def _apply_event(
    context: ApplicationContext, draft: ContextEventDraft
) -> tuple[CoreContext, Mapping[str, DomainStateEnvelope], ContextStatus]:
    event_type = draft.event_type
    payload = _payload(draft)

    if event_type in {"analysis.started", "application.started"}:
        return _start_context(context, payload)
    if event_type in {"analysis.completed", "application.completed"}:
        return context.core, context.domains, "completed"
    if event_type in {"analysis.failed", "application.failed"}:
        return _append_diagnostic(context.core, event_type, payload), context.domains, "failed"
    if event_type == "application.instruction.accepted":
        return _accept_instruction(context.core, payload), context.domains, context.status
    if event_type == "domain.state.projected":
        return _project_domain_state(context, draft, payload)
    if event_type in {"diagnostic.recorded", "audit.diagnostic.recorded", "tool.failed"}:
        return _append_diagnostic(context.core, event_type, payload), context.domains, context.status
    if event_type in {"decision.recorded"}:
        return _append_core_record(context.core, "decisions", payload), context.domains, context.status
    if event_type in {
        "turn.started",
        "turn.completed",
        "turn.failed",
    }:
        return _apply_turn_event(context.core, draft, payload), context.domains, "running"
    if event_type == "answer.submitted":
        return _set_answer_lifecycle(context.core, payload), context.domains, context.status
    if event_type == "answer.started":
        return _set_answer_lifecycle(context.core, payload), context.domains, context.status
    if event_type == "answer.rejected":
        return _set_answer_lifecycle(context.core, payload), context.domains, context.status
    if event_type in {"reference.consumed", "reference.produced"}:
        field_name = "consumed_refs" if event_type.endswith("consumed") else "produced_refs"
        return _append_references(context.core, field_name, payload), context.domains, context.status
    if event_type in {
        "tool.observation.recorded",
        "result.registered",
        "evidence.registered",
        "fact.verified",
        "limitation.recorded",
        "limitation.resolved",
    }:
        # These records remain opaque to the generic Kernel.  The event is
        # retained in the lifecycle diagnostics until a domain projector adds
        # a binding-specific state delta.
        return _append_core_record(context.core, "diagnostics", payload), context.domains, context.status
    raise ContextTransitionError("unsupported context event type")


def _start_context(
    context: ApplicationContext, payload: Mapping[str, Any]
) -> tuple[CoreContext, Mapping[str, DomainStateEnvelope], ContextStatus]:
    allowed = {"core", "domains", "input", "runtime"}
    if set(payload) - allowed:
        raise ContextTransitionError("application start payload contains unsupported fields")
    core = context.core
    if "core" in payload:
        candidate = payload["core"]
        if not isinstance(candidate, Mapping):
            raise ContextTransitionError("application start core must be an object")
        try:
            core = CoreContext.model_validate(candidate)
        except ValidationError:
            raise ContextTransitionError("application start core is invalid") from None
    elif "input" in payload or "runtime" in payload:
        values = core.model_dump(mode="python")
        if "input" in payload:
            values["input"] = payload["input"]
        if "runtime" in payload:
            values["runtime"] = payload["runtime"]
        try:
            core = CoreContext.model_validate(values)
        except ValidationError:
            raise ContextTransitionError("application start records are invalid") from None
    if "domains" in payload:
        candidate_domains = payload["domains"]
        if not isinstance(candidate_domains, Mapping):
            raise ContextTransitionError("application start domains must be an object")
        if set(candidate_domains) != set(context.domains):
            raise ContextTransitionError("application start domains do not match bindings")
        for binding_id, candidate in candidate_domains.items():
            if not isinstance(candidate, Mapping):
                raise ContextTransitionError("application start domain state is invalid")
            try:
                envelope = DomainStateEnvelope.model_validate(candidate)
            except ValidationError:
                raise ContextTransitionError("application start domain state is invalid") from None
            if envelope != context.domains[binding_id]:
                raise ContextTransitionError("application start domain state does not match bindings")
    return core, context.domains, "running"


def _project_domain_state(
    context: ApplicationContext,
    draft: ContextEventDraft,
    payload: Mapping[str, Any],
) -> tuple[CoreContext, Mapping[str, DomainStateEnvelope], ContextStatus]:
    binding_id = draft.binding_id
    if binding_id is None:
        raise ContextTransitionError("domain state projection requires a binding")
    if binding_id not in context.domains:
        raise ContextTransitionError("unknown binding")
    if set(payload) != {"schema_id", "previous_revision", "state"}:
        raise ContextTransitionError("domain state projection payload is invalid")
    schema_id = payload["schema_id"]
    previous_revision = payload["previous_revision"]
    state = payload["state"]
    current = context.domains[binding_id]
    if schema_id != current.schema_id:
        raise ContextTransitionError("schema drift")
    if previous_revision != current.revision:
        raise ContextTransitionError("stale revision")
    if not isinstance(state, Mapping):
        raise ContextTransitionError("domain state must be an object")
    _validate_state_ownership(state, binding_id=binding_id, known_bindings=context.domains)
    try:
        updated = DomainStateEnvelope(
            schema_id=current.schema_id,
            revision=current.revision + 1,
            state=state,
        )
    except (TypeError, ValueError, ValidationError):
        raise ContextTransitionError("domain state is invalid") from None
    domains = dict(context.domains)
    domains[binding_id] = updated
    return context.core, domains, context.status


def _validate_state_ownership(
    value: Any,
    *,
    binding_id: str,
    known_bindings: Mapping[str, DomainStateEnvelope],
) -> None:
    sibling_ids = set(known_bindings) - {binding_id}
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ContextTransitionError("domain state keys must be strings")
            if key in _RESERVED_STATE_KEYS:
                raise ContextTransitionError("domain state contains a reserved field")
            if key in sibling_ids or any(
                key.startswith(f"{sibling}_") or key.startswith(f"{sibling}.")
                for sibling in sibling_ids
            ):
                raise ContextTransitionError("sibling binding field is not permitted")
            normalized_key = key.lower()
            if normalized_key in _OWNER_KEYS or normalized_key.endswith("_binding_id"):
                if type(item) is not str or item != binding_id:
                    raise ContextTransitionError("foreign reference ownership")
            if normalized_key in _OWNER_LIST_KEYS or normalized_key.endswith("_binding_ids"):
                if not isinstance(item, (list, tuple)) or any(
                    type(owner) is not str or owner != binding_id for owner in item
                ):
                    raise ContextTransitionError("foreign reference ownership")
            _validate_state_ownership(
                item,
                binding_id=binding_id,
                known_bindings=known_bindings,
            )
        return
    if isinstance(value, list | tuple):
        for item in value:
            _validate_state_ownership(
                item,
                binding_id=binding_id,
                known_bindings=known_bindings,
            )
        return
    if isinstance(value, str) and _foreign_reference(value, binding_id, sibling_ids):
        raise ContextTransitionError("foreign reference ownership")


def _foreign_reference(value: str, binding_id: str, sibling_ids: set[str]) -> bool:
    del binding_id
    for sibling in sibling_ids:
        if value.startswith(f"{sibling}:") or value.startswith(f"{sibling}/"):
            return True
        if f":{sibling}:" in value or f"/{sibling}/" in value:
            return True
        if value.startswith(f"binding={sibling}:") or value == f"binding:{sibling}":
            return True
    return False


def _append_diagnostic(
    core: CoreContext, event_type: str, payload: Mapping[str, Any]
) -> CoreContext:
    record = dict(payload)
    record.setdefault("event_type", event_type)
    return _append_core_record(core, "diagnostics", record)


def _apply_turn_event(
    core: CoreContext, draft: ContextEventDraft, payload: Mapping[str, Any]
) -> CoreContext:
    event_type = draft.event_type
    values = core.model_dump(mode="python")
    if event_type == "turn.started":
        if core.active_turn is not None:
            raise ContextTransitionError("an active turn already exists")
        active = dict(payload)
        if draft.turn_id is not None:
            active.setdefault("turn_id", draft.turn_id)
        values["active_turn"] = active
    else:
        if core.active_turn is None:
            raise ContextTransitionError("turn completion requires an active turn")
        if draft.turn_id is not None and core.active_turn.get("turn_id") not in {
            None,
            draft.turn_id,
        }:
            raise ContextTransitionError("turn completion does not match the active turn")
        completed = dict(payload)
        completed.setdefault("event_type", event_type)
        if draft.turn_id is not None:
            completed.setdefault("turn_id", draft.turn_id)
        values["turns"] = tuple(core.turns) + (completed,)
        values["active_turn"] = None
    try:
        return CoreContext.model_validate(values)
    except ValidationError:
        raise ContextTransitionError("turn lifecycle record is invalid") from None


def _accept_instruction(
    core: CoreContext, payload: Mapping[str, Any]
) -> CoreContext:
    if set(payload) != {"ordinal", "instruction"} or core.active_turn is not None:
        raise ContextTransitionError("instruction acceptance is invalid")
    instruction = payload["instruction"]
    existing = core.input.get("questions")
    if not isinstance(existing, (list, tuple)) or not all(
        isinstance(question, str) for question in existing
    ):
        raise ContextTransitionError("application input questions are invalid")
    if (
        type(payload["ordinal"]) is not int
        or payload["ordinal"] != len(existing) + 1
    ):
        raise ContextTransitionError("instruction ordinal is out of order")
    if not isinstance(instruction, str) or not instruction.strip():
        raise ContextTransitionError("instruction must be non-empty text")
    values = core.model_dump(mode="python")
    values["input"] = {**core.input, "questions": [*existing, instruction]}
    try:
        return CoreContext.model_validate(values)
    except ValidationError:
        raise ContextTransitionError("accepted instruction is invalid") from None


def _append_core_record(
    core: CoreContext, field_name: str, payload: Mapping[str, Any]
) -> CoreContext:
    values = core.model_dump(mode="python")
    existing = tuple(getattr(core, field_name))
    values[field_name] = existing + (dict(payload),)
    try:
        return CoreContext.model_validate(values)
    except ValidationError:
        raise ContextTransitionError("core lifecycle record is invalid") from None


def _set_answer_lifecycle(core: CoreContext, payload: Mapping[str, Any]) -> CoreContext:
    values = core.model_dump(mode="python")
    values["answer_lifecycle"] = dict(payload)
    try:
        return CoreContext.model_validate(values)
    except ValidationError:
        raise ContextTransitionError("answer lifecycle record is invalid") from None


def _append_references(
    core: CoreContext, field_name: str, payload: Mapping[str, Any]
) -> CoreContext:
    if set(payload) == {"ref"}:
        candidates = (payload["ref"],)
    elif set(payload) == {"refs"}:
        candidates = payload["refs"]
    else:
        raise ContextTransitionError("reference event payload is invalid")
    if not isinstance(candidates, (list, tuple)) or not all(
        type(item) is str and item for item in candidates
    ):
        raise ContextTransitionError("reference event values are invalid")
    values = core.model_dump(mode="python")
    existing = tuple(getattr(core, field_name))
    values[field_name] = existing + tuple(candidates)
    try:
        return CoreContext.model_validate(values)
    except ValidationError:
        raise ContextTransitionError("reference event is invalid") from None


def _payload(draft: ContextEventDraft) -> Mapping[str, Any]:
    payload = draft.payload
    if not isinstance(payload, Mapping):
        raise ContextTransitionError("context event payload must be an object")
    return payload


__all__ = [
    "ContextTransitionError",
    "canonical_state_hash",
    "initial_context",
    "reduce_context",
]
