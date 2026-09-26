"""One persistent, registered application worker per Capstone session."""

from __future__ import annotations

import secrets
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from capstone_agent.protocol import MAX_FRAME_BYTES, Frame, ProtocolError


_SCRIPTED_ENV_NAMES = frozenset({
    "PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "SSL_CERT_FILE",
    "REQUESTS_CA_BUNDLE", "UV_CACHE_DIR", "CAPSTONE_PYPSA_MODEL_LIBRARY_DIR",
})


def _worker_environment(source: Mapping[str, str], mode: str) -> dict[str, str]:
    if mode == "provider":
        return {name: value for name, value in source.items() if name != "VIRTUAL_ENV"}
    return {name: value for name, value in source.items() if name in _SCRIPTED_ENV_NAMES}


@dataclass(frozen=True, slots=True)
class WorkerSpec:
    application_id: str
    command: tuple[str, ...]
    cwd: Path | None = None
    environment: Mapping[str, str] | None = None
    scripted_cases: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if not self.application_id or not self.command or any(not part for part in self.command):
            raise ValueError("worker registration is invalid")


class WorkerRegistry:
    """Resolve only workers declared by trusted host source code."""

    def __init__(self, specs: tuple[WorkerSpec, ...]) -> None:
        ids = [spec.application_id for spec in specs]
        if len(ids) != len(set(ids)):
            raise ValueError("worker registration is duplicated")
        self._specs = {spec.application_id: spec for spec in specs}

    def resolve(self, application_id: str) -> WorkerSpec:
        try:
            return self._specs[application_id]
        except (KeyError, TypeError):
            raise ValueError("application is not registered") from None


