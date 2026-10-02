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
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from threading import RLock
from typing import TYPE_CHECKING, Any, Mapping, Protocol, cast

if TYPE_CHECKING:
    from .turn_router import TurnPlan

from capstone_model_capability_spi import ModelCapabilitySelection

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .thread_protocol import (
    AttemptSnapshot,
    CommandReceipt,
    EventEnvelope,
    EventPage,
    ModelContextSnapshot,
    PendingModelSwitchSnapshot,
    PendingSelectionSnapshot,
    RunSnapshot,
    ThreadProtocolError,
    ThreadSnapshot,
)
from .thread_application_transition import (
    ThreadApplicationTransition,
    application_transition_hash,
)
from .model_identity import page_id_for_model, validate_model_id


_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_MAX_COMMAND_BYTES = 64 * 1024
_MAX_EVENT_BYTES = 64 * 1024
_COMMAND_FIELDS = frozenset({
    "schema", "command_id", "idempotency_key", "thread_id", "run_id",
    "kind", "expected_event_seq", "payload",
})
_MESSAGE_COMMAND_KINDS = frozenset({"send_auto", "send_ordinary", "send_professional", "send_control"})
_CONTROL_COMMAND_KINDS = frozenset({
    "cancel_live_attempt", "retry_new_attempt",
    "enable_profile", "disable_profile", "replace_selection",
    "switch_model",
})
_SELECTION_COMMAND_KINDS = frozenset({"enable_profile", "disable_profile", "replace_selection"})


class ThreadNotFound(KeyError):
    """The requested Thread does not exist in the selected store."""


class ThreadResyncRequired(RuntimeError):
    """The requested cursor predates the retained canonical event window."""

    def __init__(self, snapshot: ThreadSnapshot) -> None:
        super().__init__("thread event cursor requires a verified snapshot")
        self.snapshot = snapshot


class ThreadExecutionError(RuntimeError):
    """An Attempt cannot be claimed or mutated by the supplied worker lease."""


class ThreadService(Protocol):
    """Persistence and admission operations required by the HTTP projection."""

    def create_thread(self, snapshot: ThreadSnapshot) -> ThreadSnapshot: ...

    def snapshot(self, thread_id: str) -> ThreadSnapshot: ...

    def catalog(self, thread_id: str) -> dict[str, object]: ...

    def read_events(self, thread_id: str, after_event_seq: int) -> EventPage: ...

    def submit_command(self, command: Mapping[str, Any]) -> CommandReceipt: ...

    def apply_application_transition(
        self, transition: ThreadApplicationTransition,
    ) -> CommandReceipt: ...


@dataclass(frozen=True, slots=True)
class AttemptClaim:
    """One immutable Attempt leased to exactly one Harness worker."""

    thread_id: str
    run_id: str
    attempt: AttemptSnapshot
    kind: str
    instruction: str
    model_context_id: str
    selection_revision: str
    lease_token: str
    model_context: ModelContextSnapshot
    turn_plan: TurnPlan | None = None

    def __post_init__(self) -> None:
        if (
            self.model_context.id != self.model_context_id
            or self.model_context.selection_revision != self.selection_revision
            or self.attempt.target_model_context_id != self.model_context_id
        ):
            raise ThreadExecutionError("attempt claim model context is inconsistent")


class ThreadExecutionService(ThreadService, Protocol):
    """Durable Attempt operations used by the Harness worker."""

    def claim_attempt(self, worker_id: str, lease_seconds: int) -> AttemptClaim | None: ...

    def renew_attempt(self, claim: AttemptClaim, lease_seconds: int) -> bool: ...

    def cancel_requested(self, claim: AttemptClaim) -> bool: ...

    def rollback_selection_if_preparation_failed(
        self, claim: AttemptClaim, *, error_code: str,
    ) -> bool: ...

    def rollback_context_if_preparation_failed(
        self, claim: AttemptClaim, *, error_code: str,
    ) -> bool: ...

    def interrupt_expired_attempts(self) -> int: ...

    def append_runtime_event(
        self, claim: AttemptClaim, *, event_type: str, payload: Mapping[str, Any],
        visibility: str = "public",
    ) -> EventEnvelope: ...

    def finish_attempt(
        self, claim: AttemptClaim, *, phase: str, payload: Mapping[str, Any],
    ) -> ThreadSnapshot: ...


def _identifier(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ThreadProtocolError(f"{name} is invalid")
    return value


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _next_selection_revision(current: str, event_seq: int) -> str:
    prefix, separator, suffix = current.rpartition("_")
    if separator and suffix.isdigit():
        return f"{prefix}_{int(suffix) + 1}"
    return f"sel_{event_seq + 1}"


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True)


def _thread_catalog_document(
    model_catalog: ThreadModelCatalog | None,
    capability_catalog: ThreadCapabilityCatalog | None,
) -> dict[str, object]:
    """Project only bounded selector metadata from application-owned catalogs."""

    models: list[dict[str, object]] = []
    families: set[str] = set()
    list_entries = getattr(model_catalog, "list_entries", None)
    if callable(list_entries):
        for entry in tuple(cast(Any, list_entries)())[:128]:
            model_id = getattr(entry, "model_id", None)
            authority_model_ref = getattr(entry, "authority_model_ref", None)
            display_name = getattr(entry, "display_name", None)
            diagram_provider_id = getattr(entry, "diagram_provider_id", None)
            implementation_family = getattr(entry, "implementation_family", None)
            if not all(
                isinstance(value, str) and value.strip()
                for value in (model_id, authority_model_ref, display_name, diagram_provider_id, implementation_family)
            ):
                continue
            family_name = cast(str, implementation_family)
            families.add(family_name)
            models.append({
                "model_id": model_id,
                "authority_model_ref": authority_model_ref,
                "display_name": display_name,
                "diagram_provider_id": diagram_provider_id,
                "implementation_family": implementation_family,
            })

    profiles: dict[tuple[str, str], dict[str, object]] = {}
    list_profiles = getattr(capability_catalog, "profiles_for_family", None)
    if callable(list_profiles):
        for family in sorted(families):
            if len(profiles) >= 128:
                break
            for info in tuple(cast(Any, list_profiles)(family)):
                if len(profiles) >= 128:
                    break
                descriptor = getattr(info, "descriptor", None)
                profile_id = getattr(descriptor, "profile_id", None)
                profile_version = getattr(descriptor, "profile_version", None)
                display_name = getattr(info, "display_name", None)
                implementation_families = getattr(info, "implementation_families", None)
                if (
                    not isinstance(profile_id, str)
                    or not isinstance(profile_version, str)
                    or not isinstance(display_name, str)
                    or not isinstance(implementation_families, tuple)
                    or not all(isinstance(item, str) and item.strip() for item in implementation_families)
                ):
                    continue
                profiles[(profile_id, profile_version)] = {
                    "profile_id": profile_id,
                    "profile_version": profile_version,
                    "display_name": display_name,
                    "implementation_families": list(implementation_families),
                }

    return {
        "schema": "capstone-thread-catalog/1",
        "models": models,
        "profiles": [profiles[key] for key in sorted(profiles)],
    }


def _validate_json(value: Any, *, name: str) -> None:
    try:
        json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        raise ThreadProtocolError(f"{name} is not JSON") from None


def _validate_bounded_json(value: Any, *, name: str, maximum: int) -> None:
    _validate_json(value, name=name)
    if len(_canonical(value).encode("utf-8")) > maximum:
        raise ThreadProtocolError(f"{name} is too large")


