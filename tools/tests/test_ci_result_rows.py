import json
from pathlib import Path
from tools.ci_scope import classify


def test_result_row_gate_is_bounded():
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root/'configs/development/result-rows-gate.json').read_text())
    assert classify(manifest['paths']) == 'result-rows'
    assert classify(manifest['paths'], target='main') == 'release'
    assert classify(manifest['paths']+['packages/grid-simulator/src/grid_simulator/engine.py']) != 'result-rows'
    assert classify([p for p in manifest['paths'] if p not in manifest['anchors']]) != 'result-rows'
