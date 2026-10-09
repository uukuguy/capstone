"""Server-side projection boundary for the public ``capstone-thread/1`` API.

The service deliberately sits above the old session ledger.  A durable adapter
can implement the same operations later without making the HTTP layer aware of
Pi, DSH, Domain Packs, or authority internals.
"""

from __future__ import annotations

from .thread_input import admission_submission, freeze_activated_submission

from collections.abc import Callable
import hashlib
import json
import re
import secrets
import time
from itertools import islice
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from threading import RLock
from typing import TYPE_CHECKING, Any, Mapping, Protocol, cast

if TYPE_CHECKING:
    from .turn_router import TurnPlan

from capstone_model_capability_spi import ModelCapabilitySelection

import psycopg
from capstone_agent.database_connect import connect_database
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
from .conversation_context import ConversationContext, MAX_HISTORY_TURNS, project_conversation
from .network_diagram import MAX_DIAGRAM_BYTES, MAX_EVENT_PAGE_BYTES, normalize_network_diagram
from .result_projection import MAX_RESULT_PROJECTIONS, ResultProjection, normalize_result_projection, validate_artifact_reference
from .thread_management import history_cursor, history_page, network_context_page, thread_descriptor, thread_list_page, validate_limit
from .thread_model_workspace import MAX_OPEN_MODELS, MODEL_COMMANDS, migrate_workspace, restore_work_contexts, prepare_workspace_change, synchronize_workspace, workspace_projection, workspace_outcome, workspace_has_capacity


_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
FamilyAvailability = frozenset[str] | Callable[[], frozenset[str] | None] | None


def _resolve_available_families(source: FamilyAvailability) -> frozenset[str] | None:
    families = source() if callable(source) else source
    if families is not None and (
        not isinstance(families, frozenset)
        or any(not isinstance(item, str) or not _IDENTIFIER.fullmatch(item) for item in families)
    ):
        raise ValueError("available implementation families are invalid")
    return families
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
    "switch_model", "reopen_model_context", "switch_runtime",
}) | MODEL_COMMANDS
_SELECTION_COMMAND_KINDS = frozenset({"enable_profile", "disable_profile", "replace_selection"})
_CONTEXT_LOCK_COMMAND_KINDS = frozenset({
    "switch_model", "reopen_model_context", "enable_profile", "disable_profile", "replace_selection",
}) | MODEL_COMMANDS
_CASE_ACTIVE_BLOCKED_COMMAND_KINDS = _MESSAGE_COMMAND_KINDS | {"retry_new_attempt", "switch_runtime"}


def _workspace_blocked_reason(snapshot: ThreadSnapshot, archived: bool) -> str | None:
    if archived:
        return "thread_archived"
    if _application_context_lock(snapshot) or _application_case_active(snapshot):
        return "case_execution_active"
    if snapshot.current_attempt is not None:
        return "attempt_in_progress"
    if snapshot.pending_model_switch is not None or snapshot.pending_selection is not None:
        return "context_change_pending"
    return None if snapshot.run.state == "open" else "run_not_open"


def _workspace_activation_payload(command: Mapping[str, Any], snapshot: ThreadSnapshot, context: ModelContextSnapshot, *, resumed: bool = False) -> dict[str, Any]:
    return {"command_id": command["command_id"], "reason": "model_resume" if resumed else "model_switch",
            "previous_context": snapshot.active_model_context.to_document(),
            "previous_grid_page_id": snapshot.active_grid_page_id,
            "active_grid_page_id": page_id_for_model(context.model_id), "model_context": context.to_document()}


def _historical_network_page(snapshot: ThreadSnapshot, events: list[EventEnvelope], context_id: str,
                             attempt_id: str | None) -> dict[str, Any]:
    _identifier(context_id, name="context_id")
    if attempt_id is not None:
        _identifier(attempt_id, name="attempt_id")
    context = snapshot.active_model_context if context_id == snapshot.active_model_context.id else None
    for event in reversed(events):
        for key in ("model_context", "previous_context", "restored_context"):
            document = event.payload.get(key)
            if isinstance(document, Mapping) and document.get("id") == context_id:
                context = ModelContextSnapshot.from_document(document)
                break
        if context is not None:
            break
    if context is None:
        raise ThreadProtocolError("historical model context is unavailable")
    eligible = [event for event in events if event.model_context_id == context_id and event.visibility == "public"]
    layers = [event for event in eligible if event.event_type in {"network_layer", "network_layer_unavailable"}
              and (attempt_id is None or event.attempt_id == attempt_id)]
    layer = max(layers, key=lambda event: event.event_seq) if layers else None
    target_attempt = layer.attempt_id if layer is not None else attempt_id
    selected = [] if layer is None else [layer]
    for kind in ("network_diagram", "attempt_completed"):
        candidates = [event for event in eligible if event.event_type == kind and event.attempt_id == target_attempt]
        if not candidates and kind == "network_diagram":
            candidates = [event for event in eligible if event.event_type == kind and event.attempt_id is None]
        if candidates:
            selected.append(max(candidates, key=lambda event: event.event_seq))
    page = network_context_page(replace(snapshot, active_model_context=context), selected)
    page["model_context"] = context.to_document()
    return page


def _terminal_result_projections(
    payload: Mapping[str, Any], *, claim: AttemptClaim, phase: str,
) -> tuple[ResultProjection, ...]:
    """Admit typed result projections against this exact terminal Attempt."""

    raw_projections = payload.get("result_projections", [])
    if not isinstance(raw_projections, list) or len(raw_projections) > MAX_RESULT_PROJECTIONS:
        raise ThreadProtocolError("attempt.result_projections is invalid")
    if not raw_projections:
        return ()
    if phase != "completed":
        raise ThreadProtocolError("result projections require a completed attempt")
    raw_results = payload.get("result_refs", [])
    raw_evidence = payload.get("evidence_refs", [])
    if (
        not isinstance(raw_results, list)
        or not isinstance(raw_evidence, list)
        or any(not isinstance(item, str) for item in (*raw_results, *raw_evidence))
    ):
        raise ThreadProtocolError("attempt admitted references are invalid")
    admitted_refs = (*raw_results, *raw_evidence)
    projections: list[ResultProjection] = []
    for raw in raw_projections:
        if not isinstance(raw, Mapping):
            raise ThreadProtocolError("attempt.result_projections contains an invalid item")
        raw_document = dict(raw)
        raw_diagram_ids = raw_document.pop("_diagram_element_ids", None)
        diagram_ids: tuple[str, ...] | None = None
        if raw_diagram_ids is not None:
            if (
                not isinstance(raw_diagram_ids, (list, tuple))
                or any(not isinstance(item, str) for item in raw_diagram_ids)
            ):
                raise ThreadProtocolError("result projection diagram identity is invalid")
            diagram_ids = tuple(raw_diagram_ids)
        document = normalize_result_projection(
            raw_document,
            admitted_refs=admitted_refs,
            diagram_ids=diagram_ids,
            expected_model_revision=claim.model_context.model_revision,
        )
        projection = ResultProjection.from_document(document)
        if diagram_ids is None and (projection.element_refs or any(
            row.element_ref is not None for table in projection.tables for row in table.rows
        ) or projection.overlay is not None):
            raise ThreadProtocolError("result projection diagram identity is unavailable")
        if (
            projection.thread_id != claim.thread_id
            or projection.run_id != claim.run_id
            or projection.turn_id != claim.attempt.turn_id
            or projection.attempt_id != claim.attempt.attempt_id
            or projection.model_context_id != claim.model_context.id
            or projection.model_id != claim.model_context.model_id
        ):
            raise ThreadProtocolError("result projection Attempt binding is invalid")
        projections.append(projection)
    if len({item.result_id for item in projections}) != len(projections):
        raise ThreadProtocolError("attempt.result_projections contain duplicates")
    return tuple(projections)


def _application_context_lock(snapshot: ThreadSnapshot) -> str | None:
    """Read the neutral application lock marker used by Case admission."""

    state = snapshot.application_state
    if not isinstance(state, Mapping):
        return None
    if state.get("context_locked") is True:
        return "case_context_locked"
    return None


def _application_case_active(snapshot: ThreadSnapshot) -> bool:
    state = snapshot.application_state
    if not isinstance(state, Mapping):
        return False
    execution = state.get("case_execution")
    if not isinstance(execution, Mapping):
        return False
    return execution.get("status") in {"created", "running", "waiting_step", "blocked"}


def _is_case_step_command(snapshot: ThreadSnapshot, command: Mapping[str, Any]) -> bool:
    if command["kind"] != "send_auto":
        return False
    payload = command["payload"]
    state = snapshot.application_state
    execution = state.get("case_execution") if isinstance(state, Mapping) else None
    if not isinstance(execution, Mapping) or execution.get("status") not in {
        "created", "running", "waiting_step",
    }:
        return False
    if set(payload) != {
        "text", "case_execution_id", "step_ordinal", "case_context",
        "step_instruction_digest",
    }:
        return False
    ordinal = payload.get("step_ordinal")
    if (
        not isinstance(payload.get("case_execution_id"), str)
        or payload["case_execution_id"] != execution.get("case_execution_id")
        or type(ordinal) is not int
        or ordinal != execution.get("current_step")
    ):
        return False
    steps = execution.get("steps")
    if (
        not isinstance(steps, list)
        or not 1 <= ordinal <= len(steps)
        or not isinstance(steps[ordinal - 1], Mapping)
        or steps[ordinal - 1].get("status") not in {"pending", "running"}
    ):
        return False
    context = execution.get("context")
    if not isinstance(context, Mapping) or payload.get("case_context") != dict(context):
        return False
    active_context = snapshot.active_model_context
    if context != {
        "model_context_id": active_context.id,
        "model_id": active_context.model_id,
        "model_revision": active_context.model_revision,
        "selection_revision": active_context.selection_revision,
    }:
        return False
    instruction_digests = (
        state.get("case_step_instruction_digests")
        if isinstance(state, Mapping) else None
    )
    trusted_digest = None
    if isinstance(instruction_digests, list):
        for item in instruction_digests:
            if (
                isinstance(item, Mapping)
                and item.get("ordinal") == ordinal
                and isinstance(item.get("instruction_digest"), str)
            ):
                trusted_digest = item["instruction_digest"]
                break
    if trusted_digest is None or payload.get("step_instruction_digest") != trusted_digest:
        return False
    if not isinstance(payload.get("text"), str) or not payload["text"].strip():
        return False
    instruction_digest = hashlib.sha256(payload["text"].encode("utf-8")).hexdigest()
    if instruction_digest != trusted_digest:
        return False
    suffix = hashlib.sha256(
        f"{execution['case_execution_id']}:{ordinal}".encode(),
    ).hexdigest()[:24]
    return (
        command["command_id"] == f"case_step_{suffix}"
        and command["idempotency_key"] == f"case_step_idem_{suffix}"
    )


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

    def input_catalog(self, thread_id: str) -> dict[str, object]: ...

    def set_input_catalog_provider(
        self, provider: Callable[[ThreadSnapshot], dict[str, object]],
    ) -> None: ...

    def is_family_available(self, family: str) -> bool: ...

    def read_models(self, thread_id: str) -> dict[str, Any]: ...

    def list_threads(self, *, before: str | None = None, limit: int = 20, archived: bool = False) -> dict[str, Any]: ...

    def set_archived(self, thread_id: str, archived: bool) -> dict[str, Any]: ...

    def is_archived(self, thread_id: str) -> bool: ...

    def read_history(self, thread_id: str, *, before: int | None = None, limit: int = 128) -> dict[str, Any]: ...

    def read_network_events(self, thread_id: str, *, context_id: str | None = None, attempt_id: str | None = None) -> dict[str, Any]: ...

    def context_lock(self, thread_id: str) -> str | None: ...

    def read_events(self, thread_id: str, after_event_seq: int) -> EventPage: ...

    def submit_command(self, command: Mapping[str, Any]) -> CommandReceipt: ...

    def record_rejected_command(
        self, command: Mapping[str, Any], *, rejection: str,
    ) -> CommandReceipt: ...

    def record_command_receipt(
        self, command: Mapping[str, Any], receipt: CommandReceipt,
    ) -> CommandReceipt: ...

    def apply_application_transition(
        self, transition: ThreadApplicationTransition,
    ) -> CommandReceipt: ...

    def active_application_threads(self, limit: int = 32) -> tuple[str, ...]: ...


