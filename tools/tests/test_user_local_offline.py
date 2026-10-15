"""Offline transport tests. Docker metadata is simulated; archives are real."""
import hashlib
import gzip
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


def image_archive(path, tag, *, architecture='amd64', bad_digest=False, wrong_config=False,
                  bad_config_digest=False, source_revision=REVISION):
    """Write the exact OCI and Docker metadata emitted by a tagged save."""
    config = json.dumps({'architecture': architecture, 'os': 'linux',
                        'rootfs': {'type': 'layers', 'diff_ids': []},
                        'config': {'Labels': {'org.opencontainers.image.revision': source_revision}}}).encode()
    config_digest = 'sha256:' + hashlib.sha256(config).hexdigest()
    leaf = json.dumps({'schemaVersion': 2, 'config': {'digest': config_digest,
                       'size': len(config), 'mediaType': 'application/vnd.oci.image.config.v1+json'},
                       'layers': []}).encode()
    manifest_digest = 'sha256:' + hashlib.sha256(leaf).hexdigest()
    index = {'schemaVersion': 2, 'manifests': [{
        'mediaType': 'application/vnd.oci.image.manifest.v1+json',
        'digest': manifest_digest, 'size': len(leaf),
        'annotations': {'io.containerd.image.name': 'docker.io/' + tag}}]}
    docker_manifest = [{'Config': 'blobs/sha256/' + ('f' * 64 if wrong_config else config_digest[7:]),
                        'RepoTags': [tag], 'Layers': []}]
    entries = {'manifest.json': json.dumps(docker_manifest).encode(), 'index.json': json.dumps(index).encode(),
               'blobs/sha256/' + config_digest[7:]: config + b' ' if bad_config_digest else config,
               'blobs/sha256/' + manifest_digest[7:]: b'corrupt' if bad_digest else leaf,
               'oci-layout': b'{"imageLayoutVersion":"1.0.0"}'}
    with tarfile.open(path, 'w') as target:
        for name, data in entries.items():
            info = tarfile.TarInfo(name); info.size = len(data)
            target.addfile(info, io.BytesIO(data))
    return config_digest, manifest_digest


def layered_image_archive(path, tag, *, codec='raw', failure=None):
    blobs = {}
    layers, diff_ids, paths = [], [], []
    for ordinal in range(2):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w') as layer:
            data = ('registered-layer-' + str(ordinal)).encode()
            item = tarfile.TarInfo('file-' + str(ordinal)); item.size = len(data)
            layer.addfile(item, io.BytesIO(data))
        raw = stream.getvalue()
        encoded = gzip.compress(raw, mtime=0) if codec == 'gzip' else raw
        if failure == 'invalid_gzip' and ordinal == 0:
            encoded = b'not-a-gzip-layer'
        digest = 'sha256:' + hashlib.sha256(encoded).hexdigest()
        name = 'blobs/sha256/' + digest[7:]
        media = 'application/vnd.oci.image.layer.v1.tar' + ('+gzip' if codec == 'gzip' else '')
        layers.append({'mediaType': media, 'digest': digest, 'size': len(encoded)})
        diff_ids.append('sha256:' + hashlib.sha256(raw).hexdigest())
        paths.append(name)
        if not (failure == 'missing_layer' and ordinal == 0):
            blobs[name] = bytes([encoded[0] ^ 1]) + encoded[1:] if failure == 'wrong_layer_digest' and ordinal == 0 else encoded
    if failure == 'wrong_layer_size': layers[0]['size'] += 1
    if failure == 'unknown_codec': layers[0]['mediaType'] = 'application/vnd.oci.image.layer.v1.tar+zstd'
    if failure == 'diff_id_order': diff_ids.reverse()
    config = json.dumps({'architecture': 'amd64', 'os': 'linux',
                         'rootfs': {'type': 'layers', 'diff_ids': diff_ids},
                         'config': {'Labels': {'org.opencontainers.image.revision': REVISION}}}).encode()
    config_digest = 'sha256:' + hashlib.sha256(config).hexdigest()
    leaf = json.dumps({'schemaVersion': 2, 'config': {'digest': config_digest, 'size': len(config)},
                       'layers': layers}).encode()
    leaf_digest = 'sha256:' + hashlib.sha256(leaf).hexdigest()
    blobs.update({'blobs/sha256/' + config_digest[7:]: config, 'blobs/sha256/' + leaf_digest[7:]: leaf,
        'manifest.json': json.dumps([{'Config': 'blobs/sha256/' + config_digest[7:], 'RepoTags': [tag],
                                     'Layers': list(reversed(paths)) if failure == 'legacy_layer_order' else paths}]).encode(),
        'index.json': json.dumps({'manifests': [{'digest': leaf_digest, 'size': len(leaf),
            'mediaType': 'application/vnd.oci.image.manifest.v1+json',
            'annotations': {'io.containerd.image.name': 'docker.io/' + tag}}]}).encode()})
    with tarfile.open(path, 'w') as target:
        for name, data in blobs.items():
            info = tarfile.TarInfo(name); info.size = len(data)
            target.addfile(info, io.BytesIO(data))


