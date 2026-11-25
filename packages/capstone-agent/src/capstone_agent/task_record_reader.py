"""Read public observations from an application-selected historical task.

These records explain past execution. They do not admit historical results as
evidence for the current calculation. The caller cannot select another source.
"""

from __future__ import annotations

from typing import Any, Protocol
import hashlib
import json
from copy import deepcopy
from pathlib import Path

from capability_agent._safe_files import ensure_bound_directory, write_bound_text


class AttemptRecordStore(Protocol):
    def read_attempt_records(self, thread_id: str, attempt_id: str, *,
                             after: int = 0, limit: int = 32,
                             observations_only: bool = False,
                            workspace_name: str | None = None) -> dict[str, Any]: ...


PUBLIC_TASK_OBSERVATION_TYPES = frozenset({
    "execution_source_revision",
    "tool_started", "tool_completed", "tool_failed", "tool_cancelled",
    "validation_observation", "validation_failed",
    "research_state_updated", "answer_committed", "attempt_completed",
    "attempt_failed", "attempt_interrupted", "attempt_cancelled",
    "instruction_admitted", "attempt_delivery_recovered", "native_artifact_published",
})

PUBLIC_NATIVE_OBSERVATION_TYPES = frozenset({"tool_execution_start", "tool_execution_end"})


def is_public_task_observation(visibility, event_type, payload):
    return visibility == "public" and (
        event_type in PUBLIC_TASK_OBSERVATION_TYPES
        or (event_type == "runtime_event" and payload.get("native_type") in PUBLIC_NATIVE_OBSERVATION_TYPES)
    )


def _historical_observation(event):
    projected = deepcopy(event)
    work = projected.get('payload', {}).get('work')
    if isinstance(work, dict):
        # Queue state is a presentation projection. Only the separate consumed
        # receipt admits user directions to historical execution context.
        work.pop('instruction_queue', None)
    return projected


class SelectedTaskRecordReader:
    """Keep source access fixed while allowing bounded forward pagination."""

    def __init__(self, store: AttemptRecordStore, thread_id: str, attempt_id: str, *, handoff=None, workspace_name: str | None = None) -> None:
        self._store = store
        self._thread_id = thread_id
        self._attempt_id = attempt_id
        self._handoff = handoff
        self._workspace_name = workspace_name

    def publish(self, directory: Path) -> Path:
        """Copy terminal public pages into this attempt's private tool input."""
        root = ensure_bound_directory(directory)
        pages = []
        cursor = 0
        while True:
            page = self.read(after=cursor)
            text = json.dumps(page, ensure_ascii=False, sort_keys=True) + "\n"
            write_bound_text(root / f"{cursor}.json", text)
            pages.append({"after": cursor, "sha256": hashlib.sha256(text.encode()).hexdigest()})
            if not page["has_more"]:
                break
            next_cursor = page["next_after"]
            if type(next_cursor) is not int or next_cursor <= cursor:
                raise ValueError("historical task cursor did not advance")
            cursor = next_cursor
        write_bound_text(root / "manifest.json", json.dumps({
            "schema": "capstone-selected-task-input/1",
            "thread_id": self._thread_id, "attempt_id": self._attempt_id, "pages": pages,
        }, sort_keys=True) + "\n")
        return root

    def read(self, *, after: int = 0, limit: int = 32) -> dict[str, Any]:
        if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= 128:
            raise ValueError("historical task cursor is invalid")
        workspace = {} if self._workspace_name is None else {'workspace_name': self._workspace_name}
        page = self._store.read_attempt_records(
            self._thread_id, self._attempt_id, after=after, limit=limit, observations_only=True, **workspace,
        )
        if (page.get("schema") != "capstone-attempt-records/1"
                or page.get("thread_id") != self._thread_id
                or page.get("attempt_id") != self._attempt_id):
            raise ValueError("historical task identity does not match the selected source")
        through = None if self._handoff is None else self._handoff['through_event_seq']
        next_after = page['next_after'] if through is None else min(page['next_after'], through)
        return {
            "schema": "capstone-selected-task-records/1",
            **({"task_handoff": deepcopy(self._handoff)} if self._handoff is not None and after == 0 else {}),
            "thread_id": self._thread_id, "attempt_id": self._attempt_id,
            "historical_only": True,
            "instruction": page["instruction"], "model_context": page["model_context"],
            "events": [_historical_observation(event) for event in page["events"]
                       if (through is None or event["event_seq"] <= through)
                       and is_public_task_observation(event.get("visibility"), event.get("event_type"),
                                                      event.get("payload", {}))],
            # Advance over excluded events as well. An empty page can have more.
            "next_after": max(after, next_after),
            "has_more": page["has_more"] and (through is None or next_after < through),
        }
