from __future__ import annotations

import pytest
from pydantic import ValidationError

from capability_agent.trajectory.events import (
    Causation,
    ContextBoundary,
    EventRefs,
    EventSource,
    RunScope,
)
from capability_agent.trajectory.replay import (
    ImportedRunEvent,
    ReplayEventLike,
    SourceCoordinate,
)


def _imported_event(**overrides: object) -> ImportedRunEvent:
    draft: dict[str, object] = {
        "analysis_id": "analysis-test",
        "sequence": 1,
        "timestamp": "2026-08-14T00:00:00.000000Z",
        "event_type": "analysis.started",
        "import_previous_hash": "sha256:" + "0" * 64,
        "import_hash": "sha256:" + "1" * 64,
        "source_coordinate": {
            "path": "legacy/events.jsonl",
            "sequence": 1,
            "sha256": "a" * 64,
        },
        "source": {"kind": "observed", "integrity": "importer-integrity"},
        "payload": {"nested": {"value": 1}},
    }
    draft.update(overrides)
    return ImportedRunEvent.model_validate(draft)


def test_imported_event_freezes_payload_and_preserves_replay_protocol() -> None:
    event = _imported_event()

    assert isinstance(event, ReplayEventLike)
    assert event.payload == {"nested": {"value": 1}}
    with pytest.raises(TypeError, match="mapping is immutable"):
        event.payload["nested"] = {}  # type: ignore[index]
    with pytest.raises(TypeError, match="mapping is immutable"):
        event.payload["nested"]["value"] = 2  # type: ignore[index]


def test_imported_event_requires_importer_integrity() -> None:
    with pytest.raises(ValidationError, match="importer-integrity"):
        _imported_event(source={"kind": "observed", "integrity": "verified"})


def test_replay_support_models_are_validated() -> None:
    scope = RunScope()
    causation = Causation()
    refs = EventRefs()
    context = ContextBoundary()
    source = EventSource()
    coordinate = SourceCoordinate(
        path="legacy/events.jsonl", sequence=1, sha256="a" * 64
    )

    assert scope.turn_id is None
    assert causation.parent_sequence is None
    assert refs.produced == ()
    assert context.after_revision is None
    assert source.kind == "observed"
    assert coordinate.sequence == 1

