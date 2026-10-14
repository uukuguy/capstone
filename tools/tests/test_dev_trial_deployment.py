from __future__ import annotations

import importlib.util
import json
import stat
import os
import subprocess
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def helper():
    spec = importlib.util.spec_from_file_location('trial_runtime', ROOT / 'deploy/dev_trial_runtime.py')
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def manifest():
    return {'schema': 'capstone-dev-trial/1', 'channel': 'dev-trial', 'source_revision': 'a' * 40,
            'platforms': ['linux/amd64', 'linux/arm64'],
            'images': {key: 'registry.cn-beijing.aliyuncs.com/uukuguy/' + key + '@sha256:' + 'b' * 64
                       for key in ['backend', 'app', 'postgres', 'objects']}}


def test_private_config_is_stable_protected_and_contains_no_provider_keys(tmp_path):
    path = helper().initialize_private_environment(tmp_path / 'state')
    original = path.read_bytes()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert b'DEEPSEEK_API_KEY' not in original and b'OPENAI_API_KEY' not in original
    assert b'POSTGRES_PASSWORD=' in original and b'CAPSTONE_OPERATOR_TOKEN=' in original
    assert helper().initialize_private_environment(path.parent).read_bytes() == original


def test_private_config_never_follows_a_symlink(tmp_path):
    target = tmp_path / 'user-data'
    target.write_text('preserve')
    directory = tmp_path / 'state'
    directory.mkdir()
    (directory / 'internal.env').symlink_to(target)
    with pytest.raises(ValueError):
        helper().initialize_private_environment(directory)
    assert target.read_text() == 'preserve'


def test_manifest_requires_exact_source_digest_pins_and_both_platforms():
    runtime = helper()
    assert runtime.validate_manifest(manifest())['source_revision'] == 'a' * 40
    for change in [{'source_revision': 'dev'}, {'platforms': ['linux/arm64']},
                   {'images': manifest()['images'] | {'backend': 'backend:latest'}}]:
        with pytest.raises(ValueError):
            runtime.validate_manifest(manifest() | change)


def test_config_validation_selects_openai_without_disclosing_any_key():
    runtime = helper()
    settings = {'CAPSTONE_PUBLIC_PROVIDER': 'openai', 'CAPSTONE_PUBLIC_MODEL': 'gpt-5.5',
                'OPENAI_API_KEY': 'sentinel-openai-secret', 'DEEPSEEK_API_KEY': 'sentinel-deepseek-secret'}
    result = runtime.validate_configuration(ROOT, settings, manifest())
    assert result['provider'] == 'openai'
    assert result['source_revision'] == 'a' * 40
    assert 'sentinel' not in json.dumps(result)
    with pytest.raises(ValueError, match='^OPENAI_API_KEY$'):
        runtime.validate_configuration(ROOT, settings | {'OPENAI_API_KEY': ''}, manifest())


def test_installation_guard_preserves_another_source_receipt(tmp_path):
    runtime = helper()
    runtime.record_installation(tmp_path, manifest())
    original = (tmp_path / 'installation.json').read_bytes()
    with pytest.raises(ValueError, match='source'):
        runtime.record_installation(tmp_path, manifest() | {'source_revision': 'c' * 40})
    assert (tmp_path / 'installation.json').read_bytes() == original


def test_check_rejects_an_image_built_from_another_commit(tmp_path):
    runtime = helper()
    (tmp_path / 'deploy').mkdir()
    (tmp_path / 'deploy/image-source.txt').write_text('c' * 40 + '\n')
    with pytest.raises(ValueError, match='source'):
        runtime.verify_image_source(tmp_path, manifest())
    (tmp_path / 'deploy/image-source.txt').write_text('a' * 40 + '\n')
    runtime.verify_image_source(tmp_path, manifest())


