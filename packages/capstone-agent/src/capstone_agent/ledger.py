"""Transactional, domain-neutral session ledger shared by API and workers."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, cast

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from capstone_agent.protocol import Frame


class Conflict(ValueError):
    """A command conflicts with the committed session state."""


@dataclass(frozen=True, slots=True)
class SessionRecord:
    session_id: str
    application_id: str
    mode: str
    case_id: str | None
    provider: str | None
    model: str | None
    run_id: str | None
    state: str
    accepted_turns: int
    completed_turns: int
    error_code: str | None
    lease_token: str | None


@dataclass(frozen=True, slots=True)
class CommandRecord:
    command_id: str
    session_id: str
    ordinal: int | None
    kind: str
    instruction: str | None
    state: str


@dataclass(frozen=True, slots=True)
class EventRecord:
    session_id: str
    sequence: int
    kind: str
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    session_id: str
    run_id: str
    kind: str
    ref: str | None
    object_key: str
    sha256: str
    mime: str
    byte_count: int


_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id text PRIMARY KEY,
    application_id text NOT NULL,
    mode text NOT NULL,
    case_id text,
    provider text,
    model text,
    run_id text,
    state text NOT NULL CHECK (state IN
        ('pending', 'ready', 'executing', 'closing', 'completed', 'failed', 'interrupted')),
    accepted_turns integer NOT NULL DEFAULT 0,
    completed_turns integer NOT NULL DEFAULT 0,
    active_turn boolean NOT NULL DEFAULT false,
    error_code text,
    lease_token text,
    lease_deadline timestamptz,
    create_key text,
    create_hash text,
    capacity_victim_id text,
    created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS create_key text;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS create_hash text;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS capacity_victim_id text;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS disconnect_key text;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS disconnect_hash text;
CREATE UNIQUE INDEX IF NOT EXISTS sessions_create_key_idx ON sessions(create_key);
CREATE TABLE IF NOT EXISTS session_commands (
    command_id text PRIMARY KEY,
    session_id text NOT NULL REFERENCES sessions(session_id),
    ordinal integer,
    kind text NOT NULL CHECK (kind IN ('turn', 'close')),
    instruction text,
    idempotency_key text NOT NULL,
    request_hash text NOT NULL,
    state text NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'dispatched', 'done')),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(session_id, idempotency_key),
    UNIQUE(session_id, ordinal)
);
CREATE TABLE IF NOT EXISTS session_events (
    session_id text NOT NULL REFERENCES sessions(session_id),
    sequence integer NOT NULL,
    kind text NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(session_id, sequence)
);
CREATE TABLE IF NOT EXISTS session_artifacts (
    artifact_id text PRIMARY KEY,
    session_id text NOT NULL REFERENCES sessions(session_id),
    run_id text NOT NULL,
    kind text NOT NULL CHECK (kind IN ('report', 'evidence')),
    ref text,
    object_key text NOT NULL UNIQUE,
    sha256 text NOT NULL,
    mime text NOT NULL,
    byte_count integer NOT NULL CHECK (byte_count >= 0),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS session_artifacts_ref_idx
    ON session_artifacts(session_id, kind, ref) WHERE ref IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS session_artifacts_report_idx
    ON session_artifacts(session_id, kind) WHERE kind = 'report';
CREATE INDEX IF NOT EXISTS session_commands_pending_idx
    ON session_commands(session_id, created_at) WHERE state = 'pending';
"""


def _session(row: dict[str, Any]) -> SessionRecord:
    return SessionRecord(*(row[key] for key in (
        "session_id", "application_id", "mode", "case_id", "provider", "model",
        "run_id", "state", "accepted_turns", "completed_turns", "error_code", "lease_token",
    )))


def _command(row: dict[str, Any]) -> CommandRecord:
    return CommandRecord(*(row[key] for key in (
        "command_id", "session_id", "ordinal", "kind", "instruction", "state",
    )))