@pytest.mark.parametrize('codec', ['raw', 'gzip'])
@pytest.mark.parametrize('failure', ['missing_layer', 'wrong_layer_digest', 'wrong_layer_size',
                                    'legacy_layer_order', 'diff_id_order', 'unknown_codec', 'invalid_gzip'])
def test_export_refuses_incomplete_or_unbound_layers(tmp_path, codec, failure):
    exporter = load('build_user_local_offline')
    tag = 'capstone-offline/app:' + REVISION
    archive = tmp_path / 'layered.tar'
    layered_image_archive(archive, tag, codec=codec, failure=failure)
    with pytest.raises(ValueError):
        exporter.read_archive_identity(archive, 'app', tag, REVISION)


@pytest.mark.parametrize('codec', ['raw', 'gzip'])
def test_export_admits_verified_raw_and_gzip_layer_chains(tmp_path, codec):
    exporter = load('build_user_local_offline')
    tag = 'capstone-offline/app:' + REVISION
    archive = tmp_path / 'layered.tar'
    layered_image_archive(archive, tag, codec=codec)
    assert exporter.read_archive_identity(archive, 'app', tag, REVISION)['tag'] == tag


@pytest.mark.parametrize('duplicate', ['index.json', 'layer'])
def test_export_refuses_duplicate_metadata_or_layer_members(tmp_path, duplicate):
    exporter = load('build_user_local_offline')
    tag = 'capstone-offline/app:' + REVISION
    archive = tmp_path / 'duplicate.tar'
    layered_image_archive(archive, tag)
    with tarfile.open(archive) as source:
        name = duplicate if duplicate != 'layer' else json.load(source.extractfile('manifest.json'))[0]['Layers'][0]
        data = source.extractfile(name).read()
    with tarfile.open(archive, 'a') as target:
        info = tarfile.TarInfo(name); info.size = len(data)
        target.addfile(info, io.BytesIO(data))
    with pytest.raises(ValueError):
        exporter.read_archive_identity(archive, 'app', tag, REVISION)


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
    inputs = builder.BUNDLE_INPUTS | {'deploy/dev-trial/install-version.sh', 'deploy/dev-trial/install-offline.sh',
                                    'deploy/dev-trial/offline-validation-samples.txt'}
    (source / 'trial-context.json').write_text(json.dumps({'source_revision': REVISION,
        'data_inputs': {name: hashlib.sha256(data).hexdigest() for name, data in builder.data_contract.context_files(source).items()},
        'inputs': {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in inputs}}))
    return source


