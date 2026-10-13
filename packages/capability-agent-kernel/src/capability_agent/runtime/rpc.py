"""Line-framed Pi RPC transport with bounded stderr and semantic tracing."""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import time
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from dataclasses import dataclass, field
from queue import Empty, Queue
from threading import Event, Lock, Thread
from typing import Any, Protocol

from capability_agent.runtime.environment import PiLaunch
from capability_agent.runtime.lock import PiCommand
from capability_agent.runtime.trace import JsonlTraceWriter
from capability_agent.runtime.process_stream import ProcessStream


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
_CONTROL_POLL_SECONDS = 0.025
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


class _ReceivedLine(bytes):
    received_at: float

    def __new__(cls, raw: bytes):
        value = super().__new__(cls, raw)
        value.received_at = time.perf_counter()
        return value


@dataclass
class _PromptTiming:
    started: float = field(default_factory=time.perf_counter)
    queue_wait_seconds: float = 0.0
    max_queue_delay_seconds: float = 0.0
    trace_seconds: float = 0.0
    observer_seconds: float = 0.0
    control_seconds: float = 0.0
    raw_events: int = 0
    semantic_events: int = 0
    first_received: float | None = None
    last_received: float | None = None

    def receive(self, raw: bytes) -> None:
        self.raw_events += 1
        received = getattr(raw, "received_at", None)
        if isinstance(received, float):
            if self.first_received is None:
                self.first_received = received
            self.last_received = received
            self.max_queue_delay_seconds = max(self.max_queue_delay_seconds, time.perf_counter() - received)

    def document(self, status: str) -> dict[str, object]:
        return {"status": status, "elapsed_seconds": round(time.perf_counter() - self.started, 6),
            "raw_events": self.raw_events, "semantic_events": self.semantic_events,
            **{key: round(getattr(self, key), 6) for key in ("queue_wait_seconds", "max_queue_delay_seconds",
                "trace_seconds", "observer_seconds", "control_seconds")},
            "first_native_event_seconds": None if self.first_received is None else round(self.first_received - self.started, 6),
            "native_receive_span_seconds": None if self.first_received is None or self.last_received is None else round(self.last_received - self.first_received, 6)}


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
        process_delta_batch_seconds: float = 0,
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
        if (type(process_delta_batch_seconds) not in {int, float} or not math.isfinite(process_delta_batch_seconds)
            or not 0 <= process_delta_batch_seconds <= 1):
            raise ValueError("process delta interval must be between zero and one second")
        self.process_delta_batch_seconds = process_delta_batch_seconds
        self.process: subprocess.Popen[bytes] | None = None
        self._stdout_lines: Queue[bytes | None] | None = None
        self._stderr_capture: _BoundedStderrCapture | None = None
        self.last_prompt_interrupted = False

    def _send_control(self, command: str, **payload: object) -> None:
        if self.process is None or self.process.stdin is None:
            raise PiProtocolError("Pi RPC process is not started")
        try:
            self.process.stdin.write((json.dumps({"type": command, **payload}) + "\n").encode())
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise PiProtocolError("Pi RPC control could not be sent") from exc
        self.trace.append("rpc_control", {"command": command, **payload})

    def set_thinking_level(self, level: str) -> None:
        if level not in {"off", "minimal", "low", "medium", "high", "xhigh"}:
            raise ValueError("unsupported reasoning level")
        self._send_control("set_thinking_level", level=level)

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
        self, question: str, *,
        on_event: Callable[[dict[str, Any]], None] | None = None,
        on_semantic_event: SemanticEventCallback | None = None,
        on_heartbeat: Callable[[], None] | None = None,
        on_control_requests: Callable[[], None] | None = None,
        heartbeat_seconds: float = 10.0, require_answer_text: bool = True,
        capture: CaptureAdapter | None = None, timeout_seconds: float | None = None,
        correlation_id: str | None = None, model_idle_seconds: float | None = None,
    ) -> str:
        timing = _PromptTiming()
        status = "failed"
        def publish(payload: dict[str, Any]) -> None:
            trace_started = time.perf_counter()
            sequence = self.trace.append("pi_event", payload)
            timing.trace_seconds += time.perf_counter() - trace_started
            timing.semantic_events += 1
            if capture is not None:
                capture.on_semantic_event(payload, sequence)
            if on_semantic_event is not None:
                observer_started = time.perf_counter()
                try:
                    on_semantic_event(payload, sequence)
                finally:
                    timing.observer_seconds += time.perf_counter() - observer_started
        stream = ProcessStream(publish, self.process_delta_batch_seconds)
        try:
            answer = self._prompt_and_wait(question, timing=timing, stream=stream, on_event=on_event,
                on_semantic_event=on_semantic_event, on_heartbeat=on_heartbeat,
                on_control_requests=on_control_requests, heartbeat_seconds=heartbeat_seconds,
                require_answer_text=require_answer_text, capture=capture, timeout_seconds=timeout_seconds,
                correlation_id=correlation_id, model_idle_seconds=model_idle_seconds)
            status = "interrupted" if self.last_prompt_interrupted else "returned"
            return answer
        finally:
            stream.flush()
            document = timing.document(status)
            identity = correlation_id if correlation_id is not None else self.correlation_id
            if identity is not None:
                document["correlation_id"] = identity
            self.trace.append("rpc_prompt_timing", document)

    def _prompt_and_wait(
        self,
        question: str,
        *,
        timing: _PromptTiming,
        stream: ProcessStream,
        on_event: Callable[[dict[str, Any]], None] | None = None,
        on_semantic_event: SemanticEventCallback | None = None,
        on_heartbeat: Callable[[], None] | None = None,
        on_control_requests: Callable[[], None] | None = None,
        heartbeat_seconds: float = 10.0,
        require_answer_text: bool = True,
        capture: CaptureAdapter | None = None,
        timeout_seconds: float | None = None,
        correlation_id: str | None = None,
        model_idle_seconds: float | None = None,
    ) -> str:
        if self.process is None or self.process.stdin is None:
            raise PiProtocolError("Pi RPC process is not started")
        if heartbeat_seconds <= 0:
            raise ValueError("RPC heartbeat interval must be positive")
        if model_idle_seconds is not None and (type(model_idle_seconds) not in {int, float}
            or not math.isfinite(model_idle_seconds) or model_idle_seconds <= 0):
            raise ValueError("model step budget must be positive")
        self.last_prompt_interrupted = False
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
        answer_state = _AssistantAnswerState()
        acknowledged = False
        pending_tool_calls: dict[str, dict[str, str]] = {}
        running_tools: set[str] = set()
        last_model_action = time.monotonic()
        next_heartbeat_at = time.monotonic() + heartbeat_seconds
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            stream.flush_due()
            wait_timeout = heartbeat_seconds
            stream_remaining = stream.remaining()
            if stream_remaining is not None:
                wait_timeout = min(wait_timeout, max(.001, stream_remaining))
            if model_idle_seconds is not None and acknowledged and not running_tools and not self.last_prompt_interrupted:
                idle_remaining = model_idle_seconds - (time.monotonic() - last_model_action)
                if idle_remaining <= 0:
                    self._send_control("abort")
                    self.last_prompt_interrupted = True
                    self.trace.append("model_step_interrupted", {"reason": "model_step_budget", "budget_seconds": model_idle_seconds})
                else:
                    wait_timeout = min(wait_timeout, idle_remaining)
            if deadline is not None:
                wait_timeout = min(wait_timeout, max(0.0, deadline - time.monotonic()))
                if wait_timeout <= 0:
                    if capture is not None:
                        capture.drain_model_requests()
                    raise PiProtocolError("Pi RPC timed out")
            if on_control_requests is not None:
                # Run while tools await host commits, even without trajectory capture.
                control_started = time.perf_counter()
                on_control_requests()
                timing.control_seconds += time.perf_counter() - control_started
                wait_timeout = min(wait_timeout, _CONTROL_POLL_SECONDS)
            if capture is not None:
                wait_timeout = min(
                    _CAPTURE_POLL_SECONDS,
                    max(0.0, next_heartbeat_at - time.monotonic()),
                )
            wait_started = time.perf_counter()
            try:
                raw = lines.get(timeout=wait_timeout)
            except Empty:
                timing.queue_wait_seconds += time.perf_counter() - wait_started
                if capture is not None:
                    capture.drain_model_requests()
                now = time.monotonic()
                if now >= next_heartbeat_at:
                    if on_heartbeat is not None:
                        on_heartbeat()
                    next_heartbeat_at = now + heartbeat_seconds
                continue
            timing.queue_wait_seconds += time.perf_counter() - wait_started
            if raw is None:
                raise self._eof_error()
            timing.receive(raw)
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
            if event.get("type") == "tool_execution_start":
                running_tools.add(_event_tool_call_id(event) or "unidentified")
                last_model_action = time.monotonic()
            elif event.get("type") in {"tool_execution_end", "tool_result"}:
                running_tools.discard(_event_tool_call_id(event) or "unidentified")
                last_model_action = time.monotonic()
            elif event.get("type") == "text_delta" and isinstance(event.get("text"), str) and event["text"]:
                last_model_action = time.monotonic()
            elif event.get("type") == "message_update":
                delta = event.get("assistantMessageEvent")
                if isinstance(delta, dict) and delta.get("type") == "text_delta" and delta.get("delta"):
                    last_model_action = time.monotonic()
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
            answer_state.observe(event)
            for payload in _semantic_trace_payloads(event, answer_state.answer(), pending_tool_calls):
                trace_correlation = event_correlation or expected_correlation
                if trace_correlation is not None:
                    payload = {**payload, "correlation_id": trace_correlation}
                received = getattr(raw, "received_at", None)
                stream.emit(payload, ordinal=timing.raw_events,
                    received=None if not isinstance(received, float) else round(received - timing.started, 6))
            if event.get("type") == "prompt_ack" and event.get("ok") is True:
                acknowledged = True
                last_model_action = time.monotonic()
            if event.get("type") == "response" and event.get("command") == "prompt":
                if event.get("success") is True:
                    acknowledged = True
                    last_model_action = time.monotonic()
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
                if self.last_prompt_interrupted:
                    if capture is not None:
                        capture.drain_model_requests()
                    return ""
                provider_error = _provider_error(event)
                if provider_error:
                    if event.get("willRetry") is True:
                        answer_state = _AssistantAnswerState()
                        continue
                    if capture is not None:
                        capture.drain_model_requests()
                    raise PiProtocolError(
                        "Pi provider failure: "
                        + _sanitize_diagnostic(provider_error, self.secret_values)
                    )
                answer = answer_state.answer()
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
            lines.put(_ReceivedLine(raw))
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


