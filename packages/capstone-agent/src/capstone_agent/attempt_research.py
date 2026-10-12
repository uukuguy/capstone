"""Application-owned research lifetime for one Thread attempt."""

from collections.abc import Callable
from hashlib import sha256
import json
import os
import re
from pathlib import Path
from uuid import uuid4

from capability_agent.application import ApplicationContextStore, ContextEventDraft, ResearchController
from capability_agent.application.workspace import ApplicationWorkspace
from capability_agent.runtime.research_channel import ResearchRequestChannel


class AttemptResearch:
    """Keep task research separate from reusable model preparation workspaces.

    Thread identifiers and Kernel portable identifiers have different contracts.
    The immutable binding records both; neither namespace impersonates the other.
    Existing workspaces are never overwritten or silently resumed.
    """

    def __init__(self, root: Path, *, thread_id: str, run_id: str, attempt_id: str,
                 is_active: Callable[[], bool], admit_reference: Callable[[str], bool]) -> None:
        identities = (thread_id, run_id, attempt_id)
        if any(not isinstance(value, str) or not value or len(value) > 256 for value in identities):
            raise ValueError("invalid task research identity")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", attempt_id):
            raise ValueError("invalid research attempt identity")
        digest = sha256(json.dumps(identities).encode()).hexdigest()[:48]
        workspace = ApplicationWorkspace.create(root, run_id=f"task-{digest}")
        # The first instruction starts a research identity. It is not derived
        # from the execution identity; future turns must explicitly bind it.
        self.research_id = f"research-{uuid4().hex}"
        self.identity_path = workspace.core_path / "task-binding.json"
        binding = {"schema": "capstone-task-research-binding/1", "thread_id": thread_id,
                   "run_id": run_id, "attempt_id": attempt_id, "kernel_run_id": workspace.run_id,
                   "research_id": self.research_id}
        with self.identity_path.open("x", encoding="utf-8") as target:
            self.identity_path.chmod(0o600)
            json.dump(binding, target)
            target.flush()
            os.fsync(target.fileno())
        self.store = ApplicationContextStore.initialize(workspace)
        self.turn_id = f"turn-{digest}"
        self.store.append(ContextEventDraft(event_type="turn.started", turn_id=self.turn_id,
                                           payload={"ordinal": 1}))
        self.controller = ResearchController(self.store, research_id=self.research_id,
            turn_id=self.turn_id, admit_reference=admit_reference)
        self._closed = False
        self._is_active = is_active
        self.channel = ResearchRequestChannel(self.controller, attempt_id=attempt_id,
            is_active=lambda: not self._closed and self._is_active())

    def bind_active_check(self, check: Callable[[], bool]) -> None:
        if self._closed:
            raise RuntimeError("research attempt is closed")
        self._is_active = check

    def close(self, *, failed: bool) -> None:
        if self._closed:
            return
        # Disable new writes even if recording the terminal transition fails.
        self._closed = True
        self.store.append(ContextEventDraft(
            event_type="turn.failed" if failed else "turn.completed",
            turn_id=self.turn_id, payload={}))
