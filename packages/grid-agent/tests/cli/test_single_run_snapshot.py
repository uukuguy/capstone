from __future__ import annotations

import importlib
import importlib.util
import os
from pathlib import Path

import pytest


def _module():
    name = "grid_agent.compat.single_run_snapshot"
    assert importlib.util.find_spec(name) is not None, "snapshot publisher is not implemented"
    return importlib.import_module(name)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "runs" / "question"
    (root / "core").mkdir(parents=True)
    (root / "core/events.jsonl").write_bytes(b'{"event":1}\n')
    (root / "domains/grid/tool-results/nested").mkdir(parents=True)
    (root / "domains/grid/tool-results/nested/result.json").write_bytes(b'{"value":4}\n')
    (root / "domains/grid/evidence").mkdir()
    (root / "domains/grid/evidence/proof.json").write_bytes(b'{"proof":true}\n')
    (root / "turns").mkdir()
    (root / "turns/answer.json").write_bytes(b'canonical answer')
    return root


def test_snapshot_copies_bytes_to_independent_physical_files(workspace: Path) -> None:
    _module().publish_compatibility_snapshot(workspace)
    for source, target in (
        ("core/events.jsonl", "events.jsonl"),
        ("domains/grid/tool-results/nested/result.json", "tool-results/nested/result.json"),
        ("domains/grid/evidence/proof.json", "evidence/proof.json"),
    ):
        original, copy = workspace / source, workspace / target
        assert copy.read_bytes() == original.read_bytes()
        assert not copy.is_symlink()
        assert copy.stat().st_ino != original.stat().st_ino
        copy.write_bytes(b"changed copy")
        assert original.read_bytes() != copy.read_bytes()
    assert (workspace / "turns/answer.json").read_bytes() == b"canonical answer"


def test_snapshot_preserves_empty_evidence_for_a_no_tool_answer(workspace: Path) -> None:
    (workspace / "domains/grid/evidence/proof.json").unlink()
    (workspace / "domains/grid/evidence").rmdir()
    _module().publish_compatibility_snapshot(workspace)
    assert (workspace / "evidence").is_dir()
    assert list((workspace / "evidence").iterdir()) == []


@pytest.mark.parametrize("relative", ["core", "domains", "domains/grid/tool-results"])
def test_snapshot_rejects_symlinked_source_ancestors(workspace: Path, relative: str) -> None:
    module = _module()
    source = workspace / relative
    moved = source.with_name(source.name + "-original")
    source.rename(moved)
    source.symlink_to(moved, target_is_directory=True)
    with pytest.raises((OSError, ValueError)):
        module.publish_compatibility_snapshot(workspace)
    assert not (workspace / "events.jsonl").exists()


def test_snapshot_rejects_a_symlinked_workspace(workspace: Path) -> None:
    module = _module()
    original = workspace.with_name("original-question")
    workspace.rename(original)
    workspace.symlink_to(original, target_is_directory=True)
    with pytest.raises((OSError, ValueError)):
        module.publish_compatibility_snapshot(workspace)
    assert not (original / "events.jsonl").exists()


@pytest.mark.parametrize("kind", ["symlink", "fifo"])
def test_snapshot_rejects_nonregular_source_entries(workspace: Path, kind: str) -> None:
    module = _module()
    source = workspace / "domains/grid/evidence/unsafe"
    if kind == "symlink":
        source.symlink_to(workspace / "turns/answer.json")
    else:
        os.mkfifo(source)
    with pytest.raises((OSError, ValueError)):
        module.publish_compatibility_snapshot(workspace)
    assert not (workspace / "events.jsonl").exists()


def test_snapshot_never_overwrites_an_existing_legacy_target(workspace: Path) -> None:
    module = _module()
    (workspace / "events.jsonl").write_bytes(b"user-owned")
    with pytest.raises((OSError, ValueError)):
        module.publish_compatibility_snapshot(workspace)
    assert (workspace / "events.jsonl").read_bytes() == b"user-owned"


def test_snapshot_rejects_source_mutation_during_copy(workspace: Path, monkeypatch) -> None:
    module = _module()
    real_read = module.os.read
    mutated = False

    def mutate(fd, size):
        nonlocal mutated
        data = real_read(fd, size)
        if data and not mutated:
            mutated = True
            with (workspace / "core/events.jsonl").open("ab") as stream:
                stream.write(b"mutation")
        return data

    monkeypatch.setattr(module.os, "read", mutate)
    with pytest.raises((OSError, ValueError)):
        module.publish_compatibility_snapshot(workspace)
    assert not (workspace / "events.jsonl").exists()


