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


def test_user_local_default_port_is_separate_from_developer_services():
    assert 'CAPSTONE_APP_PORT=19173' in (ROOT / 'deploy/dev-trial/env.example').read_text()
    compose = (ROOT / 'deploy/dev-trial/compose.yaml').read_text()
    assert '${CAPSTONE_APP_PORT:-5173}' not in compose
    assert '${CAPSTONE_APP_PORT:-19173}:3000' in compose


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


def portable_manifest():
    identities = [{'kind': kind, 'tag': 'capstone-offline-' + kind + ':' + 'a' * 40,
                   'config_digest': 'sha256:' + str(i) * 64,
                   'manifest_digest': 'sha256:' + str(i + 4) * 64, 'platform': 'linux/amd64'}
                  for i, kind in enumerate(['backend', 'app', 'postgres', 'objects'])]
    return manifest() | {'channel': 'dev-trial-offline', 'platforms': ['linux/amd64'],
                         'images': {i['kind']: i['config_digest'] for i in identities},
                         'offline_image_identities': identities}


@pytest.mark.parametrize('identity_field', ['config_digest', 'manifest_digest'])
@pytest.mark.parametrize('metadata_modes', [(0o644, 0o644), (0o640, 0o604)])
def test_offline_materialization_keeps_static_contract_and_repeats(tmp_path, identity_field, metadata_modes):
    runtime = helper()
    document = portable_manifest()
    (tmp_path / 'manifest.json').write_text(json.dumps(document))
    (tmp_path / 'release.env').write_text('original')
    expected_metadata = {}
    for name, mode in zip(('manifest.json', 'release.env'), metadata_modes):
        path = tmp_path / name
        path.chmod(mode)
        metadata = path.stat()
        expected_metadata[name] = (mode, metadata.st_uid, metadata.st_gid)
    (tmp_path / 'data-contract.env').write_text('static-data-contract')
    selection = tmp_path / 'selection.tsv'
    selection.write_text(''.join(i['kind'] + '\t' + i[identity_field] + '\n'
                                for i in document['offline_image_identities']))
    for _ in range(2):
        runtime.materialize_offline(tmp_path, selection)
        for name, expected in expected_metadata.items():
            metadata = (tmp_path / name).stat()
            assert (stat.S_IMODE(metadata.st_mode), metadata.st_uid, metadata.st_gid) == expected
        actual = json.loads((tmp_path / 'manifest.json').read_text())
        assert actual['offline_image_identities'] == document['offline_image_identities']
        assert actual['images'] == {i['kind']: i[identity_field] for i in document['offline_image_identities']}
        assert (tmp_path / 'data-contract.env').read_text() == 'static-data-contract'
        runtime.validate_manifest(actual)
        runtime.record_installation(tmp_path / 'state', actual)
        assert stat.S_IMODE((tmp_path / 'state/installation.json').stat().st_mode) == 0o600
        private = runtime.initialize_private_environment(tmp_path / 'state')
        assert stat.S_IMODE(private.stat().st_mode) == 0o600
        for kind, identity in actual['images'].items():
            assert f'CAPSTONE_{kind.upper()}_IMAGE={identity}\n' in (tmp_path / 'release.env').read_text()


def test_offline_materialization_rejects_unbound_id_before_changes(tmp_path):
    runtime = helper()
    document = portable_manifest()
    original = json.dumps(document)
    (tmp_path / 'manifest.json').write_text(original)
    (tmp_path / 'release.env').write_text('original')
    selection = tmp_path / 'selection.tsv'
    selection.write_text(''.join(i['kind'] + '\tsha256:' + 'f' * 64 + '\n'
                                for i in document['offline_image_identities']))
    with pytest.raises(ValueError):
        runtime.materialize_offline(tmp_path, selection)
    assert (tmp_path / 'manifest.json').read_text() == original
    assert (tmp_path / 'release.env').read_text() == 'original'
    document['images']['backend'] = 'sha256:' + 'f' * 64
    with pytest.raises(ValueError):
        runtime.validate_manifest(document)


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
    with pytest.raises(ValueError, match='source'):
        runtime.record_installation(tmp_path, manifest(), 'capstone-user-other')
    assert (tmp_path / 'installation.json').read_bytes() == original


