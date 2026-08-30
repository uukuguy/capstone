"""Durable application-context snapshots and hash-checked event replay."""

from __future__ import annotations

import json
import os
import stat
import secrets
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path
from threading import RLock
from typing import Any

from pydantic import ValidationError

from capability_agent.application.context_models import (
    ApplicationContext,
    ContextEvent,
    ContextEventDraft,
    CoreContext,
    DomainStateEnvelope,
    canonical_state_hash,
)
from capability_agent.application.context_reducer import (
    ContextTransitionError,
    reduce_context,
)
from capability_agent.application.workspace import ApplicationWorkspace
from capability_agent.trajectory.canonical import canonical_json_bytes


class ContextStoreError(RuntimeError):
    """Raised when durable context state or replay integrity is invalid."""


class ApplicationContextStore:
    """Append context transitions and atomically materialize their snapshot."""

    def __init__(self, workspace: ApplicationWorkspace, snapshot: ApplicationContext) -> None:
        if workspace.run_id != snapshot.run_id:
            raise ContextStoreError("workspace and context run identifiers differ")
        self._workspace = workspace
        recovered = _recover_pending_transaction(workspace)
        if recovered is not None:
            snapshot = recovered
        self._snapshot = snapshot
        self._ledger_identity = _file_identity(
            workspace.context_events_path,
            label="context ledger",
        )
        self._snapshot_identity = _file_identity(
            workspace.context_snapshot_path,
            label="context snapshot",
        )
        self._append_lock = RLock()
        self._unavailable = False

    @property
    def workspace(self) -> ApplicationWorkspace:
        return self._workspace

    @property
    def snapshot(self) -> ApplicationContext:
        return self._snapshot

    @property
    def _transaction_path(self) -> Path:
        return self._workspace.core_path / ".context-transaction.json"

    @classmethod
    def initialize(
        cls,
        workspace: ApplicationWorkspace,
        *,
        domains: Mapping[str, str | DomainStateEnvelope] | None = None,
        core: CoreContext | Mapping[str, Any] | None = None,
    ) -> "ApplicationContextStore":
        """Create a store and append its self-contained genesis transition."""

        if _has_content(workspace.context_events_path):
            raise ContextStoreError("context ledger already contains events")
        if _has_content(workspace.context_snapshot_path):
            raise ContextStoreError("context snapshot already exists")

        declared = tuple(workspace.domain_roots)
        if domains is None:
            domains = {
                binding_id: "application-domain-state/1.0"
                for binding_id in declared
            }
        if set(domains) != set(declared):
            raise ContextStoreError("context domains must match declared bindings")
        try:
            initial = ApplicationContext.initial(
                run_id=workspace.run_id,
                domains=domains,
                core=core,
            )
        except (TypeError, ValueError, ValidationError):
            raise ContextStoreError("initial application context is invalid") from None
        store = cls(workspace, initial)
        start_payload = {
            "core": initial.core.model_dump(mode="json"),
            "domains": {
                binding_id: envelope.model_dump(mode="json")
                for binding_id, envelope in initial.domains.items()
            },
        }
        store.append(
            ContextEventDraft(
                event_type="analysis.started",
                payload=start_payload,
            )
        )
        return store

    def append(self, draft: ContextEventDraft) -> ContextEvent:
        """Durably append a transition before publishing its new snapshot."""

        return self.append_many((draft,))[0]

    def append_many(
        self, drafts: Iterable[ContextEventDraft]
    ) -> tuple[ContextEvent, ...]:
        """Atomically append an ordered group of context transitions.

        The complete next ledger and materialized snapshot are staged before a
        transaction marker is published.  The marker lets a later store
        instance finish or roll back an interrupted replacement, so callers
        never need to compensate by rewriting context files themselves.
        """

        try:
            pending = tuple(drafts)
        except Exception:
            raise ContextStoreError("context transaction drafts are invalid") from None
        if not pending:
            return ()
        if not all(isinstance(draft, ContextEventDraft) for draft in pending):
            raise ContextStoreError("context transaction drafts are invalid")

        with self._append_lock:
            if self._unavailable:
                raise ContextStoreError("context store is unavailable")
            previous = self._snapshot
            events: list[ContextEvent] = []
            next_state = previous
            # Reduction is deliberately completed before touching the durable
            # files.  A rejected transition therefore never makes a healthy
            # store unavailable.
            try:
                for draft in pending:
                    try:
                        candidate = reduce_context(next_state, draft)
                    except ContextTransitionError as error:
                        raise ContextStoreError(str(error)) from None
                    try:
                        event = ContextEvent(
                            run_id=previous.run_id,
                            sequence=candidate.revision,
                            event_type=draft.event_type,
                            binding_id=draft.binding_id,
                            turn_id=draft.turn_id,
                            capability=draft.capability,
                            trace_sequence=draft.trace_sequence,
                            timestamp=draft.timestamp,
                            payload=draft.payload,
                            previous_revision=next_state.revision,
                            previous_state_hash=next_state.state_hash,
                            next_revision=candidate.revision,
                            next_state_hash=candidate.state_hash,
                        )
                    except (TypeError, ValueError, ValidationError):
                        raise ContextStoreError("context event is invalid") from None
                    events.append(event)
                    next_state = candidate
            except ContextStoreError:
                raise

            transaction: _TransactionRecord | None = None
            temporary_paths: list[Path] = []
            try:
                _require_file_identity(
                    self._workspace.context_snapshot_path,
                    self._snapshot_identity,
                    label="context snapshot",
                )
                _require_file_identity(
                    self._workspace.context_events_path,
                    self._ledger_identity,
                    label="context ledger",
                )
                ledger_bytes = _read_regular_bytes(
                    self._workspace.context_events_path, label="context ledger"
                )
                snapshot_bytes = _read_regular_bytes(
                    self._workspace.context_snapshot_path, label="context snapshot"
                )
                final_ledger = ledger_bytes + b"".join(
                    canonical_json_bytes(event.model_dump(mode="json"))
                    for event in events
                )
                next_snapshot_bytes = canonical_json_bytes(
                    next_state.model_dump(mode="json")
                )
                staged_ledger = _stage_bytes(
                    self._workspace.context_events_path,
                    final_ledger,
                    label="context ledger",
                )
                temporary_paths.append(staged_ledger)
                staged_snapshot = _stage_snapshot(
                    self._workspace.context_snapshot_path,
                    next_state.model_dump(mode="json"),
                )
                temporary_paths.append(staged_snapshot)
                backup_ledger = _stage_bytes(
                    self._workspace.context_events_path,
                    ledger_bytes,
                    label="context ledger backup",
                )
                temporary_paths.append(backup_ledger)
                backup_snapshot = _stage_bytes(
                    self._workspace.context_snapshot_path,
                    snapshot_bytes,
                    label="context snapshot backup",
                )
                temporary_paths.append(backup_snapshot)
                transaction = _TransactionRecord(
                    run_id=previous.run_id,
                    previous_revision=previous.revision,
                    next_revision=next_state.revision,
                    previous_ledger_sha256=_sha256_bytes(ledger_bytes),
                    next_ledger_sha256=_sha256_bytes(final_ledger),
                    previous_snapshot_sha256=_sha256_bytes(snapshot_bytes),
                    next_snapshot_sha256=_sha256_bytes(next_snapshot_bytes),
                    staged_ledger=staged_ledger.name,
                    staged_snapshot=staged_snapshot.name,
                    backup_ledger=backup_ledger.name,
                    backup_snapshot=backup_snapshot.name,
                    phase="prepared",
                )
                _write_transaction(self._transaction_path, transaction)
                _replace_ledger(
                    staged_ledger,
                    self._workspace.context_events_path,
                    expected_identity=self._ledger_identity,
                )
                transaction = transaction.with_phase("ledger-replaced")
                _write_transaction(self._transaction_path, transaction)
                _replace_snapshot(staged_snapshot, self._workspace.context_snapshot_path)
                # Keep the marker in its last pre-snapshot phase until
                # cleanup. Recovery relies on the recorded content hashes,
                # so a crash after this replacement is still unambiguous.
                # This also leaves the snapshot replacement as the final
                # durable ``os.replace`` in the normal path.
                next_ledger_identity = _file_identity(
                    self._workspace.context_events_path,
                    label="context ledger",
                )
                next_snapshot_identity = _file_identity(
                    self._workspace.context_snapshot_path,
                    label="context snapshot",
                )
                self._snapshot = next_state
                self._ledger_identity = next_ledger_identity
                self._snapshot_identity = next_snapshot_identity
                _finish_transaction(
                    self._transaction_path, transaction, temporary_paths
                )
                return tuple(events)
            except BaseException as error:
                try:
                    if transaction is not None:
                        _rollback_transaction(
                            self._transaction_path, transaction, temporary_paths
                        )
                    else:
                        _cleanup_transaction_paths(temporary_paths)
                except Exception:
                    # The transaction marker and file identities remain the
                    # recovery boundary if rollback itself cannot complete.
                    pass
                if transaction is not None:
                    # A successful rollback restores the previous logical
                    # state. If rollback itself failed, the store is already
                    # fail-closed and this in-memory value is not publishable.
                    self._snapshot = previous
                self._unavailable = True
                # Preserve the Store's semantic errors (validation, identity,
                # and integrity failures). Only an unexpected implementation
                # exception receives the generic persistence message.
                if isinstance(error, ContextStoreError):
                    raise
                if isinstance(error, Exception):
                    raise ContextStoreError("context persistence failed") from None
                raise

    @classmethod
    def replay(
        cls, ledger_path: Path | ApplicationWorkspace
    ) -> ApplicationContext:
        """Replay a self-contained ledger and verify every hash boundary."""

        path = (
            ledger_path.context_events_path
            if isinstance(ledger_path, ApplicationWorkspace)
            else Path(ledger_path)
        )
        _require_regular_file(path, label="context ledger")
        try:
            raw_bytes = path.read_bytes()
        except OSError:
            raise ContextStoreError("context ledger cannot be read") from None
        if not raw_bytes:
            raise ContextStoreError("context ledger is empty")
        if not raw_bytes.endswith(b"\n"):
            raise ContextStoreError("context ledger must end with a newline")
        raw_lines = raw_bytes.splitlines()

        state: ApplicationContext | None = None
        expected_sequence = 1
        for line_number, raw_line in enumerate(raw_lines, start=1):
            if not raw_line.strip():
                raise ContextStoreError(f"malformed context ledger line {line_number}")
            try:
                payload = json.loads(raw_line)
                event = ContextEvent.model_validate(payload)
            except (json.JSONDecodeError, TypeError, ValueError, ValidationError):
                raise ContextStoreError(f"malformed context ledger line {line_number}") from None

            if event.sequence != expected_sequence:
                raise ContextStoreError("context ledger sequence is not contiguous")
            if state is None:
                state = _genesis_from_event(event)
            if event.run_id != state.run_id:
                raise ContextStoreError("context ledger run identifier changed")
            if event.previous_revision != state.revision:
                raise ContextStoreError("context ledger previous revision mismatch")
            if event.previous_state_hash != state.state_hash:
                raise ContextStoreError("context ledger previous state hash mismatch")
            try:
                draft = ContextEventDraft(
                    event_type=event.event_type,
                    binding_id=event.binding_id,
                    turn_id=event.turn_id,
                    capability=event.capability,
                    trace_sequence=event.trace_sequence,
                    timestamp=event.timestamp,
                    payload=event.payload,
                )
                next_state = reduce_context(state, draft)
            except (ContextTransitionError, TypeError, ValueError, ValidationError):
                raise ContextStoreError(f"invalid context transition at line {line_number}") from None
            if event.next_revision != next_state.revision:
                raise ContextStoreError("context ledger next revision mismatch")
            if event.next_state_hash != next_state.state_hash:
                raise ContextStoreError("context ledger next state hash mismatch")
            state = next_state
            expected_sequence += 1

        if state is None:
            raise ContextStoreError("context ledger is empty")
        return state

    def verify_materialized_snapshot(self) -> ApplicationContext:
        """Verify the on-disk snapshot against memory and a complete replay."""

        _require_regular_file(self._workspace.context_snapshot_path, label="context snapshot")
        try:
            snapshot_payload = json.loads(
                self._workspace.context_snapshot_path.read_text(encoding="utf-8")
            )
            materialized = ApplicationContext.model_validate(snapshot_payload)
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError, ValidationError):
            raise ContextStoreError("materialized context snapshot is invalid") from None
        if materialized.run_id != self._workspace.run_id:
            raise ContextStoreError("materialized context run identifier differs")
        if materialized.state_hash != canonical_state_hash(materialized):
            raise ContextStoreError("materialized context state hash mismatch")
        replayed = self.replay(self._workspace.context_events_path)
        if materialized != self._snapshot:
            raise ContextStoreError("materialized context snapshot mismatch")
        if materialized != replayed:
            raise ContextStoreError("materialized context does not match replay")
        return materialized


