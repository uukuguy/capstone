"""Domain-neutral trajectory lifecycle primitives."""

from capability_agent.trajectory.canonical import canonical_json_bytes, sha256_ref
from capability_agent.trajectory.events import (
    Causation,
    ContextBoundary,
    EventDraft,
    EventRefs,
    EventSource,
    RunEvent,
    RunScope,
    build_event,
    DEFAULT_EVENT_SCHEMA_VERSION,
)

__all__ = [
    "Causation",
    "ContextBoundary",
    "EventDraft",
    "EventRefs",
    "EventSource",
    "RunEvent",
    "RunScope",
    "build_event",
    "DEFAULT_EVENT_SCHEMA_VERSION",
    "canonical_json_bytes",
    "sha256_ref",
]
