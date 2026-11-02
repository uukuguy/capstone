"""Real standard-library report rendering and workspace confinement."""
import base64
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).parents[2] / 'tools/native_report.py'


def run(directory, spec, *, output='report.html'):
    (directory / 'report.json').write_text(json.dumps(spec, ensure_ascii=False))
    return subprocess.run([sys.executable, str(SCRIPT), '--spec', 'report.json', '--output', output],
        cwd=directory, capture_output=True, text=True)


def report(blocks):
    return {'title': '通用研究报告', 'subtitle': '模拟资料',
        'sections': [{'id': 'findings', 'title': '发现与限制', 'blocks': blocks}]}


def test_csv_strings_escape_and_receipt_bind_exact_sources(tmp_path):
    with (tmp_path / 'metrics.csv').open('w', newline='') as stream:
        csv.writer(stream).writerows([['name', 'ratio', 'value'], ['甲省', '0.1250%', '001.2300'],
            ['<script>alert(1)</script>', '未记录', '1,234']])
    spec = report([{'type': 'paragraph', 'text': '<b>不作数值重算</b>'},
        {'type': 'bullets', 'items': ['保留原始口径', '不证明因果']},
        {'type': 'table', 'csv': 'metrics.csv', 'columns': ['name', 'ratio', 'value'], 'caption': '源数据'}])
    result = run(tmp_path, spec)
    assert result.returncode == 0, result.stderr
    html = (tmp_path / 'report.html').read_text()
    for value in ('0.1250%', '001.2300', '1,234', '未记录', '&lt;script&gt;', '&lt;b&gt;'):
        assert value in html
    assert '<script>' not in html and '<b>' not in html
    assert 'href="#section-findings"' in html and 'id="section-findings"' in html
    assert '@media print' in html and 'Content-Security-Policy' in html
    receipt = json.loads(result.stdout)
    assert receipt['sections'] == 1 and receipt['figures'] == 0
    assert receipt['output'] == 'report.html'
    for source, digest in receipt['source_sha256'].items():
        assert hashlib.sha256((tmp_path / source).read_bytes()).hexdigest() == digest


def test_figures_are_self_contained_numbered_with_their_own_captions(tmp_path):
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><text x="1" y="10">A</text></svg>'
    (tmp_path / 'chart.svg').write_bytes(svg)
    png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Zl1sAAAAASUVORK5CYII=')
    (tmp_path / 'image.png').write_bytes(png)
    result = run(tmp_path, report([{'type': 'figure', 'path': 'chart.svg', 'caption': '甲图'},
        {'type': 'figure', 'path': 'image.png', 'caption': '乙图'}]))
    assert result.returncode == 0, result.stderr
    html = (tmp_path / 'report.html').read_text()
    assert 'data:image/svg+xml;base64,' + base64.b64encode(svg).decode() in html
    assert 'data:image/png;base64,' + base64.b64encode(png).decode() in html
    assert html.index('图 1 · 甲图') < html.index('图 2 · 乙图')
    assert '<script' not in html and 'src="http' not in html and '<link' not in html
    assert json.loads(result.stdout)['figures'] == 2


@pytest.mark.parametrize('blocks', [
    [{'type': 'html', 'text': '<p>raw</p>'}],
    [{'type': 'paragraph', 'text': 'ok', 'extra': 'unknown'}],
    [{'type': 'table', 'csv': 'missing.csv'}],
    [{'type': 'figure', 'path': 'https://example.com/chart.png', 'caption': 'Remote'}],
    [{'type': 'table', 'csv': '../outside.csv'}],
])
def test_invalid_blocks_fail_explicitly_without_output(tmp_path, blocks):
    result = run(tmp_path, report(blocks))
    assert result.returncode != 0 and result.stderr.startswith('capstone-report: ')
    assert not (tmp_path / 'report.html').exists()


def test_duplicate_ids_missing_columns_and_ragged_csv_fail(tmp_path):
    spec = report([])
    spec['sections'].append(spec['sections'][0].copy())
    assert run(tmp_path, spec).returncode != 0
    (tmp_path / 'data.csv').write_text('name,value\na,1\n')
    assert run(tmp_path, report([{'type': 'table', 'csv': 'data.csv', 'columns': ['missing']}])).returncode != 0
    (tmp_path / 'data.csv').write_text('name,value\na,1,extra\n')
    assert run(tmp_path, report([{'type': 'table', 'csv': 'data.csv'}])).returncode != 0


def test_missing_figure_reports_exact_safe_source_and_block_without_a_guessing_loop(tmp_path):
    result = run(tmp_path, report([{'type': 'paragraph', 'text': 'Useful retained finding'},
        {'type': 'figure', 'path': '图3_利用率.png', 'caption': 'Source figure'}]))
    assert result.returncode == 2 and result.stdout == ''
    diagnostic = json.loads(result.stderr.splitlines()[-1])
    assert diagnostic == {'code': 'source_missing', 'path': '图3_利用率.png',
        'location': 'sections[0].blocks[1].path'}
    assert str(tmp_path) not in result.stderr
    assert not (tmp_path / 'report.html').exists()


def test_csv_large_cell_does_not_inherit_the_default_csv_field_limit(tmp_path):
    value = 'x' * 140000
    (tmp_path / 'data.csv').write_text('value\n' + value + '\n')
    result = run(tmp_path, report([{'type': 'table', 'csv': 'data.csv'}]))
    assert result.returncode == 0, result.stderr
    assert '<td>' + value + '</td>' in (tmp_path / 'report.html').read_text()


def test_source_spec_and_external_symlink_cannot_be_overwritten_or_read(tmp_path):
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    outside = tmp_path / 'outside.csv'
    outside.write_text('a,b\n1,2\n')
    (workspace / 'link.csv').symlink_to(outside)
    assert run(workspace, report([{'type': 'table', 'csv': 'link.csv'}])).returncode != 0
    (workspace / 'escape').symlink_to(tmp_path, target_is_directory=True)
    assert run(workspace, report([]), output='escape/damaged.html').returncode != 0
    assert not (tmp_path / 'damaged.html').exists()
    original = outside.read_bytes()
    (workspace / 'data.csv').write_bytes(original)
    assert run(workspace, report([{'type': 'table', 'csv': 'data.csv'}]), output='data.csv').returncode != 0
    assert (workspace / 'data.csv').read_bytes() == original
    assert run(workspace, report([]), output='report.json').returncode != 0


@pytest.mark.parametrize('body', [
    '<script>alert(1)</script>',
    '<image href="https://example.com/a.png"/>',
    '<rect onclick="alert(1)"/>',
    '<style>rect{fill:url(https://example.com/a)}</style>',
    '<foreignObject><p>HTML</p></foreignObject>',
])
def test_svg_rejects_active_or_external_content(tmp_path, body):
    (tmp_path / 'chart.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg">' + body + '</svg>')
    assert run(tmp_path, report([{'type': 'figure', 'path': 'chart.svg', 'caption': 'Unsafe'}])).returncode != 0


def test_cli_help_and_version_are_available_without_dependencies():
    assert subprocess.check_output([sys.executable, str(SCRIPT), '--version'], text=True).strip() == 'capstone-report 1.1.0'
    help_text = subprocess.check_output([sys.executable, str(SCRIPT), '--help'], text=True)
    assert 'CSV' in help_text and 'SVG' in help_text and 'PNG' in help_text