@pytest.mark.parametrize('source_id_kind', ['config', 'manifest'])
@pytest.mark.parametrize('build_umask', [0o022, 0o077])
def test_export_checks_platform_source_and_streamed_archive_hashes(tmp_path, monkeypatch, source_id_kind, build_umask):
    exporter = load('build_user_local_offline')
    source = context(tmp_path)
    monkeypatch.setenv('OPENAI_API_KEY', 'export-secret-canary')
    refs = {key: 'fixture-' + key for key in KINDS}
    canonical, manifest = image_archive(tmp_path / 'fixture.tar', 'fixture')
    metadata = {ref: {'Id': canonical if source_id_kind == 'config' else manifest, 'Os': 'linux', 'Architecture': 'amd64',
        'RepoDigests': ['wrong-source-digest@sha256:' + 'f' * 64],
        'Config': {'Labels': {'org.opencontainers.image.revision': REVISION}}} for ref in refs.values()}
    def run(args, **kwargs):
        if args[:3] == ['docker', 'image', 'inspect']:
            return subprocess.CompletedProcess(args, 0, json.dumps([metadata[args[-1]]]))
        if args[:3] == ['docker', 'image', 'save']:
            image_archive(Path(args[args.index('--output') + 1]), args[-1])
            return subprocess.CompletedProcess(args, 0)
        if args[:3] == ['docker', 'image', 'tag']:
            assert args[-1].startswith('capstone-offline/') and args[-1].endswith(':' + REVISION)
            return subprocess.CompletedProcess(args, 0)
        raise AssertionError(args)
    monkeypatch.setattr(exporter.subprocess, 'run', run)
    out = tmp_path / 'offline'
    previous_umask = os.umask(build_umask)
    try:
        result = exporter.export_bundle(source, out, REVISION, refs)
    finally:
        os.umask(previous_umask)
    assert result['channel'] == 'dev-trial-offline'
    assert result['images'] == {key: canonical for key in KINDS}
    assert [row['kind'] for row in result['offline_image_identities']] == list(KINDS)
    for row in result['offline_image_identities']:
        assert row['tag'] == 'capstone-offline/' + row['kind'] + ':' + REVISION
        assert row['config_digest'] == canonical
        assert row['manifest_digest'] != canonical
        assert row['platform'] == 'linux/amd64'
    assert all(len(line.split('\t')) == 6 for line in (out / 'images.tsv').read_text().splitlines())
    assert json.loads((out / 'manifest.json').read_text()) == result
    samples = (source / 'deploy/dev-trial/offline-validation-samples.txt').read_text()
    assert samples in (out / 'README.txt').read_text()
    for name in ['README.txt', 'README.md']:
        guide = (out / name).read_text()
        assert guide.index('默认使用 pandapower 的 IEEE39 电网') < guide.index('1. 前提与校验')
        assert guide.index('可选说明：其他预装电网') > guide.index('5. 数据与排错')
        assert 'PyPSA示例包括' not in guide.split('可选说明：其他预装电网')[0]
    with tarfile.open(out / 'deployment.tar.gz') as bundle:
        assert bundle.getmember('manifest.json').mode == 0o644
        assert json.load(bundle.extractfile('manifest.json')) == result
        settings = bundle.extractfile('.env').read().decode()
        assert 'PROVIDER=openai\nOPENAI_MODEL=deepseek-flash\nOPENAI_BASE_URL=\n' in settings
        assert 'CAPSTONE_PUBLIC_' not in settings
        assert bundle.extractfile('.env.example').read().decode() == settings
        assert samples in bundle.extractfile('README.txt').read().decode()
        for name in ['README.txt', 'README.md']:
            guide = bundle.extractfile(name).read().decode()
            assert guide.index('默认使用 pandapower 的 IEEE39 电网') < guide.index('默认PROVIDER=')
            assert guide.index('可选说明：其他预装电网') > guide.index(samples.splitlines()[0])
            assert all(model in guide.split('可选说明：其他预装电网')[1] for model in [
                'AC-DC Meshed', 'Storage-HVDC', 'SciGrid-DE', 'Model-Energy', 'Stochastic-Network', 'Carbon Management'])
    for line in (out / 'SHA256SUMS').read_text().splitlines():
        checksum, name = line.split('  ')
        assert hashlib.sha256((out / name).read_bytes()).hexdigest() == checksum
        assert b'export-secret-canary' not in (out / name).read_bytes()
    metadata[refs['backend']]['Architecture'] = 'arm64'
    with pytest.raises(ValueError, match='platform'):
        exporter.export_bundle(source, tmp_path / 'wrong', REVISION, refs)
    assert not (tmp_path / 'wrong').exists()
    metadata[refs['backend']]['Architecture'] = 'amd64'
    metadata[refs['app']]['Config']['Labels']['org.opencontainers.image.revision'] = 'b' * 40
    with pytest.raises(ValueError, match='source'):
        exporter.export_bundle(source, tmp_path / 'wrong-source', REVISION, refs)
    (source / 'deploy/dev-trial/offline-validation-samples.txt').write_text('changed samples')
    with pytest.raises(ValueError, match='samples differ'):
        exporter.export_bundle(source, tmp_path / 'wrong-samples', REVISION, refs)
    assert not (tmp_path / 'wrong-samples').exists()


