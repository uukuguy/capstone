import json
import subprocess
from pathlib import Path

from tools.ci_scope import classify


def test_retirement_gate_covers_only_reviewed_paths_and_preserves_release():
    root = Path(__file__).resolve().parents[2]
    paths = json.loads((root / "configs/development/architecture-retirement-gate.json").read_text())["paths"]
    assert classify(paths) == "architecture-retirement"
    assert classify(paths + ["packages/grid-simulator/src/grid_simulator/engine.py"]) == "product"
    assert classify(paths, target="main") == "release"


def test_retirement_manifest_includes_deleted_names_of_migrated_files():
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root / "configs/development/architecture-retirement-gate.json").read_text())
    # The CI entry point disables rename detection. Each migrated file therefore
    # contributes both its retired name and its new owning package name.
    retired = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", "2c4ac72e440b535c40621525ee929fe37cefb9d3", "--", "packages/grid-agent"],
        cwd=root, text=True,
    ).splitlines()
    assert retired
    assert set(retired).issubset(manifest["paths"])


def test_retirement_ci_prepares_pinned_sdk_before_sdk_consumers():
    root = Path(__file__).resolve().parents[2]
    workflow = (root / ".github/workflows/verify.yml").read_text()
    setup = workflow.split("- name: Set up architecture retirement consumers", 1)[1].split("- name:", 1)[0]
    assert "make install-pi" in setup
