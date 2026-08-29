from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import capability_agent.application.context_store as context_store_module
from capability_agent.application.context_models import ContextEvent, ContextEventDraft
from capability_agent.application.context_store import (
    ApplicationContextStore,
    ContextStoreError,
)
from capability_agent.application.workspace import ApplicationWorkspace


@pytest.fixture
def workspace(tmp_path: Path) -> ApplicationWorkspace:
    return ApplicationWorkspace.create(
        tmp_path / "runs",
        run_id="run-1",
        binding_ids=("grid", "inventory"),
    )


def test_initialize_append_replay_and_materialized_snapshot(
    workspace: ApplicationWorkspace,
) -> None:
    store = ApplicationContextStore.initialize(
        workspace,
        domains={
            "grid": "pandapower-analysis-state/1.0",
            "inventory": "inventory-state/1.0",
        },
        core={"input": {"question_count": 1}},
    )
    event = store.append(
        ContextEventDraft(
            event_type="domain.state.projected",
            binding_id="grid",
            payload={
                "schema_id": "pandapower-analysis-state/1.0",
                "previous_revision": 0,
                "state": {"active_context_ref": "context:sha256:" + "a" * 64},
            },
        )
    )

    assert event.sequence == 2
    assert store.snapshot.domains["grid"].revision == 1
    assert store.verify_materialized_snapshot() == store.snapshot
    assert ApplicationContextStore.replay(workspace.context_events_path) == store.snapshot

    lines = workspace.context_events_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[-1])["next_state_hash"] == store.snapshot.state_hash


def test_append_rejects_transition_without_changing_snapshot(
    workspace: ApplicationWorkspace,
) -> None:
    store = ApplicationContextStore.initialize(
        workspace,
        domains={
            "grid": "pandapower-analysis-state/1.0",
            "inventory": "inventory-state/1.0",
        },
    )
    before = store.snapshot

    with pytest.raises(ContextStoreError, match="unknown binding"):
        store.append(
            ContextEventDraft(
                event_type="domain.state.projected",
                binding_id="missing",
                payload={
                    "schema_id": "pandapower-analysis-state/1.0",
                    "previous_revision": 0,
                    "state": {},
                },
            )
        )

    assert store.snapshot == before
    assert len(workspace.context_events_path.read_text(encoding="utf-8").splitlines()) == 1


def test_replay_detects_hash_tampering_and_snapshot_mismatch(
    workspace: ApplicationWorkspace,
) -> None:
    store = ApplicationContextStore.initialize(
        workspace,
        domains={
            "grid": "pandapower-analysis-state/1.0",
            "inventory": "inventory-state/1.0",
        },
    )
    store.append(
        ContextEventDraft(
            event_type="diagnostic.recorded",
            payload={"message": "diagnostic"},
        )
    )

    original = workspace.context_events_path.read_text(encoding="utf-8")
    records = [json.loads(line) for line in original.splitlines()]
    records[-1]["next_state_hash"] = "0" * 64
    workspace.context_events_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    with pytest.raises(ContextStoreError, match="state hash"):
        ApplicationContextStore.replay(workspace.context_events_path)

    workspace.context_events_path.write_text(original, encoding="utf-8")
    workspace.context_snapshot_path.write_text(
        json.dumps({"schema_version": "application-context/1.0"}),
        encoding="utf-8",
    )
    with pytest.raises(ContextStoreError, match="snapshot"):
        store.verify_materialized_snapshot()


def test_append_fsyncs_ledger_and_atomically_replaces_snapshot(
    workspace: ApplicationWorkspace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fsync_calls: list[int] = []
    replace_calls: list[tuple[Path, Path]] = []
    real_fsync = os.fsync
    real_replace = os.replace

    def recording_fsync(descriptor: int) -> None:
        fsync_calls.append(descriptor)
        real_fsync(descriptor)

    def recording_replace(
        source: str | os.PathLike[str], destination: str | os.PathLike[str]
    ) -> None:
        replace_calls.append((Path(source), Path(destination)))
        real_replace(source, destination)

    monkeypatch.setattr(os, "fsync", recording_fsync)
    monkeypatch.setattr(os, "replace", recording_replace)
    store = ApplicationContextStore.initialize(
        workspace,
        domains={
            "grid": "pandapower-analysis-state/1.0",
            "inventory": "inventory-state/1.0",
        },
    )
    store.append(ContextEventDraft(event_type="diagnostic.recorded", payload={"message": "x"}))

    assert fsync_calls
    assert replace_calls
    assert replace_calls[-1][1] == workspace.context_snapshot_path


def test_replay_rejects_missing_or_empty_ledger(tmp_path: Path) -> None:
    path = tmp_path / "context-events.jsonl"
    with pytest.raises(ContextStoreError, match="does not exist"):
        ApplicationContextStore.replay(path)
    path.touch()
    with pytest.raises(ContextStoreError, match="empty"):
        ApplicationContextStore.replay(path)


def test_durable_context_events_reject_nonportable_run_ids() -> None:
    with pytest.raises(ValueError, match="portable"):
        ContextEvent(
            run_id="../outside",
            sequence=1,
            event_type="analysis.started",
            payload={},
            previous_revision=0,
            previous_state_hash="a" * 64,
            next_revision=1,
            next_state_hash="b" * 64,
        )


def test_persistence_failure_is_sanitized_and_store_fails_closed(
    workspace: ApplicationWorkspace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ApplicationContextStore.initialize(
        workspace,
        domains={
            "grid": "pandapower-analysis-state/1.0",
            "inventory": "inventory-state/1.0",
        },
    )

    def fail_replace(source: Path, destination: Path) -> None:
        raise RuntimeError("backend secret=/should-not-escape")

    monkeypatch.setattr(context_store_module, "_replace_snapshot", fail_replace)

    with pytest.raises(ContextStoreError, match="persistence failed") as first:
        store.append(
            ContextEventDraft(
                event_type="diagnostic.recorded",
                payload={"message": "diagnostic"},
            )
        )
    assert "secret" not in str(first.value)

    with pytest.raises(ContextStoreError, match="unavailable"):
        store.append(
            ContextEventDraft(
                event_type="diagnostic.recorded",
                payload={"message": "later"},
            )
        )
