"""Capstone-aware boundary over replaceable agent runtime clients.

The public Thread protocol never receives native Pi or DSH frames directly.
This module keeps the runtime seam small: a selected runtime emits bounded,
typed events and returns one answer; Harness/Thread persistence can attach
identities and event sequence numbers around that seam.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Protocol


RuntimeEventSink = Callable[[dict[str, object]], None]


class HarnessRuntimeUnavailable(RuntimeError):
    """The requested replaceable runtime is not installed or enabled."""


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


_EVENT_TYPES = {
    "text_delta": ("assistant_text_delta", "public"),
    "message_update": ("assistant_message_update", "public"),
    "message_end": ("assistant_message_end", "public"),
    "tool_execution_start": ("tool_started", "public"),
    "tool_execution_end": ("tool_completed", "public"),
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
    ok = event.get("ok")
    if isinstance(ok, bool):
        payload["ok"] = ok
    return payload


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
    ) -> str:
        def emit(native: Mapping[str, object]) -> None:
            on_event(normalize_runtime_event(native, runtime_mode=self.runtime_mode))

        return self._session.prompt_and_wait(
            question,
            on_semantic_event=emit,
            correlation_id=correlation_id,
            on_heartbeat=lambda: None,
        )

    def stop(self) -> None:
        self._session.stop()


class HarnessDSHClient:
    """Reserved DSH adapter; no DSH runtime is enabled in this milestone."""

    runtime_name = "dsh"
    runtime_mode = "dsh_reference"

    def start(self) -> None:
        raise HarnessRuntimeUnavailable("DSH Harness runtime is not installed")

    def prompt(self, question: str, *, on_event: RuntimeEventSink, correlation_id: str | None = None) -> str:
        del question, on_event, correlation_id
        raise HarnessRuntimeUnavailable("DSH Harness runtime is not installed")

    def stop(self) -> None:
        return None


__all__ = [
    "HarnessDSHClient", "HarnessPiClient", "HarnessRuntimeUnavailable",
    "PiPromptSession", "normalize_runtime_event",
]
