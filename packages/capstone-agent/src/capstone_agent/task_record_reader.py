"""Read public observations from an application-selected historical task.

These records explain past execution. They do not admit historical results as
evidence for the current calculation. The caller cannot select another source.
"""

from __future__ import annotations

from typing import Any, Protocol


class AttemptRecordStore(Protocol):
    def read_attempt_records(self, thread_id: str, attempt_id: str, *,
                             after: int = 0, limit: int = 32,
                             observations_only: bool = False) -> dict[str, Any]: ...


PUBLIC_TASK_OBSERVATION_TYPES = frozenset({
    "tool_started", "tool_completed", "validation_observation",
    "research_state_updated", "answer_committed", "attempt_completed",
    "attempt_failed", "attempt_interrupted", "attempt_cancelled",
})


class SelectedTaskRecordReader:
    """Keep source access fixed while allowing bounded forward pagination."""

    def __init__(self, store: AttemptRecordStore, thread_id: str, attempt_id: str) -> None:
        self._store = store
        self._thread_id = thread_id
        self._attempt_id = attempt_id

    def read(self, *, after: int = 0, limit: int = 32) -> dict[str, Any]:
        if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= 128:
            raise ValueError("historical task cursor is invalid")
        page = self._store.read_attempt_records(
            self._thread_id, self._attempt_id, after=after, limit=limit, observations_only=True,
        )
        if (page.get("schema") != "capstone-attempt-records/1"
                or page.get("thread_id") != self._thread_id
                or page.get("attempt_id") != self._attempt_id):
            raise ValueError("historical task identity does not match the selected source")
        return {
            "schema": "capstone-selected-task-records/1",
            "thread_id": self._thread_id, "attempt_id": self._attempt_id,
            "historical_only": True,
            "instruction": page["instruction"], "model_context": page["model_context"],
            "events": [event for event in page["events"]
                       if event.get("visibility") == "public"
                       and event.get("event_type") in PUBLIC_TASK_OBSERVATION_TYPES],
            # Advance over excluded events as well. An empty page can have more.
            "next_after": page["next_after"], "has_more": page["has_more"],
        }