@dataclass(frozen=True, slots=True)
class _TransactionRecord:
    run_id: str
    previous_revision: int
    next_revision: int
    previous_ledger_sha256: str
    next_ledger_sha256: str
    previous_snapshot_sha256: str
    next_snapshot_sha256: str
    staged_ledger: str
    staged_snapshot: str
    backup_ledger: str
    backup_snapshot: str
    phase: str

    def with_phase(self, phase: str) -> "_TransactionRecord":
        return replace(self, phase=phase)

    def as_json(self) -> dict[str, object]:
        return {
            "schema": "application-context-transaction/1.0",
            "run_id": self.run_id,
            "previous_revision": self.previous_revision,
            "next_revision": self.next_revision,
            "previous_ledger_sha256": self.previous_ledger_sha256,
            "next_ledger_sha256": self.next_ledger_sha256,
            "previous_snapshot_sha256": self.previous_snapshot_sha256,
            "next_snapshot_sha256": self.next_snapshot_sha256,
            "staged_ledger": self.staged_ledger,
            "staged_snapshot": self.staged_snapshot,
            "backup_ledger": self.backup_ledger,
            "backup_snapshot": self.backup_snapshot,
            "phase": self.phase,
        }


def _recover_pending_transaction(
    workspace: ApplicationWorkspace,
) -> ApplicationContext | None:
    transaction_path = workspace.core_path / ".context-transaction.json"
    if _require_regular_file(
        transaction_path, label="context transaction", allow_missing=True
    ) is None:
        return None
    record = _read_transaction(transaction_path)
    if record.run_id != workspace.run_id:
        raise ContextStoreError("pending context transaction belongs to another run")
    core = workspace.core_path.resolve()
    paths = {
        field: _transaction_temp_path(core, getattr(record, field))
        for field in (
            "staged_ledger",
            "staged_snapshot",
            "backup_ledger",
            "backup_snapshot",
        )
    }
    ledger = _read_regular_bytes(workspace.context_events_path, label="context ledger")
    snapshot = _read_regular_bytes(
        workspace.context_snapshot_path, label="context snapshot"
    )
    ledger_hash = _sha256_bytes(ledger)
    snapshot_hash = _sha256_bytes(snapshot)
    old_pair = (
        ledger_hash == record.previous_ledger_sha256
        and snapshot_hash == record.previous_snapshot_sha256
    )
    new_pair = (
        ledger_hash == record.next_ledger_sha256
        and snapshot_hash == record.next_snapshot_sha256
    )
    ledger_new_snapshot_old = (
        ledger_hash == record.next_ledger_sha256
        and snapshot_hash == record.previous_snapshot_sha256
    )
    if old_pair:
        _finish_transaction(transaction_path, record, paths.values())
        return None
    if new_pair:
        _finish_transaction(transaction_path, record, paths.values())
        return _load_materialized_snapshot(workspace)
    if ledger_new_snapshot_old:
        staged_snapshot = paths["staged_snapshot"]
        if not staged_snapshot.is_file() or staged_snapshot.is_symlink():
            raise ContextStoreError("pending context transaction is incomplete")
        _replace_path(staged_snapshot, workspace.context_snapshot_path)
        committed = _read_regular_bytes(
            workspace.context_snapshot_path, label="context snapshot"
        )
        if _sha256_bytes(committed) != record.next_snapshot_sha256:
            raise ContextStoreError("pending context transaction is inconsistent")
        _finish_transaction(transaction_path, record, paths.values())
        return _load_materialized_snapshot(workspace)
    raise ContextStoreError("pending context transaction is inconsistent")


