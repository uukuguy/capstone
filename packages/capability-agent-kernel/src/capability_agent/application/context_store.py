"""Durable application-context snapshots and hash-checked event replay."""

from __future__ import annotations

import json
import os
import stat
import secrets
from collections.abc import Mapping
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
        self._snapshot = snapshot
        self._append_lock = RLock()
        self._unavailable = False

    @property
    def workspace(self) -> ApplicationWorkspace:
        return self._workspace

    @property
    def snapshot(self) -> ApplicationContext:
        return self._snapshot

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

        with self._append_lock:
            if self._unavailable:
                raise ContextStoreError("context store is unavailable")
            previous = self._snapshot
            try:
                next_snapshot = reduce_context(previous, draft)
            except ContextTransitionError as error:
                raise ContextStoreError(str(error)) from None

            try:
                event = ContextEvent(
                    run_id=previous.run_id,
                    sequence=next_snapshot.revision,
                    event_type=draft.event_type,
                    binding_id=draft.binding_id,
                    turn_id=draft.turn_id,
                    capability=draft.capability,
                    trace_sequence=draft.trace_sequence,
                    timestamp=draft.timestamp,
                    payload=draft.payload,
                    previous_revision=previous.revision,
                    previous_state_hash=previous.state_hash,
                    next_revision=next_snapshot.revision,
                    next_state_hash=next_snapshot.state_hash,
                )
            except (TypeError, ValueError, ValidationError):
                raise ContextStoreError("context event is invalid") from None

            temporary: Path | None = None
            try:
                temporary = _stage_snapshot(
                    self._workspace.context_snapshot_path,
                    next_snapshot.model_dump(mode="json"),
                )
                _append_jsonl_fsync(
                    self._workspace.context_events_path,
                    event.model_dump(mode="json"),
                )
                _replace_snapshot(temporary, self._workspace.context_snapshot_path)
                temporary = None
            except ContextStoreError:
                self._unavailable = True
                raise
            except Exception:
                self._unavailable = True
                raise ContextStoreError("context persistence failed") from None
            finally:
                if temporary is not None:
                    _unlink_owned_temp(temporary)
            self._snapshot = next_snapshot
            return event

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
            raw_lines = path.read_bytes().splitlines()
        except OSError:
            raise ContextStoreError("context ledger cannot be read") from None
        if not raw_lines:
            raise ContextStoreError("context ledger is empty")

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


def _require_regular_file(path: Path, *, label: str, allow_missing: bool = False) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        if allow_missing:
            return
        raise ContextStoreError(f"{label} does not exist") from None
    except OSError:
        raise ContextStoreError(f"{label} cannot be inspected") from None
    if stat.S_ISLNK(metadata.st_mode):
        raise ContextStoreError(f"{label} cannot be a symlink")
    if not stat.S_ISREG(metadata.st_mode):
        raise ContextStoreError(f"{label} is not a regular file")


def _append_jsonl_fsync(path: Path, payload: Mapping[str, Any]) -> None:
    _require_regular_file(path, label="context ledger", allow_missing=True)
    encoded = canonical_json_bytes(payload)
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags, 0o600)
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
    _require_regular_file(path, label="context snapshot", allow_missing=True)
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
    _require_regular_file(destination, label="context snapshot", allow_missing=True)
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
