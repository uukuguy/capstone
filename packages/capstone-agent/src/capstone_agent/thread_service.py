"""Server-side projection boundary for the public ``capstone-thread/1`` API.

The service deliberately sits above the old session ledger.  A durable adapter
can implement the same operations later without making the HTTP layer aware of
Pi, DSH, Domain Packs, or authority internals.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Mapping, Protocol

from .thread_protocol import (
    CommandReceipt,
    EventEnvelope,
    EventPage,
    ThreadProtocolError,
    ThreadSnapshot,
)


_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_COMMAND_FIELDS = frozenset({
    "schema", "command_id", "idempotency_key", "thread_id", "run_id",
    "kind", "expected_event_seq", "payload",
})


class ThreadNotFound(KeyError):
    """The requested Thread does not exist in the selected store."""


class ThreadResyncRequired(RuntimeError):
    """The requested cursor predates the retained canonical event window."""

    def __init__(self, snapshot: ThreadSnapshot) -> None:
        super().__init__("thread event cursor requires a verified snapshot")
        self.snapshot = snapshot


class ThreadService(Protocol):
    """Persistence and admission operations required by the HTTP projection."""

    def snapshot(self, thread_id: str) -> ThreadSnapshot: ...

    def read_events(self, thread_id: str, after_event_seq: int) -> EventPage: ...

    def submit_command(self, command: Mapping[str, Any]) -> CommandReceipt: ...


def _identifier(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ThreadProtocolError(f"{name} is invalid")
    return value


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True)


@dataclass(frozen=True, slots=True)
class _StoredCommand:
    request_hash: str
    receipt: CommandReceipt


class InMemoryThreadService:
    """Deterministic Thread store used by contract tests and local prototypes.

    It is intentionally not a replacement for the durable production adapter.
    Its public methods define the minimum persistence boundary required by the
    HTTP projection.
    """

    def __init__(self, snapshot: ThreadSnapshot) -> None:
        self._snapshot = snapshot
        self._events: list[EventEnvelope] = []
        self._commands: dict[str, _StoredCommand] = {}
        self._command_ids: set[str] = set()
        self._lock = RLock()

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> InMemoryThreadService:
        return cls(ThreadSnapshot.from_document(dict(document)))

    def snapshot(self, thread_id: str) -> ThreadSnapshot:
        with self._lock:
            self._check_thread(thread_id)
            return self._snapshot

    def read_events(self, thread_id: str, after_event_seq: int) -> EventPage:
        if type(after_event_seq) is not int or after_event_seq < 0:
            raise ThreadProtocolError("event cursor is invalid")
        with self._lock:
            self._check_thread(thread_id)
            if after_event_seq < self._snapshot.base_event_seq:
                raise ThreadResyncRequired(self._snapshot)
            events = tuple(event for event in self._events if event.event_seq > after_event_seq)
            next_event_seq = events[-1].event_seq if events else after_event_seq
            return EventPage(thread_id, after_event_seq, next_event_seq, False, events)

    def submit_command(self, command: Mapping[str, Any]) -> CommandReceipt:
        parsed = self._parse_command(command)
        with self._lock:
            self._check_thread(parsed["thread_id"])
            request_hash = hashlib.sha256(_canonical(command).encode()).hexdigest()
            existing = self._commands.get(parsed["idempotency_key"])
            if existing is not None:
                if existing.request_hash != request_hash:
                    return self._receipt(
                        parsed, status="rejected", rejection="idempotency_conflict",
                    )
                return existing.receipt
            if parsed["command_id"] in self._command_ids:
                return self._receipt(parsed, status="rejected", rejection="command_id_conflict")
            if parsed["run_id"] is not None and parsed["run_id"] != self._snapshot.run.run_id:
                receipt = self._receipt(parsed, status="rejected", rejection="run_mismatch")
                self._commands[parsed["idempotency_key"]] = _StoredCommand(request_hash, receipt)
                return receipt
            if parsed["expected_event_seq"] != self._snapshot.last_event_seq:
                receipt = self._receipt(parsed, status="rejected", rejection="stale_event_seq")
                self._commands[parsed["idempotency_key"]] = _StoredCommand(request_hash, receipt)
                return receipt
            if self._snapshot.run.state != "open":
                receipt = self._receipt(parsed, status="rejected", rejection="run_not_open")
                self._commands[parsed["idempotency_key"]] = _StoredCommand(request_hash, receipt)
                return receipt

            event_seq = self._snapshot.last_event_seq + 1
            event = EventEnvelope(
                event_id="evt_" + secrets.token_hex(8), event_seq=event_seq,
                event_type="command_accepted", event_version=1,
                thread_id=self._snapshot.thread_id, run_id=self._snapshot.run.run_id,
                turn_id=None, attempt_id=None,
                model_context_id=self._snapshot.active_model_context.id,
                selection_revision=self._snapshot.active_model_context.selection_revision,
                occurred_at=_now(), visibility="public",
                payload={"command_id": parsed["command_id"], "kind": parsed["kind"],
                         "payload": parsed["payload"]},
            )
            self._events.append(event)
            self._snapshot = replace(self._snapshot, last_event_seq=event_seq)
            receipt = self._receipt(parsed, status="accepted", accepted_event_seq=event_seq)
            self._commands[parsed["idempotency_key"]] = _StoredCommand(request_hash, receipt)
            self._command_ids.add(parsed["command_id"])
            return receipt

    def compact_before(self, base_event_seq: int) -> None:
        with self._lock:
            if type(base_event_seq) is not int or base_event_seq < self._snapshot.base_event_seq:
                raise ValueError("event base is invalid")
            if base_event_seq > self._snapshot.last_event_seq:
                raise ValueError("event base exceeds last event")
            self._events = [event for event in self._events if event.event_seq > base_event_seq]
            self._snapshot = replace(self._snapshot, base_event_seq=base_event_seq)

    def _check_thread(self, thread_id: str) -> None:
        if thread_id != self._snapshot.thread_id:
            raise ThreadNotFound(thread_id)

    @staticmethod
    def _parse_command(command: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(command, Mapping):
            raise ThreadProtocolError("command must be an object")
        unknown = set(command) - _COMMAND_FIELDS
        if unknown:
            raise ThreadProtocolError("command has unknown field: " + ", ".join(sorted(unknown)))
        required = _COMMAND_FIELDS - {"run_id"}
        missing = required - set(command)
        if missing:
            raise ThreadProtocolError("command is missing field: " + ", ".join(sorted(missing)))
        if command["schema"] != "capstone-command/1":
            raise ThreadProtocolError("command.schema is invalid")
        kind = command["kind"]
        if not isinstance(kind, str) or not _IDENTIFIER.fullmatch(kind):
            raise ThreadProtocolError("command.kind is invalid")
        expected = command["expected_event_seq"]
        if type(expected) is not int or expected < 0:
            raise ThreadProtocolError("command.expected_event_seq is invalid")
        payload = command["payload"]
        if not isinstance(payload, dict):
            raise ThreadProtocolError("command.payload is invalid")
        return {
            "command_id": _identifier(command["command_id"], name="command.command_id"),
            "idempotency_key": _identifier(command["idempotency_key"], name="command.idempotency_key"),
            "thread_id": _identifier(command["thread_id"], name="command.thread_id"),
            "run_id": None if command.get("run_id") is None else _identifier(command["run_id"], name="command.run_id"),
            "kind": kind, "expected_event_seq": expected, "payload": payload,
        }

    def _receipt(
        self, command: Mapping[str, Any], *, status: str,
        accepted_event_seq: int | None = None, rejection: str | None = None,
    ) -> CommandReceipt:
        return CommandReceipt(
            command_id=command["command_id"], idempotency_key=command["idempotency_key"],
            thread_id=command["thread_id"], run_id=self._snapshot.run.run_id,
            status=status, accepted_event_seq=accepted_event_seq,
            rejection=rejection, target=None,
        )