def _admission_rejection(command: Mapping[str, Any]) -> str | None:
    """Return a bounded semantic rejection before a command enters the ledger."""

    if command["kind"] in _CONTROL_COMMAND_KINDS:
        payload = command["payload"]
        if command["kind"] == "cancel_live_attempt":
            if set(payload) != {"attempt_id"}:
                return "cancel_target_required"
            if not isinstance(payload["attempt_id"], str) or not _IDENTIFIER.fullmatch(payload["attempt_id"]):
                return "cancel_target_invalid"
        elif command["kind"] == "retry_new_attempt":
            if set(payload) not in ({"turn_id"}, {"attempt_id"}):
                return "retry_target_required"
            target = next(iter(payload.values()))
            if not isinstance(target, str) or not _IDENTIFIER.fullmatch(target):
                return "retry_target_invalid"
        elif command["kind"] == "switch_model":
            if set(payload) != {"model_id"}:
                return "model_target_required"
            if not isinstance(payload["model_id"], str):
                return "model_target_invalid"
            try:
                validate_model_id(payload["model_id"])
            except ValueError:
                return "model_target_invalid"
        elif command["kind"] in {"enable_profile", "disable_profile"}:
            if set(payload) != {"profile_id", "profile_version"}:
                return "profile_reference_required"
            if (
                not isinstance(payload["profile_id"], str)
                or not _IDENTIFIER.fullmatch(payload["profile_id"])
                or not isinstance(payload["profile_version"], str)
                or not payload["profile_version"]
            ):
                return "profile_reference_invalid"
        else:
            if set(payload) != {"enabled_profiles"} or not isinstance(payload["enabled_profiles"], list):
                return "selection_required"
            for entry in payload["enabled_profiles"]:
                if (
                    not isinstance(entry, dict)
                    or set(entry) != {"profile_id", "profile_version"}
                    or not isinstance(entry["profile_id"], str)
                    or not _IDENTIFIER.fullmatch(entry["profile_id"])
                    or not isinstance(entry["profile_version"], str)
                    or not entry["profile_version"]
                ):
                    return "selection_invalid"
            try:
                ModelCapabilitySelection(tuple(
                    (entry["profile_id"], entry["profile_version"])
                    for entry in payload["enabled_profiles"]
                ))
            except (TypeError, ValueError):
                return "selection_invalid"
        return None
    if command["kind"] not in _MESSAGE_COMMAND_KINDS:
        return "unsupported_command"
    text = command["payload"].get("text")
    if not isinstance(text, str) or not text.strip():
        return "message_text_required"
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

    def __init__(
        self,
        snapshot: ThreadSnapshot,
        *,
        capability_catalog: ThreadCapabilityCatalog | None = None,
        model_catalog: ThreadModelCatalog | None = None,
    ) -> None:
        self._snapshot = snapshot
        self._capability_catalog = capability_catalog
        self._model_catalog = model_catalog
        self._events: list[EventEnvelope] = []
        self._commands: dict[str, _StoredCommand] = {}
        self._command_ids: set[str] = set()
        self._attempts: dict[str, dict[str, Any]] = {}
        self._cancel_requests: set[str] = set()
        self._lock = RLock()

    @classmethod
    def from_document(
        cls,
        document: Mapping[str, Any],
        *,
        capability_catalog: ThreadCapabilityCatalog | None = None,
        model_catalog: ThreadModelCatalog | None = None,
    ) -> InMemoryThreadService:
        return cls(
            ThreadSnapshot.from_document(dict(document)),
            capability_catalog=capability_catalog,
            model_catalog=model_catalog,
        )

    def create_thread(self, snapshot: ThreadSnapshot) -> ThreadSnapshot:
        with self._lock:
            if snapshot.thread_id != self._snapshot.thread_id:
                raise ValueError("in-memory service only contains its configured thread")
            raise ValueError("thread identity already exists")

    def set_capability_catalog(self, capability_catalog: ThreadCapabilityCatalog) -> None:
        if not callable(getattr(capability_catalog, "resolve", None)):
            raise TypeError("capability catalog is invalid")
        with self._lock:
            self._capability_catalog = capability_catalog

    def set_model_catalog(self, model_catalog: ThreadModelCatalog) -> None:
        if not callable(getattr(model_catalog, "resolve", None)):
            raise TypeError("model catalog is invalid")
        with self._lock:
            self._model_catalog = model_catalog

    def snapshot(self, thread_id: str) -> ThreadSnapshot:
        with self._lock:
            self._check_thread(thread_id)
            self.interrupt_expired_attempts()
            return self._snapshot

    def catalog(self, thread_id: str) -> dict[str, object]:
        with self._lock:
            self._check_thread(thread_id)
            return _thread_catalog_document(self._model_catalog, self._capability_catalog)

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
            if parsed["kind"] == "cancel_live_attempt":
                current = self._snapshot.current_attempt
                target = parsed["payload"]["attempt_id"]
                if current is None:
                    receipt = self._receipt(parsed, status="rejected", rejection="no_active_attempt")
                elif current.attempt_id != target:
                    receipt = self._receipt(parsed, status="rejected", rejection="attempt_target_mismatch")
                else:
                    accepted = self._append_event(
                        event_type="command_accepted", attempt=current,
                        payload={"command_id": parsed["command_id"], "kind": parsed["kind"],
                                 "payload": parsed["payload"]},
                    )
                    self._snapshot = replace(self._snapshot, last_event_seq=accepted.event_seq)
                    requested = self._append_event(
                        event_type="attempt_cancel_requested", attempt=current,
                        payload={"command_id": parsed["command_id"], "attempt_id": target},
                    )
                    self._snapshot = replace(self._snapshot, last_event_seq=requested.event_seq)
                    self._cancel_requests.add(target)
                    receipt = self._receipt(
                        parsed, status="accepted", accepted_event_seq=accepted.event_seq,
                        target={"turn_id": current.turn_id, "attempt_id": current.attempt_id},
                    )
                self._commands[parsed["idempotency_key"]] = _StoredCommand(request_hash, receipt)
                self._command_ids.add(parsed["command_id"])
                return receipt
            if parsed["kind"] == "switch_model":
                pending, rejection = self._model_switch_for_command(parsed)
                if rejection is not None:
                    receipt = self._receipt(parsed, status="rejected", rejection=rejection)
                else:
                    assert pending is not None
                    accepted = self._append_control_event(
                        event_type="command_accepted",
                        payload={"command_id": parsed["command_id"], "kind": parsed["kind"],
                                 "payload": parsed["payload"]},
                    )
                    self._snapshot = replace(
                        self._snapshot,
                        pending_model_switch=pending,
                        pending_selection=None,
                        last_event_seq=accepted.event_seq,
                    )
                    requested = self._append_control_event(
                        event_type="model_context_change_pending",
                        payload={
                            "command_id": parsed["command_id"],
                            "model_id": pending.model_id,
                            "model_revision": pending.model_revision,
                            "implementation_family": pending.implementation_family,
                            "selection": ModelCapabilitySelection(
                                pending.enabled_profiles,
                            ).to_document(),
                        },
                    )
                    self._snapshot = replace(self._snapshot, last_event_seq=requested.event_seq)
                    receipt = self._receipt(
                        parsed, status="accepted", accepted_event_seq=accepted.event_seq,
                        target={
                            "model_id": pending.model_id,
                            "model_revision": pending.model_revision,
                        },
                    )
                self._commands[parsed["idempotency_key"]] = _StoredCommand(request_hash, receipt)
                self._command_ids.add(parsed["command_id"])
                return receipt
            if parsed["kind"] in _SELECTION_COMMAND_KINDS:
                selection, rejection = self._selection_for_command(parsed)
                if rejection is not None:
                    receipt = self._receipt(parsed, status="rejected", rejection=rejection)
                else:
                    assert selection is not None
                    pending = PendingSelectionSnapshot(
                        command_id=parsed["command_id"],
                        enabled_profiles=selection.enabled_profiles,
                    )
                    accepted = self._append_control_event(
                        event_type="command_accepted",
                        payload={"command_id": parsed["command_id"], "kind": parsed["kind"],
                                 "payload": parsed["payload"]},
                    )
                    self._snapshot = replace(
                        self._snapshot,
                        pending_selection=pending,
                        last_event_seq=accepted.event_seq,
                    )
                    requested = self._append_control_event(
                        event_type="selection_change_pending",
                        payload={"command_id": parsed["command_id"],
                                 "selection": selection.to_document()},
                    )
                    self._snapshot = replace(self._snapshot, last_event_seq=requested.event_seq)
                    receipt = self._receipt(
                        parsed, status="accepted", accepted_event_seq=accepted.event_seq,
                        target={
                            "model_context_id": self._snapshot.active_model_context.id,
                            "selection_revision": self._snapshot.active_model_context.selection_revision,
                        },
                    )
                self._commands[parsed["idempotency_key"]] = _StoredCommand(request_hash, receipt)
                self._command_ids.add(parsed["command_id"])
                return receipt
            if parsed["kind"] == "retry_new_attempt":
                if self._snapshot.current_attempt is not None:
                    receipt = self._receipt(parsed, status="rejected", rejection="attempt_in_progress")
                else:
                    target_key = next(iter(parsed["payload"]))
                    target_value = parsed["payload"][target_key]
                    prior = next(
                        (
                            record for record in self._attempts.values()
                            if (
                                record["attempt"].turn_id == target_value
                                if target_key == "turn_id"
                                else record["attempt"].attempt_id == target_value
                            )
                        ),
                        None,
                    )
                    if prior is None:
                        receipt = self._receipt(parsed, status="rejected", rejection="retry_target_not_found")
                    elif any(
                        record["attempt"].turn_id == prior["attempt"].turn_id
                        and record["attempt"].phase == "completed"
                        for record in self._attempts.values()
                    ):
                        receipt = self._receipt(parsed, status="rejected", rejection="retry_turn_committed")
                    elif prior["attempt"].phase not in {"interrupted", "failed", "cancelled"}:
                        receipt = self._receipt(parsed, status="rejected", rejection="retry_target_not_retryable")
                    elif prior.get("model_context") != self._snapshot.active_model_context:
                        receipt = self._receipt(parsed, status="rejected", rejection="model_context_mismatch")
                    else:
                        token = secrets.token_hex(8)
                        turn_id = prior["attempt"].turn_id
                        attempt_id = "attempt_" + token
                        attempt = AttemptSnapshot(
                            turn_id=turn_id, attempt_id=attempt_id, phase="accepted",
                            target_model_context_id=self._snapshot.active_model_context.id,
                        )
                        retry_payload = {
                            "turn_id": prior["attempt"].turn_id,
                            "retry_of": prior["attempt"].attempt_id,
                        }
                        event = self._append_event(
                            event_type="command_accepted", attempt=attempt,
                            payload={"command_id": parsed["command_id"], "kind": parsed["kind"],
                                     "payload": retry_payload},
                        )
                        self._snapshot = replace(
                            self._snapshot, current_attempt=attempt, last_event_seq=event.event_seq,
                        )
                        self._attempts[attempt_id] = {
                            "attempt": attempt, "kind": prior["kind"],
                            "instruction": prior["instruction"], "lease_token": None,
                            "lease_deadline": None,
                            "model_context": self._snapshot.active_model_context,
                            "command_id": parsed["command_id"],
                        }
                        receipt = self._receipt(
                            parsed, status="accepted", accepted_event_seq=event.event_seq,
                            target={"turn_id": turn_id, "attempt_id": attempt_id},
                        )
                self._commands[parsed["idempotency_key"]] = _StoredCommand(request_hash, receipt)
                self._command_ids.add(parsed["command_id"])
                return receipt
            if self._snapshot.current_attempt is not None:
                receipt = self._receipt(parsed, status="rejected", rejection="attempt_in_progress")
                self._commands[parsed["idempotency_key"]] = _StoredCommand(request_hash, receipt)
                return receipt

            token = secrets.token_hex(8)
            turn_id = "turn_" + token
            self._activate_pending_model_switch(turn_id)
            self._activate_pending_selection(turn_id)

            event_seq = self._snapshot.last_event_seq + 1
            attempt_id = "attempt_" + token
            attempt = AttemptSnapshot(
                turn_id=turn_id, attempt_id=attempt_id, phase="accepted",
                target_model_context_id=self._snapshot.active_model_context.id,
            )
            event = EventEnvelope(
                event_id="evt_" + secrets.token_hex(8), event_seq=event_seq,
                event_type="command_accepted", event_version=1,
                thread_id=self._snapshot.thread_id, run_id=self._snapshot.run.run_id,
                turn_id=turn_id, attempt_id=attempt_id,
                model_context_id=self._snapshot.active_model_context.id,
                selection_revision=self._snapshot.active_model_context.selection_revision,
                occurred_at=_now(), visibility="public",
                payload={"command_id": parsed["command_id"], "kind": parsed["kind"],
                         "payload": parsed["payload"]},
            )
            self._events.append(event)
            self._snapshot = replace(
                self._snapshot, current_attempt=attempt, last_event_seq=event_seq,
            )
            self._attempts[attempt_id] = {
                "attempt": attempt, "kind": parsed["kind"],
                "instruction": parsed["payload"]["text"], "lease_token": None,
                "lease_deadline": None,
                "model_context": self._snapshot.active_model_context,
                "command_id": parsed["command_id"],
            }
            receipt = self._receipt(
                parsed, status="accepted", accepted_event_seq=event_seq,
                target={"turn_id": turn_id, "attempt_id": attempt_id},
            )
            self._commands[parsed["idempotency_key"]] = _StoredCommand(request_hash, receipt)
            self._command_ids.add(parsed["command_id"])
            return receipt

    def apply_application_transition(
        self, transition: ThreadApplicationTransition,
    ) -> CommandReceipt:
        """Atomically append opaque application events and state."""
        if not isinstance(transition, ThreadApplicationTransition):
            raise ThreadProtocolError("application transition is invalid")
        parsed = self._parse_command(transition.command)
        with self._lock:
            self._check_thread(parsed["thread_id"])
            request_hash = application_transition_hash(transition)
            existing = self._commands.get(parsed["idempotency_key"])
            if existing is not None:
                if existing.request_hash != request_hash:
                    return self._receipt(parsed, status="rejected", rejection="idempotency_conflict")
                return existing.receipt
            if parsed["command_id"] in self._command_ids:
                return self._receipt(parsed, status="rejected", rejection="command_id_conflict")
            if parsed["run_id"] is not None and parsed["run_id"] != self._snapshot.run.run_id:
                receipt = self._receipt(parsed, status="rejected", rejection="run_mismatch")
            elif parsed["expected_event_seq"] != self._snapshot.last_event_seq:
                receipt = self._receipt(parsed, status="rejected", rejection="stale_event_seq")
            elif self._snapshot.run.state != "open":
                receipt = self._receipt(parsed, status="rejected", rejection="run_not_open")
            else:
                envelopes: list[EventEnvelope] = []
                for offset, application_event in enumerate(transition.events, start=1):
                    envelopes.append(EventEnvelope(
                        event_id="evt_" + secrets.token_hex(8),
                        event_seq=self._snapshot.last_event_seq + offset,
                        event_type=application_event.event_type, event_version=1,
                        thread_id=self._snapshot.thread_id, run_id=self._snapshot.run.run_id,
                        turn_id=None, attempt_id=None,
                        model_context_id=self._snapshot.active_model_context.id,
                        selection_revision=self._snapshot.active_model_context.selection_revision,
                        occurred_at=_now(), visibility=application_event.visibility,
                        payload=dict(application_event.payload),
                    ))
                self._events.extend(envelopes)
                self._snapshot = replace(
                    self._snapshot,
                    application_state=None if transition.state is None else dict(transition.state),
                    last_event_seq=self._snapshot.last_event_seq + len(envelopes),
                )
                receipt = self._receipt(
                    parsed, status="accepted",
                    accepted_event_seq=envelopes[0].event_seq if envelopes else None,
                )
            self._commands[parsed["idempotency_key"]] = _StoredCommand(request_hash, receipt)
            self._command_ids.add(parsed["command_id"])
            return receipt

    def claim_attempt(self, worker_id: str, lease_seconds: int) -> AttemptClaim | None:
        if not worker_id or lease_seconds < 1:
            raise ValueError("attempt worker lease is invalid")
        with self._lock:
            for attempt_id, record in self._attempts.items():
                if record["attempt"].phase != "accepted" or record["lease_token"] is not None:
                    continue
                context = record.get("model_context")
                if context != self._snapshot.active_model_context:
                    terminal = replace(record["attempt"], phase="interrupted")
                    record["attempt"] = terminal
                    event = self._append_event(
                        event_type="attempt_interrupted", attempt=terminal,
                        payload={"reason": "model_context_snapshot_unavailable"},
                    )
                    self._snapshot = replace(
                        self._snapshot, current_attempt=None, last_event_seq=event.event_seq,
                    )
                    return None
                assert context is not None
                token = secrets.token_hex(16)
                accepted = record["attempt"]
                running = replace(accepted, phase="running")
                record["attempt"] = running
                record["lease_token"] = token
                record["lease_deadline"] = time.monotonic() + lease_seconds
                event = self._append_event(
                    event_type="attempt_started", attempt=running,
                    payload={"attempt_id": running.attempt_id},
                )
                self._snapshot = replace(self._snapshot, current_attempt=running, last_event_seq=event.event_seq)
                return AttemptClaim(
                    thread_id=self._snapshot.thread_id, run_id=self._snapshot.run.run_id,
                    attempt=running, kind=record["kind"], instruction=record["instruction"],
                    model_context_id=self._snapshot.active_model_context.id,
                    selection_revision=self._snapshot.active_model_context.selection_revision,
                    lease_token=token,
                    model_context=context,
                )
            return None

    def renew_attempt(self, claim: AttemptClaim, lease_seconds: int) -> bool:
        if lease_seconds < 1:
            raise ValueError("attempt worker lease is invalid")
        with self._lock:
            record = self._require_claim(claim)
            if record["attempt"].phase != "running":
                raise ThreadExecutionError("attempt is not running")
            record["lease_deadline"] = time.monotonic() + lease_seconds
            return True

    def cancel_requested(self, claim: AttemptClaim) -> bool:
        with self._lock:
            self._require_claim(claim)
            return claim.attempt.attempt_id in self._cancel_requests

    def rollback_context_if_preparation_failed(
        self, claim: AttemptClaim, *, error_code: str,
    ) -> bool:
        _identifier(error_code, name="selection.error_code")
        with self._lock:
            record = self._require_claim(claim)
            if record["attempt"].phase != "running":
                raise ThreadExecutionError("attempt is not running")
            active = self._snapshot.active_model_context
            if (
                active.id != claim.model_context.id
                or active.selection_revision != claim.model_context.selection_revision
            ):
                return False
            activation = next(
                (
                    event for event in reversed(self._events)
                    if event.event_type in {"selection_activated", "model_context_activated"}
                    and event.selection_revision == active.selection_revision
                    and event.model_context_id == active.id
                    and event.payload.get("activation_turn_id") == claim.attempt.turn_id
                ),
                None,
            )
            if activation is None:
                return False
            previous_context_document = activation.payload.get("previous_context")
            if activation.event_type == "model_context_activated" and isinstance(previous_context_document, dict):
                try:
                    restored = ModelContextSnapshot.from_document(previous_context_document)
                except ThreadProtocolError:
                    return False
                previous_page = activation.payload.get("previous_grid_page_id")
                if not isinstance(previous_page, str):
                    return False
                event_type = "model_context_reverted"
                event_payload = {
                    "error_code": error_code,
                    "restored_context": restored.to_document(),
                    "restored_grid_page_id": previous_page,
                }
                event = self._append_control_event(
                    event_type=event_type, payload=event_payload, context=restored,
                )
                self._snapshot = replace(
                    self._snapshot, active_model_context=restored,
                    active_grid_page_id=previous_page,
                    last_event_seq=event.event_seq,
                )
                return True
            previous_document = activation.payload.get("previous_selection")
            previous_revision = activation.payload.get("previous_selection_revision")
            if not isinstance(previous_document, dict) or not isinstance(previous_revision, str):
                return False
            try:
                previous = ModelCapabilitySelection.from_document(previous_document)
            except ValueError:
                return False
            restored = replace(
                active, selection_revision=previous_revision,
                enabled_profiles=previous.enabled_profiles,
            )
            event = self._append_control_event(
                event_type="selection_reverted",
                payload={"error_code": error_code, "restored_selection": previous_document},
                context=restored,
            )
            self._snapshot = replace(
                self._snapshot, active_model_context=restored,
                last_event_seq=event.event_seq,
            )
            return True

    def rollback_selection_if_preparation_failed(
        self, claim: AttemptClaim, *, error_code: str,
    ) -> bool:
        return self.rollback_context_if_preparation_failed(claim, error_code=error_code)

    def interrupt_expired_attempts(self) -> int:
        cutoff = time.monotonic()
        interrupted = 0
        with self._lock:
            for record in self._attempts.values():
                deadline = record.get("lease_deadline")
                if record["attempt"].phase != "running" or deadline is None or deadline > cutoff:
                    continue
                terminal = replace(record["attempt"], phase="interrupted")
                record["attempt"] = terminal
                record["lease_token"] = None
                record["lease_deadline"] = None
                event = self._append_event(
                    event_type="attempt_interrupted", attempt=terminal,
                    payload={"reason": "lease_expired"},
                )
                self._snapshot = replace(
                    self._snapshot, current_attempt=None, last_event_seq=event.event_seq,
                )
                interrupted += 1
        return interrupted

    def append_runtime_event(
        self, claim: AttemptClaim, *, event_type: str, payload: Mapping[str, Any],
        visibility: str = "public",
    ) -> EventEnvelope:
        _identifier(event_type, name="event_type")
        _validate_bounded_json(payload, name="event.payload", maximum=_MAX_EVENT_BYTES)
        with self._lock:
            record = self._require_claim(claim)
            if record["attempt"].phase != "running":
                raise ThreadExecutionError("attempt is not running")
            if visibility not in {"public", "diagnostic"}:
                raise ThreadProtocolError("event visibility is invalid")
            event = self._append_event(
                event_type=event_type, attempt=record["attempt"],
                payload=dict(payload), visibility=visibility,
                context=record["model_context"],
            )
            self._snapshot = replace(self._snapshot, last_event_seq=event.event_seq)
            return event

    def finish_attempt(
        self, claim: AttemptClaim, *, phase: str, payload: Mapping[str, Any],
    ) -> ThreadSnapshot:
        if phase not in {"completed", "failed", "cancelled", "interrupted"}:
            raise ValueError("attempt terminal phase is invalid")
        _validate_bounded_json(payload, name="attempt.payload", maximum=_MAX_EVENT_BYTES)
        with self._lock:
            record = self._require_claim(claim)
            if record["attempt"].phase != "running":
                raise ThreadExecutionError("attempt is not running")
            terminal = replace(record["attempt"], phase=phase)
            record["attempt"] = terminal
            record["lease_token"] = None
            self._cancel_requests.discard(claim.attempt.attempt_id)
            event = self._append_event(
                event_type="attempt_" + phase,
                attempt=terminal, payload=dict(payload),
                context=record["model_context"],
            )
            self._snapshot = replace(
                self._snapshot, current_attempt=None, last_event_seq=event.event_seq,
            )
            return self._snapshot

    def _require_claim(self, claim: AttemptClaim) -> dict[str, Any]:
        if claim.thread_id != self._snapshot.thread_id:
            raise ThreadExecutionError("attempt thread is invalid")
        record = self._attempts.get(claim.attempt.attempt_id)
        if (record is None or record["lease_token"] != claim.lease_token
                or record.get("lease_deadline") is None
                or record["lease_deadline"] <= time.monotonic()):
            raise ThreadExecutionError("attempt lease is unavailable")
        return record

    def _selection_for_command(
        self, command: Mapping[str, Any],
    ) -> tuple[ModelCapabilitySelection | None, str | None]:
        if self._snapshot.pending_model_switch is not None:
            return None, "context_change_pending"
        current = (
            self._snapshot.pending_selection.enabled_profiles
            if self._snapshot.pending_selection is not None
            else self._snapshot.active_model_context.enabled_profiles
        )
        payload = command["payload"]
        try:
            if command["kind"] == "enable_profile":
                reference = (payload["profile_id"], payload["profile_version"])
                if reference in current:
                    return None, "profile_already_enabled"
                selection = ModelCapabilitySelection((*current, reference))
            elif command["kind"] == "disable_profile":
                reference = (payload["profile_id"], payload["profile_version"])
                if reference not in current:
                    return None, "profile_not_enabled"
                selection = ModelCapabilitySelection(tuple(item for item in current if item != reference))
            else:
                selection = ModelCapabilitySelection(tuple(
                    (entry["profile_id"], entry["profile_version"])
                    for entry in payload["enabled_profiles"]
                ))
        except (KeyError, TypeError, ValueError):
            return None, "selection_invalid"
        catalog = self._capability_catalog
        if catalog is None:
            return None, "selection_catalog_unavailable"
        try:
            resolved = catalog.resolve(
                ThreadModelDescriptor(
                    self._snapshot.active_model_context.model_id,
                    self._snapshot.active_model_context.model_revision,
                    self._snapshot.active_model_context.implementation_family,
                ),
                selection,
            )
        except (KeyError, TypeError, ValueError):
            return None, "selection_unavailable"
        if resolved != selection:
            return None, "selection_not_exact"
        return selection, None

    def _model_switch_for_command(
        self, command: Mapping[str, Any],
    ) -> tuple[PendingModelSwitchSnapshot | None, str | None]:
        if self._snapshot.pending_model_switch is not None or self._snapshot.pending_selection is not None:
            return None, "context_change_pending"
        catalog = self._model_catalog
        if catalog is None:
            return None, "model_catalog_unavailable"
        try:
            descriptor = catalog.resolve(command["payload"]["model_id"])
        except (KeyError, TypeError, ValueError):
            return None, "model_unavailable"
        active = self._snapshot.active_model_context
        if (
            descriptor.model_id == active.model_id
            and descriptor.model_revision == active.model_revision
            and descriptor.implementation_family == active.implementation_family
        ):
            return None, "model_already_active"
        selection = ModelCapabilitySelection.empty()
        if self._capability_catalog is not None:
            try:
                selection = self._capability_catalog.resolve(descriptor, None)
            except (KeyError, TypeError, ValueError):
                return None, "selection_unavailable"
        return PendingModelSwitchSnapshot(
            command_id=command["command_id"],
            model_id=descriptor.model_id,
            model_revision=descriptor.model_revision,
            implementation_family=descriptor.implementation_family,
            enabled_profiles=selection.enabled_profiles,
        ), None

    def _activate_pending_model_switch(self, turn_id: str) -> None:
        pending = self._snapshot.pending_model_switch
        if pending is None:
            return
        previous = self._snapshot.active_model_context
        active = ModelContextSnapshot(
            id="ctx_" + secrets.token_hex(10),
            model_id=pending.model_id,
            model_revision=pending.model_revision,
            implementation_family=pending.implementation_family,
            selection_revision="sel_0",
            enabled_profiles=pending.enabled_profiles,
        )
        event = self._append_control_event(
            event_type="model_context_activated",
            payload={
                "command_id": pending.command_id,
                "activation_turn_id": turn_id,
                "previous_context": previous.to_document(),
                "previous_grid_page_id": self._snapshot.active_grid_page_id,
                "active_grid_page_id": page_id_for_model(active.model_id),
                "model_context": active.to_document(),
            },
            context=active,
        )
        self._snapshot = replace(
            self._snapshot,
            active_model_context=active,
            active_grid_page_id=page_id_for_model(active.model_id),
            pending_model_switch=None,
            pending_selection=None,
            last_event_seq=event.event_seq,
        )

    def _activate_pending_selection(self, turn_id: str) -> None:
        pending = self._snapshot.pending_selection
        if pending is None:
            return
        context = self._snapshot.active_model_context
        revision = _next_selection_revision(context.selection_revision, self._snapshot.last_event_seq)
        active = replace(
            context,
            selection_revision=revision,
            enabled_profiles=pending.enabled_profiles,
        )
        event = self._append_control_event(
            event_type="selection_activated",
            payload={
                "command_id": pending.command_id,
                "activation_turn_id": turn_id,
                "previous_selection_revision": context.selection_revision,
                "previous_selection": ModelCapabilitySelection(context.enabled_profiles).to_document(),
                "selection": ModelCapabilitySelection(pending.enabled_profiles).to_document(),
            },
            context=active,
        )
        self._snapshot = replace(
            self._snapshot,
            active_model_context=active,
            pending_selection=None,
            last_event_seq=event.event_seq,
        )

    def _append_control_event(
        self, *, event_type: str, payload: Mapping[str, Any],
        context: ModelContextSnapshot | None = None,
    ) -> EventEnvelope:
        active = self._snapshot.active_model_context if context is None else context
        event = EventEnvelope(
            event_id="evt_" + secrets.token_hex(8),
            event_seq=self._snapshot.last_event_seq + 1,
            event_type=event_type, event_version=1,
            thread_id=self._snapshot.thread_id, run_id=self._snapshot.run.run_id,
            turn_id=None, attempt_id=None,
            model_context_id=active.id,
            selection_revision=active.selection_revision,
            occurred_at=_now(), visibility="public", payload=dict(payload),
        )
        self._events.append(event)
        return event

    def _append_event(
        self, *, event_type: str, attempt: AttemptSnapshot,
        payload: Mapping[str, Any], visibility: str = "public",
        context: ModelContextSnapshot | None = None,
    ) -> EventEnvelope:
        active = self._snapshot.active_model_context if context is None else context
        event = EventEnvelope(
            event_id="evt_" + secrets.token_hex(8),
            event_seq=self._snapshot.last_event_seq + 1,
            event_type=event_type, event_version=1,
            thread_id=self._snapshot.thread_id, run_id=self._snapshot.run.run_id,
            turn_id=attempt.turn_id, attempt_id=attempt.attempt_id,
            model_context_id=active.id,
            selection_revision=active.selection_revision,
            occurred_at=_now(), visibility=visibility, payload=dict(payload),
        )
        self._events.append(event)
        return event

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
        target: dict[str, Any] | None = None,
    ) -> CommandReceipt:
        return CommandReceipt(
            command_id=command["command_id"], idempotency_key=command["idempotency_key"],
            thread_id=command["thread_id"], run_id=self._snapshot.run.run_id,
            status=status, accepted_event_seq=accepted_event_seq,
            rejection=rejection, target=target,
        )


