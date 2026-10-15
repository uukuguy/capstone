"""Offline transport tests. Docker metadata is simulated; archives are real."""
import hashlib
import importlib.util
import json
import io
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
REVISION = 'a' * 40
KINDS = ('backend', 'app', 'postgres', 'objects')


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'deploy' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_offline_manifest_allows_only_single_amd64_config_ids():
    runtime = load('dev_trial_runtime')
    document = {'schema': 'capstone-dev-trial/1', 'channel': 'dev-trial-offline',
                'source_revision': REVISION, 'platforms': ['linux/amd64'],
                'images': {key: 'sha256:' + str(i) * 64 for i, key in enumerate(KINDS)}}
    assert runtime.validate_manifest(document) == document
    for field, value in [('platforms', ['linux/arm64']), ('images', {key: 'latest' for key in KINDS})]:
        with pytest.raises(ValueError):
            runtime.validate_manifest(dict(document, **{field: value}))
    with pytest.raises(ValueError):
        runtime.validate_manifest(dict(document, channel='dev-trial'))


def test_offline_openai_requires_explicit_internal_endpoint(monkeypatch):
    runtime = load('dev_trial_runtime')
    document = {'schema': 'capstone-dev-trial/1', 'channel': 'dev-trial-offline',
                'source_revision': REVISION, 'platforms': ['linux/amd64'],
                'images': {key: 'sha256:' + str(i) * 64 for i, key in enumerate(KINDS)}}
    monkeypatch.setattr(runtime, '_runtime', lambda root: SimpleNamespace(select_runtime=lambda *args:
        (None, None, None, {'CAPSTONE_PUBLIC_PROVIDER': 'openai', 'CAPSTONE_PUBLIC_MODEL': 'deepseek-flash',
                            'CAPSTONE_RUNTIME_PROFILE': 'capstone-dev-trial-v1'})))
    with pytest.raises(ValueError, match='OPENAI_BASE_URL'):
        runtime.validate_configuration(ROOT, {'OPENAI_API_KEY': 'fixture'}, document)
    assert runtime.validate_configuration(ROOT, {'OPENAI_API_KEY': 'fixture',
        'OPENAI_BASE_URL': 'http://internal.example/v1'}, document)['status'] == 'configuration-valid'


def context(tmp_path):
    source = tmp_path / 'context'
    shutil.copytree(ROOT / 'deploy/dev-trial', source / 'deploy/dev-trial')
    shutil.copytree(ROOT / 'configs', source / 'configs')
    for name in ['pyproject.toml', 'uv.lock', 'packages/backend/pyproject.toml',
                 'packages/backend/src/store.py', 'schemas/store.json', 'deploy/dev_trial_runtime.py']:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name)
    builder = load('build_dev_trial')
    inputs = builder.BUNDLE_INPUTS | {'deploy/dev-trial/install-version.sh', 'deploy/dev-trial/install-offline.sh'}
    (source / 'trial-context.json').write_text(json.dumps({'source_revision': REVISION,
        'data_inputs': {name: hashlib.sha256(data).hexdigest() for name, data in builder.data_contract.context_files(source).items()},
        'inputs': {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in inputs}}))
    return source


