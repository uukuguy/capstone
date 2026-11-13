import json
from pathlib import Path

from tools.ci_scope import classify


def test_retirement_gate_covers_only_reviewed_paths_and_preserves_release():
    root = Path(__file__).resolve().parents[2]
    paths = json.loads((root / "configs/development/architecture-retirement-gate.json").read_text())["paths"]
    assert classify(paths) == "architecture-retirement"
    assert classify(paths + ["packages/grid-simulator/src/grid_simulator/engine.py"]) == "product"
    assert classify(paths, target="main") == "release"
