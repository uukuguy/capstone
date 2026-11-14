import json
from pathlib import Path
from tools.ci_scope import classify


def test_adoption_gate_is_focused_and_release_is_preserved():
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root/'configs/development/product-adoption-gate.json').read_text())
    assert classify(manifest['paths']) == 'product-adoption'
    assert classify(manifest['paths'], target='main') == 'release'
    assert classify(manifest['paths']+['packages/grid-simulator/src/grid_simulator/engine.py']) != 'product-adoption'
    assert classify([p for p in manifest['paths'] if p not in manifest['anchors']]) != 'product-adoption'