def test_export_checks_platform_source_and_streamed_archive_hashes(tmp_path, monkeypatch):
    exporter = load('build_user_local_offline')
    source = context(tmp_path)
    refs = {key: 'fixture-' + key for key in KINDS}
    metadata = {ref: {'Id': 'sha256:' + str(i) * 64, 'Os': 'linux', 'Architecture': 'amd64',
        'Config': {'Labels': {'org.opencontainers.image.revision': REVISION}}} for i, ref in enumerate(refs.values())}
    def run(args, **kwargs):
        if args[:3] == ['docker', 'image', 'inspect']:
            return subprocess.CompletedProcess(args, 0, json.dumps([metadata[args[-1]]]))
        if args[:3] == ['docker', 'image', 'save']:
            Path(args[args.index('--output') + 1]).write_bytes(('archive:' + args[-1]).encode())
            return subprocess.CompletedProcess(args, 0)
        raise AssertionError(args)
    monkeypatch.setattr(exporter.subprocess, 'run', run)
    out = tmp_path / 'offline'
    result = exporter.export_bundle(source, out, REVISION, refs)
    assert result['channel'] == 'dev-trial-offline'
    assert result['images'] == {key: metadata[ref]['Id'] for key, ref in refs.items()}
    with tarfile.open(out / 'deployment.tar.gz') as bundle:
        settings = bundle.extractfile('.env').read().decode()
        assert 'PROVIDER=openai\nOPENAI_MODEL=deepseek-flash\nOPENAI_BASE_URL=\n' in settings
        assert 'CAPSTONE_PUBLIC_' not in settings
        assert bundle.extractfile('.env.example').read().decode() == settings
    for line in (out / 'SHA256SUMS').read_text().splitlines():
        checksum, name = line.split('  ')
        assert hashlib.sha256((out / name).read_bytes()).hexdigest() == checksum
    metadata[refs['backend']]['Architecture'] = 'arm64'
    with pytest.raises(ValueError, match='platform'):
        exporter.export_bundle(source, tmp_path / 'wrong', REVISION, refs)
    assert not (tmp_path / 'wrong').exists()
    metadata[refs['backend']]['Architecture'] = 'amd64'
    metadata[refs['app']]['Config']['Labels']['org.opencontainers.image.revision'] = 'b' * 40
    with pytest.raises(ValueError, match='source'):
        exporter.export_bundle(source, tmp_path / 'wrong-source', REVISION, refs)


@pytest.fixture
def delivery(tmp_path):
    out = tmp_path / 'delivery'
    out.mkdir()
    files = {name: b'fixture\n' for name in ['compose.yaml', 'start.sh', '.env', '.env.example',
        'README.txt', 'data-contract.env', 'install.sh']}
    files['manifest.json'] = json.dumps({'channel': 'dev-trial-offline'}).encode()
    files['release.env'] = ''.join(f'CAPSTONE_{kind.upper()}_IMAGE=sha256:{i * 64}\n' for i, kind in zip('0123', KINDS)).encode()
    files['capstone.sh'] = b'#!/bin/sh\nprintf "manager %s %s\\n" "$1" "$2"\n'
    with tarfile.open(out / 'deployment.tar.gz', 'w:gz') as target:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            target.addfile(info, io.BytesIO(data))
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    version = (ROOT / 'deploy/dev-trial/install-version.sh').read_text()
    for key, value in {'@SOURCE_REVISION@': REVISION, '@VERSION@': 'user-local-aaaaaaa',
                       '@ARCHIVE_URL@': 'offline', '@ARCHIVE_SHA256@': digest(out / 'deployment.tar.gz')}.items():
        version = version.replace(key, value)
    (out / 'install-version.sh').write_text(version)
    shutil.copyfile(ROOT / 'deploy/dev-trial/install-offline.sh', out / 'install-offline.sh')
    (out / 'manifest.json').write_text('{}')
    (out / 'README.txt').write_text('offline fixture')
    (out / 'versions.tsv').write_text('fixture catalog\n')
    (out / 'images.tsv').write_text(''.join(f'{kind}\tsha256:{i * 64}\tlinux/amd64\t{kind}.tar\n' for i, kind in zip('0123', KINDS)))
    for kind in KINDS:
        (out / (kind + '.tar')).write_bytes(b'image fixture')
    (out / 'SHA256SUMS').write_text(''.join(digest(path) + '  ' + path.name + '\n' for path in out.iterdir()))
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    (bin_dir / 'docker').write_text('''#!/bin/sh
printf '%s\\n' "$*" >> "$CALLS"
case "$*" in
  'compose version') exit 0;;
  'image load --input '*) exit 0;;
  'image inspect --format {{.Id}} '*) for arg; do last=$arg; done; printf '%s\\n' "$last";;
  'image inspect --format {{.Os}}/{{.Architecture}} '*) printf '%s\\n' "${TEST_PLATFORM:-linux/amd64}";;
  *) exit 91;;
esac
''')
    (bin_dir / 'curl').write_text('#!/bin/sh\nexit 92\n')
    for path in bin_dir.iterdir():
        path.chmod(0o700)
    env = dict(os.environ, PATH=f'{bin_dir}:{os.environ["PATH"]}', CALLS=str(tmp_path / 'calls'),
               CAPSTONE_TRIAL_DIRECTORY=str(tmp_path / 'installation'))
    return out, env