@pytest.mark.parametrize('failure', ['manifest_sha', 'config_sha', 'config_relation', 'tag', 'platform', 'source'])
def test_export_validates_actual_archive_identity(tmp_path, failure):
    exporter = load('build_user_local_offline')
    tag = 'capstone-offline/app:' + REVISION
    path = tmp_path / 'image.tar'
    image_archive(path, 'wrong-tag' if failure == 'tag' else tag,
                  bad_digest=failure == 'manifest_sha', wrong_config=failure == 'config_relation',
                  bad_config_digest=failure == 'config_sha',
                  architecture='arm64' if failure == 'platform' else 'amd64',
                  source_revision='b' * 40 if failure == 'source' else REVISION)
    with pytest.raises(ValueError):
        exporter.read_archive_identity(path, 'app', tag, REVISION)


@pytest.fixture
def delivery(tmp_path):
    out = tmp_path / 'delivery'
    out.mkdir()
    files = {name: b'fixture\n' for name in ['compose.yaml', 'start.sh', '.env', '.env.example',
        'README.txt', 'data-contract.env', 'install.sh']}
    identities = [{'kind': kind, 'tag': 'capstone-offline/' + kind + ':' + REVISION,
                   'config_digest': 'sha256:' + str(i) * 64,
                   'manifest_digest': 'sha256:' + str(i + 4) * 64, 'platform': 'linux/amd64'}
                  for i, kind in enumerate(KINDS)]
    manifest = {'schema': 'capstone-dev-trial/1', 'channel': 'dev-trial-offline',
                'source_revision': REVISION, 'platforms': ['linux/amd64'],
                'images': {row['kind']: row['config_digest'] for row in identities},
                'offline_image_identities': identities}
    files['manifest.json'] = json.dumps(manifest, indent=2).encode()
    files['release.env'] = ''.join(f'CAPSTONE_{kind.upper()}_IMAGE=sha256:{i * 64}\n' for i, kind in zip('0123', KINDS)).encode()
    files['capstone.sh'] = b'#!/bin/sh\n[ "${TEST_REJECT_START:-0}" != 1 ] || exit 1\nprintf "manager %s %s\\n" "$1" "$2"\n'
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
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    (out / 'README.txt').write_text('offline fixture')
    (out / 'versions.tsv').write_text(catalog_row(REVISION))
    (out / 'images.tsv').write_text(''.join('\t'.join([row['kind'], row['tag'], row['config_digest'],
        row['manifest_digest'], row['platform'], row['kind'] + '.tar']) + '\n' for row in identities))
    for kind in KINDS:
        (out / (kind + '.tar')).write_bytes(b'image fixture')
    (out / 'SHA256SUMS').write_text(''.join(digest(path) + '  ' + path.name + '\n' for path in out.iterdir()))
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    (bin_dir / 'docker').write_text('#!' + os.sys.executable + '\n' + '''
import os,sys
a=sys.argv[1:]
with open(os.environ['CALLS'],'a') as f: f.write(' '.join(a)+'\\n')
if a[:2]==['compose','version'] or a[:2]==['image','load'] or a[0]=='run': sys.exit(0)
if a[:3]==['image','inspect','--format']:
 fmt,ref=a[3:5]
 if '.Id' in fmt:
  if os.environ.get('TEST_MISSING_TAG'): sys.exit(1)
  if ref.startswith('sha256:'): identity=ref
  else:
   kind=ref.split('/')[1].split(':')[0]
   digit=('backend','app','postgres','objects').index(kind)
   if os.environ.get('TEST_DAEMON')=='manifest': digit+=4
   identity='sha256:'+str(digit)*64
  print(os.environ.get('TEST_BAD_ID',identity))
 elif '.Os' in fmt: print(os.environ.get('TEST_PLATFORM','linux/amd64'))
 elif 'org.opencontainers.image.revision' in fmt: print(os.environ.get('TEST_SOURCE_LABEL','a'*40))
 else: sys.exit(91)
else: sys.exit(91)
''')
    (bin_dir / 'curl').write_text('#!/bin/sh\nexit 92\n')
    for path in bin_dir.iterdir():
        path.chmod(0o700)
    env = dict(os.environ, PATH=f'{bin_dir}:{os.environ["PATH"]}', CALLS=str(tmp_path / 'calls'),
               CAPSTONE_TRIAL_DIRECTORY=str(tmp_path / 'installation'))
    return out, env