@dataclass(frozen=True, slots=True)
class ThreadModelDescriptor:
    """Authority-resolved model identity used to create an immutable Context."""

    model_id: str
    model_revision: str
    implementation_family: str
    authority_model_ref: str | None = None
    display_name: str | None = None
    diagram_provider_id: str | None = None

    def __post_init__(self) -> None:
        validate_model_id(self.model_id)
        if not isinstance(self.model_revision, str) or not self.model_revision.strip():
            raise ValueError("model_revision is invalid")
        if not isinstance(self.implementation_family, str) or not _IDENTIFIER.fullmatch(
            self.implementation_family
        ):
            raise ValueError("implementation_family is invalid")
        for name in ("authority_model_ref", "display_name", "diagram_provider_id"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{name} is invalid")


class ThreadModelCatalog(Protocol):
    default_model_id: str

    def resolve(self, model_id: str | None) -> ThreadModelDescriptor: ...


class ThreadCapabilityCatalog(Protocol):
    def resolve(
        self, model: ThreadModelDescriptor,
        selection: ModelCapabilitySelection | None = None,
    ) -> ModelCapabilitySelection: ...


class ThreadCreator:
    """Resolve a registered model once, then persist a pinned Thread snapshot."""

    def __init__(
        self,
        service: ThreadService,
        catalog: ThreadModelCatalog,
        capability_catalog: ThreadCapabilityCatalog | None = None,
    ) -> None:
        self._service = service
        self._catalog = catalog
        self._capability_catalog = capability_catalog
        configure_model = getattr(service, "set_model_catalog", None)
        if callable(configure_model):
            configure_model(catalog)
        if capability_catalog is not None:
            configure = getattr(service, "set_capability_catalog", None)
            if callable(configure):
                configure(capability_catalog)

    def create(
        self,
        model_id: str | None = None,
        selection: ModelCapabilitySelection | None = None,
    ) -> ThreadSnapshot:
        descriptor = self._catalog.resolve(
            self._catalog.default_model_id if model_id is None else model_id
        )
        enabled_profiles = (
            self._capability_catalog.resolve(descriptor, selection).enabled_profiles
            if self._capability_catalog is not None
            else (() if selection is None else selection.enabled_profiles)
        )
        token = secrets.token_hex(10)
        context = ModelContextSnapshot(
            id="ctx_" + token, model_id=descriptor.model_id,
            model_revision=descriptor.model_revision,
            implementation_family=descriptor.implementation_family,
            selection_revision="sel_0",
            enabled_profiles=enabled_profiles,
        )
        snapshot = ThreadSnapshot(
            thread_id="thr_" + token,
            run=RunSnapshot(run_id="run_" + token, state="open"),
            active_model_context=context,
            active_grid_page_id=page_id_for_model(descriptor.model_id),
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
    enabled_profiles jsonb NOT NULL DEFAULT '[]'::jsonb,
    active_grid_page_id text NOT NULL,
    current_attempt jsonb,
    pending_selection jsonb,
    pending_model_switch jsonb,
    application_state jsonb,
    base_event_seq integer NOT NULL DEFAULT 0 CHECK (base_event_seq >= 0),
    last_event_seq integer NOT NULL DEFAULT 0 CHECK (last_event_seq >= 0),
    created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE capstone_threads ADD COLUMN IF NOT EXISTS enabled_profiles jsonb NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE capstone_threads ADD COLUMN IF NOT EXISTS pending_selection jsonb;
ALTER TABLE capstone_threads ADD COLUMN IF NOT EXISTS pending_model_switch jsonb;
ALTER TABLE capstone_threads ADD COLUMN IF NOT EXISTS application_state jsonb;
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
CREATE TABLE IF NOT EXISTS capstone_thread_attempts (
    attempt_id text PRIMARY KEY,
    thread_id text NOT NULL REFERENCES capstone_threads(thread_id) ON DELETE CASCADE,
    run_id text NOT NULL,
    turn_id text NOT NULL,
    command_id text NOT NULL,
    kind text NOT NULL,
    instruction text NOT NULL,
    model_context_id text NOT NULL,
    selection_revision text NOT NULL,
    model_context_snapshot jsonb,
    phase text NOT NULL CHECK (phase IN ('accepted', 'running', 'waiting', 'committing', 'cancelled', 'interrupted', 'completed', 'failed')),
    lease_token text,
    lease_deadline timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (thread_id, command_id)
);
ALTER TABLE capstone_thread_attempts ADD COLUMN IF NOT EXISTS model_context_snapshot jsonb;
ALTER TABLE capstone_thread_attempts DROP CONSTRAINT IF EXISTS capstone_thread_attempts_thread_id_turn_id_key;
CREATE INDEX IF NOT EXISTS capstone_thread_attempts_pending_idx
    ON capstone_thread_attempts(created_at, attempt_id)
    WHERE phase = 'accepted' AND lease_token IS NULL;
"""


def _timestamp(value: Any) -> str:
    if isinstance(value, datetime):
        value = value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return str(value)


class PostgresThreadService:
    """Durable Thread projection store kept separate from the legacy session ledger."""

    def __init__(
        self,
        dsn: str,
        *,
        capability_catalog: ThreadCapabilityCatalog | None = None,
        model_catalog: ThreadModelCatalog | None = None,
    ) -> None:
        if not dsn:
            raise ValueError("database URL is required")
        self.dsn = dsn
        self._capability_catalog = capability_catalog
        self._model_catalog = model_catalog

    def set_capability_catalog(self, capability_catalog: ThreadCapabilityCatalog) -> None:
        if not callable(getattr(capability_catalog, "resolve", None)):
            raise TypeError("capability catalog is invalid")
        self._capability_catalog = capability_catalog

    def set_model_catalog(self, model_catalog: ThreadModelCatalog) -> None:
        if not callable(getattr(model_catalog, "resolve", None)):
            raise TypeError("model catalog is invalid")
        self._model_catalog = model_catalog

    def _connect(self) -> psycopg.Connection[dict[str, Any]]:
        return cast(
            psycopg.Connection[dict[str, Any]],
            psycopg.connect(self.dsn, row_factory=cast(Any, dict_row)),
        )

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
                     implementation_family, selection_revision, enabled_profiles,
                     active_grid_page_id, current_attempt, pending_selection,
                     pending_model_switch, application_state, base_event_seq, last_event_seq)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (snapshot.thread_id, snapshot.run.run_id, snapshot.run.state,
                     context.id, context.model_id, context.model_revision,
                     context.implementation_family, context.selection_revision,
                     Jsonb(list({"profile_id": profile_id, "profile_version": profile_version}
                                for profile_id, profile_version in context.enabled_profiles)),
                     snapshot.active_grid_page_id,
                     None if snapshot.current_attempt is None else Jsonb(snapshot.current_attempt.to_document()),
                     None if snapshot.pending_selection is None else Jsonb(snapshot.pending_selection.to_document()),
                     None if snapshot.pending_model_switch is None else Jsonb(snapshot.pending_model_switch.to_document()),
                     None if snapshot.application_state is None else Jsonb(dict(snapshot.application_state)),
                     snapshot.base_event_seq, snapshot.last_event_seq),
                )
            except psycopg.errors.UniqueViolation:
                raise ValueError("thread identity already exists") from None
        return snapshot

    def snapshot(self, thread_id: str) -> ThreadSnapshot:
        self.interrupt_expired_attempts()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM capstone_threads WHERE thread_id = %s", (thread_id,),
            ).fetchone()
        if row is None:
            raise ThreadNotFound(thread_id)
        return self._snapshot_from_row(row)

    def catalog(self, thread_id: str) -> dict[str, object]:
        self.snapshot(thread_id)
        return _thread_catalog_document(self._model_catalog, self._capability_catalog)

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
            command_row = connection.execute(
                "SELECT 1 FROM capstone_thread_commands WHERE thread_id = %s AND command_id = %s",
                (parsed["thread_id"], parsed["command_id"]),
            ).fetchone()
            if command_row is not None:
                receipt = self._receipt(parsed, status="rejected", rejection="command_id_conflict")
            elif parsed["run_id"] is not None and parsed["run_id"] != snapshot.run.run_id:
                receipt = self._receipt(parsed, status="rejected", rejection="run_mismatch")
            elif parsed["expected_event_seq"] != snapshot.last_event_seq:
                receipt = self._receipt(parsed, status="rejected", rejection="stale_event_seq")
            elif (semantic_rejection := _admission_rejection(parsed)) is not None:
                receipt = self._receipt(parsed, status="rejected", rejection=semantic_rejection)
            elif snapshot.run.state != "open":
                receipt = self._receipt(parsed, status="rejected", rejection="run_not_open")
            elif parsed["kind"] == "cancel_live_attempt":
                current = snapshot.current_attempt
                target = parsed["payload"]["attempt_id"]
                if current is None:
                    receipt = self._receipt(parsed, status="rejected", rejection="no_active_attempt")
                elif current.attempt_id != target:
                    receipt = self._receipt(parsed, status="rejected", rejection="attempt_target_mismatch")
                else:
                    accepted = self._make_attempt_event(
                        thread, current, event_seq=snapshot.last_event_seq + 1,
                        event_type="command_accepted",
                        payload={"command_id": parsed["command_id"], "kind": parsed["kind"],
                                 "payload": parsed["payload"]},
                    )
                    self._insert_event(connection, accepted)
                    requested = self._make_attempt_event(
                        thread, current, event_seq=accepted.event_seq + 1,
                        event_type="attempt_cancel_requested",
                        payload={"command_id": parsed["command_id"], "attempt_id": target},
                    )
                    self._insert_event(connection, requested)
                    connection.execute(
                        "UPDATE capstone_threads SET last_event_seq = %s WHERE thread_id = %s",
                        (requested.event_seq, snapshot.thread_id),
                    )
                    receipt = self._receipt(
                        parsed, status="accepted", accepted_event_seq=accepted.event_seq,
                        target={"turn_id": current.turn_id, "attempt_id": current.attempt_id},
                    )
            elif parsed["kind"] == "switch_model":
                pending, rejection = self._model_switch_for_command(snapshot, parsed)
                if rejection is not None:
                    receipt = self._receipt(parsed, status="rejected", rejection=rejection)
                else:
                    assert pending is not None
                    accepted = self._make_control_event(
                        thread, snapshot.active_model_context,
                        event_seq=snapshot.last_event_seq + 1,
                        event_type="command_accepted",
                        payload={"command_id": parsed["command_id"], "kind": parsed["kind"],
                                 "payload": parsed["payload"]},
                    )
                    self._insert_event(connection, accepted)
                    requested = self._make_control_event(
                        thread, snapshot.active_model_context,
                        event_seq=accepted.event_seq + 1,
                        event_type="model_context_change_pending",
                        payload={
                            "command_id": parsed["command_id"],
                            "model_id": pending.model_id,
                            "model_revision": pending.model_revision,
                            "implementation_family": pending.implementation_family,
                            "selection": ModelCapabilitySelection(
                                pending.enabled_profiles,
                            ).to_document(),
                        },
                    )
                    self._insert_event(connection, requested)
                    connection.execute(
                        """UPDATE capstone_threads
                           SET pending_model_switch = %s, pending_selection = NULL,
                               last_event_seq = %s
                           WHERE thread_id = %s""",
                        (Jsonb(pending.to_document()), requested.event_seq, snapshot.thread_id),
                    )
                    receipt = self._receipt(
                        parsed, status="accepted", accepted_event_seq=accepted.event_seq,
                        target={
                            "model_id": pending.model_id,
                            "model_revision": pending.model_revision,
                        },
                    )
            elif parsed["kind"] in _SELECTION_COMMAND_KINDS:
                selection, rejection = self._selection_for_command(snapshot, parsed)
                if rejection is not None:
                    receipt = self._receipt(parsed, status="rejected", rejection=rejection)
                else:
                    assert selection is not None
                    pending = PendingSelectionSnapshot(
                        command_id=parsed["command_id"],
                        enabled_profiles=selection.enabled_profiles,
                    )
                    accepted = self._make_control_event(
                        thread, snapshot.active_model_context,
                        event_seq=snapshot.last_event_seq + 1,
                        event_type="command_accepted",
                        payload={"command_id": parsed["command_id"], "kind": parsed["kind"],
                                 "payload": parsed["payload"]},
                    )
                    self._insert_event(connection, accepted)
                    requested = self._make_control_event(
                        thread, snapshot.active_model_context,
                        event_seq=accepted.event_seq + 1,
                        event_type="selection_change_pending",
                        payload={"command_id": parsed["command_id"],
                                 "selection": selection.to_document()},
                    )
                    self._insert_event(connection, requested)
                    connection.execute(
                        """UPDATE capstone_threads
                           SET pending_selection = %s, last_event_seq = %s
                           WHERE thread_id = %s""",
                        (Jsonb(pending.to_document()), requested.event_seq, snapshot.thread_id),
                    )
                    receipt = self._receipt(
                        parsed, status="accepted", accepted_event_seq=accepted.event_seq,
                        target={
                            "model_context_id": snapshot.active_model_context.id,
                            "selection_revision": snapshot.active_model_context.selection_revision,
                        },
                    )
            elif parsed["kind"] == "retry_new_attempt":
                if snapshot.current_attempt is not None:
                    receipt = self._receipt(parsed, status="rejected", rejection="attempt_in_progress")
                else:
                    target_key = next(iter(parsed["payload"]))
                    target_value = parsed["payload"][target_key]
                    if target_key == "turn_id":
                        prior = connection.execute(
                               """SELECT * FROM capstone_thread_attempts
                               WHERE thread_id = %s AND turn_id = %s
                               ORDER BY created_at DESC, attempt_id DESC
                               LIMIT 1
                               FOR UPDATE""",
                            (snapshot.thread_id, target_value),
                        ).fetchone()
                    else:
                        prior = connection.execute(
                            """SELECT * FROM capstone_thread_attempts
                               WHERE thread_id = %s AND attempt_id = %s
                               FOR UPDATE""",
                            (snapshot.thread_id, target_value),
                        ).fetchone()
                    if prior is None:
                        receipt = self._receipt(parsed, status="rejected", rejection="retry_target_not_found")
                    elif connection.execute(
                        """SELECT 1 FROM capstone_thread_attempts
                           WHERE thread_id = %s AND turn_id = %s AND phase = 'completed'
                           LIMIT 1""",
                        (snapshot.thread_id, prior["turn_id"]),
                    ).fetchone() is not None:
                        receipt = self._receipt(parsed, status="rejected", rejection="retry_turn_committed")
                    elif prior["phase"] not in {"interrupted", "failed", "cancelled"}:
                        receipt = self._receipt(parsed, status="rejected", rejection="retry_target_not_retryable")
                    else:
                        prior_context = None
                        try:
                            if prior["model_context_snapshot"] is not None:
                                prior_context = ModelContextSnapshot.from_document(
                                    prior["model_context_snapshot"]
                                )
                        except ThreadProtocolError:
                            prior_context = None
                        if (
                            prior_context is None
                            or prior_context != snapshot.active_model_context
                            or prior["model_context_id"] != snapshot.active_model_context.id
                            or prior["selection_revision"] != snapshot.active_model_context.selection_revision
                        ):
                            receipt = self._receipt(parsed, status="rejected", rejection="model_context_mismatch")
                        else:
                            token = secrets.token_hex(8)
                            turn_id = prior["turn_id"]
                            attempt_id = "attempt_" + token
                            attempt = AttemptSnapshot(
                                turn_id=turn_id, attempt_id=attempt_id, phase="accepted",
                                target_model_context_id=snapshot.active_model_context.id,
                            )
                            retry_payload = {
                                "turn_id": prior["turn_id"],
                                "retry_of": prior["attempt_id"],
                            }
                            accepted = self._make_attempt_event(
                                thread, attempt, event_seq=snapshot.last_event_seq + 1,
                                event_type="command_accepted",
                                payload={"command_id": parsed["command_id"], "kind": parsed["kind"],
                                         "payload": retry_payload},
                            )
                            self._insert_event(connection, accepted)
                            connection.execute(
                                """INSERT INTO capstone_thread_attempts
                                   (attempt_id, thread_id, run_id, turn_id, command_id, kind,
                                    instruction, model_context_id, selection_revision,
                                    model_context_snapshot, phase)
                                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'accepted')""",
                                (attempt_id, snapshot.thread_id, snapshot.run.run_id, turn_id,
                                 parsed["command_id"], prior["kind"], prior["instruction"],
                                 snapshot.active_model_context.id,
                                 snapshot.active_model_context.selection_revision,
                                 Jsonb(snapshot.active_model_context.to_document())),
                            )
                            connection.execute(
                                """UPDATE capstone_threads
                                   SET current_attempt = %s, last_event_seq = %s
                                   WHERE thread_id = %s""",
                                (Jsonb(attempt.to_document()), accepted.event_seq, snapshot.thread_id),
                            )
                            receipt = self._receipt(
                                parsed, status="accepted", accepted_event_seq=accepted.event_seq,
                                target={"turn_id": turn_id, "attempt_id": attempt_id},
                            )
            elif snapshot.current_attempt is not None:
                receipt = self._receipt(parsed, status="rejected", rejection="attempt_in_progress")
            else:
                token = secrets.token_hex(8)
                turn_id = "turn_" + token
                if snapshot.pending_model_switch is not None:
                    snapshot = self._activate_pending_model_switch(connection, thread, snapshot, turn_id)
                    thread = {
                        **thread,
                        "model_context_id": snapshot.active_model_context.id,
                        "model_id": snapshot.active_model_context.model_id,
                        "model_revision": snapshot.active_model_context.model_revision,
                        "implementation_family": snapshot.active_model_context.implementation_family,
                        "selection_revision": snapshot.active_model_context.selection_revision,
                        "enabled_profiles": [
                            {"profile_id": profile_id, "profile_version": profile_version}
                            for profile_id, profile_version in snapshot.active_model_context.enabled_profiles
                        ],
                        "active_grid_page_id": snapshot.active_grid_page_id,
                        "pending_model_switch": None,
                        "pending_selection": None,
                        "last_event_seq": snapshot.last_event_seq,
                    }
                if snapshot.pending_selection is not None:
                    snapshot = self._activate_pending_selection(connection, thread, snapshot, turn_id)
                    thread = {
                        **thread,
                        "model_context_id": snapshot.active_model_context.id,
                        "model_id": snapshot.active_model_context.model_id,
                        "model_revision": snapshot.active_model_context.model_revision,
                        "implementation_family": snapshot.active_model_context.implementation_family,
                        "selection_revision": snapshot.active_model_context.selection_revision,
                        "enabled_profiles": [
                            {"profile_id": profile_id, "profile_version": profile_version}
                            for profile_id, profile_version in snapshot.active_model_context.enabled_profiles
                        ],
                        "pending_selection": None,
                        "last_event_seq": snapshot.last_event_seq,
                    }
                event_seq = snapshot.last_event_seq + 1
                attempt_id = "attempt_" + token
                attempt = AttemptSnapshot(
                    turn_id=turn_id, attempt_id=attempt_id, phase="accepted",
                    target_model_context_id=snapshot.active_model_context.id,
                )
                event = EventEnvelope(
                    event_id="evt_" + secrets.token_hex(8), event_seq=event_seq,
                    event_type="command_accepted", event_version=1,
                    thread_id=snapshot.thread_id, run_id=snapshot.run.run_id,
                    turn_id=turn_id, attempt_id=attempt_id,
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
                    """INSERT INTO capstone_thread_attempts
                       (attempt_id, thread_id, run_id, turn_id, command_id, kind,
                        instruction, model_context_id, selection_revision, model_context_snapshot, phase)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'accepted')""",
                    (attempt_id, snapshot.thread_id, snapshot.run.run_id, turn_id,
                     parsed["command_id"], parsed["kind"], parsed["payload"]["text"],
                     snapshot.active_model_context.id,
                     snapshot.active_model_context.selection_revision,
                     Jsonb(snapshot.active_model_context.to_document())),
                )
                connection.execute(
                    "UPDATE capstone_threads SET current_attempt = %s, last_event_seq = %s WHERE thread_id = %s",
                    (Jsonb(attempt.to_document()), event_seq, snapshot.thread_id),
                )
                receipt = self._receipt(
                    parsed, status="accepted", accepted_event_seq=event_seq,
                    target={"turn_id": turn_id, "attempt_id": attempt_id},
                )
            connection.execute(
                """INSERT INTO capstone_thread_commands
                   (thread_id, idempotency_key, request_hash, command_id, receipt)
                   VALUES (%s, %s, %s, %s, %s)""",
                (parsed["thread_id"], parsed["idempotency_key"], request_hash,
                 parsed["command_id"], Jsonb(receipt.to_document())),
            )
            return receipt

    def apply_application_transition(
        self, transition: ThreadApplicationTransition,
    ) -> CommandReceipt:
        """Persist one opaque application transition in one transaction."""
        if not isinstance(transition, ThreadApplicationTransition):
            raise ThreadProtocolError("application transition is invalid")
        parsed = InMemoryThreadService._parse_command(transition.command)
        request_hash = application_transition_hash(transition)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT request_hash, receipt FROM capstone_thread_commands "
                "WHERE thread_id = %s AND idempotency_key = %s",
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
            # The first lookup is a fast path only. A concurrent transition can
            # insert the command while this request waits for the thread lock,
            # so recheck under that lock before admitting or inserting anything.
            row = connection.execute(
                "SELECT request_hash, receipt FROM capstone_thread_commands "
                "WHERE thread_id = %s AND idempotency_key = %s",
                (parsed["thread_id"], parsed["idempotency_key"]),
            ).fetchone()
            if row is not None:
                if row["request_hash"] != request_hash:
                    return self._receipt(parsed, status="rejected", rejection="idempotency_conflict")
                return CommandReceipt.from_document(row["receipt"])
            snapshot = self._snapshot_from_row(thread)
            command_row = connection.execute(
                "SELECT 1 FROM capstone_thread_commands WHERE thread_id = %s AND command_id = %s",
                (parsed["thread_id"], parsed["command_id"]),
            ).fetchone()
            if command_row is not None:
                receipt = self._receipt(parsed, status="rejected", rejection="command_id_conflict")
            elif parsed["run_id"] is not None and parsed["run_id"] != snapshot.run.run_id:
                receipt = self._receipt(parsed, status="rejected", rejection="run_mismatch")
            elif parsed["expected_event_seq"] != snapshot.last_event_seq:
                receipt = self._receipt(parsed, status="rejected", rejection="stale_event_seq")
            elif snapshot.run.state != "open":
                receipt = self._receipt(parsed, status="rejected", rejection="run_not_open")
            else:
                events: list[EventEnvelope] = []
                for offset, application_event in enumerate(transition.events, start=1):
                    event = EventEnvelope(
                        event_id="evt_" + secrets.token_hex(8),
                        event_seq=snapshot.last_event_seq + offset,
                        event_type=application_event.event_type, event_version=1,
                        thread_id=snapshot.thread_id, run_id=snapshot.run.run_id,
                        turn_id=None, attempt_id=None,
                        model_context_id=snapshot.active_model_context.id,
                        selection_revision=snapshot.active_model_context.selection_revision,
                        occurred_at=_now(), visibility=application_event.visibility,
                        payload=dict(application_event.payload),
                    )
                    events.append(event)
                    self._insert_event(connection, event)
                connection.execute(
                    "UPDATE capstone_threads SET application_state = %s, last_event_seq = %s WHERE thread_id = %s",
                    (None if transition.state is None else Jsonb(dict(transition.state)),
                     snapshot.last_event_seq + len(events), snapshot.thread_id),
                )
                receipt = self._receipt(
                    parsed, status="accepted",
                    accepted_event_seq=events[0].event_seq if events else None,
                )
            connection.execute(
                """INSERT INTO capstone_thread_commands
                   (thread_id, idempotency_key, request_hash, command_id, receipt)
                   VALUES (%s, %s, %s, %s, %s)""",
                (parsed["thread_id"], parsed["idempotency_key"], request_hash,
                 parsed["command_id"], Jsonb(receipt.to_document())),
            )
            return receipt

    def claim_attempt(self, worker_id: str, lease_seconds: int) -> AttemptClaim | None:
        if not worker_id or lease_seconds < 1:
            raise ValueError("attempt worker lease is invalid")
        token = secrets.token_hex(16)
        with self._connect() as connection:
            row = connection.execute(
                """SELECT attempt_id FROM capstone_thread_attempts
                   WHERE phase = 'accepted' AND lease_token IS NULL
                   ORDER BY created_at, attempt_id LIMIT 1 FOR UPDATE SKIP LOCKED""",
            ).fetchone()
            if row is None:
                return None
            attempt_row = connection.execute(
                "SELECT * FROM capstone_thread_attempts WHERE attempt_id = %s FOR UPDATE",
                (row["attempt_id"],),
            ).fetchone()
            assert attempt_row is not None
            thread = connection.execute(
                "SELECT * FROM capstone_threads WHERE thread_id = %s FOR UPDATE",
                (attempt_row["thread_id"],),
            ).fetchone()
            if thread is None:
                raise ThreadNotFound(attempt_row["thread_id"])
            current = thread["current_attempt"]
            if not isinstance(current, dict) or current.get("attempt_id") != attempt_row["attempt_id"]:
                raise ThreadExecutionError("attempt snapshot is inconsistent")
            context = None
            try:
                context = ModelContextSnapshot.from_document(attempt_row["model_context_snapshot"])
            except ThreadProtocolError:
                pass
            if (
                context is None
                or context != self._snapshot_from_row(thread).active_model_context
                or context.id != attempt_row["model_context_id"]
                or context.selection_revision != attempt_row["selection_revision"]
            ):
                terminal = AttemptSnapshot.from_document({**current, "phase": "interrupted"})
                event = self._make_attempt_event(
                    thread, terminal, event_seq=thread["last_event_seq"] + 1,
                    event_type="attempt_interrupted",
                    payload={"reason": "model_context_snapshot_unavailable"},
                )
                self._insert_event(connection, event)
                connection.execute(
                    "UPDATE capstone_thread_attempts SET phase = 'interrupted' WHERE attempt_id = %s",
                    (attempt_row["attempt_id"],),
                )
                connection.execute(
                    "UPDATE capstone_threads SET current_attempt = NULL, last_event_seq = %s WHERE thread_id = %s",
                    (event.event_seq, thread["thread_id"]),
                )
                return None
            running = AttemptSnapshot.from_document({**current, "phase": "running"})
            updated = connection.execute(
                """UPDATE capstone_thread_attempts
                   SET phase = 'running', lease_token = %s,
                       lease_deadline = now() + (%s * interval '1 second')
                   WHERE attempt_id = %s AND phase = 'accepted' AND lease_token IS NULL
                   RETURNING *""",
                (token, lease_seconds, attempt_row["attempt_id"]),
            ).fetchone()
            if updated is None:
                return None
            event = self._make_attempt_event(
                thread, running, event_seq=thread["last_event_seq"] + 1,
                event_type="attempt_started", payload={"attempt_id": running.attempt_id},
            )
            self._insert_event(connection, event)
            connection.execute(
                "UPDATE capstone_threads SET current_attempt = %s, last_event_seq = %s WHERE thread_id = %s",
                (Jsonb(running.to_document()), event.event_seq, thread["thread_id"]),
            )
            return AttemptClaim(
                thread_id=thread["thread_id"], run_id=thread["run_id"], attempt=running,
                kind=updated["kind"], instruction=updated["instruction"],
                model_context_id=thread["model_context_id"],
                selection_revision=thread["selection_revision"], lease_token=token,
                model_context=context,
            )

    def renew_attempt(self, claim: AttemptClaim, lease_seconds: int) -> bool:
        if lease_seconds < 1:
            raise ValueError("attempt worker lease is invalid")
        with self._connect() as connection:
            updated = connection.execute(
                """UPDATE capstone_thread_attempts
                   SET lease_deadline = clock_timestamp() + (%s * interval '1 second')
                   WHERE attempt_id = %s AND thread_id = %s AND lease_token = %s AND phase = 'running'
                     AND lease_deadline > clock_timestamp()
                   RETURNING attempt_id""",
                (lease_seconds, claim.attempt.attempt_id, claim.thread_id, claim.lease_token),
            ).fetchone()
            return updated is not None

    def cancel_requested(self, claim: AttemptClaim) -> bool:
        with self._connect() as connection:
            active = connection.execute(
                """SELECT 1 FROM capstone_thread_attempts
                   WHERE attempt_id = %s AND thread_id = %s AND lease_token = %s
                     AND phase = 'running' AND lease_deadline > clock_timestamp()""",
                (claim.attempt.attempt_id, claim.thread_id, claim.lease_token),
            ).fetchone()
            if active is None:
                raise ThreadExecutionError("attempt lease is unavailable")
            requested = connection.execute(
                """SELECT 1 FROM capstone_thread_events
                   WHERE thread_id = %s AND attempt_id = %s
                     AND event_type = 'attempt_cancel_requested' LIMIT 1""",
                (claim.thread_id, claim.attempt.attempt_id),
            ).fetchone()
            return requested is not None

    def rollback_context_if_preparation_failed(
        self, claim: AttemptClaim, *, error_code: str,
    ) -> bool:
        _identifier(error_code, name="selection.error_code")
        with self._connect() as connection:
            attempt = connection.execute(
                """SELECT 1 FROM capstone_thread_attempts
                   WHERE attempt_id = %s AND thread_id = %s AND lease_token = %s
                     AND phase = 'running' AND lease_deadline > clock_timestamp()""",
                (claim.attempt.attempt_id, claim.thread_id, claim.lease_token),
            ).fetchone()
            if attempt is None:
                raise ThreadExecutionError("attempt lease is unavailable")
            thread = connection.execute(
                "SELECT * FROM capstone_threads WHERE thread_id = %s FOR UPDATE",
                (claim.thread_id,),
            ).fetchone()
            if thread is None:
                raise ThreadNotFound(claim.thread_id)
            snapshot = self._snapshot_from_row(thread)
            active = snapshot.active_model_context
            if (
                active.id != claim.model_context.id
                or active.selection_revision != claim.model_context.selection_revision
            ):
                return False
            row = connection.execute(
                """SELECT event_type, payload FROM capstone_thread_events
                   WHERE thread_id = %s
                     AND event_type IN ('selection_activated', 'model_context_activated')
                     AND selection_revision = %s AND model_context_id = %s
                     AND payload->>'activation_turn_id' = %s
                   ORDER BY event_seq DESC LIMIT 1""",
                (claim.thread_id, active.selection_revision, active.id, claim.attempt.turn_id),
            ).fetchone()
            if row is None or not isinstance(row["payload"], dict):
                return False
            previous_context_document = row["payload"].get("previous_context")
            if row["event_type"] == "model_context_activated" and isinstance(previous_context_document, dict):
                try:
                    restored = ModelContextSnapshot.from_document(previous_context_document)
                except ThreadProtocolError:
                    return False
                previous_page = row["payload"].get("previous_grid_page_id")
                if not isinstance(previous_page, str):
                    return False
                event = self._make_control_event(
                    thread, restored, event_seq=snapshot.last_event_seq + 1,
                    event_type="model_context_reverted",
                    payload={
                        "error_code": error_code,
                        "restored_context": restored.to_document(),
                        "restored_grid_page_id": previous_page,
                    },
                )
                self._insert_event(connection, event)
                connection.execute(
                    """UPDATE capstone_threads
                       SET model_context_id = %s, model_id = %s, model_revision = %s,
                           implementation_family = %s, selection_revision = %s,
                           enabled_profiles = %s, active_grid_page_id = %s,
                           pending_selection = NULL, pending_model_switch = NULL,
                           last_event_seq = %s
                       WHERE thread_id = %s""",
                    (
                        restored.id, restored.model_id, restored.model_revision,
                        restored.implementation_family, restored.selection_revision,
                        Jsonb([
                            {"profile_id": profile_id, "profile_version": profile_version}
                            for profile_id, profile_version in restored.enabled_profiles
                        ]), previous_page, event.event_seq, claim.thread_id,
                    ),
                )
                return True
            previous_document = row["payload"].get("previous_selection")
            previous_revision = row["payload"].get("previous_selection_revision")
            if not isinstance(previous_document, dict) or not isinstance(previous_revision, str):
                return False
            try:
                previous = ModelCapabilitySelection.from_document(previous_document)
            except ValueError:
                return False
            restored = replace(
                active, selection_revision=previous_revision,
                enabled_profiles=previous.enabled_profiles,
            )
            event = self._make_control_event(
                thread, restored, event_seq=snapshot.last_event_seq + 1,
                event_type="selection_reverted",
                payload={"error_code": error_code, "restored_selection": previous_document},
            )
            self._insert_event(connection, event)
            connection.execute(
                """UPDATE capstone_threads
                   SET selection_revision = %s, enabled_profiles = %s,
                       pending_selection = NULL, last_event_seq = %s
                   WHERE thread_id = %s""",
                (
                    restored.selection_revision,
                    Jsonb([
                        {"profile_id": profile_id, "profile_version": profile_version}
                        for profile_id, profile_version in restored.enabled_profiles
                    ]),
                    event.event_seq, claim.thread_id,
                ),
            )
            return True

    def rollback_selection_if_preparation_failed(
        self, claim: AttemptClaim, *, error_code: str,
    ) -> bool:
        return self.rollback_context_if_preparation_failed(claim, error_code=error_code)

    def interrupt_expired_attempts(self) -> int:
        interrupted = 0
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM capstone_thread_attempts
                   WHERE phase = 'running' AND lease_deadline <= clock_timestamp()
                   ORDER BY lease_deadline, attempt_id FOR UPDATE SKIP LOCKED""",
            ).fetchall()
            for attempt in rows:
                thread = connection.execute(
                    "SELECT * FROM capstone_threads WHERE thread_id = %s FOR UPDATE",
                    (attempt["thread_id"],),
                ).fetchone()
                if thread is None:
                    raise ThreadExecutionError("attempt thread is unavailable")
                current = thread["current_attempt"]
                if not isinstance(current, dict) or current.get("attempt_id") != attempt["attempt_id"]:
                    raise ThreadExecutionError("attempt snapshot is inconsistent")
                terminal = AttemptSnapshot.from_document({**current, "phase": "interrupted"})
                event = self._make_attempt_event(
                    thread, terminal, event_seq=thread["last_event_seq"] + 1,
                    event_type="attempt_interrupted", payload={"reason": "lease_expired"},
                )
                self._insert_event(connection, event)
                connection.execute(
                    """UPDATE capstone_thread_attempts
                       SET phase = 'interrupted', lease_token = NULL, lease_deadline = NULL
                       WHERE attempt_id = %s""",
                    (attempt["attempt_id"],),
                )
                connection.execute(
                    """UPDATE capstone_threads SET current_attempt = NULL, last_event_seq = %s
                       WHERE thread_id = %s""",
                    (event.event_seq, thread["thread_id"]),
                )
                interrupted += 1
        return interrupted

    def append_runtime_event(
        self, claim: AttemptClaim, *, event_type: str, payload: Mapping[str, Any],
        visibility: str = "public",
    ) -> EventEnvelope:
        _identifier(event_type, name="event_type")
        _validate_bounded_json(payload, name="event.payload", maximum=_MAX_EVENT_BYTES)
        if visibility not in {"public", "diagnostic"}:
            raise ThreadProtocolError("event visibility is invalid")
        with self._connect() as connection:
            attempt = connection.execute(
                """SELECT * FROM capstone_thread_attempts
                   WHERE attempt_id = %s AND thread_id = %s AND lease_token = %s AND phase = 'running'
                     AND lease_deadline > clock_timestamp()
                   FOR UPDATE""",
                (claim.attempt.attempt_id, claim.thread_id, claim.lease_token),
            ).fetchone()
            if attempt is None:
                raise ThreadExecutionError("attempt lease is unavailable")
            thread = connection.execute(
                "SELECT * FROM capstone_threads WHERE thread_id = %s FOR UPDATE",
                (claim.thread_id,),
            ).fetchone()
            if thread is None:
                raise ThreadNotFound(claim.thread_id)
            current = thread["current_attempt"]
            if not isinstance(current, dict) or current.get("attempt_id") != claim.attempt.attempt_id:
                raise ThreadExecutionError("attempt snapshot is inconsistent")
            running = AttemptSnapshot.from_document(current)
            event = self._make_attempt_event(
                thread, running, event_seq=thread["last_event_seq"] + 1,
                event_type=event_type, payload=dict(payload), visibility=visibility,
                context=claim.model_context,
            )
            self._insert_event(connection, event)
            connection.execute(
                "UPDATE capstone_threads SET last_event_seq = %s WHERE thread_id = %s",
                (event.event_seq, claim.thread_id),
            )
            return event

    def finish_attempt(
        self, claim: AttemptClaim, *, phase: str, payload: Mapping[str, Any],
    ) -> ThreadSnapshot:
        if phase not in {"completed", "failed", "cancelled", "interrupted"}:
            raise ValueError("attempt terminal phase is invalid")
        _validate_bounded_json(payload, name="attempt.payload", maximum=_MAX_EVENT_BYTES)
        with self._connect() as connection:
            attempt = connection.execute(
                """SELECT * FROM capstone_thread_attempts
                   WHERE attempt_id = %s AND thread_id = %s AND lease_token = %s AND phase = 'running'
                     AND lease_deadline > clock_timestamp()
                   FOR UPDATE""",
                (claim.attempt.attempt_id, claim.thread_id, claim.lease_token),
            ).fetchone()
            if attempt is None:
                raise ThreadExecutionError("attempt lease is unavailable")
            thread = connection.execute(
                "SELECT * FROM capstone_threads WHERE thread_id = %s FOR UPDATE",
                (claim.thread_id,),
            ).fetchone()
            if thread is None:
                raise ThreadNotFound(claim.thread_id)
            current = thread["current_attempt"]
            if not isinstance(current, dict) or current.get("attempt_id") != claim.attempt.attempt_id:
                raise ThreadExecutionError("attempt snapshot is inconsistent")
            terminal = AttemptSnapshot.from_document({**current, "phase": phase})
            event = self._make_attempt_event(
                thread, terminal, event_seq=thread["last_event_seq"] + 1,
                event_type="attempt_" + phase,
                payload=dict(payload), context=claim.model_context,
            )
            self._insert_event(connection, event)
            connection.execute(
                """UPDATE capstone_thread_attempts
                   SET phase = %s, lease_token = NULL, lease_deadline = NULL
                   WHERE attempt_id = %s""",
                (phase, claim.attempt.attempt_id),
            )
            updated = connection.execute(
                """UPDATE capstone_threads SET current_attempt = NULL, last_event_seq = %s
                   WHERE thread_id = %s RETURNING *""",
                (event.event_seq, claim.thread_id),
            ).fetchone()
            assert updated is not None
            return self._snapshot_from_row(updated)

    def _selection_for_command(
        self, snapshot: ThreadSnapshot, command: Mapping[str, Any],
    ) -> tuple[ModelCapabilitySelection | None, str | None]:
        if snapshot.pending_model_switch is not None:
            return None, "context_change_pending"
        current = (
            snapshot.pending_selection.enabled_profiles
            if snapshot.pending_selection is not None
            else snapshot.active_model_context.enabled_profiles
        )
        payload = command["payload"]
        try:
            if command["kind"] == "enable_profile":
                reference = (payload["profile_id"], payload["profile_version"])
                if reference in current:
                    return None, "profile_already_enabled"
                selection = ModelCapabilitySelection((*current, reference))
            elif command["kind"] == "disable_profile":
                reference = (payload["profile_id"], payload["profile_version"])
                if reference not in current:
                    return None, "profile_not_enabled"
                selection = ModelCapabilitySelection(tuple(item for item in current if item != reference))
            else:
                selection = ModelCapabilitySelection(tuple(
                    (entry["profile_id"], entry["profile_version"])
                    for entry in payload["enabled_profiles"]
                ))
        except (KeyError, TypeError, ValueError):
            return None, "selection_invalid"
        catalog = self._capability_catalog
        if catalog is None:
            return None, "selection_catalog_unavailable"
        try:
            resolved = catalog.resolve(
                ThreadModelDescriptor(
                    snapshot.active_model_context.model_id,
                    snapshot.active_model_context.model_revision,
                    snapshot.active_model_context.implementation_family,
                ),
                selection,
            )
        except (KeyError, TypeError, ValueError):
            return None, "selection_unavailable"
        if resolved != selection:
            return None, "selection_not_exact"
        return selection, None

    def _model_switch_for_command(
        self, snapshot: ThreadSnapshot, command: Mapping[str, Any],
    ) -> tuple[PendingModelSwitchSnapshot | None, str | None]:
        if snapshot.pending_model_switch is not None or snapshot.pending_selection is not None:
            return None, "context_change_pending"
        catalog = self._model_catalog
        if catalog is None:
            return None, "model_catalog_unavailable"
        try:
            descriptor = catalog.resolve(command["payload"]["model_id"])
        except (KeyError, TypeError, ValueError):
            return None, "model_unavailable"
        active = snapshot.active_model_context
        if (
            descriptor.model_id == active.model_id
            and descriptor.model_revision == active.model_revision
            and descriptor.implementation_family == active.implementation_family
        ):
            return None, "model_already_active"
        selection = ModelCapabilitySelection.empty()
        if self._capability_catalog is not None:
            try:
                selection = self._capability_catalog.resolve(descriptor, None)
            except (KeyError, TypeError, ValueError):
                return None, "selection_unavailable"
        return PendingModelSwitchSnapshot(
            command_id=command["command_id"],
            model_id=descriptor.model_id,
            model_revision=descriptor.model_revision,
            implementation_family=descriptor.implementation_family,
            enabled_profiles=selection.enabled_profiles,
        ), None

    def _activate_pending_model_switch(
        self,
        connection: psycopg.Connection[dict[str, Any]],
        thread: Mapping[str, Any],
        snapshot: ThreadSnapshot,
        turn_id: str,
    ) -> ThreadSnapshot:
        pending = snapshot.pending_model_switch
        assert pending is not None
        previous = snapshot.active_model_context
        active = ModelContextSnapshot(
            id="ctx_" + secrets.token_hex(10),
            model_id=pending.model_id,
            model_revision=pending.model_revision,
            implementation_family=pending.implementation_family,
            selection_revision="sel_0",
            enabled_profiles=pending.enabled_profiles,
        )
        event = self._make_control_event(
            thread, active, event_seq=snapshot.last_event_seq + 1,
            event_type="model_context_activated",
            payload={
                "command_id": pending.command_id,
                "activation_turn_id": turn_id,
                "previous_context": previous.to_document(),
                "previous_grid_page_id": snapshot.active_grid_page_id,
                "active_grid_page_id": page_id_for_model(active.model_id),
                "model_context": active.to_document(),
            },
        )
        self._insert_event(connection, event)
        connection.execute(
            """UPDATE capstone_threads
               SET model_context_id = %s, model_id = %s, model_revision = %s,
                   implementation_family = %s, selection_revision = %s,
                   enabled_profiles = %s, active_grid_page_id = %s,
                   pending_model_switch = NULL, pending_selection = NULL,
                   last_event_seq = %s
               WHERE thread_id = %s""",
            (
                active.id, active.model_id, active.model_revision,
                active.implementation_family, active.selection_revision,
                Jsonb([
                    {"profile_id": profile_id, "profile_version": profile_version}
                    for profile_id, profile_version in active.enabled_profiles
                ]), page_id_for_model(active.model_id), event.event_seq, snapshot.thread_id,
            ),
        )
        return replace(
            snapshot, active_model_context=active,
            active_grid_page_id=page_id_for_model(active.model_id),
            pending_model_switch=None, pending_selection=None,
            last_event_seq=event.event_seq,
        )

    def _activate_pending_selection(
        self,
        connection: psycopg.Connection[dict[str, Any]],
        thread: Mapping[str, Any],
        snapshot: ThreadSnapshot,
        turn_id: str,
    ) -> ThreadSnapshot:
        pending = snapshot.pending_selection
        assert pending is not None
        context = snapshot.active_model_context
        revision = _next_selection_revision(context.selection_revision, snapshot.last_event_seq)
        active = replace(
            context,
            selection_revision=revision,
            enabled_profiles=pending.enabled_profiles,
        )
        event = self._make_control_event(
            thread, active, event_seq=snapshot.last_event_seq + 1,
            event_type="selection_activated",
            payload={
                "command_id": pending.command_id,
                "activation_turn_id": turn_id,
                "previous_selection_revision": context.selection_revision,
                "previous_selection": ModelCapabilitySelection(context.enabled_profiles).to_document(),
                "selection": ModelCapabilitySelection(pending.enabled_profiles).to_document(),
            },
        )
        self._insert_event(connection, event)
        connection.execute(
            """UPDATE capstone_threads
               SET model_context_id = %s, model_id = %s, model_revision = %s,
                   implementation_family = %s, selection_revision = %s,
                   enabled_profiles = %s, pending_selection = NULL,
                   last_event_seq = %s
               WHERE thread_id = %s""",
            (
                active.id, active.model_id, active.model_revision,
                active.implementation_family, active.selection_revision,
                Jsonb([
                    {"profile_id": profile_id, "profile_version": profile_version}
                    for profile_id, profile_version in active.enabled_profiles
                ]), event.event_seq, snapshot.thread_id,
            ),
        )
        return replace(
            snapshot, active_model_context=active,
            pending_selection=None, last_event_seq=event.event_seq,
        )

    @staticmethod
    def _make_attempt_event(
        thread: Mapping[str, Any], attempt: AttemptSnapshot, *, event_seq: int,
        event_type: str, payload: Mapping[str, Any], visibility: str = "public",
        context: ModelContextSnapshot | None = None,
    ) -> EventEnvelope:
        model_context_id = thread["model_context_id"] if context is None else context.id
        selection_revision = thread["selection_revision"] if context is None else context.selection_revision
        return EventEnvelope(
            event_id="evt_" + secrets.token_hex(8), event_seq=event_seq,
            event_type=event_type, event_version=1,
            thread_id=thread["thread_id"], run_id=thread["run_id"],
            turn_id=attempt.turn_id, attempt_id=attempt.attempt_id,
            model_context_id=model_context_id,
            selection_revision=selection_revision,
            occurred_at=_now(), visibility=visibility, payload=dict(payload),
        )

    @staticmethod
    def _make_control_event(
        thread: Mapping[str, Any], context: ModelContextSnapshot, *, event_seq: int,
        event_type: str, payload: Mapping[str, Any], visibility: str = "public",
    ) -> EventEnvelope:
        return EventEnvelope(
            event_id="evt_" + secrets.token_hex(8), event_seq=event_seq,
            event_type=event_type, event_version=1,
            thread_id=thread["thread_id"], run_id=thread["run_id"],
            turn_id=None, attempt_id=None,
            model_context_id=context.id,
            selection_revision=context.selection_revision,
            occurred_at=_now(), visibility=visibility, payload=dict(payload),
        )

    @staticmethod
    def _insert_event(connection: psycopg.Connection[dict[str, Any]], event: EventEnvelope) -> None:
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
        pending = (
            None
            if row.get("pending_selection") is None
            else PendingSelectionSnapshot.from_document(row["pending_selection"])
        )
        pending_model_switch = (
            None
            if row.get("pending_model_switch") is None
            else PendingModelSwitchSnapshot.from_document(row["pending_model_switch"])
        )
        selection = ModelCapabilitySelection.from_document({
            "schema": "capstone-model-capability-selection/1",
            "enabled_profiles": row.get("enabled_profiles") or [],
        })
        return ThreadSnapshot(
            thread_id=row["thread_id"],
            run=RunSnapshot(row["run_id"], row["run_state"]),
            active_model_context=ModelContextSnapshot(
                row["model_context_id"], row["model_id"], row["model_revision"],
                row["implementation_family"], row["selection_revision"],
                selection.enabled_profiles,
            ),
            active_grid_page_id=row["active_grid_page_id"], current_attempt=attempt,
            last_event_seq=row["last_event_seq"], base_event_seq=row["base_event_seq"],
            pending_selection=pending,
            pending_model_switch=pending_model_switch,
            application_state=row.get("application_state"),
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
        target: dict[str, Any] | None = None,
    ) -> CommandReceipt:
        return CommandReceipt(
            command_id=command["command_id"], idempotency_key=command["idempotency_key"],
            thread_id=command["thread_id"], run_id=command.get("run_id"), status=status,
            accepted_event_seq=accepted_event_seq, rejection=rejection, target=target,
        )