@dataclass(frozen=True, slots=True)
class PriorResultReference:
    """A bounded retrieval candidate from an admitted prior Attempt."""

    result_ref: str
    evidence_refs: tuple[str, ...]
    capability_id: str
    attempt_id: str

    def __post_init__(self) -> None:
        try:
            validate_artifact_reference(self.result_ref, kind="result")
            for ref in self.evidence_refs:
                validate_artifact_reference(ref, kind="evidence")
        except (TypeError, ValueError) as exc:
            raise ThreadExecutionError("prior result retrieval candidate is invalid") from exc
        if (not isinstance(self.evidence_refs, tuple) or len(self.evidence_refs) > 128
                or not isinstance(self.capability_id, str) or not 0 < len(self.capability_id) <= 256
                or not isinstance(self.attempt_id, str) or not re.fullmatch(r"[a-z][a-z0-9_.:-]{0,127}", self.attempt_id)):
            raise ThreadExecutionError("prior result retrieval candidate is invalid")


def _prior_results_for_context(snapshot: ThreadSnapshot) -> tuple[PriorResultReference, ...]:
    candidates: list[PriorResultReference] = []
    seen: set[str] = set()
    context = snapshot.active_model_context
    for item in reversed(snapshot.result_projections):
        if (item.result_ref is None or item.result_ref in seen or item.status not in {"completed", "partial"}
                or item.thread_id != snapshot.thread_id or item.run_id != snapshot.run.run_id
                or item.model_context_id != context.id or item.model_id != context.model_id
                or item.model_revision != context.model_revision
                or item.source.implementation_family != context.implementation_family):
            continue
        candidates.append(PriorResultReference(item.result_ref, item.evidence_refs, item.source.capability_id, item.attempt_id))
        seen.add(item.result_ref)
        if len(candidates) == 8:
            break
    return tuple(candidates)


@dataclass(frozen=True, slots=True)
class PreviousInstruction:
    """Bounded reader text from the saved Context; never calculation evidence."""

    attempt_id: str
    instruction: str
    answer: str
    phase: str

    def __post_init__(self) -> None:
        _identifier(self.attempt_id, name="previous_instruction.attempt_id")
        if (not isinstance(self.instruction, str) or not self.instruction or len(self.instruction) > 4096
                or not isinstance(self.answer, str) or len(self.answer) > 4096
                or self.phase not in {"completed", "failed", "cancelled", "interrupted"}):
            raise ThreadExecutionError("previous instruction is invalid")


def _previous_instruction_from_events(events: list[EventEnvelope], attempts: Mapping[str, Any],
                                      context: ModelContextSnapshot) -> PreviousInstruction | None:
    terminal = next((event for event in reversed(events) if event.model_context_id == context.id
        and event.event_type in {"attempt_completed", "attempt_failed", "attempt_cancelled", "attempt_interrupted"}), None)
    if terminal is None or terminal.attempt_id is None:
        return None
    record = attempts.get(terminal.attempt_id)
    if record is None:
        return None
    answer = terminal.payload.get("answer")
    if not isinstance(answer, str):
        answer = "".join(str(event.payload.get("text", ""))[:4096] for event in
            [item for item in events if item.attempt_id == terminal.attempt_id and item.event_type == "assistant_text_delta"][:16])
    return PreviousInstruction(terminal.attempt_id, record["instruction"][:4096], answer[:4096], record["attempt"].phase)


def _previous_instruction_from_postgres(connection: psycopg.Connection[dict[str, Any]], thread_id: str,
                                        context: ModelContextSnapshot) -> PreviousInstruction | None:
    row = connection.execute("""SELECT a.attempt_id, a.phase, substring(a.instruction FOR 4096) AS instruction,
        substring(e.payload->>'answer' FOR 4096) AS answer FROM capstone_thread_events e
        JOIN capstone_thread_attempts a ON a.thread_id = e.thread_id AND a.attempt_id = e.attempt_id
        WHERE e.thread_id = %s AND e.model_context_id = %s AND e.visibility = 'public'
        AND e.event_type IN ('attempt_completed', 'attempt_failed', 'attempt_cancelled', 'attempt_interrupted')
        ORDER BY e.event_seq DESC LIMIT 1""", (thread_id, context.id)).fetchone()
    if row is None:
        return None
    answer = row["answer"]
    if answer is None:
        deltas = connection.execute("""SELECT substring(payload->>'text' FOR 4096) AS text FROM capstone_thread_events
            WHERE thread_id = %s AND model_context_id = %s AND attempt_id = %s
            AND event_type = 'assistant_text_delta' AND visibility = 'public' ORDER BY event_seq LIMIT 16""",
            (thread_id, context.id, row["attempt_id"])).fetchall()
        answer = "".join(item["text"] or "" for item in deltas)[:4096]
    return PreviousInstruction(row["attempt_id"], row["instruction"], answer, row["phase"])


def _conversation_model_object(context: object, context_id: str | None) -> dict[str, str] | None:
    """Use saved ledger identity only; legacy absent metadata stays absent."""
    if isinstance(context, Mapping):
        try:
            context = ModelContextSnapshot.from_document(context)
        except ThreadProtocolError:
            return None
    if not isinstance(context, ModelContextSnapshot) or context.id != context_id:
        return None
    return {"object_id": context.id, "model_id": context.model_id,
            "model_revision": context.model_revision, "implementation_family": context.implementation_family}


def _conversation_from_events(events: list[EventEnvelope], attempts: Mapping[str, Any],
                              thread_id: str, cutoff: int) -> ConversationContext:
    rows = []
    for event in events:
        if (event.thread_id != thread_id or event.event_seq > cutoff or event.visibility != "public"
                or event.attempt_id is None
                or event.event_type not in {"attempt_completed", "attempt_failed", "attempt_cancelled", "attempt_interrupted"}):
            continue
        record = attempts.get(event.attempt_id)
        if record is None:
            continue
        answer = event.payload.get("answer")
        if event.event_type == "attempt_completed" and not isinstance(answer, str):
            answer = "".join(item.payload.get("text", "") for item in events
                if item.thread_id == thread_id and item.attempt_id == event.attempt_id
                and item.visibility == "public" and item.event_seq <= event.event_seq
                and item.event_type == "assistant_text_delta")
        rows.append({"turn_id": event.turn_id, "attempt_id": event.attempt_id,
                     "model_context_id": event.model_context_id, "status": event.event_type.removeprefix("attempt_"),
                     "instruction": record["instruction"], "answer": answer,
                     "object": _conversation_model_object(record.get("model_context"), event.model_context_id)})
    return project_conversation(rows, cutoff)


def _conversation_from_postgres(connection: psycopg.Connection[dict[str, Any]], thread_id: str,
                                cutoff: int) -> ConversationContext:
    rows = connection.execute("""SELECT e.turn_id, e.attempt_id, e.model_context_id,
        replace(e.event_type, 'attempt_', '') AS status, a.instruction, e.payload->>'answer' AS answer,
        e.event_seq, a.model_context_snapshot FROM capstone_thread_events e JOIN capstone_thread_attempts a
        ON a.thread_id = e.thread_id AND a.attempt_id = e.attempt_id
        WHERE e.thread_id = %s AND e.event_seq <= %s AND e.visibility = 'public'
        AND e.event_type IN ('attempt_completed', 'attempt_failed', 'attempt_cancelled', 'attempt_interrupted')
        ORDER BY e.event_seq DESC LIMIT %s""", (thread_id, cutoff, MAX_HISTORY_TURNS + 1)).fetchall()
    for row in rows:
        row["object"] = _conversation_model_object(row["model_context_snapshot"], row["model_context_id"])
        if row["status"] == "completed" and row["answer"] is None:
            deltas = connection.execute("""SELECT payload->>'text' AS text FROM capstone_thread_events
                WHERE thread_id = %s AND attempt_id = %s AND event_seq <= %s
                AND visibility = 'public' AND event_type = 'assistant_text_delta' ORDER BY event_seq""",
                (thread_id, row["attempt_id"], row["event_seq"])).fetchall()
            row["answer"] = "".join(item["text"] or "" for item in deltas)
    return project_conversation(list(reversed(rows)), cutoff)


def _attempt_conversation_document(connection: psycopg.Connection[dict[str, Any]],
                                   attempt: Mapping[str, Any]) -> dict[str, object]:
    saved = attempt["conversation_context_snapshot"]
    if saved is not None:
        return ConversationContext.from_document(saved).to_document()
    accepted = connection.execute("""SELECT event_seq - 1 AS cutoff FROM capstone_thread_events
        WHERE thread_id = %s AND attempt_id = %s AND event_type = 'command_accepted'
        ORDER BY event_seq LIMIT 1""", (attempt["thread_id"], attempt["attempt_id"])).fetchone()
    if accepted is None:
        raise ThreadExecutionError("attempt acceptance event is unavailable")
    return _conversation_from_postgres(connection, attempt["thread_id"], accepted["cutoff"]).to_document()


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
    application_catalog: Mapping[str, object] | None = None
    prior_results: tuple[PriorResultReference, ...] = ()
    previous_instruction: PreviousInstruction | None = None
    conversation_context: ConversationContext = ConversationContext()
    submission: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.conversation_context, ConversationContext):
            raise ThreadExecutionError("attempt conversation context is invalid")
        if self.previous_instruction is not None and not isinstance(self.previous_instruction, PreviousInstruction):
            raise ThreadExecutionError("attempt previous instruction is invalid")
        if not isinstance(self.prior_results, tuple) or len(self.prior_results) > 8 or any(not isinstance(item, PriorResultReference) for item in self.prior_results):
            raise ThreadExecutionError("attempt prior results are invalid")
        if (
            self.model_context.id != self.model_context_id
            or self.model_context.selection_revision != self.selection_revision
            or self.attempt.target_model_context_id != self.model_context_id
        ):
            raise ThreadExecutionError("attempt claim model context is inconsistent")
        if self.application_catalog is not None:
            _validate_bounded_json(
                self.application_catalog,
                name="attempt.application_catalog",
                maximum=512 * 1024,
            )