class _AssistantAnswerState:
    """Keep one assistant message, never prose from previous tool cycles.

    A terminal message snapshot is authoritative. Unframed legacy deltas are
    supported only since the latest message/tool boundary. Text is not selected
    by language, keywords or domain meaning.
    """

    def __init__(self) -> None:
        self._parts: list[str] = []
        self._completed: str | None = None

    def _reset(self) -> None:
        self._parts.clear()
        self._completed = None

    def observe(self, event: Mapping[str, Any]) -> None:
        kind = event.get("type")
        if kind in {"message_start", "tool_execution_start", "tool_execution_end", "tool_result", "auto_retry_start"}:
            self._reset()
        elif kind == "text_delta":
            self._append(event.get("text"))
        elif kind == "message_update":
            update = event.get("assistantMessageEvent")
            if isinstance(update, dict) and update.get("type") == "text_delta":
                self._append(update.get("delta"))
        elif kind == "message_end":
            message = event.get("message")
            if isinstance(message, dict):
                self._completed = _final_assistant_text(message)
                self._parts.clear()
        elif kind == "agent_end":
            messages = event.get("messages")
            if isinstance(messages, list) and messages:
                self._completed = _final_assistant_text(messages[-1])
                self._parts.clear()
            if _provider_error(dict(event)):
                self._reset()

    def _append(self, value: object) -> None:
        if isinstance(value, str):
            self._completed = None
            self._parts.append(value)

    def answer(self) -> str:
        return self._completed if self._completed is not None else "".join(self._parts)