def refresh_checksums(out):
    (out / 'SHA256SUMS').write_text(''.join(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + path.name + '\n'
        for path in out.iterdir() if path.name != 'SHA256SUMS'))


@pytest.mark.parametrize('daemon', ['config', 'manifest'])
@pytest.mark.parametrize('markdown', [False, True])
def test_loader_selects_only_verified_daemon_ids_in_private_file(delivery, daemon, markdown):
    out, env = delivery
    if markdown:
        (out / 'README.md').write_text('# Offline user guide\n')
    original_manifest = (out / 'manifest.json').read_bytes()
    capture = out.parent / 'selected.tsv'
    env.update(TEST_DAEMON=daemon, CAPTURE=str(capture), OPENAI_API_KEY='secret-canary')
    (out / 'install-version.sh').write_text('''#!/bin/sh
set -eu
[ -f "$CAPSTONE_OFFLINE_IMAGE_SELECTION" ] && [ ! -L "$CAPSTONE_OFFLINE_IMAGE_SELECTION" ]
[ "$(ls -l "$CAPSTONE_OFFLINE_IMAGE_SELECTION" | awk '{print $1}')" = '-rw-------' ]
cp "$CAPSTONE_OFFLINE_IMAGE_SELECTION" "$CAPTURE"
printf '%s\\n' "$CAPSTONE_OFFLINE_IMAGE_SELECTION" > "$CAPTURE.path"
printf 'install-ready\\n' >> "$CALLS"
''')
    refresh_checksums(out)
    result = install(delivery)
    assert result.returncode == 0, result.stderr
    offset = 0 if daemon == 'config' else 4
    assert capture.read_text() == ''.join(f'{kind}\tsha256:{str(i + offset) * 64}\n' for i, kind in enumerate(KINDS))
    assert not Path(Path(str(capture) + '.path').read_text().strip()).exists()
    assert (out / 'manifest.json').read_bytes() == original_manifest
    calls = Path(env['CALLS']).read_text().splitlines()
    assert sum(line.startswith('image load ') for line in calls) == 4
    assert calls[-1] == 'install-ready'
    assert 'secret-canary' not in result.stdout + result.stderr + capture.read_text() + '\n'.join(calls)