def test_check_rejects_an_image_built_from_another_commit(tmp_path):
    runtime = helper()
    (tmp_path / 'deploy').mkdir()
    (tmp_path / 'deploy/image-source.txt').write_text('c' * 40 + '\n')
    with pytest.raises(ValueError, match='source'):
        runtime.verify_image_source(tmp_path, manifest())
    (tmp_path / 'deploy/image-source.txt').write_text('a' * 40 + '\n')
    runtime.verify_image_source(tmp_path, manifest())


def test_ready_check_requires_same_origin_app_source_and_ready_api(monkeypatch):
    runtime = helper()
    replies = {'http://app:3000/__capstone-build': {'revision': 'a' * 40, 'environment': 'local-dev', 'dirty': False},
               'http://api:8766/health/ready': {'status': 'ready'}}
    monkeypatch.setattr(runtime, 'read_public_json', lambda address: replies[address])
    assert runtime.check_readiness(manifest())['status'] == 'deployment-ready'
    replies['http://app:3000/__capstone-build']['revision'] = 'c' * 40
    with pytest.raises(ValueError, match='App'):
        runtime.check_readiness(manifest())


def test_candidate_manifest_requires_explicit_operator_opt_in(monkeypatch):
    runtime = helper()
    candidate = manifest() | {'channel': 'dev-trial-candidate', 'platforms': ['linux/arm64'],
                             'images': {key: 'capstone-trial-' + key + ':' + 'a' * 40 for key in manifest()['images']}}
    monkeypatch.delenv('CAPSTONE_CANDIDATE_VALIDATION', raising=False)
    with pytest.raises(ValueError):
        runtime.validate_manifest(candidate)
    monkeypatch.setenv('CAPSTONE_CANDIDATE_VALIDATION', '1')
    assert runtime.validate_manifest(candidate)['channel'] == 'dev-trial-candidate'


def test_candidate_image_architecture_must_match_its_manifest(tmp_path, monkeypatch):
    runtime = helper()
    (tmp_path / 'deploy').mkdir()
    (tmp_path / 'deploy/image-source.txt').write_text('a' * 40)
    monkeypatch.setenv('CAPSTONE_CANDIDATE_VALIDATION', '1')
    candidate = manifest() | {'channel': 'dev-trial-candidate', 'platforms': ['linux/amd64']}
    monkeypatch.setattr(runtime.platform, 'machine', lambda: 'aarch64')
    with pytest.raises(ValueError, match='platform'):
        runtime.verify_image_source(tmp_path, candidate)


def test_candidate_accepts_distinct_amd64_image_tags(monkeypatch):
    runtime = helper()
    monkeypatch.setenv('CAPSTONE_CANDIDATE_VALIDATION', '1')
    candidate = manifest() | {'channel': 'dev-trial-candidate', 'platforms': ['linux/amd64'],
        'images': {key: 'capstone-trial-' + key + '-amd64:' + 'a' * 40 for key in manifest()['images']}}
    assert runtime.validate_manifest(candidate)['platforms'] == ['linux/amd64']
    with pytest.raises(ValueError):
        runtime.validate_manifest(candidate | {'images': candidate['images'] | {'backend': 'capstone-trial-backend-amd65:' + 'a' * 40}})


