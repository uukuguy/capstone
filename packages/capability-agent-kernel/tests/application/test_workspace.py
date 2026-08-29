from __future__ import annotations

from pathlib import Path

import pytest

from capability_agent.application.workspace import (
    ApplicationWorkspace,
    WorkspaceError,
)


def test_workspace_creates_only_declared_portable_domain_layout(
    tmp_path: Path,
) -> None:
    workspace = ApplicationWorkspace.create(
        tmp_path / "runs",
        run_id="run-1",
        binding_ids=("inventory", "grid"),
    )

    assert workspace.root == tmp_path / "runs/run-1"
    assert workspace.root_path == workspace.root
    assert {
        path.relative_to(workspace.root).as_posix()
        for path in workspace.root.rglob("*")
        if path.is_dir()
    } >= {
        "core",
        "domains",
        "domains/grid",
        "domains/grid/runtime",
        "domains/grid/artifacts",
        "domains/grid/tool-results",
        "domains/inventory",
        "domains/inventory/runtime",
        "domains/inventory/artifacts",
        "domains/inventory/tool-results",
        "turns",
        "output",
    }
    assert workspace.context_snapshot_path == workspace.root / "core/context.json"
    assert workspace.context_events_path == workspace.root / "core/context-events.jsonl"
    assert workspace.events_path == workspace.root / "core/events.jsonl"
    assert workspace.artifacts_path == workspace.root / "core/artifacts.jsonl"
    assert workspace.domain_path("grid") == workspace.root / "domains/grid"
    assert not (workspace.root / "domains/undeclared").exists()


def test_workspace_creation_is_exclusive(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    ApplicationWorkspace.create(runs, run_id="run-1", binding_ids=("grid",))
    with pytest.raises(WorkspaceError, match="already exists"):
        ApplicationWorkspace.create(runs, run_id="run-1", binding_ids=("grid",))


@pytest.mark.parametrize(
    "unsafe_id",
    ["", ".", "..", "../outside", "/absolute", "nested/id", "nested\\id", "Upper", "under_score", "trailing-", "éxternal"],
)
def test_workspace_rejects_nonportable_run_and_binding_ids(
    tmp_path: Path,
    unsafe_id: str,
) -> None:
    with pytest.raises(WorkspaceError, match="portable"):
        ApplicationWorkspace.create(tmp_path / "runs", run_id=unsafe_id)
    with pytest.raises(WorkspaceError, match="portable"):
        ApplicationWorkspace.create(
            tmp_path / "runs",
            run_id="run-1",
            binding_ids=(unsafe_id,),
        )


def test_workspace_rejects_symlinked_root_and_unknown_binding(tmp_path: Path) -> None:
    actual = tmp_path / "actual"
    actual.mkdir()
    link = tmp_path / "runs-link"
    link.symlink_to(actual, target_is_directory=True)

    with pytest.raises(WorkspaceError, match="symlink"):
        ApplicationWorkspace.create(link, run_id="run-1")

    workspace = ApplicationWorkspace.create(
        tmp_path / "runs",
        run_id="run-2",
        binding_ids=("grid",),
    )
    with pytest.raises(WorkspaceError, match="declared"):
        workspace.domain_path("inventory")
