"""Neutral, bounded application transitions for the Thread ledger.

The transition port intentionally knows nothing about a Case (or any other
application).  Applications provide an ordinary Thread command, opaque JSON
state, and a short ordered set of events; the Thread store supplies identity,
cursor, idempotency, and atomic persistence.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Literal, Mapping

from .thread_protocol import ThreadProtocolError


MAX_APPLICATION_STATE_BYTES = 64 * 1024
MAX_APPLICATION_EVENT_BYTES = 64 * 1024
MAX_APPLICATION_EVENTS = 8
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


def _bounded_json(value: Any, *, name: str, maximum: int) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ThreadProtocolError(f"{name} must be an object")
    try:
        encoded = json.dumps(dict(value), ensure_ascii=False, allow_nan=False, sort_keys=True).encode("utf-8")
    except (TypeError, ValueError):
        raise ThreadProtocolError(f"{name} is not JSON") from None
    if len(encoded) > maximum:
        raise ThreadProtocolError(f"{name} is too large")
    return dict(value)


@dataclass(frozen=True, slots=True)
class ApplicationEvent:
    """One opaque application event to append to a Thread."""

    event_type: str
    payload: Mapping[str, Any]
    visibility: Literal["public", "diagnostic"] = "public"

    def __post_init__(self) -> None:
        if not isinstance(self.event_type, str) or not _IDENTIFIER.fullmatch(self.event_type):
            raise ThreadProtocolError("application event_type is invalid")
        if self.visibility not in {"public", "diagnostic"}:
            raise ThreadProtocolError("application event visibility is invalid")
        payload = _bounded_json(self.payload, name="application event payload", maximum=MAX_APPLICATION_EVENT_BYTES)
        object.__setattr__(self, "payload", payload)

    def to_document(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "payload": dict(self.payload),
            "visibility": self.visibility,
        }


@dataclass(frozen=True, slots=True)
class ThreadApplicationTransition:
    """A validated, bounded application update for one Thread."""

    command: Mapping[str, Any]
    state: Mapping[str, Any] | None
    events: tuple[ApplicationEvent, ...]

    def __post_init__(self) -> None:
        command = _bounded_json(self.command, name="transition command", maximum=MAX_APPLICATION_EVENT_BYTES)
        object.__setattr__(self, "command", command)
        if self.state is not None:
            state = _bounded_json(self.state, name="application state", maximum=MAX_APPLICATION_STATE_BYTES)
            object.__setattr__(self, "state", state)
        if not isinstance(self.events, tuple) or not all(isinstance(item, ApplicationEvent) for item in self.events):
            raise ThreadProtocolError("transition events are invalid")
        if len(self.events) > MAX_APPLICATION_EVENTS:
            raise ThreadProtocolError("transition has too many events")


def application_transition_hash(transition: ThreadApplicationTransition) -> str:
    """Return the canonical idempotency hash for a complete transition.

    The command identifies the operation, while the state and ordered event
    documents are also part of the atomic write.  Binding all three to the
    idempotency key prevents a retry with the same command from silently
    changing the application projection.
    """

    document = {
        "command": dict(transition.command),
        "state": None if transition.state is None else dict(transition.state),
        "events": [event.to_document() for event in transition.events],
    }
    canonical = json.dumps(document, ensure_ascii=False, allow_nan=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