class ThreadExecutionService(ThreadService, Protocol):
    """Durable Attempt operations used by the Harness worker."""

    def claim_attempt(self, worker_id: str, lease_seconds: int, implementation_family: str | None = None) -> AttemptClaim | None: ...

    def freeze_attempt_input(self, claim: AttemptClaim, document: Mapping[str, Any]) -> dict[str, Any]: ...

    def freeze_attempt_decision(self, claim: AttemptClaim, document: Mapping[str, Any] | None) -> dict[str, Any] | None: ...

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
    available_families: frozenset[str] | None = None,
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
            worker_available = available_families is None or family_name in available_families
            available = worker_available and getattr(entry, "available", True)
            reason = "worker_unavailable" if not worker_available else getattr(entry, "unavailable_reason", None)
            models.append({
                "model_id": model_id,
                "authority_model_ref": authority_model_ref,
                "display_name": display_name,
                "diagram_provider_id": diagram_provider_id,
                "implementation_family": implementation_family,
                "available": available,
                **({"unavailable_reason": reason or "model_unavailable"} if not available else {}),
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


def _validate_runtime_payload(event_type: str, payload: Mapping[str, Any], claim: AttemptClaim) -> None:
    if event_type != "network_diagram":
        _validate_bounded_json(payload, name="event.payload", maximum=_MAX_EVENT_BYTES)
        return
    _validate_bounded_json(payload, name="event.payload", maximum=MAX_DIAGRAM_BYTES + 1024)
    if set(payload) != {"diagram"}:
        raise ThreadProtocolError("network diagram payload is invalid")
    try:
        diagram = normalize_network_diagram(payload["diagram"])
    except (TypeError, ValueError) as error:
        raise ThreadProtocolError("network diagram payload is invalid") from error
    if (diagram["model"]["id"] != claim.model_context.model_id or
            diagram["model"]["revision"] != claim.model_context.model_revision):
        raise ThreadProtocolError("network diagram does not match the claimed model")


def _bounded_event_page(thread_id: str, after: int, last: int, events: tuple[EventEnvelope, ...]) -> EventPage:
    selected: list[EventEnvelope] = []
    size = 1024
    for event in events[:256]:
        event_size = len(_canonical(event.to_document()).encode("utf-8")) + 2
        if size + event_size > MAX_EVENT_PAGE_BYTES:
            if not selected:
                raise ThreadProtocolError("event exceeds the page size limit")
            break
        selected.append(event)
        size += event_size
    cursor = selected[-1].event_seq if selected else after
    return EventPage(thread_id, after, cursor, bool(selected and cursor < last), tuple(selected))


def _admission_rejection(command: Mapping[str, Any]) -> str | None:
    """Return a bounded semantic rejection before a command enters the ledger."""

    if command["kind"] in _CONTROL_COMMAND_KINDS:
        payload = command["payload"]
        if command["kind"] == "switch_runtime":
            if set(payload) != {"runtime_mode"} or payload["runtime_mode"] not in ("capstone", "pi_reference"):
                return "runtime_mode_invalid"
        elif command["kind"] == "cancel_live_attempt":
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
        elif command["kind"] in {"activate_model", "close_model"}:
            if set(payload) != {"entry_id"} or not isinstance(payload["entry_id"], str) or not _IDENTIFIER.fullmatch(payload["entry_id"]):
                return "model_target_invalid"
        elif command["kind"] in {"switch_model", "reopen_model_context", "open_model"}:
            required = {"model_id", "reason"} if command["kind"] == "reopen_model_context" else {"model_id"}
            allowed = [required, required | {"model_revision"}] if command["kind"] == "open_model" else [required]
            if set(payload) not in allowed:
                return "model_target_required"
            if "model_revision" in payload and (not isinstance(payload["model_revision"], str) or not payload["model_revision"].strip() or len(payload["model_revision"]) > 256):
                return "model_target_invalid"
            if not isinstance(payload["model_id"], str):
                return "model_target_invalid"
            try:
                validate_model_id(payload["model_id"])
            except ValueError:
                return "model_target_invalid"
            if command["kind"] == "reopen_model_context":
                reason = payload.get("reason")
                if (
                    not isinstance(reason, str) or not reason.strip()
                    or len(reason) > 256 or "\n" in reason or "\r" in reason
                ):
                    return "fresh_context_reason_invalid"
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
    if "enabled_profiles" in command["payload"]:
        try:
            _message_payload_selection(command)
        except (KeyError, TypeError, ValueError):
            return "selection_invalid"
    return None


def _message_payload_selection(command: Mapping[str, Any]) -> ModelCapabilitySelection:
    return ModelCapabilitySelection.from_document({
        "schema": "capstone-model-capability-selection/1",
        "enabled_profiles": command["payload"]["enabled_profiles"],
    })


def _message_selection_for_command(
    snapshot: ThreadSnapshot, command: Mapping[str, Any],
    catalog: ThreadCapabilityCatalog | None,
) -> tuple[ModelCapabilitySelection | None, str | None]:
    """Validate application-selected tools against the activating model."""
    if command["kind"] not in _MESSAGE_COMMAND_KINDS or "enabled_profiles" not in command["payload"]:
        return None, None
    try:
        selection = _message_payload_selection(command)
    except (KeyError, TypeError, ValueError):
        return None, "selection_invalid"
    if catalog is None:
        return None, "selection_catalog_unavailable"
    target = snapshot.pending_model_switch or snapshot.active_model_context
    locked = _application_context_lock(snapshot)
    current = snapshot.pending_selection.enabled_profiles if snapshot.pending_selection is not None else target.enabled_profiles
    if locked is not None and selection.enabled_profiles != current:
        return None, locked
    try:
        resolved = catalog.resolve(ThreadModelDescriptor(
            target.model_id, target.model_revision, target.implementation_family,
        ), selection)
    except (KeyError, TypeError, ValueError):
        return None, "selection_unavailable"
    return (selection, None) if resolved == selection else (None, "selection_not_exact")


def _with_message_selection(
    snapshot: ThreadSnapshot, command: Mapping[str, Any],
    selection: ModelCapabilitySelection | None,
) -> ThreadSnapshot:
    if selection is None:
        return snapshot
    if snapshot.pending_model_switch is not None:
        return replace(snapshot, pending_model_switch=replace(
            snapshot.pending_model_switch, enabled_profiles=selection.enabled_profiles,
        ))
    if snapshot.pending_selection is not None or selection.enabled_profiles != snapshot.active_model_context.enabled_profiles:
        return replace(snapshot, pending_selection=PendingSelectionSnapshot(
            command_id=command["command_id"], enabled_profiles=selection.enabled_profiles,
        ))
    return snapshot


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

    def set_input_catalog_provider(self, provider) -> None:
        self._input_catalog_provider = provider

    def input_catalog(self, thread_id: str) -> dict:
        if self._input_catalog_provider is None:
            raise ThreadExecutionError('input catalog is unavailable')
        return self._input_catalog_provider(self.snapshot(thread_id))

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
        self._catalog_context: Mapping[str, object] | None = None
        self._input_catalog_provider = None
        self._available_families: FamilyAvailability = None
        self._events: list[EventEnvelope] = []
        self._commands: dict[str, _StoredCommand] = {}
        self._command_ids: set[str] = set()
        self._attempts: dict[str, dict[str, Any]] = {}
        self._cancel_requests: set[str] = set()
        self._lock = RLock()
        self._created_at = datetime.now(timezone.utc).isoformat()
        self._archived = False
        self._model_workspace = synchronize_workspace(None, snapshot, model_catalog)

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

    def set_catalog_context(self, catalog_context: Mapping[str, object]) -> None:
        if not isinstance(catalog_context, Mapping):
            raise TypeError("catalog context is invalid")
        self._catalog_context = cast(
            Mapping[str, object],
            json.loads(_canonical(catalog_context)),
        )

    def snapshot(self, thread_id: str) -> ThreadSnapshot:
        with self._lock:
            self._check_thread(thread_id)
            self.interrupt_expired_attempts()
            return self._snapshot

    def catalog(self, thread_id: str) -> dict[str, object]:
        with self._lock:
            self._check_thread(thread_id)
            return _thread_catalog_document(self._model_catalog, self._capability_catalog, _resolve_available_families(self._available_families))

    def read_models(self, thread_id: str) -> dict[str, Any]:
        with self._lock:
            self._check_thread(thread_id)
            self._model_workspace = synchronize_workspace(self._model_workspace, self._snapshot, self._model_catalog)
            blocked = _workspace_blocked_reason(self._snapshot, self._archived)
            return workspace_projection(self._model_workspace, self._snapshot, blocked)

    def set_available_families(self, families: FamilyAvailability) -> None:
        if not callable(families):
            _resolve_available_families(families)
        with self._lock:
            self._available_families = families

    def is_family_available(self, family: str) -> bool:
        families = _resolve_available_families(self._available_families)
        return families is None or family in families

    def context_lock(self, thread_id: str) -> str | None:
        with self._lock:
            self._check_thread(thread_id)
            return _application_context_lock(self._snapshot)

    def active_application_threads(self, limit: int = 32) -> tuple[str, ...]:
        if type(limit) is not int or not 1 <= limit <= 256:
            raise ValueError("active thread limit is invalid")
        with self._lock:
            state = self._snapshot.application_state
            execution = state.get("case_execution") if isinstance(state, Mapping) else None
            status = execution.get("status") if isinstance(execution, Mapping) else None
            if status not in {"created", "running", "waiting_step", "blocked"}:
                return ()
            return (self._snapshot.thread_id,)

    def list_threads(self, *, before: str | None = None, limit: int = 20, archived: bool = False) -> dict[str, Any]:
        validate_limit(limit, 50)
        with self._lock:
            if before is not None:
                self._check_thread(before)
            rows = [] if before is not None or archived != self._archived else [
                thread_descriptor(self._snapshot, created_at=self._created_at, archived=self._archived),
            ]
            return thread_list_page(rows, limit)

    def set_archived(self, thread_id: str, archived: bool) -> dict[str, Any]:
        if type(archived) is not bool:
            raise ThreadProtocolError("archived must be a boolean")
        with self._lock:
            self._check_thread(thread_id)
            if self._snapshot.current_attempt is not None or _application_case_active(self._snapshot):
                raise ThreadExecutionError("thread has active work")
            self._archived = archived
            return thread_descriptor(self._snapshot, created_at=self._created_at, archived=archived)

    def is_archived(self, thread_id: str) -> bool:
        with self._lock:
            self._check_thread(thread_id)
            return self._archived

    def read_history(self, thread_id: str, *, before: int | None = None, limit: int = 128) -> dict[str, Any]:
        validate_limit(limit, 256)
        with self._lock:
            self._check_thread(thread_id)
            cursor = history_cursor(self._snapshot, before)
            events = list(islice((event for event in reversed(self._events)
                if event.event_seq < cursor and event.visibility == "public"), limit + 1))
            return history_page(thread_id, cursor, events, limit)

    def read_network_events(self, thread_id: str, *, context_id: str | None = None, attempt_id: str | None = None) -> dict[str, Any]:
        with self._lock:
            self._check_thread(thread_id)
            if context_id is not None:
                return _historical_network_page(self._snapshot, self._events, context_id, attempt_id)
            layer = next((event for event in reversed(self._events)
                if event.model_context_id == self._snapshot.active_model_context.id
                and event.visibility == "public"
                and event.event_type in {"network_layer", "network_layer_unavailable"}), None)
            baseline = next((event for event in reversed(self._events) if event.model_context_id == self._snapshot.active_model_context.id
                             and event.event_type == "network_diagram" and event.attempt_id is None), None)
            events = ([] if baseline is None else [baseline]) if layer is None else [layer]
            if layer is not None and layer.event_type == "network_layer":
                for kind in ("network_diagram", "attempt_completed"):
                    source = next((event for event in reversed(self._events)
                        if event.attempt_id == layer.attempt_id and event.model_context_id == layer.model_context_id
                        and event.event_type == kind and event.visibility == "public"), None)
                    if source is not None:
                        events.append(source)
            return network_context_page(self._snapshot, events)

    def read_events(self, thread_id: str, after_event_seq: int) -> EventPage:
        if type(after_event_seq) is not int or after_event_seq < 0:
            raise ThreadProtocolError("event cursor is invalid")
        with self._lock:
            self._check_thread(thread_id)
            if after_event_seq < self._snapshot.base_event_seq:
                raise ThreadResyncRequired(self._snapshot)
            events = tuple(islice((event for event in self._events if event.event_seq > after_event_seq), 256))
            return _bounded_event_page(thread_id, after_event_seq, self._snapshot.last_event_seq, events)

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
            if self._archived:
                receipt = self._receipt(parsed, status="rejected", rejection="thread_archived")
                self._commands[parsed["idempotency_key"]] = _StoredCommand(request_hash, receipt)
                self._command_ids.add(parsed["command_id"])
                return receipt
            if parsed["run_id"] is not None and parsed["run_id"] != self._snapshot.run.run_id:
                receipt = self._receipt(parsed, status="rejected", rejection="run_mismatch")
                self._commands[parsed["idempotency_key"]] = _StoredCommand(request_hash, receipt)
                return receipt
            if parsed["expected_event_seq"] != self._snapshot.last_event_seq:
                receipt = self._receipt(parsed, status="rejected", rejection="stale_event_seq")
                self._commands[parsed["idempotency_key"]] = _StoredCommand(request_hash, receipt)
                return receipt
            semantic_rejection = _admission_rejection(parsed)
            submission, input_rejection = admission_submission(self._snapshot, parsed, self._input_catalog_provider)
            semantic_rejection = semantic_rejection or input_rejection
            if semantic_rejection is not None:
                receipt = self._receipt(parsed, status="rejected", rejection=semantic_rejection)
                self._commands[parsed["idempotency_key"]] = _StoredCommand(request_hash, receipt)
                return receipt
            context_lock = _application_context_lock(self._snapshot)
            if context_lock is not None and parsed["kind"] in _CONTEXT_LOCK_COMMAND_KINDS:
                receipt = self._receipt(parsed, status="rejected", rejection=context_lock)
                self._commands[parsed["idempotency_key"]] = _StoredCommand(request_hash, receipt)
                return receipt
            if (
                _application_case_active(self._snapshot)
                and parsed["kind"] in _CASE_ACTIVE_BLOCKED_COMMAND_KINDS
                and not _is_case_step_command(self._snapshot, parsed)
                and not (
                    parsed["kind"] == "retry_new_attempt"
                    and isinstance(self._snapshot.application_state, Mapping)
                    and isinstance(self._snapshot.application_state.get("case_execution"), Mapping)
                    and self._snapshot.application_state["case_execution"].get("status") == "blocked"
                )
            ):
                receipt = self._receipt(
                    parsed, status="rejected", rejection="case_execution_active",
                )
                self._commands[parsed["idempotency_key"]] = _StoredCommand(request_hash, receipt)
                return receipt
            if self._snapshot.run.state != "open":
                receipt = self._receipt(parsed, status="rejected", rejection="run_not_open")
                self._commands[parsed["idempotency_key"]] = _StoredCommand(request_hash, receipt)
                return receipt
            if parsed["kind"] == "switch_runtime":
                if self._snapshot.current_attempt is not None:
                    receipt = self._receipt(parsed, status="rejected", rejection="attempt_in_progress")
                else:
                    mode = parsed["payload"]["runtime_mode"]
                    event = self._append_control_event(event_type="runtime_mode_changed", payload={
                        "command_id": parsed["command_id"], "runtime_mode": mode,
                        "previous_runtime_mode": self._snapshot.runtime_mode,
                    })
                    self._snapshot = replace(self._snapshot, runtime_mode=mode, last_event_seq=event.event_seq)
                    receipt = self._receipt(parsed, status="accepted", accepted_event_seq=event.event_seq, target={"runtime_mode": mode})
                self._commands[parsed["idempotency_key"]] = _StoredCommand(request_hash, receipt)
                self._command_ids.add(parsed["command_id"])
                return receipt
            if parsed["kind"] in MODEL_COMMANDS:
                self._model_workspace = synchronize_workspace(self._model_workspace, self._snapshot, self._model_catalog)
                change, rejection = prepare_workspace_change(self._snapshot, self._model_workspace, parsed, self._model_catalog, self.is_family_available)
                if _application_case_active(self._snapshot):
                    rejection = "case_execution_active"
                if rejection is not None:
                    receipt = self._receipt(parsed, status="rejected", rejection=rejection)
                else:
                    assert change is not None
                    if change.changed:
                        previous = self._snapshot
                        if change.context is not None:
                            event = self._append_control_event(event_type="model_context_activated", context=change.context,
                                payload=_workspace_activation_payload(parsed, previous, change.context, resumed=change.resumed))
                            self._snapshot = replace(previous, active_model_context=change.context,
                                active_grid_page_id=page_id_for_model(change.context.model_id), last_event_seq=event.event_seq)
                        if change.diagram is not None:
                            event = self._append_control_event(event_type="network_diagram", payload={"diagram": change.diagram})
                            self._snapshot = replace(self._snapshot, last_event_seq=event.event_seq)
                        event = self._append_control_event(event_type="model_workspace_changed", payload=workspace_outcome(parsed, self._model_workspace, change.workspace))
                        self._snapshot = replace(self._snapshot, last_event_seq=event.event_seq)
                        self._model_workspace = change.workspace
                    receipt = self._receipt(parsed, status="accepted", accepted_event_seq=self._snapshot.last_event_seq,
                        target={"entry_id": change.workspace["current_entry_id"], "changed": change.changed})
                self._commands[parsed["idempotency_key"]] = _StoredCommand(request_hash, receipt)
                self._command_ids.add(parsed["command_id"])
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
            if parsed["kind"] in {"switch_model", "reopen_model_context"}:
                pending, rejection = self._model_switch_for_command(parsed, allow_same=parsed["kind"] == "reopen_model_context")
                if pending is not None and not workspace_has_capacity(synchronize_workspace(self._model_workspace, self._snapshot, self._model_catalog), pending):
                    rejection = "opened_model_limit"
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
                            "reason": pending.reason,
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
                            runtime_mode=prior["attempt"].runtime_mode,
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
                            "conversation_context": prior["conversation_context"],
                            "intent_input_snapshot": prior.get("intent_input_snapshot"),
                            "intent_decision_snapshot": prior.get("intent_decision_snapshot"),
                            "submission": prior.get("submission"),
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

            selection, rejection = _message_selection_for_command(self._snapshot, parsed, self._capability_catalog)
            if rejection is not None:
                receipt = self._receipt(parsed, status="rejected", rejection=rejection)
                self._commands[parsed["idempotency_key"]] = _StoredCommand(request_hash, receipt)
                self._command_ids.add(parsed["command_id"])
                return receipt
            self._snapshot = _with_message_selection(self._snapshot, parsed, selection)
            token = secrets.token_hex(8)
            turn_id = "turn_" + token
            self._activate_pending_model_switch(turn_id)
            self._activate_pending_selection(turn_id)
            submission = freeze_activated_submission(submission, self._snapshot.active_model_context)

            event_seq = self._snapshot.last_event_seq + 1
            attempt_id = "attempt_" + token
            attempt = AttemptSnapshot(
                turn_id=turn_id, attempt_id=attempt_id, phase="accepted",
                target_model_context_id=self._snapshot.active_model_context.id,
                runtime_mode=self._snapshot.runtime_mode,
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
                         "payload": parsed["payload"], "runtime_mode": attempt.runtime_mode},
            )
            self._events.append(event)
            self._snapshot = replace(
                self._snapshot, current_attempt=attempt, last_event_seq=event_seq,
            )
            self._attempts[attempt_id] = {
                "attempt": attempt, "kind": parsed["kind"],
                "instruction": parsed["payload"]["text"], "lease_token": None,
                "submission": submission,
                "lease_deadline": None,
                "model_context": self._snapshot.active_model_context,
                "command_id": parsed["command_id"],
                "conversation_context": _conversation_from_events(self._events, self._attempts, self._snapshot.thread_id, event_seq - 1),
            }
            receipt = self._receipt(
                parsed, status="accepted", accepted_event_seq=event_seq,
                target={"turn_id": turn_id, "attempt_id": attempt_id},
            )
            self._commands[parsed["idempotency_key"]] = _StoredCommand(request_hash, receipt)
            self._command_ids.add(parsed["command_id"])
            return receipt

    def record_rejected_command(
        self, command: Mapping[str, Any], *, rejection: str,
    ) -> CommandReceipt:
        parsed = self._parse_command(command)
        _identifier(rejection, name="rejection")
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
                return self._receipt(
                    parsed, status="rejected", rejection="command_id_conflict",
                )
            receipt = self._receipt(parsed, status="rejected", rejection=rejection)
            self._commands[parsed["idempotency_key"]] = _StoredCommand(request_hash, receipt)
            self._command_ids.add(parsed["command_id"])
            return receipt

    def record_command_receipt(
        self, command: Mapping[str, Any], receipt: CommandReceipt,
    ) -> CommandReceipt:
        parsed = self._parse_command(command)
        if receipt.command_id != parsed["command_id"] or receipt.idempotency_key != parsed["idempotency_key"]:
            raise ThreadProtocolError("command receipt identity does not match command")
        with self._lock:
            self._check_thread(parsed["thread_id"])
            request_hash = hashlib.sha256(_canonical(command).encode()).hexdigest()
            existing = self._commands.get(parsed["idempotency_key"])
            if existing is not None:
                if existing.request_hash != request_hash:
                    return self._receipt(parsed, status="rejected", rejection="idempotency_conflict")
                return existing.receipt
            if parsed["command_id"] in self._command_ids:
                return self._receipt(parsed, status="rejected", rejection="command_id_conflict")
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
            if self._archived:
                receipt = self._receipt(parsed, status="rejected", rejection="thread_archived")
            elif parsed["run_id"] is not None and parsed["run_id"] != self._snapshot.run.run_id:
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

    def claim_attempt(self, worker_id: str, lease_seconds: int, implementation_family: str | None = None) -> AttemptClaim | None:
        if not worker_id or lease_seconds < 1:
            raise ValueError("attempt worker lease is invalid")
        if implementation_family is not None and not _IDENTIFIER.fullmatch(implementation_family):
            raise ValueError("implementation family is invalid")
        with self._lock:
            for attempt_id, record in self._attempts.items():
                if record["attempt"].phase != "accepted" or record["lease_token"] is not None:
                    continue
                context = record.get("model_context")
                if implementation_family is not None and (context is None or context.implementation_family != implementation_family):
                    continue
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
                    prior_results=_prior_results_for_context(self._snapshot),
                    previous_instruction=_previous_instruction_from_events(self._events, self._attempts, context),
                    conversation_context=record["conversation_context"],
                    submission=record.get("submission"),
                    application_catalog=(
                        self._catalog_context
                        if self._catalog_context is not None
                        else (
                            _thread_catalog_document(
                                self._model_catalog, self._capability_catalog,
                            )
                            if self._model_catalog is not None else None
                        )
                    ),
                )
            return None

    def freeze_attempt_input(self, claim: AttemptClaim, document: Mapping[str, Any]) -> dict[str, Any]:
        """Save recognition input once; retries retain its source and config identity."""
        _validate_bounded_json(document, name="attempt.intent_input", maximum=512 * 1024)
        with self._lock:
            record = self._require_claim(claim)
            if record.get("intent_input_snapshot") is None:
                record["intent_input_snapshot"] = json.loads(_canonical(document))
            return json.loads(_canonical(record["intent_input_snapshot"]))

    def freeze_attempt_decision(self, claim: AttemptClaim, document: Mapping[str, Any] | None) -> dict[str, Any] | None:
        """Save the accepted semantic goal identity once, including across retry."""
        if document is not None:
            _validate_bounded_json(document, name='attempt.intent_decision', maximum=32_768)
        with self._lock:
            record = self._require_claim(claim)
            if record.get('intent_decision_snapshot') is None and document is not None:
                record['intent_decision_snapshot'] = json.loads(_canonical(document))
            frozen = record.get('intent_decision_snapshot')
            return None if frozen is None else json.loads(_canonical(frozen))

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
                    if event.event_type in {
                        "selection_activated", "model_context_activated", "model_context_reopened",
                    }
                    and event.selection_revision == active.selection_revision
                    and event.model_context_id == active.id
                    and event.payload.get("activation_turn_id") == claim.attempt.turn_id
                ),
                None,
            )
            if activation is None:
                return False
            previous_context_document = activation.payload.get("previous_context")
            if activation.event_type in {"model_context_activated", "model_context_reopened"} and isinstance(previous_context_document, dict):
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
        _validate_runtime_payload(event_type, payload, claim)
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
            result_projections = _terminal_result_projections(
                payload, claim=claim, phase=phase,
            )
            existing_result_ids = {item.result_id for item in self._snapshot.result_projections}
            if any(item.result_id in existing_result_ids for item in result_projections):
                raise ThreadProtocolError("result projection already exists")
            terminal = replace(record["attempt"], phase=phase)
            record["attempt"] = terminal
            record["lease_token"] = None
            self._cancel_requests.discard(claim.attempt.attempt_id)
            event_payload = dict(payload)
            if result_projections:
                event_payload["result_projections"] = [item.to_document() for item in result_projections]
            event = self._append_event(
                event_type="attempt_" + phase,
                attempt=terminal, payload=event_payload,
                context=record["model_context"],
            )
            self._snapshot = replace(
                self._snapshot, current_attempt=None, last_event_seq=event.event_seq,
                result_projections=(self._snapshot.result_projections + result_projections)[-MAX_RESULT_PROJECTIONS:],
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
        self, command: Mapping[str, Any], *, allow_same: bool = False,
    ) -> tuple[PendingModelSwitchSnapshot | None, str | None]:
        if self._snapshot.pending_model_switch is not None or self._snapshot.pending_selection is not None:
            return None, "context_change_pending"
        catalog = self._model_catalog
        if catalog is None:
            return None, "model_catalog_unavailable"
        try:
            descriptor = catalog.resolve(command["payload"]["model_id"])
        except (LookupError, TypeError, ValueError):
            return None, "model_unavailable"
        if not self.is_family_available(descriptor.implementation_family):
            return None, "worker_unavailable"
        if not descriptor.available:
            return None, descriptor.unavailable_reason or "model_unavailable"
        active = self._snapshot.active_model_context
        if not allow_same and (
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
            reason="explicit_reopen" if command["kind"] == "reopen_model_context" else "model_switch",
            fresh_context_reason=(
                command["payload"].get("reason")
                if command["kind"] == "reopen_model_context" else None
            ),
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
            event_type=(
                "model_context_reopened"
                if pending.reason == "explicit_reopen"
                else "model_context_activated"
            ),
            payload={
                "command_id": pending.command_id,
                "activation_turn_id": turn_id,
                "reason": pending.reason,
                **({"fresh_context_reason": pending.fresh_context_reason}
                   if pending.fresh_context_reason is not None else {}),
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
        self._model_workspace = synchronize_workspace(self._model_workspace, self._snapshot, self._model_catalog)

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
            occurred_at=_now(), visibility=visibility, payload={**payload, **({"runtime_mode": attempt.runtime_mode} if event_type == "command_accepted" else {})},
        )
        self._events.append(event)
        return event

    def compact_before(self, base_event_seq: int) -> None:
        with self._lock:
            if type(base_event_seq) is not int or base_event_seq < self._snapshot.base_event_seq:
                raise ValueError("event base is invalid")
            if base_event_seq > self._snapshot.last_event_seq:
                raise ValueError("event base exceeds last event")
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
    available: bool = True
    unavailable_reason: str | None = None

    def __post_init__(self) -> None:
        if type(self.available) is not bool or (self.unavailable_reason is not None and not _IDENTIFIER.fullmatch(self.unavailable_reason)):
            raise ValueError("model availability is invalid")
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
        if not descriptor.available:
            raise ValueError(descriptor.unavailable_reason or "model_unavailable")
        available = getattr(self._service, "is_family_available", None)
        if callable(available) and not available(descriptor.implementation_family):
            raise ValueError("worker_unavailable")
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
    result_projections jsonb NOT NULL DEFAULT '[]'::jsonb,
    application_state jsonb,
    base_event_seq integer NOT NULL DEFAULT 0 CHECK (base_event_seq >= 0),
    last_event_seq integer NOT NULL DEFAULT 0 CHECK (last_event_seq >= 0),
    created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE capstone_threads ADD COLUMN IF NOT EXISTS enabled_profiles jsonb NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE capstone_threads ADD COLUMN IF NOT EXISTS pending_selection jsonb;
ALTER TABLE capstone_threads ADD COLUMN IF NOT EXISTS pending_model_switch jsonb;
ALTER TABLE capstone_threads ADD COLUMN IF NOT EXISTS result_projections jsonb NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE capstone_threads ADD COLUMN IF NOT EXISTS application_state jsonb;
ALTER TABLE capstone_threads ADD COLUMN IF NOT EXISTS runtime_mode text NOT NULL DEFAULT 'capstone' CHECK (runtime_mode IN ('capstone', 'pi_reference'));
ALTER TABLE capstone_threads ADD COLUMN IF NOT EXISTS archived boolean NOT NULL DEFAULT false;
ALTER TABLE capstone_threads ADD COLUMN IF NOT EXISTS model_workspace jsonb;
ALTER TABLE capstone_threads ADD COLUMN IF NOT EXISTS model_workspace_migrated boolean NOT NULL DEFAULT false;
CREATE INDEX IF NOT EXISTS capstone_threads_catalog_idx ON capstone_threads(archived, created_at DESC, thread_id DESC);
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
ALTER TABLE capstone_thread_attempts ADD COLUMN IF NOT EXISTS conversation_context_snapshot jsonb;
ALTER TABLE capstone_thread_attempts ADD COLUMN IF NOT EXISTS intent_input_snapshot jsonb;
ALTER TABLE capstone_thread_attempts ADD COLUMN IF NOT EXISTS intent_decision_snapshot jsonb;
ALTER TABLE capstone_thread_attempts ADD COLUMN IF NOT EXISTS submission_snapshot jsonb;
ALTER TABLE capstone_thread_attempts ADD COLUMN IF NOT EXISTS runtime_mode text NOT NULL DEFAULT 'capstone' CHECK (runtime_mode IN ('capstone', 'pi_reference'));
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

    def set_input_catalog_provider(self, provider) -> None:
        self._input_catalog_provider = provider

    def input_catalog(self, thread_id: str) -> dict:
        if self._input_catalog_provider is None:
            raise ThreadExecutionError('input catalog is unavailable')
        return self._input_catalog_provider(self.snapshot(thread_id))

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
        self._input_catalog_provider = None
        self._capability_catalog = capability_catalog
        self._model_catalog = model_catalog
        self._catalog_context: Mapping[str, object] | None = None
        self._available_families: FamilyAvailability = None

    def set_capability_catalog(self, capability_catalog: ThreadCapabilityCatalog) -> None:
        if not callable(getattr(capability_catalog, "resolve", None)):
            raise TypeError("capability catalog is invalid")
        self._capability_catalog = capability_catalog

    def set_model_catalog(self, model_catalog: ThreadModelCatalog) -> None:
        if not callable(getattr(model_catalog, "resolve", None)):
            raise TypeError("model catalog is invalid")
        self._model_catalog = model_catalog

    def set_catalog_context(self, catalog_context: Mapping[str, object]) -> None:
        if not isinstance(catalog_context, Mapping):
            raise TypeError("catalog context is invalid")
        self._catalog_context = cast(
            Mapping[str, object],
            json.loads(_canonical(catalog_context)),
        )

    def _connect(self) -> psycopg.Connection[dict[str, Any]]:
        return cast(
            psycopg.Connection[dict[str, Any]],
            connect_database(self.dsn, row_factory=cast(Any, dict_row)),
        )

    def initialize(self) -> None:
        with self._connect() as connection:
            for statement in _THREAD_SCHEMA.split(";\n"):
                if statement.strip():
                    connection.execute(statement)

    def create_thread(self, snapshot: ThreadSnapshot) -> ThreadSnapshot:
        context = snapshot.active_model_context
        initial_diagram = None
        diagram_provider = getattr(self._model_catalog, "diagram", None)
        if callable(diagram_provider):
            initial_diagram = normalize_network_diagram(diagram_provider(context.model_id, context.model_revision))
            if initial_diagram["model"]["id"] != context.model_id or initial_diagram["model"]["revision"] != context.model_revision:
                raise ThreadProtocolError("initial model diagram identity mismatch")
        with self._connect() as connection:
            try:
                connection.execute(
                    """INSERT INTO capstone_threads
                    (thread_id, run_id, run_state, model_context_id, model_id, model_revision,
                     implementation_family, selection_revision, enabled_profiles,
                     active_grid_page_id, current_attempt, pending_selection,
                     pending_model_switch, result_projections, application_state,
                     base_event_seq, last_event_seq, runtime_mode)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (snapshot.thread_id, snapshot.run.run_id, snapshot.run.state,
                     context.id, context.model_id, context.model_revision,
                     context.implementation_family, context.selection_revision,
                     Jsonb(list({"profile_id": profile_id, "profile_version": profile_version}
                                for profile_id, profile_version in context.enabled_profiles)),
                     snapshot.active_grid_page_id,
                     None if snapshot.current_attempt is None else Jsonb(snapshot.current_attempt.to_document()),
                     None if snapshot.pending_selection is None else Jsonb(snapshot.pending_selection.to_document()),
                     None if snapshot.pending_model_switch is None else Jsonb(snapshot.pending_model_switch.to_document()),
                     Jsonb([item.to_document() for item in snapshot.result_projections]),
                     None if snapshot.application_state is None else Jsonb(dict(snapshot.application_state)),
                     snapshot.base_event_seq, snapshot.last_event_seq, snapshot.runtime_mode),
                )
            except psycopg.errors.UniqueViolation:
                raise ValueError("thread identity already exists") from None
            if initial_diagram is not None:
                event = self._make_control_event({"thread_id": snapshot.thread_id, "run_id": snapshot.run.run_id}, context,
                    event_seq=snapshot.last_event_seq + 1, event_type="network_diagram", payload={"diagram": initial_diagram})
                self._insert_event(connection, event)
                snapshot = replace(snapshot, last_event_seq=event.event_seq)
                connection.execute("UPDATE capstone_threads SET last_event_seq = %s WHERE thread_id = %s", (event.event_seq, snapshot.thread_id))
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
        return _thread_catalog_document(self._model_catalog, self._capability_catalog, _resolve_available_families(self._available_families))

    def read_models(self, thread_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM capstone_threads WHERE thread_id = %s FOR UPDATE", (thread_id,)).fetchone()
            if row is None:
                raise ThreadNotFound(thread_id)
            snapshot = self._snapshot_from_row(row)
            workspace = self._synchronize_model_workspace(connection, row, snapshot)
            return workspace_projection(workspace, snapshot, _workspace_blocked_reason(snapshot, row["archived"]))

    def _synchronize_model_workspace(self, connection: psycopg.Connection[dict[str, Any]],
                                     row: Mapping[str, Any], snapshot: ThreadSnapshot) -> dict[str, Any]:
        """Run under the Thread row lock, including before the first model command."""
        if row.get("model_workspace_migrated"):
            workspace = synchronize_workspace(row.get("model_workspace"), snapshot, self._model_catalog)
        else:
            # Read retained Context identities, independent of the compacted live cursor.
            # Stop legacy import at the first explicit membership event.
            contexts = connection.execute("""SELECT document, seq FROM (
                SELECT DISTINCT ON (document->>'implementation_family', document->>'model_id', document->>'model_revision')
                document, seq FROM capstone_thread_events e CROSS JOIN LATERAL
                (VALUES (e.payload->'previous_context', e.event_seq - 1),
                        (e.payload->'model_context', e.event_seq),
                        (e.payload->'restored_context', e.event_seq)) AS c(document, seq)
                WHERE e.thread_id = %s AND e.visibility = 'public'
                AND e.event_type IN ('model_context_activated', 'model_context_reopened', 'model_context_reverted')
                AND jsonb_typeof(document) = 'object'
                AND e.event_seq < COALESCE((SELECT MIN(event_seq) FROM capstone_thread_events
                    WHERE thread_id = %s AND event_type = 'model_workspace_changed'), 2147483647)
                ORDER BY document->>'implementation_family', document->>'model_id', document->>'model_revision', seq DESC
                ) AS identities ORDER BY seq DESC LIMIT %s""",
                (snapshot.thread_id, snapshot.thread_id, MAX_OPEN_MODELS)).fetchall()
            # Older membership events recorded display names. Treat a recorded close
            # conservatively; entries already in the workspace are preserved.
            closed = connection.execute("""SELECT DISTINCT payload->>'closed_model_name' AS name
                FROM capstone_thread_events WHERE thread_id = %s AND event_type = 'model_workspace_changed'
                AND payload->>'kind' = 'close_model'""", (snapshot.thread_id,)).fetchall()
            workspace = migrate_workspace(row.get("model_workspace"), snapshot,
                [(item["seq"], item["document"]) for item in contexts], {item["name"] for item in closed}, self._model_catalog)
        missing = [entry for entry in workspace["models"] if entry["work_context"] is None]
        if missing:
            # Recover work positions for preceding-release members, including
            # Contexts created after the membership migration boundary.
            saved = connection.execute("""SELECT DISTINCT ON (document->>'implementation_family', document->>'model_id', document->>'model_revision')
                document, seq FROM capstone_thread_events e CROSS JOIN LATERAL
                (VALUES (e.payload->'previous_context', e.event_seq - 1),
                        (e.payload->'model_context', e.event_seq),
                        (e.payload->'restored_context', e.event_seq)) AS c(document, seq)
                CROSS JOIN jsonb_array_elements(%s) AS m(entry)
                WHERE e.thread_id = %s AND e.visibility = 'public'
                AND e.event_type IN ('model_context_activated', 'model_context_reopened', 'model_context_reverted')
                AND document->>'implementation_family' = entry->>'implementation_family'
                AND document->>'model_id' = entry->>'model_id'
                AND document->>'model_revision' = entry->>'model_revision'
                ORDER BY document->>'implementation_family', document->>'model_id', document->>'model_revision', seq DESC""",
                (Jsonb(missing), snapshot.thread_id)).fetchall()
            workspace = restore_work_contexts(workspace, [(item["seq"], item["document"]) for item in saved])
        if workspace != row.get("model_workspace") or not row.get("model_workspace_migrated"):
            connection.execute("UPDATE capstone_threads SET model_workspace = %s, model_workspace_migrated = true WHERE thread_id = %s",
                (Jsonb(workspace), snapshot.thread_id))
        return workspace

    def set_available_families(self, families: FamilyAvailability) -> None:
        if not callable(families):
            _resolve_available_families(families)
        self._available_families = families

    def is_family_available(self, family: str) -> bool:
        families = _resolve_available_families(self._available_families)
        return families is None or family in families

    def context_lock(self, thread_id: str) -> str | None:
        return _application_context_lock(self.snapshot(thread_id))

    def active_application_threads(self, limit: int = 32) -> tuple[str, ...]:
        if type(limit) is not int or not 1 <= limit <= 256:
            raise ValueError("active thread limit is invalid")
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT thread_id FROM capstone_threads
                   WHERE application_state->'case_execution'->>'status'
                         IN ('created', 'running', 'waiting_step', 'blocked')
                   ORDER BY thread_id LIMIT %s""",
                (limit,),
            ).fetchall()
        return tuple(row["thread_id"] for row in rows)

    def list_threads(self, *, before: str | None = None, limit: int = 20, archived: bool = False) -> dict[str, Any]:
        validate_limit(limit, 50)
        with self._connect() as connection:
            cursor = None
            if before is not None:
                cursor = connection.execute(
                    "SELECT created_at, thread_id FROM capstone_threads WHERE thread_id = %s", (before,),
                ).fetchone()
                if cursor is None:
                    raise ThreadNotFound(before)
            rows = connection.execute(
                """SELECT thread_id, model_id, implementation_family, created_at, archived, last_event_seq
                   FROM capstone_threads WHERE archived = %s
                   AND (%s::timestamptz IS NULL OR (created_at, thread_id) < (%s, %s))
                   ORDER BY created_at DESC, thread_id DESC LIMIT %s""",
                (archived, None if cursor is None else cursor["created_at"],
                 None if cursor is None else cursor["created_at"],
                 None if cursor is None else cursor["thread_id"], limit + 1),
            ).fetchall()
        descriptors = [{**row, "created_at": row["created_at"].isoformat()} for row in rows]
        return thread_list_page(descriptors, limit)

    def set_archived(self, thread_id: str, archived: bool) -> dict[str, Any]:
        if type(archived) is not bool:
            raise ThreadProtocolError("archived must be a boolean")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM capstone_threads WHERE thread_id = %s FOR UPDATE", (thread_id,),
            ).fetchone()
            if row is None:
                raise ThreadNotFound(thread_id)
            snapshot = self._snapshot_from_row(row)
            if snapshot.current_attempt is not None or _application_case_active(snapshot):
                raise ThreadExecutionError("thread has active work")
            connection.execute("UPDATE capstone_threads SET archived = %s WHERE thread_id = %s", (archived, thread_id))
        return thread_descriptor(snapshot, created_at=row["created_at"].isoformat(), archived=archived)

    def is_archived(self, thread_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute("SELECT archived FROM capstone_threads WHERE thread_id = %s", (thread_id,)).fetchone()
        if row is None:
            raise ThreadNotFound(thread_id)
        return row["archived"]

    def read_history(self, thread_id: str, *, before: int | None = None, limit: int = 128) -> dict[str, Any]:
        validate_limit(limit, 256)
        cursor = history_cursor(self.snapshot(thread_id), before)
        with self._connect() as connection:
            rows = connection.execute(
                """WITH candidates AS (
                     SELECT event_seq, octet_length(payload::text) + 1024 AS bytes
                     FROM capstone_thread_events
                     WHERE thread_id = %s AND event_seq < %s AND visibility = 'public'
                     ORDER BY event_seq DESC LIMIT %s
                   ), budget AS (
                     SELECT event_seq, sum(bytes) OVER (ORDER BY event_seq DESC) AS total,
                            row_number() OVER (ORDER BY event_seq DESC) AS rank FROM candidates
                   )
                   SELECT event.* FROM capstone_thread_events event
                   JOIN budget ON budget.event_seq = event.event_seq
                   WHERE event.thread_id = %s AND (budget.total <= %s OR budget.rank = 1)
                   ORDER BY event.event_seq DESC""",
                (thread_id, cursor, limit + 1, thread_id, MAX_EVENT_PAGE_BYTES - 1024),
            ).fetchall()
            events = [self._event_from_row(row) for row in rows]
            page = history_page(thread_id, cursor, events, limit)
            if page["events"]:
                remaining = connection.execute(
                    "SELECT EXISTS(SELECT 1 FROM capstone_thread_events WHERE thread_id = %s AND event_seq < %s AND visibility = 'public') AS more",
                    (thread_id, page["next_before_event_seq"]),
                ).fetchone()
                assert remaining is not None
                page["has_more"] = remaining["more"]
        return page

    def read_events(self, thread_id: str, after_event_seq: int) -> EventPage:
        if type(after_event_seq) is not int or after_event_seq < 0:
            raise ThreadProtocolError("event cursor is invalid")
        snapshot = self.snapshot(thread_id)
        if after_event_seq < snapshot.base_event_seq:
            raise ThreadResyncRequired(snapshot)
        with self._connect() as connection:
            rows = connection.execute(
                """WITH sizes AS (
                     SELECT event_seq, octet_length(payload::text) + 1024 AS bytes
                     FROM capstone_thread_events WHERE thread_id = %s AND event_seq > %s
                     ORDER BY event_seq LIMIT 256
                   ), budget AS (
                     SELECT event_seq, sum(bytes) OVER (ORDER BY event_seq) AS total,
                            row_number() OVER (ORDER BY event_seq) AS rank FROM sizes
                   )
                   SELECT event.* FROM capstone_thread_events AS event
                   JOIN budget ON budget.event_seq = event.event_seq
                   WHERE event.thread_id = %s AND (budget.total <= %s OR budget.rank = 1)
                   ORDER BY event.event_seq""",
                (thread_id, after_event_seq, thread_id, MAX_EVENT_PAGE_BYTES - 1024),
            ).fetchall()
        events = tuple(self._event_from_row(row) for row in rows)
        return _bounded_event_page(thread_id, after_event_seq, snapshot.last_event_seq, events)

    def read_network_events(self, thread_id: str, *, context_id: str | None = None, attempt_id: str | None = None) -> dict[str, Any]:
        snapshot = self.snapshot(thread_id)
        with self._connect() as connection:
            if context_id is not None:
                _identifier(context_id, name="context_id")
                if attempt_id is not None:
                    _identifier(attempt_id, name="attempt_id")
                target_attempt = attempt_id
                if target_attempt is None:
                    latest_layer = connection.execute("""SELECT attempt_id FROM capstone_thread_events WHERE thread_id = %s
                        AND model_context_id = %s AND visibility = 'public'
                        AND event_type IN ('network_layer', 'network_layer_unavailable') ORDER BY event_seq DESC LIMIT 1""", (thread_id, context_id)).fetchone()
                    target_attempt = latest_layer["attempt_id"] if latest_layer is not None else None
                rows = connection.execute("""SELECT DISTINCT ON (event_type, attempt_id) * FROM capstone_thread_events WHERE thread_id = %s
                    AND model_context_id = %s AND visibility = 'public'
                    AND event_type IN ('model_context_activated', 'model_context_reopened', 'model_context_reverted', 'network_diagram', 'network_layer', 'network_layer_unavailable', 'attempt_completed')
                    AND (attempt_id IS NULL OR attempt_id = %s) ORDER BY event_type, attempt_id, event_seq DESC LIMIT 8""",
                    (thread_id, context_id, target_attempt)).fetchall()
                identity = connection.execute("""SELECT * FROM capstone_thread_events WHERE thread_id = %s
                    AND (payload->'model_context'->>'id' = %s OR payload->'previous_context'->>'id' = %s OR payload->'restored_context'->>'id' = %s)
                    AND event_type IN ('model_context_activated', 'model_context_reopened', 'model_context_reverted')
                    AND visibility = 'public' ORDER BY event_seq DESC LIMIT 1""", (thread_id, context_id, context_id, context_id)).fetchone()
                if identity is not None:
                    rows.append(identity)
                return _historical_network_page(snapshot, sorted([self._event_from_row(row) for row in rows], key=lambda event: event.event_seq), context_id, attempt_id)
            layer = connection.execute(
                """SELECT * FROM capstone_thread_events WHERE thread_id = %s
                   AND model_context_id = %s AND visibility = 'public'
                   AND event_type IN ('network_layer', 'network_layer_unavailable')
                   ORDER BY event_seq DESC LIMIT 1""",
                (thread_id, snapshot.active_model_context.id),
            ).fetchone()
            rows = [] if layer is None else [layer]
            if layer is None:
                baseline = connection.execute("""SELECT * FROM capstone_thread_events WHERE thread_id = %s
                    AND model_context_id = %s AND event_type = 'network_diagram' AND attempt_id IS NULL
                    AND visibility = 'public' ORDER BY event_seq DESC LIMIT 1""", (thread_id, snapshot.active_model_context.id)).fetchone()
                if baseline is not None:
                    rows.append(baseline)
            if layer is not None and layer["event_type"] == "network_layer":
                rows.extend(connection.execute(
                    """SELECT DISTINCT ON (event_type) * FROM capstone_thread_events
                       WHERE thread_id = %s AND attempt_id = %s AND model_context_id = %s
                       AND visibility = 'public' AND event_type IN ('network_diagram', 'attempt_completed')
                       ORDER BY event_type, event_seq DESC""",
                    (thread_id, layer["attempt_id"], snapshot.active_model_context.id),
                ).fetchall())
        return network_context_page(snapshot, [self._event_from_row(row) for row in rows])

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
            # Recheck after the Thread lock: a concurrent identical request may
            # have committed while this connection waited for the row.
            existing = connection.execute("SELECT request_hash, receipt FROM capstone_thread_commands WHERE thread_id = %s AND idempotency_key = %s",
                (parsed["thread_id"], parsed["idempotency_key"])).fetchone()
            if existing is not None:
                if existing["request_hash"] != request_hash:
                    return self._receipt(parsed, status="rejected", rejection="idempotency_conflict")
                return CommandReceipt.from_document(existing["receipt"])
            message_selection, message_selection_rejection = _message_selection_for_command(snapshot, parsed, self._capability_catalog)
            submission, input_rejection = admission_submission(snapshot, parsed, self._input_catalog_provider)
            command_row = connection.execute(
                "SELECT 1 FROM capstone_thread_commands WHERE thread_id = %s AND command_id = %s",
                (parsed["thread_id"], parsed["command_id"]),
            ).fetchone()
            if command_row is not None:
                receipt = self._receipt(parsed, status="rejected", rejection="command_id_conflict")
            elif thread["archived"]:
                receipt = self._receipt(parsed, status="rejected", rejection="thread_archived")
            elif parsed["run_id"] is not None and parsed["run_id"] != snapshot.run.run_id:
                receipt = self._receipt(parsed, status="rejected", rejection="run_mismatch")
            elif parsed["expected_event_seq"] != snapshot.last_event_seq:
                receipt = self._receipt(parsed, status="rejected", rejection="stale_event_seq")
            elif (semantic_rejection := _admission_rejection(parsed)) is not None:
                receipt = self._receipt(parsed, status="rejected", rejection=semantic_rejection)
            elif input_rejection is not None:
                receipt = self._receipt(parsed, status="rejected", rejection=input_rejection)
            elif (
                (context_lock := _application_context_lock(snapshot)) is not None
                and parsed["kind"] in _CONTEXT_LOCK_COMMAND_KINDS
            ):
                receipt = self._receipt(parsed, status="rejected", rejection=context_lock)
            elif (
                _application_case_active(snapshot)
                and parsed["kind"] in _CASE_ACTIVE_BLOCKED_COMMAND_KINDS
                and not _is_case_step_command(snapshot, parsed)
                and not (
                    parsed["kind"] == "retry_new_attempt"
                    and isinstance(snapshot.application_state, Mapping)
                    and isinstance(snapshot.application_state.get("case_execution"), Mapping)
                    and snapshot.application_state["case_execution"].get("status") == "blocked"
                )
            ):
                receipt = self._receipt(
                    parsed, status="rejected", rejection="case_execution_active",
                )
            elif snapshot.run.state != "open":
                receipt = self._receipt(parsed, status="rejected", rejection="run_not_open")
            elif parsed["kind"] == "switch_runtime":
                if snapshot.current_attempt is not None:
                    receipt = self._receipt(parsed, status="rejected", rejection="attempt_in_progress")
                else:
                    mode = parsed["payload"]["runtime_mode"]
                    event = self._make_control_event(thread, snapshot.active_model_context,
                        event_seq=snapshot.last_event_seq + 1, event_type="runtime_mode_changed",
                        payload={"command_id": parsed["command_id"], "runtime_mode": mode, "previous_runtime_mode": snapshot.runtime_mode})
                    self._insert_event(connection, event)
                    connection.execute("UPDATE capstone_threads SET runtime_mode = %s, last_event_seq = %s WHERE thread_id = %s", (mode, event.event_seq, snapshot.thread_id))
                    receipt = self._receipt(parsed, status="accepted", accepted_event_seq=event.event_seq, target={"runtime_mode": mode})
            elif parsed["kind"] in MODEL_COMMANDS:
                workspace = self._synchronize_model_workspace(connection, thread, snapshot)
                change, rejection = prepare_workspace_change(snapshot, workspace, parsed, self._model_catalog, self.is_family_available)
                if _application_case_active(snapshot):
                    rejection = "case_execution_active"
                if rejection is not None:
                    receipt = self._receipt(parsed, status="rejected", rejection=rejection)
                else:
                    assert change is not None
                    context = change.context or snapshot.active_model_context
                    seq = snapshot.last_event_seq
                    if change.changed:
                        events = []
                        if change.context is not None:
                            events.append(("model_context_activated", _workspace_activation_payload(parsed, snapshot, context, resumed=change.resumed)))
                        if change.diagram is not None:
                            events.append(("network_diagram", {"diagram": change.diagram}))
                        events.append(("model_workspace_changed", workspace_outcome(parsed, workspace, change.workspace)))
                        for event_type, payload in events:
                            seq += 1
                            self._insert_event(connection, self._make_control_event(thread, context, event_seq=seq, event_type=event_type, payload=payload))
                        connection.execute("""UPDATE capstone_threads SET model_context_id = %s, model_id = %s,
                            model_revision = %s, implementation_family = %s, selection_revision = %s,
                            enabled_profiles = %s, active_grid_page_id = %s, model_workspace = %s, last_event_seq = %s
                            WHERE thread_id = %s""", (context.id, context.model_id, context.model_revision, context.implementation_family,
                            context.selection_revision, Jsonb([{"profile_id": pid, "profile_version": version} for pid, version in context.enabled_profiles]),
                            page_id_for_model(context.model_id), Jsonb(change.workspace), seq, snapshot.thread_id))
                    receipt = self._receipt(parsed, status="accepted", accepted_event_seq=seq,
                        target={"entry_id": change.workspace["current_entry_id"], "changed": change.changed})
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
            elif parsed["kind"] in {"switch_model", "reopen_model_context"}:
                pending, rejection = self._model_switch_for_command(snapshot, parsed, allow_same=parsed["kind"] == "reopen_model_context")
                if pending is not None and not workspace_has_capacity(self._synchronize_model_workspace(connection, thread, snapshot), pending):
                    rejection = "opened_model_limit"
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
                            "reason": pending.reason,
                            **({"fresh_context_reason": pending.fresh_context_reason}
                               if pending.fresh_context_reason is not None else {}),
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
                                runtime_mode=prior["runtime_mode"],
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
                                    model_context_snapshot, conversation_context_snapshot, intent_input_snapshot,
                                    intent_decision_snapshot, runtime_mode, submission_snapshot, phase)
                                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'accepted')""",
                                (attempt_id, snapshot.thread_id, snapshot.run.run_id, turn_id,
                                 parsed["command_id"], prior["kind"], prior["instruction"],
                                 snapshot.active_model_context.id,
                                 snapshot.active_model_context.selection_revision,
                                 Jsonb(snapshot.active_model_context.to_document()),
                                 Jsonb(_attempt_conversation_document(connection, prior)),
                                 None if prior["intent_input_snapshot"] is None else Jsonb(prior["intent_input_snapshot"]),
                                 None if prior['intent_decision_snapshot'] is None else Jsonb(prior['intent_decision_snapshot']),
                                 attempt.runtime_mode, None if prior['submission_snapshot'] is None else Jsonb(prior['submission_snapshot'])),
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
            elif message_selection_rejection is not None:
                receipt = self._receipt(parsed, status="rejected", rejection=message_selection_rejection)
            else:
                snapshot = _with_message_selection(snapshot, parsed, message_selection)
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
                submission = freeze_activated_submission(submission, snapshot.active_model_context)
                event_seq = snapshot.last_event_seq + 1
                attempt_id = "attempt_" + token
                attempt = AttemptSnapshot(
                    turn_id=turn_id, attempt_id=attempt_id, phase="accepted",
                    target_model_context_id=snapshot.active_model_context.id,
                    runtime_mode=snapshot.runtime_mode,
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
                             "payload": parsed["payload"], "runtime_mode": attempt.runtime_mode},
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
                        instruction, model_context_id, selection_revision, model_context_snapshot, conversation_context_snapshot, runtime_mode, submission_snapshot, phase)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'accepted')""",
                    (attempt_id, snapshot.thread_id, snapshot.run.run_id, turn_id,
                     parsed["command_id"], parsed["kind"], parsed["payload"]["text"],
                     snapshot.active_model_context.id,
                     snapshot.active_model_context.selection_revision,
                     Jsonb(snapshot.active_model_context.to_document()),
                     Jsonb(_conversation_from_postgres(connection, snapshot.thread_id, event_seq - 1).to_document()), attempt.runtime_mode,
                     None if submission is None else Jsonb(submission)),
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

    def record_rejected_command(
        self, command: Mapping[str, Any], *, rejection: str,
    ) -> CommandReceipt:
        """Persist a rejected command receipt without emitting a Thread event."""
        parsed = InMemoryThreadService._parse_command(command)
        _identifier(rejection, name="rejection")
        request_hash = hashlib.sha256(_canonical(command).encode()).hexdigest()
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
            row = connection.execute(
                "SELECT request_hash, receipt FROM capstone_thread_commands "
                "WHERE thread_id = %s AND idempotency_key = %s",
                (parsed["thread_id"], parsed["idempotency_key"]),
            ).fetchone()
            if row is not None:
                if row["request_hash"] != request_hash:
                    return self._receipt(parsed, status="rejected", rejection="idempotency_conflict")
                return CommandReceipt.from_document(row["receipt"])
            command_row = connection.execute(
                "SELECT 1 FROM capstone_thread_commands "
                "WHERE thread_id = %s AND command_id = %s",
                (parsed["thread_id"], parsed["command_id"]),
            ).fetchone()
            if command_row is not None:
                return self._receipt(parsed, status="rejected", rejection="command_id_conflict")
            receipt = self._receipt(parsed, status="rejected", rejection=rejection)
            connection.execute(
                """INSERT INTO capstone_thread_commands
                   (thread_id, idempotency_key, request_hash, command_id, receipt)
                   VALUES (%s, %s, %s, %s, %s)""",
                (parsed["thread_id"], parsed["idempotency_key"], request_hash,
                 parsed["command_id"], Jsonb(receipt.to_document())),
            )
            return receipt

    def record_command_receipt(
        self, command: Mapping[str, Any], receipt: CommandReceipt,
    ) -> CommandReceipt:
        parsed = InMemoryThreadService._parse_command(command)
        if receipt.command_id != parsed["command_id"] or receipt.idempotency_key != parsed["idempotency_key"]:
            raise ThreadProtocolError("command receipt identity does not match command")
        request_hash = hashlib.sha256(_canonical(command).encode()).hexdigest()
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
                "SELECT 1 FROM capstone_threads WHERE thread_id = %s FOR UPDATE",
                (parsed["thread_id"],),
            ).fetchone()
            if thread is None:
                raise ThreadNotFound(parsed["thread_id"])
            row = connection.execute(
                "SELECT request_hash, receipt FROM capstone_thread_commands "
                "WHERE thread_id = %s AND idempotency_key = %s",
                (parsed["thread_id"], parsed["idempotency_key"]),
            ).fetchone()
            if row is not None:
                if row["request_hash"] != request_hash:
                    return self._receipt(parsed, status="rejected", rejection="idempotency_conflict")
                return CommandReceipt.from_document(row["receipt"])
            command_row = connection.execute(
                "SELECT 1 FROM capstone_thread_commands "
                "WHERE thread_id = %s AND command_id = %s",
                (parsed["thread_id"], parsed["command_id"]),
            ).fetchone()
            if command_row is not None:
                return self._receipt(parsed, status="rejected", rejection="command_id_conflict")
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
                # The command identity is protected by a durable unique key.
                # Do not insert a second receipt with the same command_id; the
                # rejection is deterministic and can be recomputed on retry.
                return self._receipt(parsed, status="rejected", rejection="command_id_conflict")
            elif thread["archived"]:
                receipt = self._receipt(parsed, status="rejected", rejection="thread_archived")
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

    def claim_attempt(self, worker_id: str, lease_seconds: int, implementation_family: str | None = None) -> AttemptClaim | None:
        if not worker_id or lease_seconds < 1:
            raise ValueError("attempt worker lease is invalid")
        if implementation_family is not None and not _IDENTIFIER.fullmatch(implementation_family):
            raise ValueError("implementation family is invalid")
        token = secrets.token_hex(16)
        with self._connect() as connection:
            row = connection.execute(
                """SELECT attempt_id FROM capstone_thread_attempts
                   WHERE phase = 'accepted' AND lease_token IS NULL
                     AND (%s::text IS NULL OR model_context_snapshot->>'implementation_family' = %s::text)
                   ORDER BY created_at, attempt_id LIMIT 1 FOR UPDATE SKIP LOCKED""",
                (implementation_family, implementation_family),
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
            conversation = _attempt_conversation_document(connection, attempt_row)
            if attempt_row["conversation_context_snapshot"] is None:
                connection.execute("UPDATE capstone_thread_attempts SET conversation_context_snapshot = %s WHERE attempt_id = %s", (Jsonb(conversation), attempt_row["attempt_id"]))
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
                prior_results=_prior_results_for_context(self._snapshot_from_row(thread)),
                previous_instruction=_previous_instruction_from_postgres(connection, thread["thread_id"], context),
                conversation_context=ConversationContext.from_document(conversation),
                submission=updated.get('submission_snapshot'),
                application_catalog=(
                    self._catalog_context
                    if self._catalog_context is not None
                    else (
                        _thread_catalog_document(
                            self._model_catalog, self._capability_catalog,
                        )
                        if self._model_catalog is not None else None
                    )
                ),
            )

    def freeze_attempt_input(self, claim: AttemptClaim, document: Mapping[str, Any]) -> dict[str, Any]:
        """Save input/config once; callers rebind the current retry Attempt identity."""
        _validate_bounded_json(document, name="attempt.intent_input", maximum=512 * 1024)
        with self._connect() as connection:
            row = connection.execute("""SELECT intent_input_snapshot FROM capstone_thread_attempts
                WHERE thread_id = %s AND attempt_id = %s AND lease_token = %s
                AND phase = 'running' AND lease_deadline > clock_timestamp() FOR UPDATE""",
                (claim.thread_id, claim.attempt.attempt_id, claim.lease_token)).fetchone()
            if row is None:
                raise ThreadExecutionError("attempt lease is unavailable")
            frozen = row["intent_input_snapshot"]
            if frozen is None:
                frozen = json.loads(_canonical(document))
                connection.execute("UPDATE capstone_thread_attempts SET intent_input_snapshot = %s WHERE attempt_id = %s", (Jsonb(frozen), claim.attempt.attempt_id))
            return json.loads(_canonical(frozen))

    def freeze_attempt_decision(self, claim: AttemptClaim, document: Mapping[str, Any] | None) -> dict[str, Any] | None:
        if document is not None:
            _validate_bounded_json(document, name='attempt.intent_decision', maximum=32_768)
        with self._connect() as connection:
            row = connection.execute("""SELECT intent_decision_snapshot FROM capstone_thread_attempts
                WHERE thread_id = %s AND attempt_id = %s AND lease_token = %s
                AND phase = 'running' AND lease_deadline > clock_timestamp() FOR UPDATE""",
                (claim.thread_id, claim.attempt.attempt_id, claim.lease_token)).fetchone()
            if row is None:
                raise ThreadExecutionError('attempt lease is unavailable')
            frozen = row['intent_decision_snapshot']
            if frozen is None and document is not None:
                frozen = json.loads(_canonical(document))
                connection.execute('UPDATE capstone_thread_attempts SET intent_decision_snapshot = %s WHERE attempt_id = %s',
                                   (Jsonb(frozen), claim.attempt.attempt_id))
            return None if frozen is None else json.loads(_canonical(frozen))

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
                     AND event_type IN ('selection_activated', 'model_context_activated', 'model_context_reopened')
                     AND selection_revision = %s AND model_context_id = %s
                     AND payload->>'activation_turn_id' = %s
                   ORDER BY event_seq DESC LIMIT 1""",
                (claim.thread_id, active.selection_revision, active.id, claim.attempt.turn_id),
            ).fetchone()
            if row is None or not isinstance(row["payload"], dict):
                return False
            previous_context_document = row["payload"].get("previous_context")
            if row["event_type"] in {"model_context_activated", "model_context_reopened"} and isinstance(previous_context_document, dict):
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
        _validate_runtime_payload(event_type, payload, claim)
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
            result_projections = _terminal_result_projections(
                payload, claim=claim, phase=phase,
            )
            existing_projections = tuple(
                ResultProjection.from_document(item)
                for item in (thread.get("result_projections") or [])
            )
            existing_result_ids = {item.result_id for item in existing_projections}
            if any(item.result_id in existing_result_ids for item in result_projections):
                raise ThreadProtocolError("result projection already exists")
            event_payload = dict(payload)
            if result_projections:
                event_payload["result_projections"] = [item.to_document() for item in result_projections]
            event = self._make_attempt_event(
                thread, terminal, event_seq=thread["last_event_seq"] + 1,
                event_type="attempt_" + phase,
                payload=event_payload, context=claim.model_context,
            )
            self._insert_event(connection, event)
            connection.execute(
                """UPDATE capstone_thread_attempts
                   SET phase = %s, lease_token = NULL, lease_deadline = NULL
                   WHERE attempt_id = %s""",
                (phase, claim.attempt.attempt_id),
            )
            updated = connection.execute(
                """UPDATE capstone_threads
                   SET current_attempt = NULL, result_projections = %s, last_event_seq = %s
                   WHERE thread_id = %s RETURNING *""",
                (Jsonb([item.to_document() for item in (existing_projections + result_projections)[-MAX_RESULT_PROJECTIONS:]]),
                 event.event_seq, claim.thread_id),
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
        self, snapshot: ThreadSnapshot, command: Mapping[str, Any], *, allow_same: bool = False,
    ) -> tuple[PendingModelSwitchSnapshot | None, str | None]:
        if snapshot.pending_model_switch is not None or snapshot.pending_selection is not None:
            return None, "context_change_pending"
        catalog = self._model_catalog
        if catalog is None:
            return None, "model_catalog_unavailable"
        try:
            descriptor = catalog.resolve(command["payload"]["model_id"])
        except (LookupError, TypeError, ValueError):
            return None, "model_unavailable"
        if not self.is_family_available(descriptor.implementation_family):
            return None, "worker_unavailable"
        if not descriptor.available:
            return None, descriptor.unavailable_reason or "model_unavailable"
        active = snapshot.active_model_context
        if not allow_same and (
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
            reason="explicit_reopen" if command["kind"] == "reopen_model_context" else "model_switch",
            fresh_context_reason=(
                command["payload"].get("reason")
                if command["kind"] == "reopen_model_context" else None
            ),
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
            event_type=(
                "model_context_reopened"
                if pending.reason == "explicit_reopen"
                else "model_context_activated"
            ),
            payload={
                "command_id": pending.command_id,
                "activation_turn_id": turn_id,
                "reason": pending.reason,
                **({"fresh_context_reason": pending.fresh_context_reason}
                   if pending.fresh_context_reason is not None else {}),
                "previous_context": previous.to_document(),
                "previous_grid_page_id": snapshot.active_grid_page_id,
                "active_grid_page_id": page_id_for_model(active.model_id),
                "model_context": active.to_document(),
            },
        )
        self._insert_event(connection, event)
        workspace = self._synchronize_model_workspace(connection, thread, snapshot)
        workspace = synchronize_workspace(workspace, replace(snapshot, active_model_context=active, last_event_seq=event.event_seq), self._model_catalog)
        connection.execute("UPDATE capstone_threads SET model_workspace = %s WHERE thread_id = %s", (Jsonb(workspace), snapshot.thread_id))
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
            occurred_at=_now(), visibility=visibility, payload={**payload, **({"runtime_mode": attempt.runtime_mode} if event_type == "command_accepted" else {})},
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
            result_projections=tuple(
                ResultProjection.from_document(item)
                for item in (row.get("result_projections") or [])
            ),
            application_state=row.get("application_state"),
            runtime_mode=row.get("runtime_mode", "capstone"),
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
