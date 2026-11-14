import json
from pathlib import Path
from tools.ci_scope import classify


def test_reference_gate_is_bounded_and_preserves_release_scope():
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root/'configs/development/product-references-gate.json').read_text())
    paths = manifest['paths']
    assert classify(paths) == 'product-references'
    assert classify(paths + ['packages/capstone-agent/tests/test_thread_products.py']) == 'product-references'
    assert classify(paths, target='main') == 'release'
    assert classify(paths + ['packages/grid-simulator/src/grid_simulator/engine.py']) != 'product-references'
    assert classify([p for p in paths if p not in manifest['anchors']]) != 'product-references'


def test_reference_gate_requires_database_and_runs_direct_consumers():
    root = Path(__file__).resolve().parents[2]
    workflow = (root/'.github/workflows/verify.yml').read_text()
    assert workflow.index('run: make doctor') < workflow.index('- name: Verify product references with disposable PostgreSQL')
    script = (root/'tools/test_product_references.sh').read_text()
    assert 'CAPSTONE_TEST_DATABASE_URL:?' in script
    for name in ('test_product_index_service.py', 'test_thread_products.py', 'test_thread_input.py', 'test_cli.py', 'test_hosting.py', 'ProductParagraphPicker.test.tsx', 'threadProductsTransport.test.ts'):
        assert name in script
