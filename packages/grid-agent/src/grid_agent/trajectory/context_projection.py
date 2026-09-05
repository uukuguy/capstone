"""Pure context-state time travel over a replay event stream."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import json
import os
import stat
from pathlib import Path
from typing import Any

from capability_agent.trajectory.artifacts import ArtifactPointer
from capability_agent.trajectory.canonical import canonical_json_bytes
from grid_agent.trajectory.projection_models import (
    BindingProjectionMetadata,
    ContextCheckpoint,
    ContextFrame,
    ContextTimeline,
    DomainPayloadView,
)
from capability_agent.trajectory.replay import ReplayEventLike


RULE_CONTEXT_FRAME = "context-frame/v2"
MAX_CONTEXT_PREVIEW_BYTES = 131072
OMITTED_CONTEXT = "Context state omitted because it exceeds 128 KiB; context metadata was not inspected."
MISSING_REQUEST_INPUT = "legacy source did not capture model request input"
UNAVAILABLE_CONTEXT_ARTIFACT = "context artifact could not be verified"
UNAVAILABLE_NATIVE_CONTEXT = "native context state has no verified artifact"


@dataclass(frozen=True)
class _ContextState:
    value: dict[str, Any] | None
    references: tuple[str, ...] = ()
    reason: str | None = None


def _state_hash(state: Mapping[str, Any]) -> str:
    return "sha256:" + sha256(canonical_json_bytes(state)).hexdigest()


def _copy_state(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(key): _copy_value(item) for key, item in value.items()}
    return {}


def _copy_value(value: object) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _copy_value(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_copy_value(item) for item in value]
    return value


def _delta(before: object, after: object) -> dict[str, Any]:
    if isinstance(before, Mapping) and isinstance(after, Mapping):
        result: dict[str, Any] = {}
        for key in sorted(set(before) | set(after), key=str):
            name = str(key)
            if key not in before:
                if isinstance(after[key], Mapping):
                    result[name] = {"added": sorted(map(str, after[key]))}
                else:
                    result.setdefault("added", []).append(name)
            elif key not in after:
                if isinstance(before[key], Mapping):
                    result[name] = {"removed": sorted(map(str, before[key]))}
                else:
                    result.setdefault("removed", []).append(name)
            else:
                nested = _delta(before[key], after[key])
                if nested:
                    result[name] = nested
        return result
    return {} if before == after else {"before": _copy_value(before), "after": _copy_value(after)}


def _open_context_file(path: Path) -> int:
    """Reopen the registry's absolute path without following replaced parents."""
    if not path.is_absolute():
        raise ValueError("context artifact path must be absolute")
    directory = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parts[1:-1]:
            next_directory = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = next_directory
        return os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    finally:
        os.close(directory)


def _verified_context_state(
    artifacts: object, reference: str, event: ReplayEventLike
) -> _ContextState | None:
    verify_reference = getattr(artifacts, "verify_reference", None)
    verify = getattr(artifacts, "verify", None)
    if not callable(verify_reference) or not callable(verify):
        return None
    try:
        pointer = verify_reference(reference)
        if not isinstance(pointer, ArtifactPointer) or pointer.kind != "context-view":
            return None
        path = verify(pointer)
        if not isinstance(path, Path):
            return None
        if pointer.size_bytes > MAX_CONTEXT_PREVIEW_BYTES:
            return _ContextState(None, (reference,), OMITTED_CONTEXT)
        descriptor = _open_context_file(path)
        try:
            opened_stat = os.fstat(descriptor)
            if not stat.S_ISREG(opened_stat.st_mode) or opened_stat.st_size != pointer.size_bytes:
                return None
            with os.fdopen(descriptor, "rb") as source:
                descriptor = -1
                content = source.read(MAX_CONTEXT_PREVIEW_BYTES + 1)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        if len(content) != pointer.size_bytes or sha256(content).hexdigest() != pointer.sha256:
            return None
        document = json.loads(content)
    except (OSError, TypeError, ValueError, RuntimeError, json.JSONDecodeError):
        return None
    if not isinstance(document, Mapping):
        return None
    if (
        document.get("analysis_id") != event.analysis_id
        or document.get("revision") != event.payload.get("revision")
        or document.get("state_hash") != event.payload.get("state_hash")
    ):
        return None
    return _ContextState(_copy_state(document), (reference,))


def _after_state(
    state: _ContextState, event: ReplayEventLike, artifacts: object
) -> _ContextState:
    payload = event.payload
    artifact_ref = payload.get("artifact_ref")
    if event.event_type in {"context.projected", "context.injected"} and isinstance(
        artifact_ref, str
    ):
        verified = _verified_context_state(artifacts, artifact_ref, event)
        if verified is not None:
            return verified
        return _ContextState(None, reason=UNAVAILABLE_CONTEXT_ARTIFACT)
    snapshot = payload.get("after_state", payload.get("context_state"))
    if isinstance(snapshot, Mapping):
        return _ContextState(_copy_state(snapshot))
    if event.event_type in {"context.projected", "context.injected"}:
        return _ContextState(None, reason=UNAVAILABLE_NATIVE_CONTEXT)
    return state


