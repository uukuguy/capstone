from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, cast
import pytest

from grid_agent.trajectory.context_projection import (
    UNAVAILABLE_NATIVE_CONTEXT,
    project_context,
    project_context_payload,
)
from grid_agent.trajectory.artifacts import ArtifactPointer
from grid_agent.trajectory.events import Causation, ContextBoundary, EventRefs, EventSource, RunScope
from grid_agent.trajectory.replay import ReplayEventLike


@dataclass(frozen=True)
class Event:
    sequence: int
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    scope: RunScope = field(default_factory=RunScope)
    analysis_id: str = "analysis-1"
    timestamp: str | None = None
    causation: Causation = field(default_factory=Causation)
    source: EventSource = field(default_factory=EventSource)
    context: ContextBoundary = field(default_factory=ContextBoundary)
    refs: EventRefs = field(default_factory=EventRefs)


def _replay_events(*events: Event) -> tuple[ReplayEventLike, ...]:
    return cast(tuple[ReplayEventLike, ...], events)


class VerifiedContextArtifacts:
    def __init__(self, pointer: ArtifactPointer, path: Path) -> None:
        self.pointer = pointer
        self.path = path
        self.references: list[str] = []

    def verify_reference(self, reference: str) -> ArtifactPointer:
        self.references.append(reference)
        if reference != self.pointer.ref:
            raise RuntimeError("unregistered artifact")
        return self.pointer

    def verify(self, pointer: ArtifactPointer) -> Path:
        assert pointer == self.pointer
        return self.path


def test_context_frame_returns_before_delta_after_and_next_request_input() -> None:
    events = (
        Event(1, "context.projected", {"after_state": {"domain_state": {}}}, context=ContextBoundary(after_revision=1)),
        Event(4, "context.projected", {"after_state": {"domain_state": {"calculations": {"artifact:result": {"status": "converged"}}}}}, context=ContextBoundary(before_revision=1, after_revision=2)),
        Event(5, "model.request.started", {"artifact_ref": "artifact:request"}),
    )

    frame = project_context(_replay_events(*events), artifacts=None, checkpoint_interval=2).at_sequence(4)

    assert frame.before_revision == 1
    assert frame.after_revision == 2
    assert frame.delta["domain_state"]["calculations"]["added"] == ("artifact:result",)
    assert frame.after_state["domain_state"]["calculations"]["artifact:result"]["status"] == "converged"
    assert frame.request_artifact_ref == "artifact:request"


def test_context_frame_labels_missing_request_unavailable() -> None:
    event = Event(8, "context.projected", {"after_state": {}}, context=ContextBoundary(before_revision=0, after_revision=1))
    frame = project_context(_replay_events(event), artifacts=None).at_sequence(8)
    assert frame.request_artifact_ref is None
    assert frame.unavailable_reason == "legacy source did not capture model request input"


def test_native_context_unavailable_preserves_next_request_artifact_reference() -> None:
    events = (
        Event(
            7,
            "context.injected",
            {"revision": 7, "state_hash": "sha256:state-7"},
            context=ContextBoundary(before_revision=7, after_revision=7),
        ),
        Event(8, "model.request.started", {"artifact_ref": "artifact:request-8"}),
    )

    frame = project_context(_replay_events(*events), artifacts=None).at_sequence(7)

    assert frame.status == "unavailable"
    assert frame.unavailable_reason == UNAVAILABLE_NATIVE_CONTEXT
    assert frame.request_artifact_ref == "artifact:request-8"
    assert frame.model_dump(mode="json")["after_state"] is None
    assert frame.state_omitted