def _load_materialized_snapshot(workspace: ApplicationWorkspace) -> ApplicationContext:
    try:
        payload = json.loads(
            workspace.context_snapshot_path.read_text(encoding="utf-8")
        )
        snapshot = ApplicationContext.model_validate(payload)
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError, ValidationError):
        raise ContextStoreError("materialized context snapshot is invalid") from None
    if snapshot.run_id != workspace.run_id:
        raise ContextStoreError("materialized context run identifier differs")
    if snapshot.state_hash != canonical_state_hash(snapshot):
        raise ContextStoreError("materialized context state hash mismatch")
    return snapshot


def _read_transaction(path: Path) -> _TransactionRecord:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ContextStoreError("pending context transaction is unreadable") from None
    if not isinstance(payload, Mapping):
        raise ContextStoreError("pending context transaction is invalid")
    required = {
        "schema",
        "run_id",
        "previous_revision",
        "next_revision",
        "previous_ledger_sha256",
        "next_ledger_sha256",
        "previous_snapshot_sha256",
        "next_snapshot_sha256",
        "staged_ledger",
        "staged_snapshot",
        "backup_ledger",
        "backup_snapshot",
        "phase",
    }
    if (
        set(payload) != required
        or payload.get("schema") != "application-context-transaction/1.0"
    ):
        raise ContextStoreError("pending context transaction is invalid")
    try:
        record = _TransactionRecord(
            run_id=payload["run_id"],
            previous_revision=payload["previous_revision"],
            next_revision=payload["next_revision"],
            previous_ledger_sha256=payload["previous_ledger_sha256"],
            next_ledger_sha256=payload["next_ledger_sha256"],
            previous_snapshot_sha256=payload["previous_snapshot_sha256"],
            next_snapshot_sha256=payload["next_snapshot_sha256"],
            staged_ledger=payload["staged_ledger"],
            staged_snapshot=payload["staged_snapshot"],
            backup_ledger=payload["backup_ledger"],
            backup_snapshot=payload["backup_snapshot"],
            phase=payload["phase"],
        )
    except (TypeError, ValueError, KeyError):
        raise ContextStoreError("pending context transaction is invalid") from None
    if (
        not isinstance(record.run_id, str)
        or type(record.previous_revision) is not int
        or type(record.next_revision) is not int
        or record.previous_revision < 0
        or record.next_revision <= record.previous_revision
        or record.phase not in {"prepared", "ledger-replaced", "snapshot-replaced"}
        or any(
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
            for value in (
                record.previous_ledger_sha256,
                record.next_ledger_sha256,
                record.previous_snapshot_sha256,
                record.next_snapshot_sha256,
            )
        )
    ):
        raise ContextStoreError("pending context transaction is invalid")
    return record


