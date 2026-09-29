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

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .thread_protocol import (
    CommandReceipt,
    EventEnvelope,
    EventPage,
    ModelContextSnapshot,
    RunSnapshot,
    ThreadProtocolError,
    ThreadSnapshot,
)


_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_MAX_COMMAND_BYTES = 64 * 1024
_COMMAND_FIELDS = frozenset({
    "schema", "command_id", "idempotency_key", "thread_id", "run_id",
    "kind", "expected_event_seq", "payload",
})
_MESSAGE_COMMAND_KINDS = frozenset({"send_ordinary", "send_professional", "send_control"})


class ThreadNotFound(KeyError):
    """The requested Thread does not exist in the selected store."""


class ThreadResyncRequired(RuntimeError):
    """The requested cursor predates the retained canonical event window."""

    def __init__(self, snapshot: ThreadSnapshot) -> None:
        super().__init__("thread event cursor requires a verified snapshot")
        self.snapshot = snapshot


class ThreadService(Protocol):
    """Persistence and admission operations required by the HTTP projection."""

    def create_thread(self, snapshot: ThreadSnapshot) -> ThreadSnapshot: ...

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


def _validate_json(value: Any, *, name: str) -> None:
    try:
        json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        raise ThreadProtocolError(f"{name} is not JSON") from None


def _admission_rejection(command: Mapping[str, Any]) -> str | None:
    """Return a bounded semantic rejection before a command enters the ledger."""

    if command["kind"] not in _MESSAGE_COMMAND_KINDS:
        return "unsupported_command"
    text = command["payload"].get("text")
    if not isinstance(text, str) or not text.strip():
        return "message_text_required"
    if "\n" in text or "\r" in text:
        return "message_text_multiline"
    return None


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

    def create_thread(self, snapshot: ThreadSnapshot) -> ThreadSnapshot:
        with self._lock:
            if snapshot.thread_id != self._snapshot.thread_id:
                raise ValueError("in-memory service only contains its configured thread")
            raise ValueError("thread identity already exists")

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
            semantic_rejection = _admission_rejection(parsed)
            if semantic_rejection is not None:
                receipt = self._receipt(parsed, status="rejected", rejection=semantic_rejection)
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
        _validate_json(payload, name="command.payload")
        try:
            if len(_canonical(command).encode("utf-8")) > _MAX_COMMAND_BYTES:
                raise ThreadProtocolError("command is too large")
        except (TypeError, ValueError):
            raise ThreadProtocolError("command is not JSON") from None
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


@dataclass(frozen=True, slots=True)
class ThreadModelDescriptor:
    """Authority-resolved model identity used to create an immutable Context."""

    model_id: str
    model_revision: str
    implementation_family: str


class ThreadModelCatalog(Protocol):
    default_model_id: str

    def resolve(self, model_id: str | None) -> ThreadModelDescriptor: ...


class ThreadCreator:
    """Resolve a registered model once, then persist a pinned Thread snapshot."""

    def __init__(self, service: ThreadService, catalog: ThreadModelCatalog) -> None:
        self._service = service
        self._catalog = catalog

    def create(self, model_id: str | None = None) -> ThreadSnapshot:
        descriptor = self._catalog.resolve(
            self._catalog.default_model_id if model_id is None else model_id
        )
        token = secrets.token_hex(10)
        context = ModelContextSnapshot(
            id="ctx_" + token, model_id=descriptor.model_id,
            model_revision=descriptor.model_revision,
            implementation_family=descriptor.implementation_family,
            selection_revision="sel_0",
        )
        snapshot = ThreadSnapshot(
            thread_id="thr_" + token,
            run=RunSnapshot(run_id="run_" + token, state="open"),
            active_model_context=context,
            active_grid_page_id="page_" + descriptor.model_id,
            current_attempt=None, last_event_seq=0, base_event_seq=0,
        )
        return self._service.create_thread(snapshot)