@pytest.mark.skipif(not shutil.which('docker'), reason='Docker CLI is required for real Compose interpolation')
def test_real_compose_interpolation_honors_startup_environment_and_worker_only_keys(tmp_path):
    private = helper().initialize_private_environment(tmp_path / 'state')
    release = tmp_path / 'release.env'
    keys = {'backend': 'BACKEND', 'app': 'APP', 'postgres': 'POSTGRES', 'objects': 'OBJECTS'}
    release.write_text(''.join('CAPSTONE_' + keys[k] + '_IMAGE=' + v + '\n' for k, v in manifest()['images'].items()))
    settings = tmp_path / '.env'
    settings.write_text('CAPSTONE_PUBLIC_PROVIDER=deepseek\nCAPSTONE_PUBLIC_MODEL=deepseek-flash\nPOSTGRES_PASSWORD=unsafe-override\nCAPSTONE_OPERATOR_TOKEN=unsafe-override\n')
    environment = os.environ | {'CAPSTONE_PUBLIC_PROVIDER': 'openai', 'CAPSTONE_PUBLIC_MODEL': 'gpt-5.5',
                               'OPENAI_API_KEY': 'sentinel-openai-secret', 'DEEPSEEK_API_KEY': 'sentinel-deepseek-secret'}
    result = subprocess.run(['docker', 'compose', '--env-file', str(release), '--env-file', str(settings),
                             '--env-file', str(private), '-f', str(ROOT / 'deploy/dev-trial/compose.yaml'),
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
    assert services['postgres']['environment']['POSTGRES_PASSWORD'] != 'unsafe-override'
    assert services['api']['environment']['CAPSTONE_OPERATOR_TOKEN'] != 'unsafe-override'


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


def test_shell_lifecycle_keeps_instances_private_and_handles_failed_start(tmp_path):
    bundle = tmp_path / 'bundle'
    bundle.mkdir()
    for name in ['start.sh', 'compose.yaml']:
        shutil.copyfile(ROOT / 'deploy/dev-trial' / name, bundle / name)
    (bundle / '.env.example').write_text('CAPSTONE_PUBLIC_PROVIDER=deepseek\nCAPSTONE_PUBLIC_MODEL=deepseek-flash\n')
    (bundle / 'manifest.json').write_text(json.dumps(manifest()))
    (bundle / 'release.env').write_text('CAPSTONE_BACKEND_IMAGE=' + manifest()['images']['backend'] + '\nCAPSTONE_TRIAL_PLATFORM=linux/arm64\n')
    binary = tmp_path / 'bin'
    binary.mkdir()
    fake = binary / 'docker'
    fake.write_text('#!' + os.sys.executable + '\n' + r'''
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with open(os.environ['DOCKER_RECORD'], 'a') as output:
    output.write(json.dumps({'args': args, 'provider': os.environ.get('CAPSTONE_PUBLIC_PROVIDER'),
                            'image_override': 'CAPSTONE_BACKEND_IMAGE' in os.environ}) + '\n')
if args[0] == 'run':
    state = Path(next(value[:-7] for value in args if value.endswith(':/state')))
    if args[-1] == 'init':
        (state / 'internal.env').touch(exist_ok=True)
    elif args[-1] == 'record':
        (state / 'installation.json').write_text('{}')
elif args[0] == 'compose' and '-f' in args:
    command = args[args.index('-f') + 2:]
    if command[0] == 'up' and os.environ.get('FAIL_START') == '1':
        sys.exit(1)
    if command[:2] == ['ps', '-q']:
        print('owned-' + command[2])
elif args[0] == 'inspect':
    print('sha256:' + 'b' * 64)
elif args[:2] == ['image', 'inspect']:
    print('arm64')
''')
    fake.chmod(0o755)
    record = tmp_path / 'docker.jsonl'
    environment = os.environ | {'PATH': str(binary) + os.pathsep + os.environ['PATH'],
        'DOCKER_RECORD': str(record), 'CAPSTONE_INSTANCE': 'capstone-user-first',
        'CAPSTONE_PUBLIC_PROVIDER': 'openai', 'CAPSTONE_BACKEND_IMAGE': 'unsafe-override'}
    result = subprocess.run(['sh', str(bundle / 'start.sh')], env=environment, capture_output=True, text=True)
    assert result.returncode == 0 and 'trial is ready' in result.stdout
    first = bundle / '.capstone-trial/capstone-user-first/internal.env'
    assert first.exists()
    calls = [json.loads(line) for line in record.read_text().splitlines()]
    helpers = [call for call in calls if call['args'][0] == 'run']
    assert all(call['args'][1:3] == ['--platform', 'linux/arm64'] for call in helpers)
    assert all(not call['image_override'] and call['provider'] == 'openai' for call in helpers)
    compose = next(call['args'] for call in calls if 'config' in call['args'])
    files = [compose[index + 1] for index, value in enumerate(compose) if value == '--env-file']
    assert files[-1] == str(first)
    assert files[:-1] == [str(bundle / '.env'), str(bundle / 'release.env')]
    result = subprocess.run(['sh', str(bundle / 'start.sh')],
        env=environment | {'CAPSTONE_INSTANCE': 'capstone-user-second', 'FAIL_START': '1'},
        capture_output=True, text=True)
    assert result.returncode != 0 and 'trial is ready' not in result.stdout
    assert first.exists() and (bundle / '.capstone-trial/capstone-user-second/internal.env').exists()
    result = subprocess.run(['sh', str(bundle / 'start.sh'), 'stop'], env=environment,
                            capture_output=True, text=True)
    assert result.returncode == 0 and first.exists()
    assert not any('down' in json.loads(line)['args'] for line in record.read_text().splitlines())
