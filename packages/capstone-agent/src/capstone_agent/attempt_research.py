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
from capability_agent._safe_files import read_bound_regular_path, write_bound_text
from .thread_protocol import ModelContextSnapshot


class AttemptResearch:
    """Keep task research separate from reusable model preparation workspaces.

    Thread identifiers and Kernel portable identifiers have different contracts.
    The immutable binding records both; neither namespace impersonates the other.
    Research is restored by Thread and model identity; attempts have separate
    channels and immutable bindings. An unfinished turn requires recovery.
    """

    def __init__(self, root: Path, *, thread_id: str, run_id: str, attempt_id: str,
                 model_context: ModelContextSnapshot,
                 research_generation: str | None = None,
                 channel_root: Path | None = None,
                 is_active: Callable[[], bool], admit_reference: Callable[[str], bool]) -> None:
        if not isinstance(model_context, ModelContextSnapshot):
            raise TypeError("research requires the selected model snapshot")
        identities = (thread_id, run_id, attempt_id)
        if any(not isinstance(value, str) or not value or len(value) > 256 for value in identities):
            raise ValueError("invalid task research identity")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", attempt_id):
            raise ValueError("invalid research attempt identity")
        digest = sha256(json.dumps(identities).encode()).hexdigest()[:48]
        owner = {"thread_id": thread_id, "model_id": model_context.model_id,
                 "implementation_family": model_context.implementation_family}
        if research_generation is not None:
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", research_generation):
                raise ValueError("invalid research generation")
            owner["research_generation"] = research_generation
        storage_id = "study-" + sha256(json.dumps(owner, sort_keys=True).encode()).hexdigest()[:48]
        existing = (root / storage_id).exists()
        workspace = (ApplicationWorkspace.open_existing(root, run_id=storage_id) if existing
                     else ApplicationWorkspace.create(root, run_id=storage_id))
        # Reserve a host identity for the channel, not a visible research.
        # Only a committed initial goal creates research state.
        owner_path = workspace.core_path / "research-binding.json"
        if existing:
            saved = json.loads(read_bound_regular_path(owner_path))
            if saved.get("owner") != owner:
                raise ValueError("research owner does not match selected model")
            self.research_id = saved["research_id"]
            self.store = ApplicationContextStore(workspace, ApplicationContextStore.replay(workspace))
        else:
            self.research_id = f"research-{uuid4().hex}"
            write_bound_text(owner_path, json.dumps({"owner": owner, "research_id": self.research_id}))
            self.store = ApplicationContextStore.initialize(workspace)
        self.model_context = model_context
        self.identity_path = workspace.turns_path / f"{attempt_id}.json"
        binding = {"schema": "capstone-task-research-binding/1", "thread_id": thread_id,
                   "run_id": run_id, "attempt_id": attempt_id, "kernel_run_id": workspace.run_id,
                   "research_id": self.research_id,
                   "research_generation": research_generation,
                   "baseline_model_context": model_context.to_document()}
        with self.identity_path.open("x", encoding="utf-8") as target:
            self.identity_path.chmod(0o600)
            json.dump(binding, target)
            target.flush()
            os.fsync(target.fileno())
        self.turn_id = f"turn-{digest}"
        self._start_event = ContextEventDraft(event_type="turn.started", turn_id=self.turn_id,
            payload={"ordinal": len(self.store.snapshot.core.turns) + 1,
                     "attempt_id": attempt_id, "run_id": run_id,
                     "model_context": model_context.to_document()})
        self._started = self.store.snapshot.core.active_turn is None
        if self._started:
            self.store.append(self._start_event)
        self.controller = ResearchController(self.store, research_id=self.research_id,
            turn_id=self.turn_id, admit_reference=admit_reference)
        self._closed = False
        self._is_active = is_active
        self.channel = ResearchRequestChannel(self.controller, attempt_id=attempt_id,
            is_active=lambda: self._started and not self._closed and self._is_active(), channel_root=channel_root)

    def bind_active_check(self, check: Callable[[], bool],
                          terminal_phase: Callable[[str], str | None] | None = None) -> None:
        if self._closed:
            raise RuntimeError("research attempt is closed")
        self._is_active = check
        if not self._started:
            previous = self.store.snapshot.core.active_turn
            previous_attempt = previous.get("attempt_id") if previous else None
            phase = terminal_phase(previous_attempt) if terminal_phase and isinstance(previous_attempt, str) else None
            if not check() or phase not in {"completed", "failed", "cancelled", "interrupted"}:
                raise RuntimeError("previous research attempt has no verified terminal state")
            assert previous is not None
            self.store.append(ContextEventDraft(
                event_type="turn.completed" if phase == "completed" else "turn.failed",
                turn_id=previous["turn_id"], payload={"attempt_id": previous_attempt,
                    "terminal_phase": phase, "recovered_from_thread": True}))
            self.store.append(ContextEventDraft(event_type="turn.started", turn_id=self.turn_id,
                payload={**self._start_event.payload, "ordinal": len(self.store.snapshot.core.turns) + 1}))
            self._started = True

    def current_projection(self) -> dict[str, object] | None:
        state = self.controller.read()
        if state is None:
            return None
        return {"research_id": state.research_id, "research_revision": state.revision,
                "goal": state.goal, "baseline_model_context": self.model_context.to_document(),
                "claim_count": len(state.claims), "open_question_count": len(state.open_questions),
                "research_snapshot": state.model_dump(mode="json")}

    def close(self, *, failed: bool) -> None:
        if self._closed:
            return
        # Disable new writes even if recording the terminal transition fails.
        self._closed = True
        if not self._started:
            return
        self.store.append(ContextEventDraft(
            event_type="turn.failed" if failed else "turn.completed",
            turn_id=self.turn_id, payload={}))