def _final_assistant_text(message: object) -> str:
    if not isinstance(message, dict) or message.get("role") != "assistant":
        return ""
    if message.get("stopReason") in {"toolUse", "tool_use", "error", "aborted"}:
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list) or any(isinstance(block, dict) and block.get("type") in {"toolCall", "tool_use"} for block in content):
        return ""
    return "".join(block["text"] for block in content if isinstance(block, dict)
                   and block.get("type") == "text" and isinstance(block.get("text"), str))


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
    # Deltas are provisional process output until the final message and answer
    # admission complete. They must never be treated as the formal answer stream.
    if event.get("type") in {"turn_start", "turn_end"}:
        return ({"type": "runtime_action", "phase": "started" if event["type"] == "turn_start" else "completed"},)
    if event.get("type") == "message_end":
        message = event.get("message")
        if isinstance(message, dict) and message.get("role") == "assistant":
            content = message.get("content")
            tools = isinstance(content, list) and any(isinstance(item, dict) and item.get("type") == "toolCall" for item in content)
            return ({"type": "runtime_action", "phase": "response_completed", "response_kind": "tools" if tools else "text"},)
    delta = event.get("text") if event.get("type") == "text_delta" else None
    update = event.get("assistantMessageEvent") if event.get("type") == "message_update" else None
    if isinstance(update, dict) and update.get("type") == "text_delta":
        delta = update.get("delta")
    if isinstance(delta, str):
        return ({"type": "assistant_process_delta", "text": delta[:16384]},)
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
    for field in ("capability_key", "projector_id", "result_kind", "request_parameters"):
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