class Ledger:
    def __init__(self, dsn: str) -> None:
        if not dsn:
            raise ValueError("database URL is required")
        self.dsn = dsn

    def _connect(self) -> psycopg.Connection[dict[str, Any]]:
        return cast(
            psycopg.Connection[dict[str, Any]],
            psycopg.connect(self.dsn, row_factory=cast(Any, dict_row)),
        )

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(152695101)")
            for statement in _SCHEMA.split(";\n"):
                if statement.strip():
                    connection.execute(statement)

    def ping(self) -> bool:
        with self._connect() as connection:
            return connection.execute("SELECT 1").fetchone() is not None

    def create_session(
        self, application_id: str, mode: str, case_id: str | None,
        provider: str | None, model: str | None,
        *, idempotency_key: str | None = None,
    ) -> SessionRecord:
        if idempotency_key is not None and (not idempotency_key or len(idempotency_key) > 200):
            raise ValueError("idempotency key is invalid")
        request_hash = hashlib.sha256(repr((application_id, mode, case_id, provider, model))
                                      .encode()).hexdigest()
        session_id = "session-" + secrets.token_hex(12)
        with self._connect() as connection:
            row = connection.execute(
                """INSERT INTO sessions
                   (session_id, application_id, mode, case_id, provider, model,
                    state, create_key, create_hash)
                   VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s, %s)
                   ON CONFLICT (create_key) DO NOTHING RETURNING *""",
                (session_id, application_id, mode, case_id, provider, model,
                 idempotency_key, request_hash),
            ).fetchone()
            if row is None:
                row = connection.execute(
                    "SELECT * FROM sessions WHERE create_key = %s", (idempotency_key,),
                ).fetchone()
        assert row is not None
        if row["create_hash"] != request_hash:
            raise Conflict("idempotency key has another session request")
        return _session(row)

    def get_session(self, session_id: str) -> SessionRecord | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM sessions WHERE session_id = %s",
                                     (session_id,)).fetchone()
        return _session(row) if row is not None else None

    def disconnect_session(self, session_id: str, idempotency_key: str) -> SessionRecord:
        """Interrupt a session and release its worker lease, safely retryable."""
        if not idempotency_key or len(idempotency_key) > 200:
            raise ValueError("idempotency key is invalid")
        request_hash = hashlib.sha256(f"disconnect\0{session_id}".encode()).hexdigest()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM sessions WHERE session_id = %s FOR UPDATE", (session_id,),
            ).fetchone()
            if row is None:
                raise KeyError("session not found")
            if row["disconnect_key"] is not None:
                if row["disconnect_key"] != idempotency_key or row["disconnect_hash"] != request_hash:
                    raise Conflict("disconnect key has another request")
                return _session(row)
            state = row["state"]
            next_state = "interrupted" if state not in {"completed", "failed", "interrupted"} else state
            error_code = "session_disconnected" if next_state == "interrupted" else row["error_code"]
            updated = connection.execute(
                """UPDATE sessions SET state = %s, error_code = %s, active_turn = false,
                   lease_token = NULL, lease_deadline = NULL, disconnect_key = %s,
                   disconnect_hash = %s WHERE session_id = %s RETURNING *""",
                (next_state, error_code, idempotency_key, request_hash, session_id),
            ).fetchone()
        assert updated is not None
        return _session(updated)

    def claim_pending(self, worker_id: str, lease_seconds: int) -> SessionRecord | None:
        if not worker_id or lease_seconds < 1:
            raise ValueError("worker lease is invalid")
        token = secrets.token_hex(16)
        with self._connect() as connection:
            row = connection.execute(
                """SELECT session_id FROM sessions WHERE state = 'pending' AND lease_token IS NULL
                   ORDER BY created_at, session_id LIMIT 1 FOR UPDATE SKIP LOCKED"""
            ).fetchone()
            if row is None:
                return None
            claimed = connection.execute(
                """UPDATE sessions SET lease_token = %s,
                   lease_deadline = now() + (%s * interval '1 second')
                   WHERE session_id = %s RETURNING *""",
                (token, lease_seconds, row["session_id"]),
            ).fetchone()
        assert claimed is not None
        return _session(claimed)

    def renew_lease(self, session_id: str, token: str, lease_seconds: int) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """UPDATE sessions SET lease_deadline = now() + (%s * interval '1 second')
                   WHERE session_id = %s AND lease_token = %s
                   AND state NOT IN ('completed', 'failed', 'interrupted') RETURNING session_id""",
                (lease_seconds, session_id, token),
            ).fetchone()
        return row is not None

    def mark_interrupted_stale(self, *, now: datetime | None = None) -> int:
        moment = now or datetime.now(timezone.utc)
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE sessions SET state = 'interrupted', error_code = 'worker_interrupted',
                   lease_token = NULL, lease_deadline = NULL
                   WHERE lease_token IS NOT NULL AND lease_deadline < %s
                   AND state NOT IN ('completed', 'failed', 'interrupted')""",
                (moment,),
            )
            return cursor.rowcount

    def mark_interrupted_idle(self, session_id: str, token: str) -> bool:
        """Release an idle ready session only if no command was accepted meanwhile."""
        with self._connect() as connection:
            row = connection.execute(
                """UPDATE sessions AS current
                   SET state = 'interrupted', error_code = 'session_idle_timeout',
                       lease_token = NULL, lease_deadline = NULL
                   WHERE current.session_id = %s AND current.lease_token = %s
                   AND current.state = 'ready' AND NOT current.active_turn
                   AND NOT EXISTS (
                       SELECT 1 FROM session_commands AS command
                       WHERE command.session_id = current.session_id AND command.state = 'pending'
                   ) RETURNING current.session_id""",
                (session_id, token),
            ).fetchone()
        return row is not None

    def evict_oldest_idle(
        self, *, minimum_idle_seconds: float = 30, minimum_wait_seconds: float = 1,
    ) -> str | None:
        """Reserve one globally oldest idle slot for one waiting session."""
        if minimum_idle_seconds < 0 or minimum_wait_seconds < 0:
            raise ValueError("minimum idle or waiting duration is invalid")
        with self._connect() as connection:
            waiting = connection.execute(
                """SELECT session_id FROM sessions
                   WHERE state = 'pending' AND lease_token IS NULL
                   AND capacity_victim_id IS NULL
                   AND created_at <= now() - (%s * interval '1 second')
                   ORDER BY created_at, session_id
                   LIMIT 1 FOR UPDATE SKIP LOCKED""",
                (minimum_wait_seconds,),
            ).fetchone()
            if waiting is None:
                return None
            victim = connection.execute(
                """SELECT current.session_id FROM sessions AS current
                   WHERE current.state = 'ready' AND NOT current.active_turn
                   AND COALESCE((
                       SELECT max(event.created_at) FROM session_events AS event
                       WHERE event.session_id = current.session_id
                       AND event.kind IN ('ready', 'answer_committed')
                   ), current.created_at) <= now() - (%s * interval '1 second')
                   AND NOT EXISTS (
                       SELECT 1 FROM session_commands AS command
                       WHERE command.session_id = current.session_id
                       AND command.state = 'pending'
                   )
                   ORDER BY COALESCE((
                       SELECT max(event.created_at) FROM session_events AS event
                       WHERE event.session_id = current.session_id
                       AND event.kind IN ('ready', 'answer_committed')
                   ), current.created_at), current.session_id
                   LIMIT 1 FOR UPDATE OF current SKIP LOCKED""",
                (minimum_idle_seconds,),
            ).fetchone()
            if victim is None:
                return None
            connection.execute(
                """UPDATE sessions SET state = 'interrupted',
                   error_code = 'session_capacity_evicted',
                   lease_token = NULL, lease_deadline = NULL
                   WHERE session_id = %s""",
                (victim["session_id"],),
            )
            connection.execute(
                "UPDATE sessions SET capacity_victim_id = %s WHERE session_id = %s",
                (victim["session_id"], waiting["session_id"]),
            )
            return victim["session_id"]

    def mark_failed(self, session_id: str, token: str, error_code: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """UPDATE sessions SET state = 'failed', error_code = %s,
                   active_turn = false, lease_token = NULL, lease_deadline = NULL
                   WHERE session_id = %s AND lease_token = %s
                   AND state NOT IN ('completed', 'failed', 'interrupted')
                   RETURNING session_id""",
                (error_code, session_id, token),
            ).fetchone()
        return row is not None

    def _accept(self, session_id: str, kind: str, instruction: str | None,
                idempotency_key: str) -> CommandRecord:
        if not idempotency_key or len(idempotency_key) > 200:
            raise ValueError("idempotency key is invalid")
        request_hash = hashlib.sha256(f"{kind}\0{instruction or ''}".encode()).hexdigest()
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM sessions WHERE session_id = %s FOR UPDATE",
                                     (session_id,)).fetchone()
            if row is None:
                raise KeyError("session not found")
            existing = connection.execute(
                """SELECT * FROM session_commands
                   WHERE session_id = %s AND idempotency_key = %s""",
                (session_id, idempotency_key),
            ).fetchone()
            if existing is not None:
                if existing["request_hash"] != request_hash:
                    raise Conflict("idempotency key has another command")
                return _command(existing)
            if kind == "turn":
                if row["state"] != "ready" or row["active_turn"]:
                    raise Conflict("session cannot accept a turn")
                ordinal = row["accepted_turns"] + 1
                connection.execute(
                    """UPDATE sessions SET accepted_turns = %s, active_turn = true,
                       state = 'executing' WHERE session_id = %s""",
                    (ordinal, session_id),
                )
            else:
                if row["state"] != "ready" or row["active_turn"]:
                    raise Conflict("session cannot close")
                ordinal = None
                connection.execute("UPDATE sessions SET state = 'closing' WHERE session_id = %s",
                                   (session_id,))
            inserted = connection.execute(
                """INSERT INTO session_commands
                   (command_id, session_id, ordinal, kind, instruction,
                    idempotency_key, request_hash)
                   VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *""",
                ("command-" + secrets.token_hex(12), session_id, ordinal, kind,
                 instruction, idempotency_key, request_hash),
            ).fetchone()
        assert inserted is not None
        return _command(inserted)

    def accept_turn(self, session_id: str, instruction: str,
                    idempotency_key: str) -> CommandRecord:
        if not instruction or not instruction.strip() or len(instruction) > 32_000:
            raise ValueError("instruction is invalid")
        return self._accept(session_id, "turn", instruction, idempotency_key)

    def accept_close(self, session_id: str, idempotency_key: str) -> CommandRecord:
        return self._accept(session_id, "close", None, idempotency_key)

    def next_command(self, session_id: str, token: str) -> CommandRecord | None:
        with self._connect() as connection:
            owner = connection.execute(
                """SELECT session_id FROM sessions WHERE session_id = %s
                   AND lease_token = %s AND state NOT IN ('failed', 'interrupted', 'completed')""",
                (session_id, token),
            ).fetchone()
            if owner is None:
                raise Conflict("worker lease is unavailable")
            row = connection.execute(
                """SELECT * FROM session_commands WHERE session_id = %s AND state = 'pending'
                   ORDER BY created_at, command_id LIMIT 1 FOR UPDATE SKIP LOCKED""",
                (session_id,),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                "UPDATE session_commands SET state = 'dispatched' WHERE command_id = %s",
                (row["command_id"],),
            )
            return _command({**row, "state": "dispatched"})

    def append_event(self, session_id: str, token: str, frame: Frame) -> None:
        if frame.session_id != session_id:
            raise Conflict("event session differs from lease")
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM sessions WHERE session_id = %s FOR UPDATE",
                                     (session_id,)).fetchone()
            if row is None or row["lease_token"] != token or row["state"] in {
                "failed", "interrupted", "completed"
            }:
                raise Conflict("worker lease is unavailable")
            previous = connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) AS sequence FROM session_events WHERE session_id = %s",
                (session_id,),
            ).fetchone()
            assert previous is not None
            if frame.sequence != previous["sequence"] + 1:
                raise Conflict("event sequence is out of order")
            connection.execute(
                """INSERT INTO session_events (session_id, sequence, kind, payload)
                   VALUES (%s, %s, %s, %s)""",
                (session_id, frame.sequence, frame.kind, Jsonb(frame.payload)),
            )
            if frame.kind == "ready":
                connection.execute(
                    "UPDATE sessions SET state = 'ready', run_id = %s WHERE session_id = %s",
                    (frame.payload["run_id"], session_id),
                )
            elif frame.kind == "answer_committed":
                ordinal = frame.payload["ordinal"]
                if ordinal != row["completed_turns"] + 1 or not row["active_turn"]:
                    raise Conflict("answer ordinal is out of order")
                connection.execute(
                    """UPDATE sessions SET completed_turns = %s, active_turn = false,
                       state = 'ready' WHERE session_id = %s""",
                    (ordinal, session_id),
                )
                connection.execute(
                    """UPDATE session_commands SET state = 'done'
                       WHERE session_id = %s AND kind = 'turn' AND ordinal = %s""",
                    (session_id, ordinal),
                )
            elif frame.kind in {"completed", "failed"}:
                state = "completed" if frame.kind == "completed" else "failed"
                error_code = None if state == "completed" else frame.payload["code"]
                connection.execute(
                    """UPDATE sessions SET state = %s, error_code = %s, active_turn = false,
                       lease_token = NULL, lease_deadline = NULL WHERE session_id = %s""",
                    (state, error_code, session_id),
                )
                if state == "completed":
                    connection.execute(
                        """UPDATE session_commands SET state = 'done'
                           WHERE session_id = %s AND kind = 'close'""",
                        (session_id,),
                    )

    def events_after(self, session_id: str, sequence: int) -> list[EventRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT session_id, sequence, kind, payload FROM session_events
                   WHERE session_id = %s AND sequence > %s ORDER BY sequence""",
                (session_id, sequence),
            ).fetchall()
        return [EventRecord(**row) for row in rows]

    def save_artifact(self, artifact: ArtifactRecord) -> None:
        with self._connect() as connection:
            session = connection.execute(
                "SELECT run_id FROM sessions WHERE session_id = %s FOR UPDATE",
                (artifact.session_id,),
            ).fetchone()
            if session is None or session["run_id"] != artifact.run_id:
                raise Conflict("artifact does not belong to current run")
            if artifact.kind == "evidence":
                if not artifact.ref:
                    raise ValueError("evidence reference is invalid")
                admitted = connection.execute(
                    """SELECT 1 FROM session_events WHERE session_id = %s
                       AND kind = 'answer_committed' AND payload->'evidence_refs' ? %s LIMIT 1""",
                    (artifact.session_id, artifact.ref),
                ).fetchone()
                if admitted is None:
                    raise ValueError("evidence reference was not admitted")
            elif artifact.kind != "report" or artifact.ref is not None:
                raise ValueError("artifact kind or reference is invalid")
            connection.execute(
                """INSERT INTO session_artifacts
                   (artifact_id, session_id, run_id, kind, ref, object_key,
                    sha256, mime, byte_count)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                ("artifact-" + secrets.token_hex(12), artifact.session_id,
                 artifact.run_id, artifact.kind, artifact.ref, artifact.object_key,
                 artifact.sha256, artifact.mime, artifact.byte_count),
            )

    def get_artifact(self, session_id: str, kind: str,
                     ref: str | None) -> ArtifactRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT session_id, run_id, kind, ref, object_key, sha256, mime,
                   byte_count FROM session_artifacts WHERE session_id = %s
                   AND kind = %s AND ref IS NOT DISTINCT FROM %s""",
                (session_id, kind, ref),
            ).fetchone()
        return ArtifactRecord(**row) if row is not None else None