class WorkerSession:
    """Validate a worker's ordered events and serialize its instructions."""

    def __init__(
        self, spec: WorkerSpec, *, mode: str, case_id: str | None = None,
        provider: str | None = None, model: str | None = None,
        timeout: float = 900.0,
        on_event: Callable[[Frame], None] | None = None,
        session_id: str | None = None,
        persist_event: Callable[[Frame], None] | None = None,
    ) -> None:
        if mode not in {"provider", "scripted-demo"}:
            raise ValueError("application mode is invalid")
        if mode == "scripted-demo":
            if (spec.scripted_cases is not None and case_id not in spec.scripted_cases):
                raise ValueError("scripted case is not registered")
            if provider is not None or model is not None:
                raise ValueError("scripted case does not accept Provider options")
        elif case_id is not None:
            raise ValueError("Provider route does not accept a case ID")
        self.spec = spec
        self.mode = mode
        self.case_id = case_id
        self.provider = provider
        self.model = model
        self.timeout = timeout
        self.on_event = on_event
        self.persist_event = persist_event
        self.session_id = session_id or "session-" + secrets.token_hex(12)
        Frame(self.session_id, 1, "close", {})
        self.run_id: str | None = None
        self._process: subprocess.Popen[bytes] | None = None
        self._reader: threading.Thread | None = None
        self._condition = threading.Condition()
        self._evidence_lock = threading.Lock()
        self._events: list[Frame] = []
        self._failure: str | None = None
        self._failure_code: str | None = None
        self._send_sequence = 0
        self._busy = False
        self._closed = False
        self._accepted = 0

    @property
    def events(self) -> tuple[Frame, ...]:
        with self._condition:
            return tuple(self._events)

    @property
    def busy(self) -> bool:
        with self._condition:
            return self._busy

    @property
    def accepted(self) -> int:
        with self._condition:
            return self._accepted

    @property
    def closed(self) -> bool:
        with self._condition:
            return self._closed

    @property
    def failure_code(self) -> str | None:
        with self._condition:
            return self._failure_code

    def __enter__(self) -> WorkerSession:
        if self._process is not None:
            raise RuntimeError("worker session is already open")
        self._process = subprocess.Popen(
            self.spec.command, cwd=self.spec.cwd,
            env=_worker_environment(self.spec.environment or os.environ, self.mode),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr,
        )
        try:
            self._reader = threading.Thread(target=self._read_events, daemon=True)
            self._reader.start()
            self._send("open", {
                "application_id": self.spec.application_id, "mode": self.mode,
                "case_id": self.case_id, "provider": self.provider,
                "model": self.model,
                "run_id": "run-" + secrets.token_hex(12),
            })
            ready = self.wait_for("ready")
            run_id = ready.payload.get("run_id")
            if not isinstance(run_id, str) or not run_id:
                raise RuntimeError("worker returned an invalid run ID")
            self.run_id = run_id
            return self
        except Exception:
            self._terminate_process()
            raise

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        try:
            if not self._closed and self._failure is None:
                self.close()
        finally:
            self._terminate_process()

    def _terminate_process(self) -> None:
        process = self._process
        if process is None:
            return
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        if process.stdin is not None:
            process.stdin.close()
        if process.stdout is not None:
            process.stdout.close()

    def submit(self, instruction: str) -> int:
        if not isinstance(instruction, str) or not instruction.strip() or len(instruction) > 32_000:
            raise ValueError("instruction is invalid")
        with self._condition:
            if self._closed or self._failure is not None:
                raise RuntimeError("worker session is unavailable")
            if self._busy:
                raise RuntimeError("an active turn already exists")
            self._busy = True
            self._accepted += 1
            ordinal = self._accepted
        try:
            self._send("turn", {"instruction": instruction})
        except Exception:
            with self._condition:
                self._busy = False
            raise
        return ordinal

    def submit_and_wait(self, instruction: str) -> Frame:
        after = self.events[-1].sequence if self.events else 0
        ordinal = self.submit(instruction)
        answer = self.wait_for("answer_committed", after=after)
        if answer.payload.get("ordinal") != ordinal:
            raise RuntimeError("worker answer ordinal is invalid")
        return answer

    def close(self) -> Frame:
        self.request_close()
        return self.wait_for("completed")

    def request_close(self) -> None:
        if not self._closed:
            self._closed = True
            self._send("close", {})

    def read_evidence(self, reference: str) -> object | None:
        if not isinstance(reference, str) or not reference or len(reference) > 2048:
            raise ValueError("evidence reference is invalid")
        with self._evidence_lock:
            events = self.events
            after = events[-1].sequence if events else 0
            self._send("evidence", {"ref": reference})
            response = self.wait_for("evidence_result", after=after)
            if response.payload.get("ref") != reference:
                raise RuntimeError("worker evidence identity is invalid")
            return response.payload.get("value")

    def wait_for(self, kind: str, *, after: int = 0) -> Frame:
        deadline = time.monotonic() + self.timeout
        with self._condition:
            while True:
                for event in self._events:
                    if event.sequence > after and event.kind == kind:
                        return event
                if self._failure is not None:
                    raise RuntimeError(self._failure)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("worker response timed out")
                self._condition.wait(remaining)

    def next_event(self, *, after: int, timeout: float | None = None) -> Frame | None:
        deadline = time.monotonic() + (self.timeout if timeout is None else timeout)
        with self._condition:
            while True:
                for event in self._events:
                    if event.sequence > after:
                        return event
                if self._failure is not None:
                    raise RuntimeError(self._failure)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._condition.wait(remaining)

    def _send(self, kind: str, payload: dict[str, object]) -> None:
        process = self._process
        if process is None or process.stdin is None:
            raise RuntimeError("worker session is not open")
        with self._condition:
            self._send_sequence += 1
            frame = Frame(self.session_id, self._send_sequence, kind, payload)
            try:
                process.stdin.write(frame.to_line())
                process.stdin.flush()
            except OSError:
                self._failure = "application worker disconnected"
                self._failure_code = "worker_disconnected"
                self._condition.notify_all()
                raise RuntimeError(self._failure) from None

    def _read_events(self) -> None:
        process = self._process
        assert process is not None and process.stdout is not None
        expected = 1
        try:
            while raw := process.stdout.readline(MAX_FRAME_BYTES + 1):
                event = Frame.from_line(raw, expected_sequence=expected)
                if event.session_id != self.session_id or event.kind not in {
                    "ready", "progress", "answer_committed", "completed", "failed", "evidence_result"
                }:
                    raise ProtocolError("worker event is invalid")
                expected += 1
                if self.persist_event is not None:
                    try:
                        self.persist_event(event)
                    except Exception:
                        with self._condition:
                            self._failure = "worker event persistence failed"
                            self._failure_code = "event_persistence_failed"
                            self._condition.notify_all()
                        return
                with self._condition:
                    self._events.append(event)
                    if event.kind in {"answer_committed", "failed"}:
                        self._busy = False
                    if event.kind == "failed":
                        self._failure = "application worker failed"
                        self._failure_code = "application_worker_failed"
                    self._condition.notify_all()
                if self.on_event is not None:
                    try:
                        self.on_event(event)
                    except Exception:
                        pass
            with self._condition:
                if (self._failure is None
                        and not any(event.kind == "completed" for event in self._events)):
                    self._failure = "application worker disconnected"
                    self._failure_code = "worker_disconnected"
                self._condition.notify_all()
        except (ProtocolError, OSError):
            with self._condition:
                self._failure = "application worker protocol failed"
                self._failure_code = "worker_protocol_failed"
                self._condition.notify_all()