def test_candidate_manifest_requires_explicit_operator_opt_in(monkeypatch):
    runtime = helper()
    candidate = manifest() | {'channel': 'dev-trial-candidate', 'platforms': ['linux/arm64'],
                             'images': {key: 'capstone-trial-' + key + ':' + 'a' * 40 for key in manifest()['images']}}
    monkeypatch.delenv('CAPSTONE_CANDIDATE_VALIDATION', raising=False)
    with pytest.raises(ValueError):
        runtime.validate_manifest(candidate)
    monkeypatch.setenv('CAPSTONE_CANDIDATE_VALIDATION', '1')
    assert runtime.validate_manifest(candidate)['channel'] == 'dev-trial-candidate'


@pytest.mark.skipif(not shutil.which('docker'), reason='Docker CLI is required for real Compose interpolation')
def test_real_compose_interpolation_honors_startup_environment_and_worker_only_keys(tmp_path):
    private = helper().initialize_private_environment(tmp_path / 'state')
    release = tmp_path / 'release.env'
    keys = {'backend': 'BACKEND', 'app': 'APP', 'postgres': 'POSTGRES', 'objects': 'OBJECTS'}
    release.write_text(''.join('CAPSTONE_' + keys[k] + '_IMAGE=' + v + '\n' for k, v in manifest()['images'].items()))
    settings = tmp_path / '.env'
    settings.write_text('CAPSTONE_PUBLIC_PROVIDER=deepseek\nCAPSTONE_PUBLIC_MODEL=deepseek-flash\n')
    environment = os.environ | {'CAPSTONE_PUBLIC_PROVIDER': 'openai', 'CAPSTONE_PUBLIC_MODEL': 'gpt-5.5',
                               'OPENAI_API_KEY': 'sentinel-openai-secret', 'DEEPSEEK_API_KEY': 'sentinel-deepseek-secret'}
    result = subprocess.run(['docker', 'compose', '--env-file', str(release), '--env-file', str(private),
                             '--env-file', str(settings), '-f', str(ROOT / 'deploy/dev-trial/compose.yaml'),
                             'config', '--format', 'json'], env=environment, capture_output=True, text=True, check=True)
    services = json.loads(result.stdout)['services']
    assert all('build' not in spec for spec in services.values())
    assert len({spec['image'] for spec in services.values()}) == 4
    assert services['worker']['environment']['CAPSTONE_PUBLIC_PROVIDER'] == 'openai'
    assert services['worker']['environment']['CAPSTONE_PUBLIC_MODEL'] == 'gpt-5.5'
    assert services['worker']['environment']['OPENAI_API_KEY'] == 'sentinel-openai-secret'
    assert services['worker-pypsa']['image'] == services['api']['image'] == services['worker']['image']
    assert not {'OPENAI_API_KEY', 'DEEPSEEK_API_KEY'} & services['api']['environment'].keys()
    assert not {'OPENAI_API_KEY', 'DEEPSEEK_API_KEY'} & services['app']['environment'].keys()
    assert not any('ports' in services[name] for name in ['api', 'worker', 'worker-pypsa', 'postgres', 'objects'])


def test_start_entry_rejects_reserved_project_before_running_docker(tmp_path):
    environment = os.environ | {'CAPSTONE_INSTANCE': 'capstone'}
    result = subprocess.run(['sh', str(ROOT / 'deploy/dev-trial/start.sh')], env=environment,
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert 'CAPSTONE_INSTANCE' in result.stderr


def test_container_cli_missing_key_reports_only_the_required_variable(tmp_path):
    document = tmp_path / 'manifest.json'
    document.write_text(json.dumps(manifest()))
    environment = os.environ.copy()
    environment.pop('DEEPSEEK_API_KEY', None)
    environment.pop('OPENAI_API_KEY', None)
    environment.update(CAPSTONE_PUBLIC_PROVIDER='openai', CAPSTONE_PUBLIC_MODEL='gpt-5.5')
    result = subprocess.run([os.sys.executable, str(ROOT / 'deploy/dev_trial_runtime.py'), 'check',
                             '--manifest', str(document)], env=environment, capture_output=True, text=True)
    assert result.returncode == 1
    assert 'OPENAI_API_KEY' in result.stderr
    assert 'Traceback' not in result.stderr
