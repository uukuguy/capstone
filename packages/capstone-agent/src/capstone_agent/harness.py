"""Capstone-aware boundary over replaceable agent runtime clients.

The public Thread protocol never receives native Pi or DSH frames directly.
This module keeps the runtime seam small: a selected runtime emits bounded,
typed events and returns one answer; Harness/Thread persistence can attach
identities and event sequence numbers around that seam.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from .thread_service import AttemptClaim, ThreadExecutionService


RuntimeEventSink = Callable[[dict[str, object]], None]


class HarnessRuntimeUnavailable(RuntimeError):
    """The requested replaceable runtime is not installed or enabled."""


@dataclass(frozen=True, slots=True)
class HarnessAttemptResult:
    status: str
    answer: str | None
    error_code: str | None


class PiPromptSession(Protocol):
    def start(self) -> None: ...

    def prompt_and_wait(
        self,
        question: str,
        *,
        on_semantic_event: Callable[[Mapping[str, object]], None],
        correlation_id: str | None,
        on_heartbeat: Callable[[], None],
    ) -> str: ...

    def stop(self) -> None: ...


class HarnessRuntime(Protocol):
    def start(self) -> None: ...

    def prompt(
        self, question: str, *, on_event: RuntimeEventSink,
        correlation_id: str | None = None,
        on_heartbeat: Callable[[], None] | None = None,
    ) -> str: ...

    def stop(self) -> None: ...


_EVENT_TYPES = {
    "text_delta": ("assistant_text_delta", "public"),
    "message_update": ("assistant_message_update", "public"),
    "message_end": ("assistant_message_end", "public"),
    "tool_execution_start": ("tool_started", "public"),
    "tool_execution_end": ("tool_completed", "public"),
    "tool_result": ("tool_completed", "public"),
    "agent_end": ("runtime_completed", "public"),
    "application_turn_completed": ("runtime_completed", "public"),
    "auto_retry_start": ("runtime_retry_started", "diagnostic"),
    "auto_retry_end": ("runtime_retry_completed", "diagnostic"),
    "prompt_ack": ("runtime_prompt_ack", "diagnostic"),
    "response": ("runtime_response", "diagnostic"),
}


def normalize_runtime_event(
    event: Mapping[str, object], *, runtime_mode: str,
) -> dict[str, object]:
    """Map one native runtime event to a bounded Harness event document."""

    native_type = event.get("type")
    if not isinstance(native_type, str) or not native_type:
        native_type = "unknown"
    event_type, visibility = _EVENT_TYPES.get(native_type, ("runtime_event", "diagnostic"))
    payload: dict[str, object]
    if event_type == "assistant_text_delta":
        text = event.get("text")
        payload = {"text": text[:16_384]} if isinstance(text, str) else {}
    elif event_type in {"tool_started", "tool_completed"}:
        payload = _tool_payload(event)
    elif event_type == "runtime_event":
        payload = {"native_type": native_type}
    else:
        payload = _small_runtime_payload(event)
    return {
        "event_type": event_type,
        "runtime_mode": runtime_mode,
        "visibility": visibility,
        "payload": payload,
    }


def _tool_payload(event: Mapping[str, object]) -> dict[str, object]:
    payload: dict[str, object] = {}
    for source, target in (
        ("toolCallId", "tool_call_id"), ("tool_call_id", "tool_call_id"),
        ("toolName", "tool_name"), ("tool_name", "tool_name"),
    ):
        value = event.get(source)
        if isinstance(value, str) and value and target not in payload:
            payload[target] = value[:256]
    details = _tool_details(event)
    ok = event.get("ok", details.get("ok"))
    if isinstance(ok, bool):
        payload["ok"] = ok
    for source, target in (
        ("capability", "capability"),
        ("projector_id", "projector_id"),
        ("result_kind", "result_kind"),
    ):
        value = event.get(source, details.get(source))
        if isinstance(value, str) and value:
            payload[target] = value[:512]
    capability_key = event.get("capability_key", details.get("capability_key"))
    if isinstance(capability_key, Mapping):
        for source, target in (
            ("binding_id", "binding_id"), ("bindingId", "binding_id"),
            ("capability_id", "capability_id"), ("capabilityId", "capability_id"),
        ):
            value = capability_key.get(source)
            if isinstance(value, str) and value and target not in payload:
                payload[target] = value[:256]
    refs = event.get("evidence_refs", details.get("evidence_refs"))
    if isinstance(refs, (list, tuple)):
        bounded = [ref[:512] for ref in refs if isinstance(ref, str) and ref][:128]
        if bounded:
            payload["evidence_refs"] = bounded
    return payload


def _tool_details(event: Mapping[str, object]) -> Mapping[str, object]:
    result = event.get("result")
    if isinstance(result, Mapping):
        details = result.get("details")
        if isinstance(details, Mapping):
            return details
    details = event.get("details")
    return details if isinstance(details, Mapping) else {}


def _small_runtime_payload(event: Mapping[str, object]) -> dict[str, object]:
    allowed = {
        "command": str, "success": bool, "ok": bool, "attempt": int,
        "maxAttempts": int, "delayMs": int, "stop_status": str,
    }
    return {
        key: value
        for key, expected in allowed.items()
        if isinstance((value := event.get(key)), expected)
    }


class HarnessPiClient:
    """Adapt an injected Pi-compatible session to the Harness event seam."""

    runtime_name = "pi"

    def __init__(self, session: PiPromptSession, *, runtime_mode: str = "capstone") -> None:
        if runtime_mode not in {"capstone", "pi_reference"}:
            raise ValueError("Pi runtime mode is invalid")
        self._session = session
        self.runtime_mode = runtime_mode

    def start(self) -> None:
        self._session.start()

    def prompt(
        self, question: str, *, on_event: RuntimeEventSink,
        correlation_id: str | None = None,
        on_heartbeat: Callable[[], None] | None = None,
    ) -> str:
        def emit(native: Mapping[str, object]) -> None:
            on_event(normalize_runtime_event(native, runtime_mode=self.runtime_mode))

        return self._session.prompt_and_wait(
            question,
            on_semantic_event=emit,
            correlation_id=correlation_id,
            on_heartbeat=on_heartbeat or (lambda: None),
        )

    def stop(self) -> None:
        self._session.stop()


class HarnessDSHClient:
    """Reserved DSH adapter; no DSH runtime is enabled in this milestone."""

    runtime_name = "dsh"
    runtime_mode = "dsh_reference"

    def start(self) -> None:
        raise HarnessRuntimeUnavailable("DSH Harness runtime is not installed")

    def prompt(
        self, question: str, *, on_event: RuntimeEventSink,
        correlation_id: str | None = None,
        on_heartbeat: Callable[[], None] | None = None,
    ) -> str:
        del question, on_event, correlation_id, on_heartbeat
        raise HarnessRuntimeUnavailable("DSH Harness runtime is not installed")

    def stop(self) -> None:
        return None


class HarnessAttemptRunner:
    """Run one claimed Attempt and commit only a terminal, bounded outcome."""

    def __init__(
        self, service: ThreadExecutionService, runtime: HarnessRuntime,
        *, lease_seconds: int = 30,
    ) -> None:
        if lease_seconds < 1:
            raise ValueError("attempt worker lease is invalid")
        self._service = service
        self._runtime = runtime
        self._lease_seconds = lease_seconds

    def run(self, claim: AttemptClaim) -> HarnessAttemptResult:
        try:
            self._runtime.start()
            answer = self._runtime.prompt(
                claim.instruction,
                correlation_id=claim.attempt.attempt_id,
                on_event=lambda event: self._persist_event(claim, event),
                on_heartbeat=lambda: self._renew_lease(claim),
            )
            if not isinstance(answer, str):
                raise TypeError("runtime answer is invalid")
            bounded_answer = answer[:64_000]
            self._service.finish_attempt(
                claim, phase="completed", payload={"answer": bounded_answer},
            )
            return HarnessAttemptResult("completed", bounded_answer, None)
        except Exception:
            self._finish_failed(claim)
            return HarnessAttemptResult("failed", None, "runtime_failed")
        finally:
            try:
                self._runtime.stop()
            except Exception:
                pass

    def _persist_event(self, claim: AttemptClaim, event: Mapping[str, object]) -> None:
        event_type = event.get("event_type")
        runtime_mode = event.get("runtime_mode")
        visibility = event.get("visibility", "diagnostic")
        payload = event.get("payload")
        if not isinstance(event_type, str) or not isinstance(runtime_mode, str):
            raise ValueError("runtime event is invalid")
        if not isinstance(payload, Mapping):
            raise ValueError("runtime event payload is invalid")
        self._service.append_runtime_event(
            claim,
            event_type=event_type,
            payload={"runtime_mode": runtime_mode, **dict(payload)},
            visibility=visibility if isinstance(visibility, str) else "diagnostic",
        )

    def _renew_lease(self, claim: AttemptClaim) -> None:
        if not self._service.renew_attempt(claim, self._lease_seconds):
            raise RuntimeError("attempt lease is unavailable")

    def _finish_failed(self, claim: AttemptClaim) -> None:
        try:
            self._service.finish_attempt(
                claim, phase="failed", payload={"error_code": "runtime_failed"},
            )
        except Exception as exc:
            # The durable service remains the source of truth. If its terminal
            # write failed, do not claim that the Attempt was safely finished.
            raise RuntimeError("attempt terminal persistence failed") from exc


__all__ = [
    "HarnessAttemptResult", "HarnessAttemptRunner", "HarnessDSHClient", "HarnessPiClient", "HarnessRuntimeUnavailable",
    "PiPromptSession", "normalize_runtime_event",
    "HarnessRuntime",
]