def _request_refs(events: Sequence[ReplayEventLike]) -> dict[int, str | None]:
    next_ref: str | None = None
    links: dict[int, str | None] = {}
    for event in reversed(events):
        if event.event_type == "model.request.started":
            value = event.payload.get("artifact_ref")
            next_ref = value if isinstance(value, str) and value else None
        links[event.sequence] = next_ref
    return links


def project_context(
    events: Sequence[ReplayEventLike],
    artifacts: object,
    *,
    checkpoint_interval: int = 100,
    binding: BindingProjectionMetadata | None = None,
) -> ContextTimeline:
    """Return immutable frames using only snapshots or verified context views."""
    if checkpoint_interval < 1:
        raise ValueError("checkpoint_interval must be positive")
    if not events:
        return ContextTimeline(analysis_id="unknown", binding=binding)

    state = _ContextState({})
    frames: list[ContextFrame] = []
    checkpoints: list[ContextCheckpoint] = []
    requests = _request_refs(events)
    revision = 0
    for event in events:
        explicit_before = event.payload.get("before_state")
        before = _ContextState(_copy_state(explicit_before)) if isinstance(explicit_before, Mapping) else state
        before_revision = event.context.before_revision
        if before_revision is None:
            before_revision = revision
        after = _after_state(before, event, artifacts)
        state_omitted = before.value is None or after.value is None
        context_unavailable_reason = (after.reason or before.reason) if state_omitted else None
        delta = _delta(before.value, after.value) if not state_omitted else None
        omitted_fields = tuple(name for name, value in (
            ("before_state", before.value), ("delta", delta), ("after_state", after.value)
        ) if value is None)
        after_revision = event.context.after_revision
        if after_revision is None:
            after_revision = before_revision
        request_ref = requests[event.sequence]
        frame = ContextFrame(
            id=f"context:{event.analysis_id}:{event.sequence}",
            source_sequences=(event.sequence,),
            rule_id=RULE_CONTEXT_FRAME,
            source_sequence=event.sequence,
            before_revision=before_revision,
            after_revision=after_revision,
            before_state_hash=_state_hash(before.value) if before.value is not None else None,
            after_state_hash=_state_hash(after.value) if after.value is not None else None,
            before_state=before.value,
            delta=delta,
            after_state=after.value,
            state_omitted=state_omitted,
            omitted_fields=omitted_fields,
            admitted_artifact_refs=tuple(dict.fromkeys(before.references + after.references)) if state_omitted else (),
            state_unavailable_reason=context_unavailable_reason,
            request_input_unavailable_reason=None if request_ref else MISSING_REQUEST_INPUT,
            request_artifact_ref=request_ref,
            status="unavailable" if context_unavailable_reason else "completed",
            unavailable_reason=(
                context_unavailable_reason
                if context_unavailable_reason
                else None if request_ref else MISSING_REQUEST_INPUT
            ),
        )
        frames.append(frame)
        state, revision = after, after_revision
        if event.sequence % checkpoint_interval == 0 or event.event_type in {"turn.completed", "analysis.completed"}:
            checkpoints.append(ContextCheckpoint(source_sequence=event.sequence, context_revision=revision, state_hash=frame.after_state_hash, state=state.value, state_omitted=state.value is None))
    return ContextTimeline(
        analysis_id=events[0].analysis_id,
        frames=tuple(frames),
        checkpoints=tuple(checkpoints),
        binding=binding,
    )


def project_context_payload(
    *,
    analysis_id: str,
    binding_id: str,
    domain_id: str,
    authority_id: str,
    schema: str,
    payload: Mapping[str, Any],
    presentation: Mapping[str, Any] | None = None,
) -> DomainPayloadView:
    """Expose unknown domain context as opaque, read-only structured data."""

    del analysis_id
    if not isinstance(payload, Mapping):
        raise TypeError("domain context payload must be a mapping")
    return DomainPayloadView(
        binding_id=binding_id,
        domain_id=domain_id,
        authority_id=authority_id,
        schema_id=schema,
        payload=dict(payload),
        presentation={} if presentation is None else dict(presentation),
    )


__all__ = [
    "MISSING_REQUEST_INPUT",
    "RULE_CONTEXT_FRAME",
    "UNAVAILABLE_CONTEXT_ARTIFACT",
    "UNAVAILABLE_NATIVE_CONTEXT",
    "project_context",
    "project_context_payload",
]
