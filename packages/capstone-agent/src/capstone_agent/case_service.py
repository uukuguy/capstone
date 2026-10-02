"""Application-owned admission and first-step dispatch for Thread Cases."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from .case_definition import CaseCatalog, CaseDefinition
from .case_execution import (
    CaseExecution,
    PinnedCaseContext,
    SequentialBatchExecutor,
)
from .thread_application_transition import ApplicationEvent, ThreadApplicationTransition
from .thread_commands import ThreadCommandFactory
from .thread_protocol import CommandReceipt, ThreadProtocolError
from .thread_service import ThreadExecutionService, ThreadNotFound


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
        "case_execution": execution.to_document(),
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
        return CaseExecution.from_document(raw)
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
        return _execution_from_snapshot(self.thread_service.snapshot(thread_id))

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
                self._dispatch_step(command, current_snapshot, replay_execution, definition)
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
        self._dispatch_step(command, snapshot, execution, definition)
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
        return self._reject(command, "case_retry_unavailable")

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
        transition = ThreadApplicationTransition(
            command=command,
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
        transition_command = {
            **dict(command),
            "expected_event_seq": self.thread_service.snapshot(
                command["thread_id"],
            ).last_event_seq,
        }
        final = self.thread_service.apply_application_transition(
            ThreadApplicationTransition(
                command=transition_command,
                state=transition.state,
                events=transition.events,
            ),
        )
        return final

    def _resume(self, command: Mapping[str, Any], execution_id: str) -> CommandReceipt:
        snapshot, rejection = self._snapshot_or_rejection(command)
        if rejection is not None:
            return rejection
        execution = _execution_from_snapshot(snapshot)
        if execution is None or execution.case_execution_id != execution_id:
            return self._reject(command, "case_execution_not_found")
        return self._reject(command, "case_resume_unavailable")

    def _reject(self, command: Mapping[str, Any], rejection: str) -> CommandReceipt:
        return self.thread_service.record_rejected_command(
            command, rejection=rejection,
        )

    def _dispatch_step(
        self,
        command: Mapping[str, Any],
        snapshot: Any,
        execution: CaseExecution,
        definition: CaseDefinition,
    ) -> None:
        ordinal = execution.current_step
        if ordinal != 1:
            raise ThreadProtocolError("initial Case step is invalid")
        context = execution.context
        step = definition.steps[ordinal - 1]
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
            return
        target = step_receipt.target
        started = execution.with_current_step(
            ordinal,
            turn_id=target["turn_id"],
            attempt_id=target["attempt_id"],
        )
        started_command = {
            **dict(command),
            "command_id": f"{execution.case_execution_id}_started",
            "idempotency_key": f"{execution.case_execution_id}_started_idem",
            "expected_event_seq": step_receipt.accepted_event_seq,
        }
        self.thread_service.apply_application_transition(
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


__all__ = ["CaseExecutionService"]
