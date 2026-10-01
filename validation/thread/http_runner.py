"""Provider-free acceptance helpers layered on the production Thread HTTP client."""

from __future__ import annotations

import time

from capstone_agent.thread_http import (
    HttpThreadSession as _HttpThreadSession,
    ThreadHttpError,
    ThreadResyncRequired,
)
from capstone_agent.thread_protocol import ThreadSnapshot

from .catalog import ThreadCatalog


class HttpThreadSession(_HttpThreadSession):
    """Add the validation-only catalog projection to the runtime HTTP client."""

    def catalog(self) -> ThreadCatalog:
        thread_id, _ = self._require_identity()
        return ThreadCatalog.from_document(self._request("GET", f"/api/v1/threads/{thread_id}/catalog"))


def wait_for_terminal(
    session: HttpThreadSession, *, attempt_id: str | None = None,
    timeout_seconds: float = 30.0,
) -> ThreadSnapshot:
    deadline = time.monotonic() + timeout_seconds
    initial = session.snapshot()
    target_attempt_id = attempt_id
    if target_attempt_id is None and initial.current_attempt is not None:
        target_attempt_id = initial.current_attempt.attempt_id
    if target_attempt_id is None:
        raise RuntimeError("no active Attempt to wait for")
    cursor = initial.last_event_seq
    terminal_seen = False
    while time.monotonic() < deadline:
        page = session.events(after=cursor)
        cursor = page.next_event_seq
        terminal_seen = terminal_seen or any(
            event.attempt_id == target_attempt_id
            and event.event_type in {"attempt_completed", "attempt_failed", "attempt_cancelled", "attempt_interrupted"}
            for event in page.events
        )
        if terminal_seen:
            snapshot = session.snapshot()
            if snapshot.current_attempt is None or snapshot.current_attempt.attempt_id != target_attempt_id:
                return snapshot
        time.sleep(0.05)
    raise TimeoutError("Thread attempt did not reach a terminal snapshot before timeout")


__all__ = ["HttpThreadSession", "ThreadHttpError", "ThreadResyncRequired", "wait_for_terminal"]