def test_native_context_injection_uses_verified_context_view_artifact(tmp_path: Path) -> None:
    document = {
        "schema_version": "analysis-context-view/1.0",
        "analysis_id": "analysis-1",
        "revision": 7,
        "state_hash": "sha256:state-7",
        "reusable_calculations": [{"result_ref": "result-7", "status": "converged"}],
    }
    path = tmp_path / "view.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    digest = sha256(path.read_bytes()).hexdigest()
    pointer = ArtifactPointer("artifact:sha256:" + digest, "context-view", "context/views/r7/view.json", digest, path.stat().st_size)
    artifacts = VerifiedContextArtifacts(pointer, path)
    event = Event(
        7,
        "context.injected",
        {"revision": 7, "state_hash": "sha256:state-7", "artifact_ref": pointer.ref},
        context=ContextBoundary(before_revision=7, after_revision=7),
        refs=EventRefs(produced=(pointer.ref,)),
    )

    frame = project_context(_replay_events(event), artifacts).at_sequence(7)

    assert artifacts.references == [pointer.ref]
    assert frame.model_dump(mode="json")["after_state"] == document


def test_large_context_is_unknown_until_a_complete_snapshot_returns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "view.json"
    path.write_text(json.dumps({"body": "x" * 131072}), encoding="utf-8")
    pointer = ArtifactPointer("artifact:sha256:" + "a" * 64, "context-view",
                              "context/views/r1/view.json", "a" * 64, path.stat().st_size)
    artifacts = VerifiedContextArtifacts(pointer, path)

    def forbidden(_: Path) -> bytes:
        pytest.fail("large context must not be decoded for display")

    monkeypatch.setattr(Path, "read_bytes", forbidden)
    events = _replay_events(
        Event(1, "context.injected", {"artifact_ref": pointer.ref},
              context=ContextBoundary(after_revision=1)),
        Event(2, "model.request.started", {"artifact_ref": "artifact:request"}),
        Event(3, "context.projected", {"after_state": {"value": 1}},
              context=ContextBoundary(after_revision=2)),
        Event(4, "analysis.completed"),
    )
    timeline = project_context(events, artifacts, checkpoint_interval=1)
    first, inherited, restored, complete = timeline.frames
    assert first.state_omitted
    assert first.after_state is None and first.after_state_hash is None
    assert first.delta is None
    assert first.admitted_artifact_refs == (pointer.ref,)
    assert inherited.before_state is None and inherited.after_state is None
    assert inherited.before_state_hash is None and inherited.after_state_hash is None
    assert restored.state_omitted and restored.before_state is None
    assert restored.after_state == {"value": 1}
    assert not complete.state_omitted
    assert complete.before_state == complete.after_state == {"value": 1}
    assert timeline.checkpoints[0].state is None
    assert timeline.checkpoints[0].state_hash is None
    assert timeline.checkpoints[0].state_omitted


@pytest.mark.parametrize("parent_swap", [False, True])
def test_context_rejects_symlink_replacement_after_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, parent_swap: bool
) -> None:
    content = json.dumps({"analysis_id": "analysis-1", "revision": 1, "state_hash": "state-1"}).encode()
    path = tmp_path / "context" / "view.json"
    path.parent.mkdir()
    outside = tmp_path / "replacement.json"
    path.write_bytes(content)
    outside.write_bytes(content)
    digest = sha256(content).hexdigest()
    pointer = ArtifactPointer("artifact:sha256:" + digest, "context-view",
                              "context/views/r1/view.json", digest, len(content))
    artifacts = VerifiedContextArtifacts(pointer, path)

    def swapped(_: ArtifactPointer) -> Path:
        if parent_swap:
            path.parent.rename(tmp_path / "original-context")
            path.parent.symlink_to(tmp_path / "original-context", target_is_directory=True)
        else:
            path.unlink()
            path.symlink_to(outside)
        return path

    monkeypatch.setattr(artifacts, "verify", swapped)
    frame = project_context(_replay_events(Event(1, "context.injected", {
        "artifact_ref": pointer.ref, "revision": 1, "state_hash": "state-1"
    })), artifacts).frames[0]
    assert frame.after_state is None
    assert frame.status == "unavailable"


def test_unknown_domain_context_payload_is_not_interpreted_as_grid_state() -> None:
    payload = {"stock": {"A-1": {"available": 4}}}

    projected = project_context_payload(
        analysis_id="analysis-inventory",
        binding_id="inventory",
        domain_id="inventory-readonly",
        authority_id="inventory-api",
        schema="inventory-context/1.0",
        payload=payload,
    )

    assert projected.payload == payload
    assert projected.interpretation == "opaque"
