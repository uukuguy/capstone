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


def test_streamed_instruction_is_durable_and_ordered(
    workspace: ApplicationWorkspace,
) -> None:
    store = ApplicationContextStore.initialize(
        workspace,
        core={"input": {"application_id": "fixture", "questions": []}},
    )
    store.append(ContextEventDraft(
        event_type="application.instruction.accepted",
        payload={"ordinal": 1, "instruction": "first"},
    ))

    assert list(store.snapshot.core.input["questions"]) == ["first"]
    assert ApplicationContextStore.replay(workspace.context_events_path) == store.snapshot
    with pytest.raises(ContextStoreError, match="instruction ordinal"):
        store.append(ContextEventDraft(
            event_type="application.instruction.accepted",
            payload={"ordinal": 1, "instruction": "duplicate"},
        ))


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


def test_replay_events_rejects_ledger_replaced_during_read(
    workspace: ApplicationWorkspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ApplicationContextStore.initialize(workspace)
    replacement = workspace.context_events_path.with_name("replacement.jsonl")
    replacement.write_bytes(workspace.context_events_path.read_bytes())
    real_fstat = context_store_module.os.fstat
    calls = 0

    def replace_after_open(descriptor: int):
        nonlocal calls
        calls += 1
        if calls == 1:
            replacement.replace(workspace.context_events_path)
        return real_fstat(descriptor)

    monkeypatch.setattr(context_store_module.os, "fstat", replace_after_open)
    with pytest.raises(ContextStoreError, match="cannot be read"):
        ApplicationContextStore.replay_events(workspace)


def test_replay_events_reads_a_relative_ledger_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = ApplicationWorkspace.create(
        tmp_path / "relative" / "runs", run_id="relative-run"
    )
    store = ApplicationContextStore.initialize(workspace)
    monkeypatch.chdir(tmp_path)
    relative_ledger = workspace.context_events_path.relative_to(tmp_path)

    replayed, events = ApplicationContextStore.replay_events(relative_ledger)

    assert replayed == store.snapshot
    assert tuple(event.event_type for event in events) == ("analysis.started",)


def test_replay_events_rejects_a_symlinked_parent_directory(
    workspace: ApplicationWorkspace,
) -> None:
    ApplicationContextStore.initialize(workspace)
    original_core = workspace.root / "original-core"
    workspace.core_path.rename(original_core)
    workspace.core_path.symlink_to(original_core, target_is_directory=True)

    with pytest.raises(ContextStoreError, match="cannot be read"):
        ApplicationContextStore.replay_events(workspace)


def test_replay_events_rejects_named_ledger_metadata_changed_after_read(
    workspace: ApplicationWorkspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    ApplicationContextStore.initialize(workspace)
    real_stat = context_store_module.os.stat
    mutated = False

    def mutate_before_named_identity(*args: object, **kwargs: object):
        nonlocal mutated
        if not mutated:
            mutated = True
            with workspace.context_events_path.open("ab") as stream:
                stream.write(b"tampered-after-read")
        return real_stat(*args, **kwargs)

    monkeypatch.setattr(context_store_module.os, "stat", mutate_before_named_identity)

    with pytest.raises(ContextStoreError, match="cannot be read"):
        ApplicationContextStore.replay_events(workspace)


@pytest.mark.parametrize("target", ["ledger", "snapshot"])
@pytest.mark.parametrize("replacement", [False, True])
def test_append_fails_closed_when_persisted_destination_is_removed_or_replaced(
    workspace: ApplicationWorkspace,
    target: str,
    replacement: bool,
) -> None:
    store = ApplicationContextStore.initialize(
        workspace,
        domains={
            "grid": "pandapower-analysis-state/1.0",
            "inventory": "inventory-state/1.0",
        },
    )
    destination = (
        workspace.context_events_path
        if target == "ledger"
        else workspace.context_snapshot_path
    )
    before = store.snapshot
    before_snapshot = workspace.context_snapshot_path.read_bytes()
    if replacement:
        replacement_path = destination.with_name(f"{destination.name}.replacement")
        replacement_path.write_bytes(destination.read_bytes())
        os.replace(replacement_path, destination)
    else:
        destination.unlink()

    with pytest.raises(ContextStoreError):
        store.append(
            ContextEventDraft(
                event_type="diagnostic.recorded",
                payload={"message": "must not persist"},
            )
        )

    assert store.snapshot == before
    if target == "ledger":
        assert workspace.context_snapshot_path.read_bytes() == before_snapshot
    elif replacement:
        assert destination.read_bytes() == before_snapshot
    else:
        assert not destination.exists()
    with pytest.raises(ContextStoreError, match="unavailable"):
        store.append(
            ContextEventDraft(
                event_type="diagnostic.recorded",
                payload={"message": "must remain unavailable"},
            )
        )


def test_replay_rejects_a_non_empty_ledger_without_a_final_newline(
    workspace: ApplicationWorkspace,
) -> None:
    ApplicationContextStore.initialize(
        workspace,
        domains={
            "grid": "pandapower-analysis-state/1.0",
            "inventory": "inventory-state/1.0",
        },
    )
    raw = workspace.context_events_path.read_bytes()
    assert raw.endswith(b"\n")
    workspace.context_events_path.write_bytes(raw[:-1])

    with pytest.raises(ContextStoreError, match="newline"):
        ApplicationContextStore.replay(workspace.context_events_path)


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


def test_append_many_empty_or_invalid_drafts_do_not_touch_durable_state(
    workspace: ApplicationWorkspace,
) -> None:
    store = ApplicationContextStore.initialize(
        workspace,
        domains={
            "grid": "pandapower-analysis-state/1.0",
            "inventory": "inventory-state/1.0",
        },
    )
    before_snapshot = store.snapshot
    before_ledger = workspace.context_events_path.read_bytes()
    before_materialized = workspace.context_snapshot_path.read_bytes()

    assert store.append_many(()) == ()
    with pytest.raises(ContextStoreError, match="drafts"):
        store.append_many((object(),))  # type: ignore[arg-type]

    assert store.snapshot == before_snapshot
    assert workspace.context_events_path.read_bytes() == before_ledger
    assert workspace.context_snapshot_path.read_bytes() == before_materialized
    assert not (workspace.core_path / ".context-transaction.json").exists()


@pytest.mark.parametrize("after_snapshot", [False, True])
def test_append_many_recovers_a_pending_transaction_after_interruption(
    workspace: ApplicationWorkspace,
    monkeypatch: pytest.MonkeyPatch,
    after_snapshot: bool,
) -> None:
    store = ApplicationContextStore.initialize(
        workspace,
        domains={
            "grid": "pandapower-analysis-state/1.0",
            "inventory": "inventory-state/1.0",
        },
    )
    before = store.snapshot
    draft = ContextEventDraft(
        event_type="diagnostic.recorded", payload={"message": "recover me"}
    )
    real_replace_snapshot = context_store_module._replace_snapshot

    def interrupt_snapshot(source: Path, destination: Path) -> None:
        if after_snapshot:
            real_replace_snapshot(source, destination)
        raise KeyboardInterrupt("simulated process interruption")

    def interrupt_rollback(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise KeyboardInterrupt("simulated process interruption")

    monkeypatch.setattr(
        context_store_module, "_replace_snapshot", interrupt_snapshot
    )
    monkeypatch.setattr(
        context_store_module, "_rollback_transaction", interrupt_rollback
    )

    with pytest.raises(KeyboardInterrupt):
        store.append_many((draft,))

    marker = workspace.core_path / ".context-transaction.json"
    assert marker.is_file()

    recovered = ApplicationContextStore(workspace, before)
    assert recovered.snapshot.revision == before.revision + 1
    assert ApplicationContextStore.replay(workspace.context_events_path) == recovered.snapshot
    assert recovered.verify_materialized_snapshot() == recovered.snapshot
    assert not marker.exists()
    assert not list(workspace.core_path.glob(".*.tmp"))
