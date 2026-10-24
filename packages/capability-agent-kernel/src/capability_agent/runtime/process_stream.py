"""Bounded batching for provisional text, with original fragments retained."""
from collections.abc import Callable
import time
from typing import Any
from capability_agent.runtime.capacity import runtime_limits as resolve_limits


class ProcessStream:
    def __init__(self, publish: Callable[[dict[str, Any]], None], interval: float, *, runtime_limits=None) -> None:
        self.publish = publish
        self.runtime_limits=resolve_limits(runtime_limits)
        self.interval = interval
        self.fragments: list[dict[str, object]] = []
        self.correlation: str | None = None
        self.deadline: float | None = None
        self.characters = 0
        self.failed = False

    def remaining(self) -> float | None:
        return None if self.deadline is None else max(0, self.deadline - time.perf_counter())

    def flush_due(self) -> None:
        if self.deadline is not None and time.perf_counter() >= self.deadline:
            self.flush()

    def emit(self, payload: dict[str, Any], *, ordinal: int, received: float | None) -> None:
        text = payload.get("text")
        if self.interval == 0 or payload.get("type") != "assistant_process_delta" or not isinstance(text, str):
            self.flush()
            self.publish(payload)
            return
        correlation = payload.get("correlation_id")
        limits=self.runtime_limits
        if self.fragments and (correlation != self.correlation or self.characters + len(text) > limits['rpc_frame_bytes']):
            self.flush()
        if not self.fragments:
            self.deadline = time.perf_counter() + self.interval
            self.correlation = correlation
        self.fragments.append({"text": text, "native_ordinal": ordinal, "received_seconds": received})
        self.characters += len(text)
        if self.characters >= limits['rpc_frame_bytes'] or len(self.fragments) >= limits['rpc_batch_requests']:
            self.flush()
        else:
            self.flush_due()

    def flush(self) -> None:
        if not self.fragments or self.failed:
            return
        payload: dict[str, Any] = {"type": "assistant_process_delta",
            "text": "".join(str(fragment["text"]) for fragment in self.fragments),
            "delta_records": list(self.fragments)}
        if self.correlation is not None:
            payload["correlation_id"] = self.correlation
        # Clear only after the durable callback returns. Failed writes remain fatal.
        try:
            self.publish(payload)
        except BaseException:
            self.failed = True
            raise
        self.fragments.clear()
        self.deadline = None
        self.characters = 0
