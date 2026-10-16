"""Source-bound conservative guard, not a substitute for migration/old-data tests.

Backend or dependency changes require verification even when no migration is
needed. Source revisions, App files, manager files and timestamps do not affect
the format digest. The CLI reads an exact Git archive without extracting it.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile

MAX_FILES = 100000
MAX_BYTES = 512 * 1024 * 1024
REQUIRED = {'pyproject.toml', 'uv.lock', 'deploy/dev_trial_runtime.py'}
MANIFESTS = {'pyproject.toml', 'uv.lock', 'package.json', 'package-lock.json',
             'pnpm-lock.yaml', 'yarn.lock', 'poetry.lock', 'Pipfile', 'Pipfile.lock',
             'setup.py', 'setup.cfg'}


def selected(name: str) -> bool:
    parts = PurePosixPath(name).parts
    if any(part in {'__pycache__', 'tests', 'capstone-app'} for part in parts):
        return False
    return (name in REQUIRED or name.startswith(('schemas/', 'configs/capabilities/'))
            or (len(parts) > 3 and parts[0] == 'packages' and parts[2] == 'src')
            or (parts and (parts[-1] in MANIFESTS or parts[-1].startswith('requirements'))
                and (len(parts) == 1 or (len(parts) == 3 and parts[0] == 'packages'))))


def _descriptor(files: dict[str, bytes], revision: str, images: dict) -> dict[str, str]:
    if not re.fullmatch(r'[a-f0-9]{40}', revision):
        raise ValueError('An exact source revision is required')
    if not REQUIRED <= files.keys() or any(not any(name.startswith(prefix) for name in files)
            for prefix in ['packages/', 'schemas/', 'configs/capabilities/']):
        raise ValueError('Missing required persistence context input')
    if not any(name.startswith('packages/') and '/src/' in name for name in files):
        raise ValueError('Missing required backend source input')
    packages = {name.split('/')[1] for name in files
                if name.startswith('packages/') and '/src/' in name}
    if any(not any(f'packages/{package}/{manifest}' in files for manifest in MANIFESTS)
           for package in packages):
        raise ValueError('Missing required backend dependency manifest')
    if len(files) > MAX_FILES or sum(map(len, files.values())) > MAX_BYTES:
        raise ValueError('Persistence context exceeds bounds')
    digest = hashlib.sha256(b'capstone-data-format/1\0')
    entries = dict(files)
    for key in ['postgres', 'objects']:
        value = images.get(key)
        if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9][a-zA-Z0-9._:/@+-]*', value):
            raise ValueError('Exact storage image references are required')
        entries['@images/' + key] = value.encode('utf-8')
    for name, content in sorted(entries.items()):
        encoded = name.encode('utf-8')
        digest.update(len(encoded).to_bytes(8, 'big') + encoded)
        digest.update(len(content).to_bytes(8, 'big') + content)
    return {'CAPSTONE_DATA_CONTRACT_VERSION': '1',
            'CAPSTONE_DATA_SOURCE_REVISION': revision,
            'CAPSTONE_DATA_FORMAT_SHA256': digest.hexdigest()}


def context_files(context: Path) -> dict[str, bytes]:
    context = Path(context).absolute()
    if any(path.is_symlink() for path in [context, *context.parents]):
        raise ValueError('Context must not pass through a symlink')
    files = {}
    total = 0
    candidates = list(context.glob('*'))
    for directory in [context / 'schemas', context / 'configs/capabilities', context / 'packages']:
        if directory.is_symlink():
            raise ValueError('Persistence directory contains a symlink')
    for package in (context / 'packages').glob('*'):
        if package.name == 'capstone-app':
            continue
        if package.is_symlink() or (package / 'src').is_symlink():
            raise ValueError('Backend directory contains a symlink')
        candidates.extend(package.glob('*'))
        candidates.extend((package / 'src').rglob('*'))
    for directory in ['schemas', 'configs/capabilities']:
        candidates.extend((context / directory).rglob('*'))
    candidates.append(context / 'deploy/dev_trial_runtime.py')
    for path in candidates:
        name = path.relative_to(context).as_posix()
        if selected(name):
            if any(parent.is_symlink() for parent in [path, *path.parents]):
                raise ValueError('Persistence input contains a symlink')
            if path.is_file():
                total += path.stat().st_size
                if total > MAX_BYTES or len(files) >= MAX_FILES:
                    raise ValueError('Persistence input exceeds bounds')
                files[name] = path.read_bytes()
    return files


def generate_descriptor(context: Path, revision: str, images: dict) -> dict[str, str]:
    return _descriptor(context_files(context), revision, images)


def descriptor_from_git(root: Path, revision: str, images: dict) -> dict[str, str]:
    if not re.fullmatch(r'[a-f0-9]{40}', revision):
        raise ValueError('An exact source revision is required')
    archive = subprocess.run(['git', '-C', str(root), 'archive', '--format=tar', revision],
                             check=True, capture_output=True, timeout=60).stdout
    files = {}
    total = 0
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:
        for item in source:
            path = PurePosixPath(item.name)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('Unsafe archive path')
            if (item.issym() or item.islnk()) and (item.name in {'packages', 'schemas', 'configs',
                    'configs/capabilities', 'deploy'} or (path.parts and path.parts[0] == 'packages'
                    and 'capstone-app' not in path.parts and len(path.parts) <= 3)):
                raise ValueError('Persistence archive directory contains a symlink')
            if selected(item.name):
                if not (item.isfile() or item.isdir()):
                    raise ValueError('Persistence archive contains a symlink or unsafe entry')
                if item.isfile():
                    total += item.size
                    if total > MAX_BYTES or len(files) >= MAX_FILES or item.name in files:
                        raise ValueError('Persistence input exceeds bounds')
                    files[item.name] = source.extractfile(item).read()
    return _descriptor(files, revision, images)


def render_descriptor(descriptor: dict[str, str]) -> str:
    return ''.join(f'{key}={value}\n' for key, value in descriptor.items())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    origin = parser.add_mutually_exclusive_group(required=True)
    origin.add_argument('--context', type=Path)
    origin.add_argument('--git-root', type=Path)
    parser.add_argument('--source-revision', required=True)
    parser.add_argument('--image-manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        identity = json.loads(args.image_manifest.read_text())
        if identity.get('source_revision') != args.source_revision:
            raise ValueError('Image receipt source differs')
        function = generate_descriptor if args.context else descriptor_from_git
        result = render_descriptor(function(args.context or args.git_root, args.source_revision, identity['images']))
        if args.output:
            with args.output.open('x') as destination:
                destination.write(result)
        else:
            print(result, end='')
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        parser.exit(1, f'Data descriptor failed: {error}\n')


if __name__ == '__main__':
    main()
