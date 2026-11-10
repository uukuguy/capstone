"""Frozen inputs remain usable after source files change or disappear."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile

SCRIPT = Path(__file__).parents[1] / 'native_presentation_library.py'
TEMPLATE = Path(__file__).parents[1] / 'presentation-templates/state-grid.pptx'


def run(root, *args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=root, capture_output=True, text=True)


def test_render_and_rerender_keep_frozen_content_and_exact_dependencies(tmp_path):
    document = {'schema': 'capstone-presentation/1', 'title': 'Saved comparison',
        'slides': [{'title': 'Exact values', 'blocks': [
            {'type': 'table', 'csv': 'values.csv', 'max_rows': 5}]}]}
    (tmp_path / 'content.json').write_text(json.dumps(document))
    (tmp_path / 'values.csv').write_text('name,value\nalpha,7\n')
    args = ['--template', str(TEMPLATE), '--template-sha256', hashlib.sha256(TEMPLATE.read_bytes()).hexdigest()]
    first = run(tmp_path, '--spec', 'content.json', '--output', 'first.pptx', *args)
    assert first.returncode == 0, first.stderr
    receipt = json.loads(first.stdout)
    assert receipt['pdf']['status'] == 'not_requested'
    bundle = tmp_path / receipt['bundle']
    with ZipFile(bundle) as archive:
        assert archive.read('sources/values.csv') == b'name,value\nalpha,7\n'
        assert json.loads(archive.read('content.json')) == document
    (tmp_path / 'values.csv').unlink()
    (tmp_path / 'content.json').write_text('{}')
    again = run(tmp_path, '--bundle', receipt['bundle'], '--output', 'second.pptx', *args)
    assert again.returncode == 0, again.stderr
    assert json.loads(again.stdout)['content_sha256'] == receipt['content_sha256']
    assert (tmp_path / 'first.pptx').exists() and (tmp_path / 'second.pptx').exists()
    roles = json.loads((tmp_path / '.capstone-products.json').read_text())['products']
    assert {p['path'] for p in roles} >= {'first.pptx', 'second.pptx', 'first.source.zip', 'second.source.zip'}


def test_corrupt_bundle_cannot_replace_or_create_outputs(tmp_path):
    with ZipFile(tmp_path / 'bad.zip', 'w') as archive:
        archive.writestr('content.json', '{}')
        archive.writestr('manifest.json', json.dumps({'schema': 'capstone-presentation-source/1',
            'content_sha256': '0' * 64, 'sources': {}}))
    result = run(tmp_path, '--bundle', 'bad.zip', '--output', 'bad.pptx',
        '--template', str(TEMPLATE), '--template-sha256', hashlib.sha256(TEMPLATE.read_bytes()).hexdigest())
    assert result.returncode == 2
    assert not (tmp_path / 'bad.pptx').exists()


def test_layout_failure_returns_actionable_structured_diagnostic(tmp_path):
    (tmp_path / 'content.json').write_text(json.dumps({'schema': 'capstone-presentation/2', 'title': 'Saved',
        'slides': [{'title': 'Missing argument', 'blocks': []}]}))
    result = run(tmp_path, '--spec', 'content.json', '--output', 'rejected.pptx',
        '--template', str(TEMPLATE), '--template-sha256', hashlib.sha256(TEMPLATE.read_bytes()).hexdigest())
    assert result.returncode == 2
    failure = json.loads(result.stderr)
    assert failure['schema'] == 'capstone-presentation-render-error/1'
    assert 'explanation' in failure['message']
    assert failure['diagnostic']['location'] == 'slides[0].argument'
    assert not (tmp_path / 'rejected.pptx').exists()


def test_digest_change_and_output_collision_preserve_existing_products(tmp_path):
    (tmp_path / 'content.json').write_text(json.dumps({'schema': 'capstone-presentation/1', 'title': 'Saved', 'slides': []}))
    (tmp_path / 'kept.pptx').write_bytes(b'old')
    result = run(tmp_path, '--spec', 'content.json', '--output', 'kept.pptx',
        '--template', str(TEMPLATE), '--template-sha256', '0' * 64)
    assert result.returncode == 2
    assert (tmp_path / 'kept.pptx').read_bytes() == b'old'
    assert not (tmp_path / 'kept.source.zip').exists()