def _transaction_temp_path(core: Path, name: str) -> Path:
    if (
        not isinstance(name, str)
        or not name.startswith(".")
        or Path(name).name != name
        or name in {".", ".."}
    ):
        raise ContextStoreError("pending context transaction path is invalid")
    return core / name


def _write_transaction(path: Path, record: _TransactionRecord) -> None:
    temporary = _stage_unbound_bytes(path, canonical_json_bytes(record.as_json()))
    _replace_path(temporary, path)
    _fsync_directory(path.parent)


def _finish_transaction(
    transaction_path: Path,
    record: _TransactionRecord,
    temporary_paths: Iterable[Path] = (),
) -> None:
    del record
    for path in temporary_paths:
        _unlink_owned_temp(path)
    _require_regular_file(
        transaction_path, label="context transaction", allow_missing=True
    )
    try:
        transaction_path.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        raise ContextStoreError("context transaction cleanup failed") from None
    _fsync_directory(transaction_path.parent)


def _cleanup_transaction_paths(paths: Iterable[Path]) -> None:
    for path in paths:
        _unlink_owned_temp(path)


def _rollback_transaction(
    transaction_path: Path,
    record: _TransactionRecord,
    temporary_paths: Iterable[Path],
) -> None:
    """Restore a prepared transaction, refusing to overwrite unknown files."""

    if _require_regular_file(
        transaction_path, label="context transaction", allow_missing=True
    ) is None:
        _cleanup_transaction_paths(temporary_paths)
        return
    core = transaction_path.parent.resolve()
    paths = {
        field: _transaction_temp_path(core, getattr(record, field))
        for field in (
            "staged_ledger",
            "staged_snapshot",
            "backup_ledger",
            "backup_snapshot",
        )
    }
    ledger_path = core / "context-events.jsonl"
    snapshot_path = core / "context.json"
    ledger = _read_regular_bytes(ledger_path, label="context ledger")
    snapshot = _read_regular_bytes(snapshot_path, label="context snapshot")
    ledger_hash = _sha256_bytes(ledger)
    snapshot_hash = _sha256_bytes(snapshot)
    if ledger_hash not in {
        record.previous_ledger_sha256,
        record.next_ledger_sha256,
    } or snapshot_hash not in {
        record.previous_snapshot_sha256,
        record.next_snapshot_sha256,
    }:
        raise ContextStoreError("context transaction rollback boundary changed")
    if ledger_hash == record.next_ledger_sha256:
        backup = paths["backup_ledger"]
        if not backup.is_file() or backup.is_symlink():
            raise ContextStoreError("context transaction ledger backup is missing")
        _replace_path(backup, ledger_path)
    if snapshot_hash == record.next_snapshot_sha256:
        backup = paths["backup_snapshot"]
        if not backup.is_file() or backup.is_symlink():
            raise ContextStoreError("context transaction snapshot backup is missing")
        _replace_path(backup, snapshot_path)
    _finish_transaction(transaction_path, record, paths.values())


