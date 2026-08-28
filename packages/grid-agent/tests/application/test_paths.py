from pathlib import Path
import subprocess
import sys

import pytest

from grid_agent.application.paths import ProjectPaths
from grid_agent.application.workspace import RunWorkspace, RunWorkspaceLeaseError


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

    successor = RunWorkspace.create(runs_root, "same-question")
    successor.close()


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