def test_snapshot_exclusive_publish_rejects_a_target_inserted_at_rename(workspace: Path, monkeypatch) -> None:
    module = _module()
    real_rename = module._rename_exclusive

    def insert(source_fd, source_name, target_fd, target_name):
        if target_name == "events.jsonl":
            (workspace / "events.jsonl").write_bytes(b"concurrent owner")
        return real_rename(source_fd, source_name, target_fd, target_name)

    monkeypatch.setattr(module, "_rename_exclusive", insert)
    with pytest.raises(OSError):
        module.publish_compatibility_snapshot(workspace)
    assert (workspace / "events.jsonl").read_bytes() == b"concurrent owner"


def test_snapshot_pinned_destination_cannot_write_through_a_replaced_parent(workspace: Path, tmp_path: Path, monkeypatch) -> None:
    module = _module()
    outside = tmp_path / "outside"
    outside.mkdir()
    real_rename = module._rename_exclusive
    replaced = False

    def replace_parent(source_fd, source_name, target_fd, target_name):
        nonlocal replaced
        if not replaced:
            replaced = True
            workspace.rename(workspace.with_name("original-question"))
            workspace.symlink_to(outside, target_is_directory=True)
        return real_rename(source_fd, source_name, target_fd, target_name)

    monkeypatch.setattr(module, "_rename_exclusive", replace_parent)
    with pytest.raises((OSError, ValueError)):
        module.publish_compatibility_snapshot(workspace)
    assert list(outside.iterdir()) == []


def test_snapshot_interruption_does_not_publish_or_modify_primary_answer(workspace: Path, monkeypatch) -> None:
    module = _module()

    def interrupt(_fd):
        raise KeyboardInterrupt()

    monkeypatch.setattr(module.os, "fsync", interrupt)
    with pytest.raises(KeyboardInterrupt):
        module.publish_compatibility_snapshot(workspace)
    assert not (workspace / "events.jsonl").exists()
    assert (workspace / "turns/answer.json").read_bytes() == b"canonical answer"


def test_snapshot_mid_publish_failure_preserves_primary_answer(workspace: Path, monkeypatch) -> None:
    module = _module()
    real_rename = module._rename_exclusive

    def fail_second(source_fd, source_name, target_fd, target_name):
        if target_name == "tool-results":
            raise OSError("injected publish failure")
        return real_rename(source_fd, source_name, target_fd, target_name)

    monkeypatch.setattr(module, "_rename_exclusive", fail_second)
    with pytest.raises(OSError):
        module.publish_compatibility_snapshot(workspace)
    assert (workspace / "events.jsonl").read_bytes() == (workspace / "core/events.jsonl").read_bytes()
    assert (workspace / "turns/answer.json").read_bytes() == b"canonical answer"


@pytest.mark.parametrize("relative", ["events.jsonl", "tool-results/nested/result.json"])
def test_snapshot_rejects_staged_object_replacement_before_publish(workspace: Path, monkeypatch, relative: str) -> None:
    module = _module()
    real_fsync = module.os.fsync
    replaced = False

    def replace_staged(descriptor):
        nonlocal replaced
        real_fsync(descriptor)
        if replaced:
            return
        try:
            names = os.listdir(descriptor)
        except NotADirectoryError:
            return
        if not {"events.jsonl", "tool-results", "evidence"}.issubset(names):
            return
        replaced = True
        stage = next(workspace.glob(".single-run-snapshot-*"))
        target = stage / relative
        target.unlink()
        target.symlink_to(workspace / "turns/answer.json")

    monkeypatch.setattr(module.os, "fsync", replace_staged)
    with pytest.raises((OSError, ValueError)):
        module.publish_compatibility_snapshot(workspace)
    assert not (workspace / "events.jsonl").is_symlink()


def test_snapshot_detects_replacement_inside_exclusive_publication(workspace: Path, monkeypatch) -> None:
    module = _module()
    real_rename = module._rename_exclusive

    def replace_leaf(source_fd, source_name, target_fd, target_name):
        if target_name == "events.jsonl":
            os.unlink(source_name, dir_fd=source_fd)
            os.symlink(workspace / "turns/answer.json", source_name, dir_fd=source_fd)
        return real_rename(source_fd, source_name, target_fd, target_name)

    monkeypatch.setattr(module, "_rename_exclusive", replace_leaf)
    with pytest.raises((OSError, ValueError)):
        module.publish_compatibility_snapshot(workspace)
    assert (workspace / "turns/answer.json").read_bytes() == b"canonical answer"
