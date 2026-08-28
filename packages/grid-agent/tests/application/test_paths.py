from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest

from grid_agent.application import workspace as workspace_module
from grid_agent.application.paths import ProjectPaths
from grid_agent.application.workspace import (
    RunWorkspace,
    RunWorkspaceExistsError,
    RunWorkspaceLeaseError,
    RunWorkspacePathError,
)


def test_project_paths_separate_internal_state_from_auditable_runs(tmp_path: Path) -> None:
    paths = ProjectPaths.from_root(tmp_path)

    assert paths.runs_dir == tmp_path / "runs"
    assert paths.internal_dir == tmp_path / ".grid-agent"
    assert paths.pi_runtime_dir == tmp_path / ".grid-agent/runtime/pi"
    assert paths.pi_agent_dir == tmp_path / ".grid-agent/auth/pi"
    assert paths.sessions_dir == tmp_path / ".grid-agent/sessions"
    assert paths.trajectory_acks_dir == tmp_path / ".grid-agent/trajectory-acks"
    assert paths.trajectory_acks_path("analysis-test") == (
        tmp_path / ".grid-agent/trajectory-acks/analysis-test"
    )
    assert paths.runtime_lock == tmp_path / "configs/runtime/pi-runtime.lock.json"


def test_run_workspace_uses_operator_visible_layout(tmp_path: Path) -> None:
    workspace = RunWorkspace.create(ProjectPaths.from_root(tmp_path).runs_dir, "q-test")

    assert workspace.root_path == tmp_path / "runs/q-test"
    assert workspace.tool_results_path == tmp_path / "runs/q-test/tool-results"
    assert workspace.evidence_path == tmp_path / "runs/q-test/evidence"
    assert workspace.answer_path == tmp_path / "runs/q-test/answer.json"
    workspace.close()


def test_same_question_id_lease_fails_closed_without_overwriting_evidence(
    tmp_path: Path,
) -> None:
    runs_root = tmp_path / "runs"
    first = RunWorkspace.create(runs_root, "same-question")
    marker = first.evidence_path / "current.json"
    marker.write_text('{"owner":"first"}\n', encoding="utf-8")

    try:
        with pytest.raises(RunWorkspaceLeaseError, match="already active"):
            RunWorkspace.create(runs_root, "same-question")
        assert marker.read_text(encoding="utf-8") == '{"owner":"first"}\n'
    finally:
        first.close()

    with pytest.raises(RunWorkspaceExistsError, match="already exists"):
        RunWorkspace.create(runs_root, "same-question")
    assert marker.read_text(encoding="utf-8") == '{"owner":"first"}\n'


def test_same_question_id_lease_is_enforced_across_processes(tmp_path: Path) -> None:
    runs_root = tmp_path / "runs"
    first = RunWorkspace.create(runs_root, "cross-process")
    script = """
from pathlib import Path
from grid_agent.application.workspace import RunWorkspace, RunWorkspaceLeaseError
try:
    RunWorkspace.create(Path(__import__('sys').argv[1]), 'cross-process')
except RunWorkspaceLeaseError:
    raise SystemExit(73)
raise SystemExit(0)
"""
    try:
        completed = subprocess.run(
            [sys.executable, "-c", script, str(runs_root)],
            check=False,
        )
        assert completed.returncode == 73
    finally:
        first.close()


@pytest.mark.parametrize(
    "run_id",
    ("../escape", "/tmp/escape", "nested/name", r"nested\name", ".hidden"),
)
def test_run_workspace_rejects_unsafe_run_ids(tmp_path: Path, run_id: str) -> None:
    runs_root = tmp_path / "runs"

    with pytest.raises(ValueError, match="safe portable basename"):
        RunWorkspace.create(runs_root, run_id)

    assert not (tmp_path / "escape").exists()


def test_run_workspace_rejects_stale_run_directory_without_reusing_evidence(
    tmp_path: Path,
) -> None:
    stale = tmp_path / "runs/stale/evidence"
    stale.mkdir(parents=True)
    marker = stale / "old.json"
    marker.write_text('{"run":"old"}\n', encoding="utf-8")

    with pytest.raises(RunWorkspaceExistsError, match="already exists"):
        RunWorkspace.create(tmp_path / "runs", "stale")

    assert marker.read_text(encoding="utf-8") == '{"run":"old"}\n'


def test_run_workspace_rejects_symlinked_runs_root(tmp_path: Path) -> None:
    external = tmp_path / "external"
    external.mkdir()
    runs_root = tmp_path / "runs"
    runs_root.symlink_to(external, target_is_directory=True)

    with pytest.raises(RunWorkspacePathError, match="runs root"):
        RunWorkspace.create(runs_root, "q-safe")

    assert not (external / "q-safe").exists()


def test_run_workspace_rejects_symlinked_run_leaf(tmp_path: Path) -> None:
    external = tmp_path / "external"
    external.mkdir()
    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    (runs_root / "q-safe").symlink_to(external, target_is_directory=True)

    with pytest.raises(RunWorkspacePathError, match="run workspace"):
        RunWorkspace.create(runs_root, "q-safe")

    assert list(external.iterdir()) == []


def test_run_workspace_rejects_symlinked_internal_state_parent_without_external_writes(
    tmp_path: Path,
) -> None:
    external = tmp_path / "external"
    external.mkdir()
    (tmp_path / ".grid-agent").symlink_to(external, target_is_directory=True)

    with pytest.raises(RunWorkspacePathError, match="internal state"):
        RunWorkspace.create(tmp_path / "runs", "q-safe")

    assert list(external.iterdir()) == []


def test_run_workspace_rejects_symlinked_lease_directory_without_external_writes(
    tmp_path: Path,
) -> None:
    external = tmp_path / "external"
    external.mkdir()
    internal = tmp_path / ".grid-agent"
    internal.mkdir()
    (internal / "run-leases").symlink_to(external, target_is_directory=True)

    with pytest.raises(RunWorkspacePathError, match="run lease directory"):
        RunWorkspace.create(tmp_path / "runs", "q-safe")

    assert list(external.iterdir()) == []


@pytest.mark.parametrize("exchange_component", (".grid-agent", "run-leases"))
def test_run_workspace_rejects_lease_directory_exchange_after_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exchange_component: str,
) -> None:
    internal = tmp_path / ".grid-agent"
    lease_directory = internal / "run-leases"
    lease_directory.mkdir(parents=True)
    external = tmp_path / "external"
    external.mkdir()
    detached = tmp_path / f"detached-{exchange_component.lstrip('.')}"
    real_open = workspace_module.os.open
    exchanged = False

    def exchange_after_open(
        path: Any,
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal exchanged
        descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
        path_name = str(path)
        is_current_full_path_open = Path(path_name) == lease_directory
        is_new_component_open = path_name == exchange_component
        if not exchanged and (is_current_full_path_open or is_new_component_open):
            exchanged = True
            target = internal if exchange_component == ".grid-agent" else lease_directory
            target.rename(detached)
            target.symlink_to(external, target_is_directory=True)
        return descriptor

    monkeypatch.setattr(workspace_module.os, "open", exchange_after_open)

    with pytest.raises(RunWorkspacePathError, match="named binding changed"):
        RunWorkspace.create(tmp_path / "runs", "q-safe")

    assert exchanged
    assert list(external.iterdir()) == []