@pytest.mark.parametrize('failure', ['tag', 'missing_tag', 'digest', 'source_label'])
def test_loader_rejects_unverified_identity_before_install(delivery, failure):
    out, env = delivery
    if failure == 'tag':
        (out / 'images.tsv').write_text((out / 'images.tsv').read_text().replace('capstone-offline/backend:', 'wrong/backend:'))
        refresh_checksums(out)
    else:
        env[{'missing_tag': 'TEST_MISSING_TAG', 'digest': 'TEST_BAD_ID', 'source_label': 'TEST_SOURCE_LABEL'}[failure]] = 'sha256:' + 'f' * 64
    result = install(delivery)
    assert result.returncode != 0
    assert not Path(env['CAPSTONE_TRIAL_DIRECTORY']).exists()


def install(delivery):
    out, env = delivery
    return subprocess.run(['sh', str(out / 'install-offline.sh')], env=env, capture_output=True, text=True)


@pytest.mark.parametrize('defect', ['unlisted', 'changed', 'symlink'])
def test_loader_rejects_unverified_markdown_before_docker(delivery, defect):
    out, env = delivery
    guide = out / 'README.md'
    guide.write_text('# Offline user guide\n')
    if defect != 'unlisted':
        refresh_checksums(out)
    if defect == 'changed':
        guide.write_text('changed guide')
    elif defect == 'symlink':
        guide.unlink()
        guide.symlink_to(out / 'README.txt')
    result = install(delivery)
    assert result.returncode != 0
    assert not Path(env['CALLS']).exists()
    assert not Path(env['CAPSTONE_TRIAL_DIRECTORY']).exists()


def test_loader_rejects_lookalike_archive_name_before_docker(delivery):
    out, env = delivery
    (out / 'backendXtar').write_bytes((out / 'backend.tar').read_bytes())
    checksums = out / 'SHA256SUMS'
    checksums.write_text(checksums.read_text().replace('  backend.tar\n', '  backendXtar\n'))
    result = install(delivery)
    assert result.returncode != 0
    assert not Path(env['CALLS']).exists()


def catalog_row(revision, checksum='0' * 64):
    tag = 'user-local-' + revision[:12]
    return f'{revision}\t{tag}\thttps://github.com/uukuguy/capstone/releases/download/{tag}/install.sh\t{checksum}\t2026-10-15\n'


def test_failed_offline_start_retains_previous_catalog_and_repeat_deduplicates(delivery):
    _, env = delivery
    root = Path(env['CAPSTONE_TRIAL_DIRECTORY'])
    meta = root / '.capstone-management'
    meta.mkdir(parents=True)
    previous = 'b' * 40
    old_row = catalog_row(previous)
    (meta / 'versions.tsv').write_text(old_row)
    env['TEST_REJECT_START'] = '1'
    for _ in range(2):
        result = install(delivery)
        assert result.returncode != 0
        rows = (meta / 'versions.tsv').read_text()
        assert rows == catalog_row(REVISION) + old_row
        assert previous in rows
        assert 'stop' not in Path(env['CALLS']).read_text()


@pytest.mark.parametrize('existing', ['conflict', 'invalid', 'oversize'])
def test_offline_catalog_merge_rejects_invalid_or_conflicting_existing_rows(delivery, existing):
    _, env = delivery
    root = Path(env['CAPSTONE_TRIAL_DIRECTORY'])
    meta = root / '.capstone-management'
    meta.mkdir(parents=True)
    original = catalog_row(REVISION, '1' * 64) if existing == 'conflict' else 'invalid\n' if existing == 'invalid' else '#' * 1048577
    (meta / 'versions.tsv').write_text(original)
    result = install(delivery)
    assert result.returncode != 0
    assert (meta / 'versions.tsv').read_text() == original
    assert not (root / 'capstone.sh').exists()


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
    assert not any(line.startswith(('pull ', 'image pull ', 'stop ')) for line in calls.splitlines())
    assert all('--pull never' in line for line in calls.splitlines() if line.startswith('run '))
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
