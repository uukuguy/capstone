"""Line-framed Pi RPC transport with bounded stderr and semantic tracing."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Lock, Thread
from typing import Any, Protocol

from capability_agent.runtime.environment import PiLaunch
from capability_agent.runtime.lock import PiCommand
from capability_agent.runtime.trace import JsonlTraceWriter


SemanticEventCallback = Callable[[dict[str, Any], int], None]
TRACEABLE_RPC_TYPES = frozenset(
    {
        "prompt_ack",
        "response",
        "tool_execution_start",
        "tool_execution_end",
        "agent_end",
        "agent_settled",
        "auto_retry_start",
        "auto_retry_end",
    }
)
CAPTURE_FATAL_EXIT_CODE = 86
CAPTURE_FATAL_MARKER = "trajectory model request commit failed"
_CAPTURE_POLL_SECONDS = 0.025
_STDERR_CAPTURE_LIMIT = 64 * 1024
_SAFE_TOOL_CALL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
_DIAGNOSTIC_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_-]?key|token|password|secret|credential|authorization)\s*[:=]\s*([^\s,;]+)"
)
_DIAGNOSTIC_BEARER = re.compile(r"(?i)\b(bearer\s+)([^\s,;]+)")


class RpcWorkspace(Protocol):
    @property
    def root_path(self) -> Path: ...


class CaptureAdapter(Protocol):
    def drain_model_requests(self) -> None: ...

    def on_raw_event(self, event: dict[str, Any]) -> None: ...

    def on_semantic_event(self, event: dict[str, Any], sequence: int) -> None: ...


class PiProtocolError(RuntimeError):
    pass


class PiCaptureIntegrityError(PiProtocolError):
    """Raised when an optional request-capture boundary fails closed."""


class PiRpcClient:
    def __init__(
        self,
        command: PiCommand | PiLaunch,
        workspace: RpcWorkspace,
        trace: JsonlTraceWriter,
        *,
        environment: dict[str, str] | None = None,
        secret_values: Iterable[str] | None = None,
        capture_error_type: type[RuntimeError] = PiCaptureIntegrityError,
        timeout_seconds: float | None = None,
        correlation_id: str | None = None,
    ) -> None:
        self.command = command
        self.workspace = workspace
        self.trace = trace
        self.environment = environment
        self.secret_values = frozenset(
            value for value in (secret_values or ()) if isinstance(value, str) and value
        )
        self.capture_error_type = capture_error_type
        if timeout_seconds is not None and timeout_seconds <= 0:
            raise ValueError("RPC timeout must be positive")
        if correlation_id is not None and (
            not isinstance(correlation_id, str) or not correlation_id
        ):
            raise ValueError("RPC correlation ID must be non-empty text")
        self.timeout_seconds = timeout_seconds
        self.correlation_id = correlation_id
        self.process: subprocess.Popen[bytes] | None = None
        self._stdout_lines: Queue[bytes | None] | None = None
        self._stderr_capture: _BoundedStderrCapture | None = None

    def start(self) -> None:
        launch_environment = (
            self.command.environment
            if isinstance(self.command, PiLaunch)
            else self.environment
        )
        try:
            self.process = subprocess.Popen(
                list(self.command.argv),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.workspace.root_path,
                env=launch_environment,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise PiProtocolError("Pi RPC process could not be started") from exc
        self._stdout_lines = Queue()
        if self.process.stdout is not None:
            Thread(
                target=_read_lines,
                args=(self.process.stdout, self._stdout_lines),
                daemon=True,
            ).start()
        self._stderr_capture = _BoundedStderrCapture()
        if self.process.stderr is not None:
            Thread(
                target=_drain_stderr,
                args=(self.process.stderr, self._stderr_capture),
                daemon=True,
            ).start()

    def prompt_and_wait(
        self,
        question: str,
        *,
        on_event: Callable[[dict[str, Any]], None] | None = None,
        on_semantic_event: SemanticEventCallback | None = None,
        on_heartbeat: Callable[[], None] | None = None,
        heartbeat_seconds: float = 10.0,
        require_answer_text: bool = True,
        capture: CaptureAdapter | None = None,
        timeout_seconds: float | None = None,
        correlation_id: str | None = None,
    ) -> str:
        if self.process is None or self.process.stdin is None:
            raise PiProtocolError("Pi RPC process is not started")
        if heartbeat_seconds <= 0:
            raise ValueError("RPC heartbeat interval must be positive")
        timeout = self.timeout_seconds if timeout_seconds is None else timeout_seconds
        if timeout is not None and timeout <= 0:
            raise ValueError("RPC timeout must be positive")
        expected_correlation = (
            correlation_id
            if correlation_id is not None
            else self.correlation_id
        )
        prompt_payload: dict[str, object] = {
            "type": "prompt",
            "message": question,
        }
        if correlation_id is not None or self.correlation_id is not None:
            prompt_payload["request_id"] = expected_correlation
        try:
            self.process.stdin.write(
                (
                    json.dumps(
                        prompt_payload,
                        separators=(",", ":"),
                    )
                    + "\n"
                ).encode()
            )
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise PiProtocolError("Pi RPC prompt could not be sent") from exc
        if self._stdout_lines is None:
            raise PiProtocolError("Pi RPC stdout reader is not started")
        if capture is not None:
            capture.drain_model_requests()
        lines = self._stdout_lines
        text: list[str] = []
        acknowledged = False
        pending_tool_calls: dict[str, dict[str, str]] = {}
        next_heartbeat_at = time.monotonic() + heartbeat_seconds
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            wait_timeout = heartbeat_seconds
            if deadline is not None:
                wait_timeout = min(wait_timeout, max(0.0, deadline - time.monotonic()))
                if wait_timeout <= 0:
                    if capture is not None:
                        capture.drain_model_requests()
                    raise PiProtocolError("Pi RPC timed out")
            if capture is not None:
                wait_timeout = min(
                    _CAPTURE_POLL_SECONDS,
                    max(0.0, next_heartbeat_at - time.monotonic()),
                )
            try:
                raw = lines.get(timeout=wait_timeout)
            except Empty:
                if capture is not None:
                    capture.drain_model_requests()
                now = time.monotonic()
                if now >= next_heartbeat_at:
                    if on_heartbeat is not None:
                        on_heartbeat()
                    next_heartbeat_at = now + heartbeat_seconds
                continue
            if raw is None:
                raise self._eof_error()
            try:
                line = raw.decode("utf-8").rstrip("\r\n")
            except UnicodeDecodeError as exc:
                raise PiProtocolError("Pi RPC returned invalid UTF-8") from exc
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise PiProtocolError("Pi RPC returned invalid JSONL") from exc
            if not isinstance(event, dict):
                raise PiProtocolError("Pi RPC event must be an object")
            event_correlation = _event_correlation(event)
            if (
                expected_correlation is not None
                and event_correlation is not None
                and event_correlation != expected_correlation
            ):
                raise PiProtocolError("Pi RPC correlation mismatch")
            if capture is not None:
                capture.drain_model_requests()
                capture.on_raw_event(event)
            if on_event is not None:
                on_event(event)
            if event.get("type") == "text_delta":
                text.append(str(event.get("text", "")))
            if event.get("type") == "message_update":
                assistant_event = event.get("assistantMessageEvent")
                if isinstance(assistant_event, dict) and assistant_event.get("type") == "text_delta":
                    text.append(str(assistant_event.get("delta", "")))
            for payload in _semantic_trace_payloads(event, "".join(text), pending_tool_calls):
                trace_correlation = event_correlation or expected_correlation
                if trace_correlation is not None:
                    payload = {**payload, "correlation_id": trace_correlation}
                sequence = self.trace.append("pi_event", payload)
                if capture is not None:
                    capture.on_semantic_event(payload, sequence)
                if on_semantic_event is not None:
                    on_semantic_event(payload, sequence)
            if event.get("type") == "prompt_ack" and event.get("ok") is True:
                acknowledged = True
            if event.get("type") == "response" and event.get("command") == "prompt":
                if event.get("success") is True:
                    acknowledged = True
                else:
                    if capture is not None:
                        capture.drain_model_requests()
                    detail = event.get("error") or event.get("message") or "unknown error"
                    raise PiProtocolError(
                        f"Pi prompt failed: {_sanitize_diagnostic(detail, self.secret_values)}"
                    )
            if event.get("type") == "agent_end":
                if not acknowledged:
                    if capture is not None:
                        capture.drain_model_requests()
                    raise PiProtocolError("Pi agent ended before prompt acknowledgement")
                provider_error = _provider_error(event)
                if provider_error:
                    if event.get("willRetry") is True:
                        text.clear()
                        continue
                    if capture is not None:
                        capture.drain_model_requests()
                    raise PiProtocolError(
                        "Pi provider failure: "
                        + _sanitize_diagnostic(provider_error, self.secret_values)
                    )
                answer = "".join(text)
                if not answer.strip():
                    if not require_answer_text:
                        if capture is not None:
                            capture.drain_model_requests()
                        return ""
                    if capture is not None:
                        capture.drain_model_requests()
                    raise PiProtocolError("Pi agent ended without answer text")
                if capture is not None:
                    capture.drain_model_requests()
                return answer

    def _eof_error(self) -> RuntimeError:
        process = self.process
        if process is None:
            return PiProtocolError("Pi RPC ended before agent completion")
        returncode = process.poll()
        if returncode is None:
            try:
                returncode = process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                returncode = process.poll()
        stderr = self._stderr_capture
        if stderr is not None:
            stderr.wait(timeout=0.5 if returncode is not None else 0.0)
            stderr_text = stderr.text()
        else:
            stderr_text = ""
        marker_line = next(
            (
                _sanitize_diagnostic(line, self.secret_values)
                for line in stderr_text.splitlines()
                if CAPTURE_FATAL_MARKER in line.lower()
            ),
            None,
        )
        if returncode == CAPTURE_FATAL_EXIT_CODE or marker_line is not None:
            detail = marker_line or next(
                (
                    _sanitize_diagnostic(line, self.secret_values)
                    for line in stderr_text.splitlines()
                    if line.strip()
                ),
                CAPTURE_FATAL_MARKER,
            )
            return self.capture_error_type(
                f"capture-fatal exit {returncode}: {detail}"
            )
        if returncode is not None:
            return PiProtocolError(
                f"Pi RPC ended before agent completion (exit {returncode})"
            )
        return PiProtocolError("Pi RPC ended before agent completion")

    def stop(self) -> None:
        if self.process is None:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        self.process = None
        self._stdout_lines = None
        self._stderr_capture = None


class _BoundedStderrCapture:
    def __init__(self, limit: int = _STDERR_CAPTURE_LIMIT) -> None:
        self._limit = limit
        self._buffer = bytearray()
        self._lock = Lock()
        self._done = Event()

    def append(self, chunk: bytes) -> None:
        with self._lock:
            self._buffer.extend(chunk)
            if len(self._buffer) > self._limit:
                del self._buffer[: len(self._buffer) - self._limit]

    def finish(self) -> None:
        self._done.set()

    def wait(self, timeout: float) -> None:
        self._done.wait(timeout)

    def text(self) -> str:
        with self._lock:
            return bytes(self._buffer).decode("utf-8", errors="replace")


def _read_lines(stream: Any, lines: Queue[bytes | None]) -> None:
    try:
        for raw in stream:
            lines.put(raw)
    finally:
        lines.put(None)


def _drain_stderr(stream: Any, capture: _BoundedStderrCapture) -> None:
    try:
        while True:
            chunk = stream.read(8192)
            if not chunk:
                return
            capture.append(chunk)
    finally:
        capture.finish()


def _provider_error(event: dict[str, Any]) -> str | None:
    messages = event.get("messages")
    if not isinstance(messages, list):
        return None
    for message in reversed(messages):
        if isinstance(message, dict) and message.get("stopReason") == "error":
            error = message.get("errorMessage")
            if isinstance(error, str) and error:
                return error
    return None


def _sanitize_diagnostic(value: object, secret_values: Iterable[str] = ()) -> str:
    if isinstance(value, str):
        text = value
    elif isinstance(value, (int, float, bool)):
        text = str(value)
    else:
        text = "provider reported an invalid diagnostic"
    for secret in sorted(
        (item for item in secret_values if item), key=len, reverse=True
    ):
        text = text.replace(secret, "[REDACTED]")
    text = _DIAGNOSTIC_SECRET_ASSIGNMENT.sub(r"\1=[REDACTED]", text)
    text = _DIAGNOSTIC_BEARER.sub(r"\1[REDACTED]", text)
    text = text.strip()[:500]
    return text or "provider reported an error"


def _semantic_trace_payloads(
    event: dict[str, Any],
    assembled_public_text: str,
    pending_tool_calls: dict[str, dict[str, str]],
) -> tuple[dict[str, Any], ...]:
    canonical_tool_result = _canonical_tool_result_event(event, pending_tool_calls)
    if canonical_tool_result is not None:
        return (canonical_tool_result,)
    if event.get("type") not in TRACEABLE_RPC_TYPES:
        return ()
    event_type = event.get("type")
    if event_type in {"prompt_ack", "response"}:
        return (
            {key: event[key] for key in ("type", "command", "success", "ok") if key in event},
        )
    if event_type in {"agent_settled", "auto_retry_start", "auto_retry_end"}:
        return (
            {
                key: event[key]
                for key in (
                    "type",
                    "attempt",
                    "maxAttempts",
                    "delayMs",
                    "success",
                    "finalError",
                    "errorMessage",
                )
                if key in event
            },
        )
    if event_type == "tool_execution_start":
        start = _canonical_tool_start_event(event)
        pending = {
            key: value
            for key, value in {
                "tool_call_id": start.get("tool_call_id"),
                "tool_name": start.get("tool_name"),
            }.items()
            if isinstance(value, str)
        }
        if isinstance(pending.get("tool_call_id"), str):
            pending_tool_calls[pending["tool_call_id"]] = pending
        return (start,)
    if event_type == "agent_end":
        payloads: list[dict[str, Any]] = [
            {"type": "agent_end", "stop_status": _stop_status(event, assembled_public_text)}
        ]
        if assembled_public_text.strip():
            payloads.append({"type": "assistant_message", "text": assembled_public_text})
        return tuple(payloads)
    return ()


def _stop_status(event: dict[str, Any], text: str) -> str:
    if _provider_error(event):
        return "error"
    if text.strip():
        return "answered"
    return "no_answer"


def _canonical_tool_start_event(event: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {"type": "tool_execution_start"}
    tool_call_id = _event_tool_call_id(event)
    tool_name = _event_tool_name(event)
    if tool_call_id is not None:
        payload["tool_call_id"] = tool_call_id
    if tool_name is not None:
        payload["tool_name"] = tool_name
        payload["toolName"] = tool_name
    args = event.get("args")
    if isinstance(args, dict):
        payload["args"] = args
    return payload


def _canonical_tool_result_event(
    event: dict[str, Any], pending_tool_calls: dict[str, dict[str, str]] | None = None
) -> dict[str, Any] | None:
    if event.get("type") not in {"tool_execution_end", "tool_result"}:
        return None
    details = _tool_result_details(event)
    if not isinstance(details, dict):
        return None
    capability = details.get("capability")
    if not isinstance(capability, str):
        return None
    ok = details.get("ok")
    if ok is not True and ok is not False:
        ok = event.get("isError") is not True
    result = details.get("result", {})
    error = details.get("error")
    evidence_refs = details.get("evidence_refs", [])
    if not isinstance(result, dict):
        result = {}
    if error is not None and not isinstance(error, dict):
        error = {"message": str(error)}
    if not isinstance(evidence_refs, list):
        evidence_refs = []
    canonical: dict[str, Any] = {
        "type": "tool_result",
        "event": "tool_result",
        "capability": capability,
        "ok": ok,
        "result": result,
        "evidence_refs": [ref for ref in evidence_refs if isinstance(ref, str)],
    }
    for field in ("capability_key", "projector_id", "result_kind"):
        if field in details:
            canonical[field] = details[field]
    pair = _consume_tool_pair(event, pending_tool_calls)
    if isinstance(pair.get("tool_call_id"), str):
        canonical["tool_call_id"] = pair["tool_call_id"]
    if isinstance(pair.get("tool_name"), str):
        canonical["tool_name"] = pair["tool_name"]
        canonical["toolName"] = pair["tool_name"]
    if error is not None:
        canonical["error"] = error
    return canonical


def _tool_result_details(event: dict[str, Any]) -> object:
    if event.get("type") == "tool_result":
        return event
    result = event.get("result")
    if isinstance(result, dict):
        details = result.get("details")
        return details if isinstance(details, dict) else result
    details = event.get("details")
    return details if isinstance(details, dict) else None


def _consume_tool_pair(
    event: dict[str, Any], pending_tool_calls: dict[str, dict[str, str]] | None
) -> dict[str, str]:
    event_pair = {
        key: value
        for key, value in {
            "tool_call_id": _event_tool_call_id(event),
            "tool_name": _event_tool_name(event),
        }.items()
        if isinstance(value, str)
    }
    if pending_tool_calls is None:
        return event_pair
    call_id = event_pair.get("tool_call_id")
    pending = pending_tool_calls.pop(call_id, {}) if call_id is not None else {}
    return {**pending, **event_pair}


def _event_tool_call_id(event: dict[str, Any]) -> str | None:
    raw = _string_value(event, "toolCallId") or _string_value(event, "tool_call_id")
    if raw is None or _SAFE_TOOL_CALL_ID.fullmatch(raw):
        return raw
    return "pi-call-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _event_tool_name(event: dict[str, Any]) -> str | None:
    return _string_value(event, "toolName") or _string_value(event, "tool_name")


def _string_value(event: dict[str, Any], key: str) -> str | None:
    value = event.get(key)
    return value if isinstance(value, str) and value else None


def _event_correlation(event: Mapping[str, Any]) -> str | None:
    for key in ("request_id", "requestId", "correlation_id", "correlationId"):
        value = event.get(key)
        if value is not None:
            if isinstance(value, str) and value:
                return value
            raise PiProtocolError("Pi RPC correlation ID must be text")
    return None


__all__ = [
    "CaptureAdapter",
    "PiCaptureIntegrityError",
    "PiProtocolError",
    "PiRpcClient",
    "RpcWorkspace",
    "SemanticEventCallback",
]
