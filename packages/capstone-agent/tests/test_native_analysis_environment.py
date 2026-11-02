"""Build manifest, dependency lock and truthful receipt boundary."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).parents[3]


def smoke_module():
    spec = importlib.util.spec_from_file_location('native_analysis_smoke', ROOT / 'tools/native_analysis_smoke.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_manifest_lock_covers_general_environment_and_preserves_shared_pins():
    source = ROOT / 'configs/runtime/native-analysis.json'
    manifest = json.loads(source.read_text())
    lock = (ROOT / 'configs/runtime/native-analysis.lock.txt').read_text()
    assert '# manifest-sha256: ' + hashlib.sha256(source.read_bytes()).hexdigest() in lock
    shared = ROOT / manifest['constraints_source']
    assert '# shared-constraints-sha256: ' + hashlib.sha256(shared.read_bytes()).hexdigest() in lock
    normalize = lambda name: re.sub(r'[-_.]+', '-', name).lower()
    roots = {normalize(item['requirement'].split('==')[0]) for item in manifest['packages']}
    assert roots == {'numpy', 'pandas', 'scipy', 'statsmodels', 'scikit-learn', 'matplotlib', 'seaborn',
        'plotly', 'pillow', 'openpyxl', 'xlsxwriter', 'pyarrow', 'duckdb', 'pypdf', 'pdfplumber',
        'python-docx', 'python-pptx', 'beautifulsoup4', 'lxml', 'jinja2', 'requests', 'httpx', 'pyyaml', 'tabulate'}
    resolved = {normalize(name): version for name, version in re.findall(r'^([\w.-]+)==([^\s;]+)', lock, re.M)}
    assert roots <= resolved.keys()
    assert not {'pandapower', 'pypsa', 'torch', 'tensorflow', 'transformers', 'jax'}.intersection(resolved)
    for name, version in json.loads(shared.read_text())['dependencies'].items():
        if normalize(name) in resolved:
            assert resolved[normalize(name)] == version
    assert len(re.findall(r'^    --hash=sha256:[a-f0-9]{64}', lock, re.M)) >= len(resolved)
    assert {'ripgrep', 'jq', 'unzip', 'zip', 'poppler-utils', 'fonts-noto-cjk'} <= set(manifest['apt_packages'])


def test_build_reuses_node_and_pi_assets_and_publishes_only_verified_receipt():
    image = (ROOT / 'deploy/general-pi.Dockerfile').read_text()
    assert 'COPY --from=node /usr/local/lib/node_modules/npm/' in image
    assert '/opt/pi/node_modules/typescript/bin/tsc /usr/local/bin/tsc' in image
    assert '/opt/pi/node_modules/tsx/dist/cli.mjs /usr/local/bin/tsx' in image
    assert 'COPY packages/capstone-agent/src/capstone_agent/native_environment.py' in image
    assert 'python tools/native_analysis_smoke.py' in image
    assert 'COPY tools/native_report.py' in image
    assert '/usr/local/bin/capstone-report' in image


def test_report_cli_is_registered_and_real_standalone_smoke_passes(tmp_path):
    manifest = json.loads((ROOT / 'configs/runtime/native-analysis.json').read_text())
    entry = next(item for item in manifest['commands'] if item['name'] == 'capstone-report')
    assert entry['version_args'] == ['--version']
    smoke_module().exercise_report(tmp_path, renderer=[sys.executable, str(ROOT / 'tools/native_report.py')])


def test_inventory_rejects_missing_or_unlocked_packages(monkeypatch):
    module = smoke_module()
    monkeypatch.setattr(module.importlib, 'import_module', lambda name: None)
    monkeypatch.setattr(module.metadata, 'version', lambda name: '2.0')
    manifest = {'packages': [{'requirement': 'example', 'module': 'example'}], 'commands': []}
    with pytest.raises(ValueError, match='does not match'):
        module.inspect_inventory(manifest, 'example==1.0\n')
    monkeypatch.setattr(module.importlib, 'import_module', lambda name: (_ for _ in ()).throw(ImportError('missing')))
    with pytest.raises(ImportError):
        module.inspect_inventory(manifest, 'example==2.0\n')


def test_inventory_extracts_versions_without_banners_or_paths(monkeypatch):
    module = smoke_module()
    monkeypatch.setattr(module, 'command', lambda args: 'program 1.2.3 /private/operator/path')
    manifest = {'packages': [], 'commands': [{'name': 'program', 'version_args': ['--version'],
                                             'version_pattern': r'program ([0-9.]+)'}]}
    assert module.inspect_inventory(manifest, '') == ({}, {'program': '1.2.3'})


def test_failed_smoke_does_not_create_or_replace_inventory(tmp_path, monkeypatch):
    module = smoke_module()
    manifest = tmp_path / 'manifest.json'
    manifest.write_text('{"schema":"capstone-native-analysis/1"}')
    lock = tmp_path / 'lock.txt'
    lock.write_text('')
    output = tmp_path / 'inventory.json'
    args = ['smoke', '--manifest', str(manifest), '--lock', str(lock), '--inventory-output', str(output)]
    monkeypatch.setattr('sys.argv', args)
    monkeypatch.setattr(module, 'inspect_inventory', lambda *args: ({'example': '1.0'}, {'node': '24.20.0'}))
    monkeypatch.setattr(module, 'exercise', lambda path: (_ for _ in ()).throw(RuntimeError('check failed')))
    with pytest.raises(RuntimeError):
        module.main()
    assert not output.exists()
    output.write_text('previous verified receipt')
    with pytest.raises(RuntimeError):
        module.main()
    assert output.read_text() == 'previous verified receipt'
    monkeypatch.setattr(module, 'exercise', lambda path: ['csv_dataframes'])
    module.main()
    receipt = json.loads(output.read_text())
    assert receipt['schema'] == 'capstone-native-environment/1'
    assert receipt['packages'] == {'example': '1.0'}
    assert receipt['smoke_capabilities'] == ['csv_dataframes']
    assert str(tmp_path) not in output.read_text()


def test_command_failure_does_not_echo_private_process_output(monkeypatch):
    module = smoke_module()
    monkeypatch.setattr(module.subprocess, 'run', lambda *args, **kwargs:
        SimpleNamespace(returncode=1, stdout='PRIVATE', stderr='SECRET'))
    with pytest.raises(RuntimeError, match='command check failed: program') as error:
        module.command(['program', 'private argument'])
    assert 'PRIVATE' not in str(error.value) and 'SECRET' not in str(error.value)