def _read_regular_bytes(path: Path, *, label: str) -> bytes:
    _require_regular_file(path, label=label)
    try:
        return path.read_bytes()
    except OSError:
        raise ContextStoreError(f"{label} cannot be read") from None


def _sha256_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def _stage_unbound_bytes(destination: Path, payload: bytes) -> Path:
    temporary: Path | None = None
    descriptor: int | None = None
    try:
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if destination.is_symlink():
            raise OSError("transaction destination cannot be a symlink")
        temporary = destination.with_name(
            f".{destination.name}.{secrets.token_hex(8)}.tmp"
        )
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(temporary, flags, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            descriptor = None
            written = stream.write(payload)
            if written != len(payload):
                raise OSError("short transaction write")
            stream.flush()
            os.fsync(stream.fileno())
    except OSError:
        if descriptor is not None:
            os.close(descriptor)
        if temporary is not None:
            _unlink_owned_temp(temporary)
        raise ContextStoreError("context transaction staging failed") from None
    assert temporary is not None
    return temporary


def _stage_bytes(path: Path, payload: bytes, *, label: str) -> Path:
    _require_regular_file(path, label=label)
    return _stage_unbound_bytes(path, payload)


def _replace_path(source: Path, destination: Path) -> None:
    _require_regular_file(source, label="context transaction staging")
    try:
        os.replace(source, destination)
    except OSError:
        raise ContextStoreError("context transaction replacement failed") from None
    _fsync_directory(destination.parent)


def _replace_ledger(
    temporary: Path,
    destination: Path,
    *,
    expected_identity: tuple[int, int],
) -> None:
    _require_file_identity(destination, expected_identity, label="context ledger")
    _replace_path(temporary, destination)


def _genesis_from_event(event: ContextEvent) -> ApplicationContext:
    if event.sequence != 1 or event.event_type not in {"analysis.started", "application.started"}:
        raise ContextStoreError("context ledger must begin with an application start event")
    if event.previous_revision != 0:
        raise ContextStoreError("application start must begin at revision zero")
    payload = event.payload
    if set(payload) != {"core", "domains"}:
        raise ContextStoreError("application start must contain core and domains")
    raw_domains = payload["domains"]
    if not isinstance(raw_domains, Mapping):
        raise ContextStoreError("application start domains are invalid")
    try:
        domains = {
            binding_id: DomainStateEnvelope.model_validate(value)
            for binding_id, value in raw_domains.items()
        }
        core = CoreContext.model_validate(payload["core"])
        state = ApplicationContext.initial(
            run_id=event.run_id,
            domains=domains,
            core=core,
        )
    except (TypeError, ValueError, ValidationError):
        raise ContextStoreError("application start records are invalid") from None
    if event.previous_state_hash != state.state_hash:
        raise ContextStoreError("application start state hash mismatch")
    return state


def _has_content(path: Path) -> bool:
    _require_regular_file(path, label="context file", allow_missing=True)
    try:
        return path.stat().st_size > 0
    except OSError:
        raise ContextStoreError("context file cannot be inspected") from None


def _require_regular_file(
    path: Path, *, label: str, allow_missing: bool = False
) -> tuple[int, int] | None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        if allow_missing:
            return None
        raise ContextStoreError(f"{label} does not exist") from None
    except OSError:
        raise ContextStoreError(f"{label} cannot be inspected") from None
    if stat.S_ISLNK(metadata.st_mode):
        raise ContextStoreError(f"{label} cannot be a symlink")
    if not stat.S_ISREG(metadata.st_mode):
        raise ContextStoreError(f"{label} is not a regular file")
    return metadata.st_dev, metadata.st_ino


def _file_identity(path: Path, *, label: str) -> tuple[int, int]:
    identity = _require_regular_file(path, label=label)
    assert identity is not None
    return identity


def _require_file_identity(
    path: Path,
    expected: tuple[int, int],
    *,
    label: str,
) -> None:
    actual = _file_identity(path, label=label)
    if actual != expected:
        raise ContextStoreError(f"{label} changed")


def _append_jsonl_fsync(
    path: Path,
    payload: Mapping[str, Any],
    *,
    expected_identity: tuple[int, int] | None = None,
) -> None:
    identity = _require_regular_file(path, label="context ledger")
    if expected_identity is not None and identity != expected_identity:
        raise ContextStoreError("context ledger changed")
    encoded = canonical_json_bytes(payload)
    flags = os.O_WRONLY | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags, 0o600)
        metadata = os.fstat(descriptor)
        opened_identity = (metadata.st_dev, metadata.st_ino)
        if not stat.S_ISREG(metadata.st_mode):
            raise OSError("context ledger is not a regular file")
        if expected_identity is not None and opened_identity != expected_identity:
            raise OSError("context ledger changed")
        with os.fdopen(descriptor, "ab", closefd=True) as stream:
            descriptor = None
            written = stream.write(encoded)
            if written != len(encoded):
                raise OSError("short context ledger write")
            stream.flush()
            os.fsync(stream.fileno())
    except OSError:
        raise ContextStoreError("context ledger append failed") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)
    _fsync_directory(path.parent)


def _stage_snapshot(path: Path, payload: Mapping[str, Any]) -> Path:
    _require_regular_file(path, label="context snapshot")
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(temporary, flags, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            descriptor = None
            encoded = canonical_json_bytes(payload)
            written = stream.write(encoded)
            if written != len(encoded):
                raise OSError("short context snapshot write")
            stream.flush()
            os.fsync(stream.fileno())
    except OSError:
        if descriptor is not None:
            os.close(descriptor)
        _unlink_owned_temp(temporary)
        raise ContextStoreError("context snapshot staging failed") from None
    return temporary


def _replace_snapshot(temporary: Path, destination: Path) -> None:
    _require_regular_file(destination, label="context snapshot")
    _require_regular_file(temporary, label="context snapshot staging")
    try:
        os.replace(temporary, destination)
    except OSError:
        raise ContextStoreError("context snapshot replacement failed") from None
    _fsync_directory(destination.parent)


def _unlink_owned_temp(path: Path) -> None:
    try:
        if path.is_file() and not path.is_symlink():
            path.unlink()
    except OSError:
        pass


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


__all__ = ["ApplicationContextStore", "ContextStoreError"]