def install(delivery):
    out, env = delivery
    return subprocess.run(['sh', str(out / 'install-offline.sh')], env=env, capture_output=True, text=True)


def test_offline_install_has_no_downloads_and_repeat_keeps_private_files(delivery):
    out, env = delivery
    result = install(delivery)
    assert result.returncode == 0, result.stderr
    root = Path(env['CAPSTONE_TRIAL_DIRECTORY'])
    (root / '.env').write_text('OPENAI_API_KEY=secret-canary\n')
    private = root / 'versions' / REVISION / '.capstone-trial' / 'capstone-user-existing'
    private.mkdir(parents=True)
    (private / 'internal.env').write_text('private-canary')
    (private / 'installation.json').write_text('old receipt')
    result = install(delivery)
    assert result.returncode == 0, result.stderr
    assert (root / '.env').read_text() == 'OPENAI_API_KEY=secret-canary\n'
    assert (private / 'internal.env').read_text() == 'private-canary'
    assert (private / 'installation.json').read_text() == 'old receipt'
    calls = Path(env['CALLS']).read_text()
    assert 'pull' not in calls and 'stop' not in calls
    assert 'secret-canary' not in result.stdout + result.stderr


@pytest.mark.parametrize('failure', ['checksum', 'missing', 'platform'])
def test_offline_inputs_fail_before_existing_services_stop(delivery, failure):
    out, env = delivery
    if failure == 'checksum':
        (out / 'objects.tar').write_bytes(b'corrupt')
    elif failure == 'missing':
        (out / 'objects.tar').unlink()
    else:
        env['TEST_PLATFORM'] = 'linux/arm64'
    result = install(delivery)
    assert result.returncode != 0
    assert not Path(env['CAPSTONE_TRIAL_DIRECTORY']).exists()
    calls = Path(env['CALLS'])
    if failure != 'platform':
        assert not calls.exists()
    else:
        assert 'stop' not in calls.read_text()


def test_manager_uses_imported_config_ids_without_registry_digests():
    spec = importlib.util.spec_from_file_location('offline_manager_fixture', ROOT / 'tools/tests/test_capstone_manager.py')
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    case = fixture.ManagerTests()
    case.setUp()
    try:
        package = case.package(fixture.A)
        images = {key: 'sha256:' + str(i) * 64 for i, key in enumerate(KINDS)}
        (package / 'manifest.json').write_text(json.dumps({'schema': 'capstone-dev-trial/1',
            'channel': 'dev-trial-offline', 'platforms': ['linux/amd64'], 'source_revision': fixture.A, 'images': images}))
        (package / 'release.env').write_text(''.join(f'CAPSTONE_{key.upper()}_IMAGE={ref}\n' for key, ref in images.items()) + 'CAPSTONE_TRIAL_PLATFORM=linux/amd64\n')
        database = json.loads(case.db.read_text())
        database['images'] = {ref: {'id': ref, 'source': fixture.A, 'date': '2026-10-01T00:00:00Z'} for ref in images.values()}
        case.db.write_text(json.dumps(database))
        docker = case.bin / 'docker'
        docker.write_text(docker.read_text().replace("'amd64' if 'Architecture'", "'linux/amd64' if '.Os' in fmt else 'amd64' if 'Architecture'"))
        result = case.run_manager('start', fixture.A)
        assert result.returncode == 0, result.stderr
        assert (case.state / 'active').read_text().strip() == fixture.A
    finally:
        case.doCleanups()
