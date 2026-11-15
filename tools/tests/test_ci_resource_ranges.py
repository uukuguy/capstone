import json
from pathlib import Path

from tools.ci_scope import classify


def test_resource_range_gate_is_focused():
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root / 'configs/development/resource-ranges-gate.json').read_text())
    paths = manifest['paths']
    assert classify(paths) == 'resource-ranges'
    assert classify(paths, target='main') == 'release'
    assert classify(paths, release=True) == 'release'
    assert classify(paths + ['packages/grid-simulator/src/grid_simulator/engine.py']) != 'resource-ranges'
    assert classify(paths + ['packages/capstone-agent/src/capstone_agent/intent_runtime.py']) != 'resource-ranges'
    assert classify([p for p in paths if p not in manifest['anchors']]) != 'resource-ranges'