_THREAD_SCHEMA = """
CREATE TABLE IF NOT EXISTS capstone_threads (
    thread_id text PRIMARY KEY,
    run_id text NOT NULL UNIQUE,
    run_state text NOT NULL CHECK (run_state IN ('created', 'open', 'closing', 'closed', 'failed')),
    model_context_id text NOT NULL,
    model_id text NOT NULL,
    model_revision text NOT NULL,
    implementation_family text NOT NULL,
    selection_revision text NOT NULL,
    active_grid_page_id text NOT NULL,
    current_attempt jsonb,
    base_event_seq integer NOT NULL DEFAULT 0 CHECK (base_event_seq >= 0),
    last_event_seq integer NOT NULL DEFAULT 0 CHECK (last_event_seq >= 0),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS capstone_thread_events (
    thread_id text NOT NULL REFERENCES capstone_threads(thread_id) ON DELETE CASCADE,
    event_seq integer NOT NULL CHECK (event_seq > 0),
    event_id text NOT NULL UNIQUE,
    event_type text NOT NULL,
    event_version integer NOT NULL CHECK (event_version > 0),
    run_id text NOT NULL,
    turn_id text,
    attempt_id text,
    model_context_id text,
    selection_revision text,
    occurred_at timestamptz NOT NULL,
    visibility text NOT NULL CHECK (visibility IN ('public', 'diagnostic')),
    payload jsonb NOT NULL,
    PRIMARY KEY (thread_id, event_seq)
);
CREATE TABLE IF NOT EXISTS capstone_thread_commands (
    thread_id text NOT NULL REFERENCES capstone_threads(thread_id) ON DELETE CASCADE,
    idempotency_key text NOT NULL,
    request_hash text NOT NULL,
    command_id text NOT NULL,
    receipt jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (thread_id, idempotency_key),
    UNIQUE (thread_id, command_id)
);
"""


def _timestamp(value: Any) -> str:
    if isinstance(value, datetime):
        value = value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return str(value)


