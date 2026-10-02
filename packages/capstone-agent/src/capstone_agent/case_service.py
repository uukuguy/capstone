"""Application-owned admission and first-step dispatch for Thread Cases."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import replace
from typing import Any, Literal, cast

from .case_definition import CaseCatalog, CaseDefinition
from .case_execution import (
    CaseExecution,
    PinnedCaseContext,
    SequentialBatchExecutor,
    StepOutcome,
)
from .thread_application_transition import ApplicationEvent, ThreadApplicationTransition
from .thread_commands import ThreadCommandFactory
from .thread_protocol import CommandReceipt, ThreadProtocolError
from .thread_service import (
    ThreadExecutionService,
    ThreadNotFound,
    ThreadResyncRequired,
)


_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_CASE_COMMANDS = frozenset({
    "start_case_execution",
    "retry_case_step",
    "cancel_case_execution",
    "resume_case_execution",
})
_ACTIVE_STATUSES = frozenset({"created", "running", "waiting_step"})


def _identifier(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ThreadProtocolError(f"{name} is invalid")
    return value


def _command(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ThreadProtocolError("command must be an object")
    allowed = {
        "schema", "command_id", "idempotency_key", "thread_id", "run_id",
        "kind", "expected_event_seq", "payload",
    }
    unknown = set(value) - allowed
    if unknown:
        raise ThreadProtocolError("command has unknown field: " + ", ".join(sorted(unknown)))
    required = allowed - {"run_id"}
    missing = required - set(value)
    if missing:
        raise ThreadProtocolError("command is missing field: " + ", ".join(sorted(missing)))
    if value.get("schema") != "capstone-command/1":
        raise ThreadProtocolError("command.schema is invalid")
    expected = value.get("expected_event_seq")
    if type(expected) is not int or expected < 0:
        raise ThreadProtocolError("command.expected_event_seq is invalid")
    payload = value.get("payload")
    if not isinstance(payload, Mapping):
        raise ThreadProtocolError("command.payload is invalid")
    try:
        json.dumps(dict(value), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        raise ThreadProtocolError("command is not JSON") from None
    return {
        "schema": "capstone-command/1",
        "command_id": _identifier(value["command_id"], name="command.command_id"),
        "idempotency_key": _identifier(
            value["idempotency_key"], name="command.idempotency_key",
        ),
        "thread_id": _identifier(value["thread_id"], name="command.thread_id"),
        "run_id": (
            None
            if value.get("run_id") is None
            else _identifier(value["run_id"], name="command.run_id")
        ),
        "kind": _identifier(value["kind"], name="command.kind"),
        "expected_event_seq": expected,
        "payload": dict(payload),
    }


def _payload(command: Mapping[str, Any], fields: set[str]) -> dict[str, Any]:
    payload = command["payload"]
    if set(payload) != fields:
        raise ThreadProtocolError(
            "case command payload fields are invalid: "
            + ", ".join(sorted(set(payload) ^ fields)),
        )
    return dict(payload)


def _text(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ThreadProtocolError(f"{name} is invalid")
    return value


def _execution_id(command: Mapping[str, Any]) -> str:
    raw = (
        f"{command['thread_id']}:{command['run_id']}:{command['command_id']}"
    ).encode("utf-8")
    return "case_exec_" + hashlib.sha256(raw).hexdigest()[:24]


def _step_identity(execution_id: str, ordinal: int) -> tuple[str, str]:
    suffix = hashlib.sha256(f"{execution_id}:{ordinal}".encode()).hexdigest()[:24]
    return f"case_step_{suffix}", f"case_step_idem_{suffix}"


def _state(execution: CaseExecution) -> dict[str, Any]:
    return {
        "case_execution": {
            **execution.to_document(),
            # These presentation hints are application-owned and ignored by
            # the durable Case state parser. They let every client render the
            # same trusted titles without deriving labels from IDs.
            "display_name": execution.case_id,
            "step_titles": [f"步骤 {step.ordinal}" for step in execution.steps],
        },
        "context_locked": execution.status in _ACTIVE_STATUSES,
    }


def _execution_from_snapshot(snapshot: Any) -> CaseExecution | None:
    state = snapshot.application_state
    if not isinstance(state, Mapping):
        return None
    raw = state.get("case_execution")
    if raw is None:
        return None
    try:
        return CaseExecution.from_document({key: value for key, value in raw.items()
                                            if key not in {"display_name", "step_titles"}})
    except (TypeError, ValueError):
        return None


class CaseExecutionService:
    """Admit registered Cases while keeping their state above the Thread store."""

    def __init__(self, catalog: CaseCatalog, thread_service: ThreadExecutionService) -> None:
        if not isinstance(catalog, CaseCatalog):
            raise TypeError("catalog must be a CaseCatalog")
        if not callable(getattr(thread_service, "submit_command", None)):
            raise TypeError("thread_service is invalid")
        if not callable(getattr(thread_service, "apply_application_transition", None)):
            raise TypeError("thread_service transition support is required")
        if not callable(getattr(thread_service, "record_rejected_command", None)):
            raise TypeError("thread_service rejection ledger support is required")
        self._case_catalog = catalog
        self.thread_service = thread_service

    def catalog(self, thread_id: str) -> dict[str, object]:
        document = dict(self.thread_service.catalog(thread_id))
        definitions = getattr(self._case_catalog, "_definitions", {})
        cases = []
        for definition in sorted(definitions.values(), key=lambda item: (item.case_id, item.case_version)):
            cases.append({
                "case_id": definition.case_id,
                "case_version": definition.case_version,
                "title": definition.display_name,
                "summary": definition.description,
                "model_ids": list(definition.model_ids),
                "step_count": len(definition.steps),
            })
        document["cases"] = cases
        return document

    def reconcile(self, thread_id: str) -> CaseExecution | None:
        """Consume committed Attempt terminal events and advance one Case step.

        Reconciliation is deliberately conservative.  It only dispatches a new
        Turn after the preceding terminal Attempt and its application event are
        both durably visible.  Any uncertainty is persisted as a blocked Case so
        a restart cannot silently skip a step or duplicate an Attempt.
        """
        snapshot = self.thread_service.snapshot(thread_id)
        execution = _execution_from_snapshot(snapshot)
        if execution is None:
            return None
        if execution.thread_id != thread_id:
            return execution
        if execution.status in {"completed", "cancelled"}:
            return execution

        try:
            definition = self._case_catalog.get(execution.case_id)
        except LookupError:
            return self._block(snapshot, execution, "case_definition_unavailable")
        if definition.case_revision != execution.case_revision:
            return self._block(snapshot, execution, "case_revision_mismatch")
        context = execution.context
        active = snapshot.active_model_context
        if (
            context.model_context_id != active.id
            or context.model_id != active.model_id
            or context.model_revision != active.model_revision
            or context.selection_revision != active.selection_revision
        ):
            return self._block(snapshot, execution, "case_context_mismatch")

        try:
            events = self._event_window(snapshot)
        except (ThreadResyncRequired, ThreadProtocolError, ValueError, KeyError):
            return self._block(snapshot, execution, "case_event_window_uncertain")

        # A retry command may have committed a new Attempt before the process
        # crashed while persisting the application state.  Recover from the
        # immutable command event even if the replacement Attempt has already
        # reached a terminal state and cleared current_attempt.
        if execution.status == "blocked":
            recovered = self._recover_retry(snapshot, execution, events)
            if recovered is not None:
                execution = recovered
                snapshot = self.thread_service.snapshot(thread_id)

        ordinal = execution.current_step
        if ordinal is None:
            return execution
        step = execution.steps[ordinal - 1]

        if step.status == "pending":
            if snapshot.current_attempt is not None:
                recovered = self._recover_dispatched_step(
                    snapshot, execution, definition, events,
                )
                if recovered is not None:
                    return recovered
                return self._block(snapshot, execution, "case_untracked_attempt")
            self._dispatch_step(snapshot, execution, definition)
            return _execution_from_snapshot(self.thread_service.snapshot(thread_id)) or execution

        if step.status != "running":
            return execution
        if snapshot.current_attempt is not None:
            current = snapshot.current_attempt
            if current.attempt_id != step.latest_attempt_id:
                return self._block(snapshot, execution, "case_attempt_identity_mismatch")
            if current.phase not in {"accepted", "running"}:
                return self._block(snapshot, execution, "case_attempt_terminal_uncertain")
            return execution

        terminal = next(
            (
                event for event in reversed(events)
                if event.attempt_id == step.latest_attempt_id
                and event.event_type in {
                    "attempt_completed", "attempt_failed", "attempt_cancelled", "attempt_interrupted",
                }
            ),
            None,
        )
        if terminal is None:
            return self._block(snapshot, execution, "case_terminal_attempt_missing")
        if (
            terminal.model_context_id != context.model_context_id
            or terminal.selection_revision != context.selection_revision
        ):
            return self._block(snapshot, execution, "case_terminal_context_mismatch")
        try:
            outcome = self._outcome_from_terminal(terminal)
            decision = SequentialBatchExecutor(definition).advance(execution, outcome)
        except (TypeError, ValueError, KeyError):
            return self._block(snapshot, execution, "case_terminal_result_uncertain")

        state = _state(decision.execution)
        state["case_step_instruction_digests"] = [
            {"ordinal": item.ordinal, "instruction_digest": item.instruction_digest}
            for item in definition.steps
        ]
        event_type = "case_step_completed" if outcome.status == "completed" else "case_execution_blocked"
        payload = {
            "case_execution_id": execution.case_execution_id,
            "case_id": execution.case_id,
            "case_revision": execution.case_revision,
            "step_ordinal": ordinal,
            "turn_id": step.turn_id,
            "attempt_id": outcome.attempt_id,
            "status": outcome.status,
            "error_code": outcome.error_code,
            "result_refs": list(outcome.result_refs),
            "evidence_refs": list(outcome.evidence_refs),
        }
        if decision.execution.status == "completed":
            event_type = "case_execution_completed"
        transition = self._transition(
            snapshot, decision.execution, event_type, payload,
            suffix=f"terminal_{ordinal}_{outcome.attempt_id}",
            state=state,
        )
        if transition.status != "accepted":
            return _execution_from_snapshot(self.thread_service.snapshot(thread_id)) or execution
        committed = _execution_from_snapshot(self.thread_service.snapshot(thread_id)) or decision.execution
        if decision.next_step is not None and committed.status == "waiting_step":
            self._dispatch_step(self.thread_service.snapshot(thread_id), committed, definition)
            committed = _execution_from_snapshot(self.thread_service.snapshot(thread_id)) or committed
        return committed

    def reconcile_active(self, limit: int = 32) -> int:
        """Reconcile each active Case Thread through the public store port."""
        if type(limit) is not int or not 1 <= limit <= 256:
            raise ValueError("reconcile limit is invalid")
        enumerate_threads = getattr(self.thread_service, "active_application_threads", None)
        if not callable(enumerate_threads):
            return 0
        count = 0
        for active_thread_id in cast(tuple[str, ...], enumerate_threads(limit)):
            try:
                if self.reconcile(active_thread_id) is not None:
                    count += 1
            except ThreadNotFound:
                continue
        return count

    def _event_window(self, snapshot: Any) -> tuple[Any, ...]:
        cursor = snapshot.base_event_seq
        events: list[Any] = []
        while cursor < snapshot.last_event_seq:
            previous_cursor = cursor
            page = self.thread_service.read_events(snapshot.thread_id, cursor)
            page_events = tuple(page.events)
            if not page_events:
                raise ValueError("event page is empty before snapshot tail")
            expected = cursor + 1
            for event in page_events:
                if event.event_seq != expected:
                    raise ValueError("event sequence is not contiguous")
                expected += 1
            events.extend(page_events)
            cursor = page.next_event_seq
            if cursor != expected - 1 or cursor <= previous_cursor:
                raise ValueError("event page cursor did not advance")
            if not page.has_more and cursor < snapshot.last_event_seq:
                raise ValueError("event page ended before snapshot tail")
        if cursor != snapshot.last_event_seq:
            raise ValueError("event window does not reach snapshot tail")
        return tuple(events)

    @staticmethod
    def _outcome_from_terminal(event: Any) -> StepOutcome:
        payload = event.payload if isinstance(event.payload, Mapping) else {}
        status = {
            "attempt_completed": "completed",
            "attempt_failed": "failed",
            "attempt_cancelled": "cancelled",
            "attempt_interrupted": "interrupted",
        }[event.event_type]
        answer = payload.get("answer")
        raw_results = payload.get("result_refs", ())
        raw_evidence = payload.get("evidence_refs", ())
        if not isinstance(raw_results, (list, tuple)) or not isinstance(raw_evidence, (list, tuple)):
            raise ValueError("terminal references are invalid")
        duration = payload.get("duration_ms")
        error = payload.get("error_code", payload.get("reason"))
        return StepOutcome(
            status=cast(Literal["completed", "failed", "cancelled", "interrupted"], status),
            attempt_id=event.attempt_id or "",
            answer=answer if isinstance(answer, str) else None,
            result_refs=tuple(raw_results),
            evidence_refs=tuple(raw_evidence),
            duration_ms=duration if duration is None or type(duration) is int else None,
            error_code=error if isinstance(error, str) else None,
        )

    def _transition(
        self,
        snapshot: Any,
        execution: CaseExecution,
        event_type: str,
        payload: Mapping[str, Any],
        *,
        suffix: str,
        state: Mapping[str, Any] | None = None,
    ) -> CommandReceipt:
        token = hashlib.sha256(
            f"{execution.case_execution_id}:{suffix}".encode("utf-8"),
        ).hexdigest()[:24]
        command = {
            "schema": "capstone-command/1",
            "command_id": f"case_{token}",
            "idempotency_key": f"case_idem_{token}",
            "thread_id": snapshot.thread_id,
            "run_id": snapshot.run.run_id,
            "kind": "case_reconcile",
            "expected_event_seq": snapshot.last_event_seq,
            "payload": {"case_execution_id": execution.case_execution_id, "event_type": event_type},
        }
        return self.thread_service.apply_application_transition(
            ThreadApplicationTransition(
                command=command,
                state=dict(state if state is not None else _state(execution)),
                events=(ApplicationEvent(event_type, dict(payload)),),
            ),
        )

    def _block(self, snapshot: Any, execution: CaseExecution, error_code: str) -> CaseExecution:
        if execution.status in {"blocked", "completed", "cancelled"}:
            return execution
        steps = list(execution.steps)
        if execution.current_step is not None:
            current = steps[execution.current_step - 1]
            if current.status == "running":
                steps[execution.current_step - 1] = replace(
                    current, status="interrupted", answer=None,
                    result_refs=(), evidence_refs=(), error_code=error_code,
                )
        blocked = replace(execution, steps=tuple(steps), status="blocked")
        self._transition(
            snapshot, blocked, "case_execution_blocked",
            {
                "case_execution_id": execution.case_execution_id,
                "step_ordinal": execution.current_step,
                "attempt_id": execution.steps[execution.current_step - 1].latest_attempt_id
                if execution.current_step is not None else None,
                "error_code": error_code,
            },
            suffix=f"blocked_{error_code}",
        )
        return _execution_from_snapshot(self.thread_service.snapshot(snapshot.thread_id)) or blocked

    def _recover_retry(
        self, snapshot: Any, execution: CaseExecution, events: tuple[Any, ...],
    ) -> CaseExecution | None:
        if execution.current_step is None:
            return None
        ordinal = execution.current_step
        step = execution.steps[ordinal - 1]
        if step.status not in {"failed", "cancelled", "interrupted"}:
            return None
        retry_event = next(
            (
                event for event in reversed(events)
                if event.event_type == "command_accepted"
                and event.attempt_id is not None
                and event.turn_id is not None
                and isinstance(event.payload, Mapping)
                and event.payload.get("kind") == "retry_new_attempt"
                and isinstance(event.payload.get("payload"), Mapping)
                and event.payload["payload"].get("retry_of") == step.latest_attempt_id
            ),
            None,
        )
        if retry_event is None:
            return None
        retry_payload = retry_event.payload["payload"]
        retry_attempt_id = retry_event.attempt_id
        retry_turn_id = retry_event.turn_id
        if (
            retry_attempt_id is None
            or retry_turn_id is None
            or retry_attempt_id == step.latest_attempt_id
            or retry_turn_id != step.turn_id
            or retry_payload.get("turn_id") != retry_turn_id
            or retry_payload.get("retry_of") != step.latest_attempt_id
            or retry_event.model_context_id != execution.context.model_context_id
            or retry_event.selection_revision != execution.context.selection_revision
        ):
            return None

        current = snapshot.current_attempt
        terminal = None
        if current is None:
            terminal = next(
                (
                    event for event in reversed(events)
                    if event.attempt_id == retry_attempt_id
                    and event.turn_id == retry_turn_id
                    and event.event_type in {
                        "attempt_completed", "attempt_failed", "attempt_cancelled", "attempt_interrupted",
                    }
                ),
                None,
            )
            if terminal is None:
                return None
            if (
                terminal.model_context_id != execution.context.model_context_id
                or terminal.selection_revision != execution.context.selection_revision
            ):
                return None
            try:
                terminal_outcome = self._outcome_from_terminal(terminal)
            except (TypeError, ValueError, KeyError):
                return None
            if terminal_outcome.attempt_id != retry_attempt_id:
                return None
        else:
            if (
                current.attempt_id != retry_attempt_id
                or current.turn_id != retry_turn_id
                or current.target_model_context_id != execution.context.model_context_id
                or current.phase not in {"accepted", "running"}
            ):
                return None

        resumed = replace(
            execution,
            status="waiting_step",
            steps=tuple(
                replace(item, status="running", turn_id=retry_turn_id,
                        latest_attempt_id=retry_attempt_id, answer=None,
                        result_refs=(), evidence_refs=(), duration_ms=None,
                        error_code=None)
                if item.ordinal == ordinal else item
                for item in execution.steps
            ),
        )
        self._transition(
            snapshot, resumed, "case_retry_created",
            {
                "case_execution_id": execution.case_execution_id,
                "step_ordinal": ordinal,
                "turn_id": retry_turn_id,
                "attempt_id": retry_attempt_id,
                "retry_of": step.latest_attempt_id,
            },
            suffix=f"retry_{ordinal}_{retry_attempt_id}",
        )
        return _execution_from_snapshot(self.thread_service.snapshot(snapshot.thread_id)) or resumed

    def _recover_dispatched_step(
        self,
        snapshot: Any,
        execution: CaseExecution,
        definition: CaseDefinition,
        events: tuple[Any, ...],
    ) -> CaseExecution | None:
        ordinal = execution.current_step
        current = snapshot.current_attempt
        if ordinal is None or current is None or current.phase not in {"accepted", "running"}:
            return None
        step = definition.steps[ordinal - 1]
        command_event = next(
            (
                event for event in reversed(events)
                if event.event_type == "command_accepted"
                and event.attempt_id == current.attempt_id
                and isinstance(event.payload, Mapping)
                and event.payload.get("kind") == "send_auto"
                and isinstance(event.payload.get("payload"), Mapping)
            ),
            None,
        )
        if command_event is None:
            return None
        payload = command_event.payload["payload"]
        if (
            payload.get("case_execution_id") != execution.case_execution_id
            or payload.get("step_ordinal") != ordinal
            or payload.get("step_instruction_digest") != step.instruction_digest
            or payload.get("case_context") != execution.context.to_document()
            or payload.get("text") != step.instruction
        ):
            return None
        started = execution.with_current_step(
            ordinal, turn_id=current.turn_id, attempt_id=current.attempt_id,
        )
        self._transition(
            snapshot, started, "case_execution_started",
            {
                "case_execution_id": execution.case_execution_id,
                "step_ordinal": ordinal,
                "turn_id": current.turn_id,
                "attempt_id": current.attempt_id,
                "model_context": execution.context.to_document(),
            },
            suffix=f"started_{ordinal}_{current.attempt_id}",
            state={
                **_state(started),
                "case_step_instruction_digests": [
                    {"ordinal": item.ordinal, "instruction_digest": item.instruction_digest}
                    for item in definition.steps
                ],
            },
        )
        return _execution_from_snapshot(self.thread_service.snapshot(snapshot.thread_id)) or started

    def submit_command(self, command: Mapping[str, Any]) -> CommandReceipt:
        parsed = _command(command)
        kind = parsed["kind"]
        if kind not in _CASE_COMMANDS:
            return self.thread_service.submit_command(command)
        if kind == "start_case_execution":
            payload = _payload(parsed, {"case_id", "case_version", "strategy_id"})
            _identifier(payload["case_id"], name="case_id")
            case_version = _text(payload["case_version"], name="case_version")
            strategy_id = _identifier(payload["strategy_id"], name="strategy_id")
            return self._start(parsed, payload["case_id"], case_version, strategy_id)
        if kind == "retry_case_step":
            payload = _payload(parsed, {
                "case_execution_id", "step_ordinal", "failed_attempt_id",
            })
            if type(payload["step_ordinal"]) is not int or payload["step_ordinal"] < 1:
                raise ThreadProtocolError("step_ordinal is invalid")
            return self._retry(
                parsed,
                _identifier(payload["case_execution_id"], name="case_execution_id"),
                payload["step_ordinal"],
                _identifier(payload["failed_attempt_id"], name="failed_attempt_id"),
            )
        if kind == "cancel_case_execution":
            payload = _payload(parsed, {"case_execution_id"})
            return self._cancel(
                parsed,
                _identifier(payload["case_execution_id"], name="case_execution_id"),
            )
        payload = _payload(parsed, {"case_execution_id"})
        return self._resume(
            parsed,
            _identifier(payload["case_execution_id"], name="case_execution_id"),
        )

    def _snapshot_or_rejection(
        self, command: Mapping[str, Any],
    ) -> tuple[Any, CommandReceipt | None]:
        try:
            snapshot = self.thread_service.snapshot(command["thread_id"])
        except ThreadNotFound:
            raise
        if command["run_id"] is not None and command["run_id"] != snapshot.run.run_id:
            return snapshot, self._reject(command, "run_mismatch")
        if command["expected_event_seq"] != snapshot.last_event_seq:
            return snapshot, self._reject(command, "stale_event_seq")
        if snapshot.run.state != "open":
            return snapshot, self._reject(command, "run_not_open")
        return snapshot, None

    def _start(
        self,
        command: Mapping[str, Any],
        case_id: str,
        case_version: str,
        strategy_id: str,
    ) -> CommandReceipt:
        current_snapshot = self.thread_service.snapshot(command["thread_id"])
        current_execution = _execution_from_snapshot(current_snapshot)
        if (
            current_execution is not None
            and current_execution.case_execution_id == _execution_id(command)
        ):
            try:
                definition = self._case_catalog.get(case_id, case_version)
            except LookupError:
                return self._reject(command, "case_not_found")
            if strategy_id != "sequential_batch":
                return self._reject(command, "strategy_not_supported")
            replay_execution = SequentialBatchExecutor(definition).create_execution(
                definition,
                current_execution.context,
                case_execution_id=current_execution.case_execution_id,
                thread_id=current_execution.thread_id,
                run_id=current_execution.run_id,
            )
            receipt = self.thread_service.apply_application_transition(
                self._created_transition(command, replay_execution, definition),
            )
            if (
                receipt.status == "accepted"
                and current_execution.status == "created"
                and current_execution.current_step == 1
            ):
                self._dispatch_step(current_snapshot, replay_execution, definition)
            return receipt
        snapshot, rejection = self._snapshot_or_rejection(command)
        if rejection is not None:
            return rejection
        try:
            definition = self._case_catalog.get(case_id, case_version)
        except LookupError:
            return self._reject(command, "case_not_found")
        if strategy_id != "sequential_batch":
            return self._reject(command, "strategy_not_supported")
        if snapshot.active_model_context.model_id not in definition.model_ids:
            return self._reject(command, "case_model_mismatch")
        if snapshot.current_attempt is not None:
            return self._reject(command, "thread_busy")
        existing = _execution_from_snapshot(snapshot)
        if existing is not None and existing.status in _ACTIVE_STATUSES:
            return self._reject(command, "case_execution_active")

        context = PinnedCaseContext(
            model_context_id=snapshot.active_model_context.id,
            model_id=snapshot.active_model_context.model_id,
            model_revision=snapshot.active_model_context.model_revision,
            selection_revision=snapshot.active_model_context.selection_revision,
        )
        execution = SequentialBatchExecutor(definition).create_execution(
            definition,
            context,
            case_execution_id=_execution_id(command),
            thread_id=snapshot.thread_id,
            run_id=snapshot.run.run_id,
        )
        transition = self._created_transition(command, execution, definition)
        receipt = self.thread_service.apply_application_transition(transition)
        if receipt.status != "accepted":
            return receipt
        self._dispatch_step(snapshot, execution, definition)
        return receipt

    def _created_transition(
        self,
        command: Mapping[str, Any],
        execution: CaseExecution,
        definition: CaseDefinition,
    ) -> ThreadApplicationTransition:
        context = execution.context
        return ThreadApplicationTransition(
            command=command,
            state={
                **_state(execution),
                "case_step_instruction_digests": [
                    {
                        "ordinal": step.ordinal,
                        "instruction_digest": step.instruction_digest,
                    }
                    for step in definition.steps
                ],
            },
            events=(
                ApplicationEvent(
                    "case_execution_created",
                    {
                        "case_execution_id": execution.case_execution_id,
                        "case_id": execution.case_id,
                        "case_revision": execution.case_revision,
                        "strategy_id": execution.strategy_id,
                        "strategy_version": execution.strategy_version,
                        "model_context_id": context.model_context_id,
                        "model_revision": context.model_revision,
                        "selection_revision": context.selection_revision,
                    },
                ),
            ),
        )

    def _retry(
        self,
        command: Mapping[str, Any],
        execution_id: str,
        ordinal: int,
        failed_attempt_id: str,
    ) -> CommandReceipt:
        snapshot, rejection = self._snapshot_or_rejection(command)
        if rejection is not None:
            return rejection
        execution = _execution_from_snapshot(snapshot)
        if (
            execution is None
            or execution.case_execution_id != execution_id
            or execution.status != "blocked"
            or execution.current_step != ordinal
        ):
            return self._reject(command, "case_retry_target_mismatch")
        step = execution.steps[ordinal - 1]
        if step.latest_attempt_id != failed_attempt_id or step.status not in {
            "failed", "cancelled", "interrupted",
        }:
            return self._reject(command, "case_retry_target_mismatch")
        retry_token = hashlib.sha256(
            f"{execution.case_execution_id}:{ordinal}:{failed_attempt_id}".encode("utf-8"),
        ).hexdigest()[:24]
        retry_command = ThreadCommandFactory(
            snapshot.thread_id, snapshot.run.run_id,
        ).retry_new_attempt(
            expected_event_seq=snapshot.last_event_seq,
            command_id=f"case_retry_{retry_token}",
            idempotency_key=f"case_retry_idem_{retry_token}",
            attempt_id=failed_attempt_id,
        )
        retry_receipt = self.thread_service.submit_command(retry_command)
        if retry_receipt.status != "accepted" or retry_receipt.target is None:
            return self._reject(command, retry_receipt.rejection or "case_retry_rejected")
        target = retry_receipt.target
        resumed = replace(
            execution,
            status="waiting_step",
            steps=tuple(
                replace(item, status="running", turn_id=target["turn_id"],
                        latest_attempt_id=target["attempt_id"], answer=None,
                        result_refs=(), evidence_refs=(), duration_ms=None,
                        error_code=None)
                if item.ordinal == ordinal else item
                for item in execution.steps
            ),
        )
        after_retry = self.thread_service.snapshot(snapshot.thread_id)
        transition = self._transition(
            after_retry, resumed, "case_retry_created",
            {
                "case_execution_id": execution.case_execution_id,
                "step_ordinal": ordinal,
                "turn_id": target["turn_id"],
                "attempt_id": target["attempt_id"],
                "retry_of": failed_attempt_id,
            },
            suffix=f"retry_{ordinal}_{target['attempt_id']}",
        )
        accepted_event_seq = transition.accepted_event_seq or retry_receipt.accepted_event_seq
        outer = CommandReceipt(
            command_id=command["command_id"], idempotency_key=command["idempotency_key"],
            thread_id=command["thread_id"], run_id=snapshot.run.run_id,
            status="accepted", accepted_event_seq=accepted_event_seq,
            rejection=None, target=target,
        )
        return self.thread_service.record_command_receipt(command, outer)

    def _cancel(self, command: Mapping[str, Any], execution_id: str) -> CommandReceipt:
        snapshot, rejection = self._snapshot_or_rejection(command)
        if rejection is not None:
            return rejection
        execution = _execution_from_snapshot(snapshot)
        if execution is None or execution.case_execution_id != execution_id:
            return self._reject(command, "case_execution_not_found")
        if execution.status not in _ACTIVE_STATUSES:
            return self._reject(command, "case_execution_not_active")
        if snapshot.current_attempt is None:
            return self._reject(command, "case_attempt_not_found")
        cancel_command = ThreadCommandFactory(
            snapshot.thread_id, snapshot.run.run_id,
        ).cancel_live_attempt(
            snapshot.current_attempt.attempt_id,
            expected_event_seq=snapshot.last_event_seq,
            command_id=f"{execution.case_execution_id}_cancel_attempt",
            idempotency_key=f"{execution.case_execution_id}_cancel_attempt_idem",
        )
        receipt = self.thread_service.submit_command(cancel_command)
        if receipt.status != "accepted":
            return self._reject(command, "case_cancel_rejected")
        current_step = execution.current_step
        step = execution.steps[current_step - 1] if current_step is not None else None
        if step is not None:
            steps = list(execution.steps)
            assert current_step is not None
            steps[current_step - 1] = replace(step, status="cancelled")
            execution = replace(
                execution,
                status="cancelled",
                current_step=None,
                steps=tuple(steps),
            )
        transition_command = {
            **dict(command),
            "command_id": f"{execution.case_execution_id}_cancel_transition",
            "idempotency_key": f"{execution.case_execution_id}_cancel_transition_idem",
            "expected_event_seq": self.thread_service.snapshot(
                command["thread_id"],
            ).last_event_seq,
        }
        transition = ThreadApplicationTransition(
            command=transition_command,
            state=_state(execution),
            events=(
                ApplicationEvent(
                    "case_execution_cancelled",
                    {
                        "case_execution_id": execution.case_execution_id,
                        "step_ordinal": step.ordinal if step is not None else None,
                        "attempt_id": step.latest_attempt_id if step is not None else None,
                    },
                ),
            ),
        )
        final = self.thread_service.apply_application_transition(
            transition,
        )
        if final.status != "accepted":
            return final
        outer_receipt = CommandReceipt(
            command_id=command["command_id"],
            idempotency_key=command["idempotency_key"],
            thread_id=command["thread_id"],
            run_id=snapshot.run.run_id,
            status="accepted",
            accepted_event_seq=final.accepted_event_seq,
            rejection=None,
            target=receipt.target,
        )
        return self.thread_service.record_command_receipt(command, outer_receipt)

    def _resume(self, command: Mapping[str, Any], execution_id: str) -> CommandReceipt:
        snapshot, rejection = self._snapshot_or_rejection(command)
        if rejection is not None:
            return rejection
        execution = _execution_from_snapshot(snapshot)
        if execution is None or execution.case_execution_id != execution_id:
            return self._reject(command, "case_execution_not_found")
        if execution.status != "waiting_step" or execution.current_step is None:
            return self._reject(command, "case_resume_unavailable")
        current = execution.steps[execution.current_step - 1]
        if (
            current.status != "pending"
            or snapshot.current_attempt is not None
            or any(step.status != "completed" for step in execution.steps[: execution.current_step - 1])
        ):
            return self._reject(command, "case_resume_unavailable")
        try:
            definition = self._case_catalog.get(execution.case_id)
        except LookupError:
            return self._reject(command, "case_definition_unavailable")
        self._dispatch_step(snapshot, execution, definition)
        current_snapshot = self.thread_service.snapshot(command["thread_id"])
        if current_snapshot.current_attempt is None:
            return self._reject(command, "case_resume_rejected")
        receipt = CommandReceipt(
            command_id=command["command_id"], idempotency_key=command["idempotency_key"],
            thread_id=command["thread_id"], run_id=snapshot.run.run_id,
            status="accepted", accepted_event_seq=current_snapshot.last_event_seq,
            rejection=None,
            target={
                "turn_id": current_snapshot.current_attempt.turn_id,
                "attempt_id": current_snapshot.current_attempt.attempt_id,
            },
        )
        return self.thread_service.record_command_receipt(command, receipt)

    def _reject(self, command: Mapping[str, Any], rejection: str) -> CommandReceipt:
        return self.thread_service.record_rejected_command(
            command, rejection=rejection,
        )

    def _dispatch_step(
        self,
        snapshot: Any,
        execution: CaseExecution,
        definition: CaseDefinition,
    ) -> bool:
        ordinal = execution.current_step
        if ordinal is None or not 1 <= ordinal <= len(definition.steps):
            raise ThreadProtocolError("Case step is invalid")
        if snapshot.current_attempt is not None:
            return False
        context = execution.context
        step = definition.steps[ordinal - 1]
        if step.ordinal != ordinal or execution.steps[ordinal - 1].status == "running":
            return False
        step_command_id, step_idempotency_key = _step_identity(
            execution.case_execution_id, ordinal,
        )
        current = self.thread_service.snapshot(snapshot.thread_id)
        step_command = ThreadCommandFactory(
            snapshot.thread_id, snapshot.run.run_id,
        ).send_auto(
            step.instruction,
            expected_event_seq=current.last_event_seq,
            command_id=step_command_id,
            idempotency_key=step_idempotency_key,
        )
        step_command["payload"].update({
            "case_execution_id": execution.case_execution_id,
            "step_ordinal": ordinal,
            "case_context": context.to_document(),
            "step_instruction_digest": step.instruction_digest,
        })
        step_receipt = self.thread_service.submit_command(step_command)
        if step_receipt.status != "accepted" or step_receipt.target is None:
            return False
        target = step_receipt.target
        started = execution.with_current_step(
            ordinal,
            turn_id=target["turn_id"],
            attempt_id=target["attempt_id"],
        )
        started_token = hashlib.sha256(
            f"{execution.case_execution_id}:started:{ordinal}:{target['attempt_id']}".encode("utf-8"),
        ).hexdigest()[:24]
        started_command = {
            "schema": "capstone-command/1",
            "command_id": f"case_started_{started_token}",
            "idempotency_key": f"case_started_idem_{started_token}",
            "thread_id": snapshot.thread_id,
            "run_id": snapshot.run.run_id,
            "kind": "case_step_started",
            "expected_event_seq": step_receipt.accepted_event_seq,
            "payload": {"case_execution_id": execution.case_execution_id, "step_ordinal": ordinal},
        }
        started_receipt = self.thread_service.apply_application_transition(
            ThreadApplicationTransition(
                command=started_command,
                state={
                    **_state(started),
                    "case_step_instruction_digests": [
                        {
                            "ordinal": item.ordinal,
                            "instruction_digest": definition.steps[item.ordinal - 1].instruction_digest,
                        }
                        for item in started.steps
                    ],
                },
                events=(
                    ApplicationEvent(
                        "case_execution_started",
                        {
                            "case_execution_id": execution.case_execution_id,
                            "step_ordinal": ordinal,
                            "turn_id": target["turn_id"],
                            "attempt_id": target["attempt_id"],
                            "model_context": context.to_document(),
                        },
                    ),
                ),
            ),
        )
        return started_receipt.status == "accepted"


__all__ = ["CaseExecutionService"]
