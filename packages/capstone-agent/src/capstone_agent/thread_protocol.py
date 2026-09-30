"""Strict public read-model and command-receipt shapes for ``capstone-thread/1``."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from capstone_model_capability_spi import ModelCapabilitySelection


THREAD_PROTOCOL = "capstone-thread/1"
_SNAPSHOT_SCHEMA = "capstone-thread-snapshot/1"
_EVENT_PAGE_SCHEMA = "capstone-thread-events/1"
_RECEIPT_SCHEMA = "capstone-command-receipt/1"
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


class ThreadProtocolError(ValueError):
    """A public Thread document is malformed or cannot be safely applied."""


def _document(value: Any, *, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ThreadProtocolError(f"{name} must be an object")
    return value


def _fields(value: Mapping[str, Any], allowed: frozenset[str], *, name: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ThreadProtocolError(f"{name} has unknown field: {names}")


def _required(value: Mapping[str, Any], required: frozenset[str], *, name: str) -> None:
    missing = required - set(value)
    if missing:
        names = ", ".join(sorted(missing))
        raise ThreadProtocolError(f"{name} is missing field: {names}")


def _identifier(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ThreadProtocolError(f"{name} is invalid")
    return value


def _text(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ThreadProtocolError(f"{name} is invalid")
    return value


def _sequence(value: Any, *, name: str) -> int:
    if type(value) is not int or value < 0:
        raise ThreadProtocolError(f"{name} is invalid")
    return value


def _json(value: Any, *, name: str) -> None:
    try:
        json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        raise ThreadProtocolError(f"{name} is not JSON") from None


def _timestamp(value: Any, *, name: str) -> str:
    text = _text(value, name=name)
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise ThreadProtocolError(f"{name} is invalid") from None
    return text


def _optional_identifier(value: Any, *, name: str) -> str | None:
    return None if value is None else _identifier(value, name=name)


@dataclass(frozen=True, slots=True)
class RunSnapshot:
    run_id: str
    state: str

    @classmethod
    def from_document(cls, value: Any) -> RunSnapshot:
        document = _document(value, name="run")
        _fields(document, frozenset({"run_id", "state"}), name="run")
        _required(document, frozenset({"run_id", "state"}), name="run")
        run_id = _identifier(document["run_id"], name="run.run_id")
        state = _text(document["state"], name="run.state")
        if state not in {"created", "open", "closing", "closed", "failed"}:
            raise ThreadProtocolError("run.state is invalid")
        return cls(run_id=run_id, state=state)

    def to_document(self) -> dict[str, Any]:
        return {"run_id": self.run_id, "state": self.state}


@dataclass(frozen=True, slots=True)
class ModelContextSnapshot:
    id: str
    model_id: str
    model_revision: str
    implementation_family: str
    selection_revision: str
    enabled_profiles: tuple[tuple[str, str], ...] = ()

    @classmethod
    def from_document(cls, value: Any) -> ModelContextSnapshot:
        document = _document(value, name="active_model_context")
        allowed = frozenset({"id", "model_id", "model_revision", "implementation_family", "selection_revision", "enabled_profiles"})
        _fields(document, allowed, name="active_model_context")
        _required(
            document,
            allowed - {"enabled_profiles"},
            name="active_model_context",
        )
        try:
            selection = (
                ModelCapabilitySelection.empty()
                if "enabled_profiles" not in document
                else ModelCapabilitySelection.from_document(document["enabled_profiles"])
            )
        except ValueError as error:
            raise ThreadProtocolError(str(error)) from None
        return cls(
            id=_identifier(document["id"], name="active_model_context.id"),
            model_id=_identifier(document["model_id"], name="active_model_context.model_id"),
            model_revision=_text(document["model_revision"], name="active_model_context.model_revision"),
            implementation_family=_identifier(
                document["implementation_family"], name="active_model_context.implementation_family"
            ),
            selection_revision=_text(document["selection_revision"], name="active_model_context.selection_revision"),
            enabled_profiles=selection.enabled_profiles,
        )

    def to_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "id": self.id,
            "model_id": self.model_id,
            "model_revision": self.model_revision,
            "implementation_family": self.implementation_family,
            "selection_revision": self.selection_revision,
        }
        if self.enabled_profiles:
            document["enabled_profiles"] = ModelCapabilitySelection(self.enabled_profiles).to_document()
        return document


@dataclass(frozen=True, slots=True)
class PendingSelectionSnapshot:
    """A validated profile set waiting for the next Turn boundary."""

    command_id: str
    enabled_profiles: tuple[tuple[str, str], ...]

    @classmethod
    def from_document(cls, value: Any) -> PendingSelectionSnapshot:
        document = _document(value, name="pending_selection")
        allowed = frozenset({"command_id", "selection"})
        _fields(document, allowed, name="pending_selection")
        _required(document, allowed, name="pending_selection")
        try:
            selection = ModelCapabilitySelection.from_document(document["selection"])
        except ValueError as error:
            raise ThreadProtocolError(str(error)) from None
        return cls(
            command_id=_identifier(document["command_id"], name="pending_selection.command_id"),
            enabled_profiles=selection.enabled_profiles,
        )

    def to_document(self) -> dict[str, Any]:
        return {
            "command_id": self.command_id,
            "selection": ModelCapabilitySelection(self.enabled_profiles).to_document(),
        }


@dataclass(frozen=True, slots=True)
class AttemptSnapshot:
    turn_id: str
    attempt_id: str
    phase: str
    target_model_context_id: str

    @classmethod
    def from_document(cls, value: Any) -> AttemptSnapshot:
        document = _document(value, name="current_attempt")
        allowed = frozenset({"turn_id", "attempt_id", "phase", "target_model_context_id"})
        _fields(document, allowed, name="current_attempt")
        _required(document, allowed, name="current_attempt")
        phase = _text(document["phase"], name="current_attempt.phase")
        if phase not in {"created", "accepted", "running", "waiting", "committing", "cancelled", "interrupted", "completed", "failed"}:
            raise ThreadProtocolError("current_attempt.phase is invalid")
        return cls(
            turn_id=_identifier(document["turn_id"], name="current_attempt.turn_id"),
            attempt_id=_identifier(document["attempt_id"], name="current_attempt.attempt_id"),
            phase=phase,
            target_model_context_id=_identifier(
                document["target_model_context_id"], name="current_attempt.target_model_context_id"
            ),
        )

    def to_document(self) -> dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "attempt_id": self.attempt_id,
            "phase": self.phase,
            "target_model_context_id": self.target_model_context_id,
        }


@dataclass(frozen=True, slots=True)
class ThreadSnapshot:
    thread_id: str
    run: RunSnapshot
    active_model_context: ModelContextSnapshot
    active_grid_page_id: str
    current_attempt: AttemptSnapshot | None
    last_event_seq: int
    base_event_seq: int
    pending_selection: PendingSelectionSnapshot | None = None

    @classmethod
    def from_document(cls, value: Any) -> ThreadSnapshot:
        document = _document(value, name="snapshot")
        allowed = frozenset({
            "schema", "thread_id", "run", "active_model_context", "active_grid_page_id",
            "current_attempt", "last_event_seq", "base_event_seq", "pending_selection",
        })
        _fields(document, allowed, name="snapshot")
        _required(document, allowed - {"pending_selection"}, name="snapshot")
        if document["schema"] != _SNAPSHOT_SCHEMA:
            raise ThreadProtocolError("snapshot.schema is invalid")
        last_event_seq = _sequence(document["last_event_seq"], name="snapshot.last_event_seq")
        base_event_seq = _sequence(document["base_event_seq"], name="snapshot.base_event_seq")
        if base_event_seq > last_event_seq:
            raise ThreadProtocolError("snapshot base_event_seq exceeds last_event_seq")
        context = ModelContextSnapshot.from_document(document["active_model_context"])
        attempt = None if document["current_attempt"] is None else AttemptSnapshot.from_document(document["current_attempt"])
        if attempt is not None and attempt.target_model_context_id != context.id:
            raise ThreadProtocolError("current_attempt target context does not match active context")
        pending = (
            None
            if document.get("pending_selection") is None
            else PendingSelectionSnapshot.from_document(document["pending_selection"])
        )
        return cls(
            thread_id=_identifier(document["thread_id"], name="snapshot.thread_id"),
            run=RunSnapshot.from_document(document["run"]),
            active_model_context=context,
            active_grid_page_id=_identifier(document["active_grid_page_id"], name="snapshot.active_grid_page_id"),
            current_attempt=attempt,
            last_event_seq=last_event_seq,
            base_event_seq=base_event_seq,
            pending_selection=pending,
        )

    def to_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "schema": _SNAPSHOT_SCHEMA,
            "thread_id": self.thread_id,
            "run": self.run.to_document(),
            "active_model_context": self.active_model_context.to_document(),
            "active_grid_page_id": self.active_grid_page_id,
            "current_attempt": None if self.current_attempt is None else self.current_attempt.to_document(),
            "last_event_seq": self.last_event_seq,
            "base_event_seq": self.base_event_seq,
        }
        if self.pending_selection is not None:
            document["pending_selection"] = self.pending_selection.to_document()
        return document


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    event_id: str
    event_seq: int
    event_type: str
    event_version: int
    thread_id: str
    run_id: str
    turn_id: str | None
    attempt_id: str | None
    model_context_id: str | None
    selection_revision: str | None
    occurred_at: str
    visibility: str
    payload: dict[str, Any]

    @classmethod
    def from_document(cls, value: Any) -> EventEnvelope:
        document = _document(value, name="event")
        allowed = frozenset({
            "event_id", "event_seq", "event_type", "event_version", "thread_id", "run_id",
            "turn_id", "attempt_id", "model_context_id", "selection_revision", "occurred_at",
            "visibility", "payload",
        })
        _fields(document, allowed, name="event")
        required = frozenset({"event_id", "event_seq", "event_type", "event_version", "thread_id", "run_id", "occurred_at", "visibility", "payload"})
        _required(document, required, name="event")
        if type(document["event_version"]) is not int or document["event_version"] < 1:
            raise ThreadProtocolError("event.event_version is invalid")
        visibility = _text(document["visibility"], name="event.visibility")
        if visibility not in {"public", "diagnostic"}:
            raise ThreadProtocolError("event.visibility is invalid")
        payload = _document(document["payload"], name="event.payload")
        _json(payload, name="event.payload")
        return cls(
            event_id=_identifier(document["event_id"], name="event.event_id"),
            event_seq=_sequence(document["event_seq"], name="event.event_seq"),
            event_type=_text(document["event_type"], name="event.event_type"),
            event_version=document["event_version"],
            thread_id=_identifier(document["thread_id"], name="event.thread_id"),
            run_id=_identifier(document["run_id"], name="event.run_id"),
            turn_id=_optional_identifier(document.get("turn_id"), name="event.turn_id"),
            attempt_id=_optional_identifier(document.get("attempt_id"), name="event.attempt_id"),
            model_context_id=_optional_identifier(document.get("model_context_id"), name="event.model_context_id"),
            selection_revision=None if document.get("selection_revision") is None else _text(document["selection_revision"], name="event.selection_revision"),
            occurred_at=_timestamp(document["occurred_at"], name="event.occurred_at"),
            visibility=visibility,
            payload=payload,
        )

    def to_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "event_id": self.event_id,
            "event_seq": self.event_seq,
            "event_type": self.event_type,
            "event_version": self.event_version,
            "thread_id": self.thread_id,
            "run_id": self.run_id,
            "occurred_at": self.occurred_at,
            "visibility": self.visibility,
            "payload": self.payload,
        }
        for field in ("turn_id", "attempt_id", "model_context_id", "selection_revision"):
            value = getattr(self, field)
            if value is not None:
                document[field] = value
        return document


@dataclass(frozen=True, slots=True)
class EventPage:
    thread_id: str
    after_event_seq: int
    next_event_seq: int
    has_more: bool
    events: tuple[EventEnvelope, ...]

    @classmethod
    def from_document(cls, value: Any, *, expected_after_seq: int | None = None) -> EventPage:
        document = _document(value, name="event_page")
        allowed = frozenset({"schema", "thread_id", "after_event_seq", "next_event_seq", "has_more", "events"})
        _fields(document, allowed, name="event_page")
        _required(document, allowed, name="event_page")
        if document["schema"] != _EVENT_PAGE_SCHEMA:
            raise ThreadProtocolError("event_page.schema is invalid")
        after_event_seq = _sequence(document["after_event_seq"], name="event_page.after_event_seq")
        if expected_after_seq is not None and after_event_seq != expected_after_seq:
            raise ThreadProtocolError("event page does not start at expected cursor")
        if not isinstance(document["has_more"], bool):
            raise ThreadProtocolError("event_page.has_more is invalid")
        raw_events = document["events"]
        if not isinstance(raw_events, list):
            raise ThreadProtocolError("event_page.events is invalid")
        events = tuple(EventEnvelope.from_document(item) for item in raw_events)
        thread_id = _identifier(document["thread_id"], name="event_page.thread_id")
        expected = after_event_seq + 1
        for item in events:
            if item.thread_id != thread_id:
                raise ThreadProtocolError("event thread_id does not match page")
            if item.event_seq != expected:
                raise ThreadProtocolError("event page is not contiguous")
            expected += 1
        next_event_seq = _sequence(document["next_event_seq"], name="event_page.next_event_seq")
        if next_event_seq != expected - 1:
            raise ThreadProtocolError("event_page.next_event_seq is invalid")
        return cls(thread_id, after_event_seq, next_event_seq, document["has_more"], events)

    def to_document(self) -> dict[str, Any]:
        return {
            "schema": _EVENT_PAGE_SCHEMA,
            "thread_id": self.thread_id,
            "after_event_seq": self.after_event_seq,
            "next_event_seq": self.next_event_seq,
            "has_more": self.has_more,
            "events": [event.to_document() for event in self.events],
        }


@dataclass(frozen=True, slots=True)
class CommandReceipt:
    command_id: str
    idempotency_key: str
    thread_id: str
    run_id: str | None
    status: str
    accepted_event_seq: int | None
    rejection: str | None
    target: dict[str, Any] | None

    @classmethod
    def from_document(cls, value: Any) -> CommandReceipt:
        document = _document(value, name="receipt")
        allowed = frozenset({"schema", "command_id", "idempotency_key", "thread_id", "run_id", "status", "accepted_event_seq", "rejection", "target"})
        _fields(document, allowed, name="receipt")
        _required(document, frozenset({"schema", "command_id", "idempotency_key", "thread_id", "status"}), name="receipt")
        if document["schema"] != _RECEIPT_SCHEMA:
            raise ThreadProtocolError("receipt.schema is invalid")
        status = _text(document["status"], name="receipt.status")
        if status not in {"accepted", "rejected", "pending"}:
            raise ThreadProtocolError("receipt.status is invalid")
        accepted_event_seq = document.get("accepted_event_seq")
        if accepted_event_seq is not None:
            accepted_event_seq = _sequence(accepted_event_seq, name="receipt.accepted_event_seq")
        rejection = document.get("rejection")
        if rejection is not None:
            rejection = _text(rejection, name="receipt.rejection")
        target = document.get("target")
        if target is not None:
            target = _document(target, name="receipt.target")
            _json(target, name="receipt.target")
        return cls(
            command_id=_identifier(document["command_id"], name="receipt.command_id"),
            idempotency_key=_identifier(document["idempotency_key"], name="receipt.idempotency_key"),
            thread_id=_identifier(document["thread_id"], name="receipt.thread_id"),
            run_id=_optional_identifier(document.get("run_id"), name="receipt.run_id"),
            status=status,
            accepted_event_seq=accepted_event_seq,
            rejection=rejection,
            target=target,
        )

    def to_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "schema": _RECEIPT_SCHEMA,
            "command_id": self.command_id,
            "idempotency_key": self.idempotency_key,
            "thread_id": self.thread_id,
            "status": self.status,
        }
        if self.run_id is not None:
            document["run_id"] = self.run_id
        if self.accepted_event_seq is not None:
            document["accepted_event_seq"] = self.accepted_event_seq
        if self.rejection is not None:
            document["rejection"] = self.rejection
        if self.target is not None:
            document["target"] = self.target
        return document