class PostgresThreadService:
    """Durable Thread projection store kept separate from the legacy session ledger."""

    def __init__(self, dsn: str) -> None:
        if not dsn:
            raise ValueError("database URL is required")
        self.dsn = dsn

    def _connect(self) -> psycopg.Connection[dict[str, Any]]:
        return psycopg.connect(self.dsn, row_factory=dict_row)

    def initialize(self) -> None:
        with self._connect() as connection:
            for statement in _THREAD_SCHEMA.split(";\n"):
                if statement.strip():
                    connection.execute(statement)

    def create_thread(self, snapshot: ThreadSnapshot) -> ThreadSnapshot:
        context = snapshot.active_model_context
        with self._connect() as connection:
            try:
                connection.execute(
                    """INSERT INTO capstone_threads
                    (thread_id, run_id, run_state, model_context_id, model_id, model_revision,
                     implementation_family, selection_revision, active_grid_page_id,
                     current_attempt, base_event_seq, last_event_seq)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (snapshot.thread_id, snapshot.run.run_id, snapshot.run.state,
                     context.id, context.model_id, context.model_revision,
                     context.implementation_family, context.selection_revision,
                     snapshot.active_grid_page_id,
                     None if snapshot.current_attempt is None else Jsonb(snapshot.current_attempt.to_document()),
                     snapshot.base_event_seq, snapshot.last_event_seq),
                )
            except psycopg.errors.UniqueViolation:
                raise ValueError("thread identity already exists") from None
        return snapshot

    def snapshot(self, thread_id: str) -> ThreadSnapshot:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM capstone_threads WHERE thread_id = %s", (thread_id,),
            ).fetchone()
        if row is None:
            raise ThreadNotFound(thread_id)
        return self._snapshot_from_row(row)

    def read_events(self, thread_id: str, after_event_seq: int) -> EventPage:
        if type(after_event_seq) is not int or after_event_seq < 0:
            raise ThreadProtocolError("event cursor is invalid")
        snapshot = self.snapshot(thread_id)
        if after_event_seq < snapshot.base_event_seq:
            raise ThreadResyncRequired(snapshot)
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM capstone_thread_events
                   WHERE thread_id = %s AND event_seq > %s
                   ORDER BY event_seq LIMIT 256""",
                (thread_id, after_event_seq),
            ).fetchall()
        events = tuple(self._event_from_row(row) for row in rows)
        next_event_seq = events[-1].event_seq if events else after_event_seq
        has_more = bool(events and next_event_seq < snapshot.last_event_seq)
        return EventPage(thread_id, after_event_seq, next_event_seq, has_more, events)

    def submit_command(self, command: Mapping[str, Any]) -> CommandReceipt:
        parsed = InMemoryThreadService._parse_command(command)
        request_hash = hashlib.sha256(_canonical(command).encode()).hexdigest()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT request_hash, receipt FROM capstone_thread_commands WHERE thread_id = %s AND idempotency_key = %s",
                (parsed["thread_id"], parsed["idempotency_key"]),
            ).fetchone()
            if row is not None:
                if row["request_hash"] != request_hash:
                    return self._receipt(parsed, status="rejected", rejection="idempotency_conflict")
                return CommandReceipt.from_document(row["receipt"])
            thread = connection.execute(
                "SELECT * FROM capstone_threads WHERE thread_id = %s FOR UPDATE",
                (parsed["thread_id"],),
            ).fetchone()
            if thread is None:
                raise ThreadNotFound(parsed["thread_id"])
            snapshot = self._snapshot_from_row(thread)
            if parsed["run_id"] is not None and parsed["run_id"] != snapshot.run.run_id:
                receipt = self._receipt(parsed, status="rejected", rejection="run_mismatch")
            elif parsed["expected_event_seq"] != snapshot.last_event_seq:
                receipt = self._receipt(parsed, status="rejected", rejection="stale_event_seq")
            elif (semantic_rejection := _admission_rejection(parsed)) is not None:
                receipt = self._receipt(parsed, status="rejected", rejection=semantic_rejection)
            elif snapshot.run.state != "open":
                receipt = self._receipt(parsed, status="rejected", rejection="run_not_open")
            else:
                event_seq = snapshot.last_event_seq + 1
                event = EventEnvelope(
                    event_id="evt_" + secrets.token_hex(8), event_seq=event_seq,
                    event_type="command_accepted", event_version=1,
                    thread_id=snapshot.thread_id, run_id=snapshot.run.run_id,
                    turn_id=None, attempt_id=None,
                    model_context_id=snapshot.active_model_context.id,
                    selection_revision=snapshot.active_model_context.selection_revision,
                    occurred_at=_now(), visibility="public",
                    payload={"command_id": parsed["command_id"], "kind": parsed["kind"],
                             "payload": parsed["payload"]},
                )
                connection.execute(
                    """INSERT INTO capstone_thread_events
                       (thread_id, event_seq, event_id, event_type, event_version, run_id,
                        turn_id, attempt_id, model_context_id, selection_revision,
                        occurred_at, visibility, payload)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (event.thread_id, event.event_seq, event.event_id, event.event_type,
                     event.event_version, event.run_id, event.turn_id, event.attempt_id,
                     event.model_context_id, event.selection_revision, event.occurred_at,
                     event.visibility, Jsonb(event.payload)),
                )
                connection.execute(
                    "UPDATE capstone_threads SET last_event_seq = %s WHERE thread_id = %s",
                    (event_seq, snapshot.thread_id),
                )
                receipt = self._receipt(parsed, status="accepted", accepted_event_seq=event_seq)
            connection.execute(
                """INSERT INTO capstone_thread_commands
                   (thread_id, idempotency_key, request_hash, command_id, receipt)
                   VALUES (%s, %s, %s, %s, %s)""",
                (parsed["thread_id"], parsed["idempotency_key"], request_hash,
                 parsed["command_id"], Jsonb(receipt.to_document())),
            )
            return receipt

    def compact_before(self, thread_id: str, base_event_seq: int) -> None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT base_event_seq, last_event_seq FROM capstone_threads WHERE thread_id = %s FOR UPDATE",
                (thread_id,),
            ).fetchone()
            if row is None:
                raise ThreadNotFound(thread_id)
            if base_event_seq < row["base_event_seq"] or base_event_seq > row["last_event_seq"]:
                raise ValueError("event base is invalid")
            connection.execute(
                "DELETE FROM capstone_thread_events WHERE thread_id = %s AND event_seq <= %s",
                (thread_id, base_event_seq),
            )
            connection.execute(
                "UPDATE capstone_threads SET base_event_seq = %s WHERE thread_id = %s",
                (base_event_seq, thread_id),
            )

    @staticmethod
    def _snapshot_from_row(row: Mapping[str, Any]) -> ThreadSnapshot:
        from .thread_protocol import AttemptSnapshot, ModelContextSnapshot, RunSnapshot

        attempt = None if row["current_attempt"] is None else AttemptSnapshot.from_document(row["current_attempt"])
        return ThreadSnapshot(
            thread_id=row["thread_id"],
            run=RunSnapshot(row["run_id"], row["run_state"]),
            active_model_context=ModelContextSnapshot(
                row["model_context_id"], row["model_id"], row["model_revision"],
                row["implementation_family"], row["selection_revision"],
            ),
            active_grid_page_id=row["active_grid_page_id"], current_attempt=attempt,
            last_event_seq=row["last_event_seq"], base_event_seq=row["base_event_seq"],
        )

    @staticmethod
    def _event_from_row(row: Mapping[str, Any]) -> EventEnvelope:
        return EventEnvelope(
            event_id=row["event_id"], event_seq=row["event_seq"], event_type=row["event_type"],
            event_version=row["event_version"], thread_id=row["thread_id"], run_id=row["run_id"],
            turn_id=row["turn_id"], attempt_id=row["attempt_id"],
            model_context_id=row["model_context_id"], selection_revision=row["selection_revision"],
            occurred_at=_timestamp(row["occurred_at"]), visibility=row["visibility"],
            payload=row["payload"],
        )

    @staticmethod
    def _receipt(
        command: Mapping[str, Any], *, status: str,
        accepted_event_seq: int | None = None, rejection: str | None = None,
    ) -> CommandReceipt:
        return CommandReceipt(
            command_id=command["command_id"], idempotency_key=command["idempotency_key"],
            thread_id=command["thread_id"], run_id=command.get("run_id"), status=status,
            accepted_event_seq=accepted_event_seq, rejection=rejection, target=None,
        )
