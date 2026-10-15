"""Container-side trial installation checks. Never emit credential values."""
from __future__ import annotations

import argparse
from functools import lru_cache
import importlib.util
import json
import os
import platform
from pathlib import Path
import re
import secrets
import stat
import sys
from urllib.request import urlopen


class TrialConfigurationError(ValueError):
    """Public diagnostic with no input values."""


def _directory(path: Path) -> Path:
    path = Path(os.path.abspath(path))
    for parent in [path, *path.parents]:
        if parent.is_symlink():
            raise TrialConfigurationError('state directory must not be a symlink')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.is_dir():
        raise TrialConfigurationError('state directory is unavailable')
    return path


def _private_write(path: Path, content: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError:
        raise TrialConfigurationError('state file already exists') from None
    with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
        handle.write(content)


def initialize_private_environment(directory: Path) -> Path:
    directory = _directory(directory)
    path = directory / 'internal.env'
    names = ('POSTGRES_PASSWORD', 'S3_ACCESS_KEY', 'S3_SECRET_KEY', 'CAPSTONE_OPERATOR_TOKEN')
    if path.is_symlink():
        raise TrialConfigurationError('private configuration must not be a symlink')
    if path.exists():
        if not path.is_file() or stat.S_IMODE(path.stat().st_mode) != 0o600:
            raise TrialConfigurationError('private configuration requires mode0600')
        fields = dict(line.split('=', 1) for line in path.read_text().splitlines() if '=' in line)
        if set(fields) != set(names) or not all(re.fullmatch(r'[a-f0-9]{32,128}', value) for value in fields.values()):
            raise TrialConfigurationError('private configuration is invalid; existing data is preserved')
        return path
    _private_write(path, ''.join(name + '=' + secrets.token_hex(32) + '\n' for name in names))
    return path


def validate_manifest(document: dict) -> dict:
    offline = isinstance(document, dict) and document.get('channel') == 'dev-trial-offline'
    candidate = (isinstance(document, dict) and document.get('channel') == 'dev-trial-candidate'
                 and os.environ.get('CAPSTONE_CANDIDATE_VALIDATION') == '1')
    if (not isinstance(document, dict) or document.get('schema') != 'capstone-dev-trial/1'
            or document.get('channel') != ('dev-trial-offline' if offline else 'dev-trial-candidate' if candidate else 'dev-trial')
            or not re.fullmatch(r'[a-f0-9]{40}', str(document.get('source_revision', '')))):
        raise TrialConfigurationError('trial source manifest is invalid')
    allowed = [['linux/amd64']] if offline else ([['linux/amd64'], ['linux/arm64']] if candidate else [['linux/amd64', 'linux/arm64']])
    if document.get('platforms') not in allowed:
        raise TrialConfigurationError('candidate requires one Linux platform' if candidate else 'trial manifest requires both Linux platforms')
    images = document.get('images')
    if not isinstance(images, dict) or set(images) != {'backend', 'app', 'postgres', 'objects'}:
        raise TrialConfigurationError('trial requires four image classes')
    for name, reference in images.items():
        if offline:
            if not isinstance(reference, str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', reference):
                raise TrialConfigurationError('offline images require exact local image IDs')
            continue
        if candidate and isinstance(reference, str) and re.fullmatch(
                r'capstone-trial-' + name + r'(?:-amd64|-arm64)?:' + document['source_revision'], reference):
            continue
        if not isinstance(reference, str) or not re.fullmatch(r'[a-z0-9][a-z0-9._:/-]*@sha256:[a-f0-9]{64}', reference):
            raise TrialConfigurationError('trial image references must use exact digests')
    if 'offline_image_identities' in document:
        identities = document['offline_image_identities']
        if not offline or not isinstance(identities, list) or len(identities) != 4:
            raise TrialConfigurationError('offline image identities are invalid')
        seen = set()
        tags = set()
        for identity in identities:
            if (not isinstance(identity, dict)
                    or set(identity) != {'kind', 'tag', 'config_digest', 'manifest_digest', 'platform'}):
                raise TrialConfigurationError('offline image identity fields are invalid')
            kind = identity['kind']
            if not isinstance(kind, str) or kind not in images or kind in seen:
                raise TrialConfigurationError('offline image kinds are invalid')
            seen.add(kind)
            tag = identity['tag']
            if (not isinstance(tag, str) or not re.fullmatch(r'[a-z0-9][a-z0-9._/-]*:[a-zA-Z0-9_.-]+', tag)
                    or tag in tags or identity['platform'] != 'linux/amd64'):
                raise TrialConfigurationError('offline image locator or platform is invalid')
            tags.add(tag)
            for field in ('config_digest', 'manifest_digest'):
                if not isinstance(identity[field], str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', identity[field]):
                    raise TrialConfigurationError('offline image digest is invalid')
            if images[kind] not in {identity['config_digest'], identity['manifest_digest']}:
                raise TrialConfigurationError('offline runtime image is not bound to its archive')
    return document


def materialize_offline(bundle: Path, selection: Path) -> None:
    """Project verified daemon IDs without changing the static data contract."""
    bundle = _directory(bundle)
    manifest_path = bundle / 'manifest.json'
    release_path = bundle / 'release.env'
    for path in (manifest_path, release_path, selection):
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 1048576:
            raise TrialConfigurationError('offline projection input is invalid')
    document = validate_manifest(json.loads(manifest_path.read_text()))
    if document['channel'] != 'dev-trial-offline' or 'offline_image_identities' not in document:
        raise TrialConfigurationError('portable offline identities are required')
    chosen = {}
    for line in selection.read_text().splitlines():
        fields = line.split('\t')
        if len(fields) != 2 or fields[0] in chosen:
            raise TrialConfigurationError('offline runtime selection is invalid')
        chosen[fields[0]] = fields[1]
    document = validate_manifest(document | {'images': chosen})
    content = {
        manifest_path: json.dumps(document, indent=2, sort_keys=True) + '\n',
        release_path: ''.join(f'CAPSTONE_{kind.upper()}_IMAGE={chosen[kind]}\n'
                              for kind in ('backend', 'app', 'postgres', 'objects'))
                      + 'CAPSTONE_TRIAL_PLATFORM=linux/amd64\n',
    }
    staged = []
    try:
        for path, value in content.items():
            metadata = path.stat()
            temporary = path.with_name(path.name + '.new')
            _private_write(temporary, value)
            staged.append((temporary, path))
            # The root container helper must retain the installer user's ownership.
            if os.geteuid() == 0:
                os.chown(temporary, metadata.st_uid, metadata.st_gid)
        for temporary, path in staged:
            os.replace(temporary, path)
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)


def verify_image_source(root: Path, manifest: dict) -> None:
    manifest = validate_manifest(manifest)
    path = root / 'deploy/image-source.txt'
    if not path.is_file() or path.read_text().strip() != manifest['source_revision']:
        raise TrialConfigurationError('backend image source differs from the trial manifest')
    architecture = {'x86_64': 'amd64', 'aarch64': 'arm64', 'arm64': 'arm64'}.get(platform.machine())
    if 'linux/' + str(architecture) not in manifest['platforms']:
        raise TrialConfigurationError('backend image platform differs from the trial manifest')


def read_public_json(address: str) -> dict:
    with urlopen(address, timeout=10) as response:
        payload = response.read(8193)
    if len(payload) > 8192:
        raise TrialConfigurationError('public identity response is invalid')
    document = json.loads(payload)
    if not isinstance(document, dict):
        raise TrialConfigurationError('public identity response is invalid')
    return document


def check_readiness(manifest: dict) -> dict:
    manifest = validate_manifest(manifest)
    app = read_public_json('http://app:3000/__capstone-build')
    if (app.get('revision') != manifest['source_revision'] or app.get('environment') != 'local-dev'
            or app.get('dirty') is not False):
        raise TrialConfigurationError('App source differs from the trial manifest')
    if read_public_json('http://api:8766/health/ready').get('status') != 'ready':
        raise TrialConfigurationError('API is not ready')
    return {'schema': 'capstone-dev-trial-ready/1', 'source_revision': manifest['source_revision'],
            'status': 'deployment-ready'}


@lru_cache(maxsize=4)
def _runtime(root: Path):
    spec = importlib.util.spec_from_file_location('trial_host_runtime', root / 'deploy/launch_host_runtime.py')
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_configuration(root: Path, environment: dict[str, str], manifest: dict) -> dict:
    manifest = validate_manifest(manifest)
    settings = dict(environment)
    settings.update(CAPSTONE_RUNTIME_PROFILE='capstone-dev-trial-v1',
                    CAPSTONE_DEPLOYMENT_STAGE='local', CAPSTONE_HOSTED_APPLICATION='pandapower')
    _, _, _, selected = _runtime(root).select_runtime(root, settings, 'worker')
    if (manifest['channel'] == 'dev-trial-offline' and selected['CAPSTONE_PUBLIC_PROVIDER'] == 'openai'
            and not environment.get('OPENAI_BASE_URL', '').strip()):
        raise TrialConfigurationError('OPENAI_BASE_URL is required for the offline OpenAI-compatible Provider')
    if selected['CAPSTONE_PUBLIC_MODEL'] in {environment.get('DEEPSEEK_API_KEY'), environment.get('OPENAI_API_KEY')}:
        raise TrialConfigurationError('CAPSTONE_PUBLIC_MODEL')
    for key, name in [('CAPSTONE_BACKEND_IMAGE', 'backend'), ('CAPSTONE_APP_IMAGE', 'app'),
                      ('CAPSTONE_POSTGRES_IMAGE', 'postgres'), ('CAPSTONE_OBJECTS_IMAGE', 'objects')]:
        if key in environment and environment[key] != manifest['images'][name]:
            raise TrialConfigurationError('trial image configuration differs from its manifest')
    return {'schema': 'capstone-dev-trial-check/1', 'source_revision': manifest['source_revision'],
            'provider': selected['CAPSTONE_PUBLIC_PROVIDER'], 'model': selected['CAPSTONE_PUBLIC_MODEL'],
            'profile': selected['CAPSTONE_RUNTIME_PROFILE'], 'status': 'configuration-valid'}


def record_installation(directory: Path, manifest: dict, instance: str = 'capstone-user-local-dev') -> Path:
    document = validate_manifest(manifest)
    if not re.fullmatch(r'capstone-user-[a-z0-9_-]+', instance):
        raise TrialConfigurationError('CAPSTONE_INSTANCE')
    directory = _directory(directory)
    path = directory / 'installation.json'
    if path.is_symlink():
        raise TrialConfigurationError('installation receipt must not be a symlink')
    if path.exists():
        existing = json.loads(path.read_text())
        if (existing.get('source_revision') != document['source_revision'] or existing.get('images') != document['images']
                or existing.get('instance') != instance):
            raise TrialConfigurationError('installed source differs; preserve data and use an explicit upgrade plan')
        return path
    _private_write(path, json.dumps({'source_revision': document['source_revision'], 'instance': instance,
                                    'images': document['images']}, sort_keys=True) + '\n')
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('init', 'check', 'record', 'ready', 'materialize-offline', 'verify'))
    parser.add_argument('--state', type=Path, default=Path('/state'))
    parser.add_argument('--manifest', type=Path, default=Path('/bundle/manifest.json'))
    parser.add_argument('--bundle', type=Path, default=Path('/bundle'))
    parser.add_argument('--selection', type=Path, default=Path('/selection.tsv'))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    runtime = _runtime(root)
    try:
        if args.command == 'verify':
            verify_image_source(root, json.loads(args.manifest.read_text()))
            print('Trial image identity is valid.')
        elif args.command == 'materialize-offline':
            verify_image_source(root, json.loads((args.bundle / 'manifest.json').read_text()))
            materialize_offline(args.bundle, args.selection)
            print('Offline runtime image selection is ready.')
        elif args.command == 'init':
            initialize_private_environment(args.state)
            print('Local internal configuration is ready.')
        elif args.command == 'check':
            manifest = json.loads(args.manifest.read_text())
            result = validate_configuration(root, dict(os.environ), manifest)
            verify_image_source(root, manifest)
            print(json.dumps(result, sort_keys=True))
        elif args.command == 'ready':
            manifest = json.loads(args.manifest.read_text())
            verify_image_source(root, manifest)
            print(json.dumps(check_readiness(manifest), sort_keys=True))
        else:
            record_installation(args.state, json.loads(args.manifest.read_text()),
                                os.environ.get('CAPSTONE_INSTANCE', 'capstone-user-local-dev'))
            print('Trial source installation receipt is ready.')
        return 0
    except (TrialConfigurationError, runtime.RuntimeContractError) as error:
        print('Trial configuration failed: ' + str(error), file=sys.stderr)
    except (OSError, ValueError):
        print('Trial configuration failed: check local files and permissions.', file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
