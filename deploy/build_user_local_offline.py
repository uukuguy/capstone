"""Export four existing Linux AMD64 images with a frozen source-free deployment."""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

KINDS = ('backend', 'app', 'postgres', 'objects')


def _builder():
    spec = importlib.util.spec_from_file_location('offline_trial_builder', Path(__file__).with_name('build_dev_trial.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def export_bundle(context: Path, output: Path, revision: str, images: dict) -> dict:
    if (not re.fullmatch(r'[a-f0-9]{40}', revision) or set(images) != set(KINDS)
            or output.exists() or any(p.is_symlink() for p in [output, *output.parents])):
        raise ValueError('Select an exact source, four images and a new output')
    receipt = json.loads((context / 'trial-context.json').read_text())
    if receipt.get('source_revision') != revision:
        raise ValueError('Offline context source differs')
    # Transport scripts must also come from the frozen context.
    for name in ['install-offline.sh', 'install-version.sh']:
        path = 'deploy/dev-trial/' + name
        if checksum(context / path) != receipt.get('inputs', {}).get(path):
            raise ValueError('Offline installer differs from the frozen context')
    identities = {}
    for kind in KINDS:
        result = subprocess.run(['docker', 'image', 'inspect', images[kind]], check=True,
                                capture_output=True, text=True)
        metadata = json.loads(result.stdout)[0]
        if metadata.get('Os') != 'linux' or metadata.get('Architecture') != 'amd64':
            raise ValueError('Offline image platform must be linux/amd64')
        if kind in {'backend', 'app'} and metadata.get('Config', {}).get('Labels', {}).get(
                'org.opencontainers.image.revision') != revision:
            raise ValueError('Offline image source differs')
        identity = metadata.get('Id', '')
        if not re.fullmatch(r'sha256:[a-f0-9]{64}', identity):
            raise ValueError('Offline image ID is invalid')
        identities[kind] = identity
    builder = _builder()
    # A separate offline channel keeps online dual-platform acceptance unchanged.
    deployment = output / 'deployment'
    document = builder.write_bundle(context, deployment, revision, identities, ['linux/amd64'], candidate=True)
    document['channel'] = 'dev-trial-offline'
    (deployment / 'manifest.json').write_text(json.dumps(document, indent=2, sort_keys=True) + '\n')
    settings = ('# Keep OPENAI_API_KEY in the startup environment.\n'
                'PROVIDER=openai\nOPENAI_MODEL=deepseek-flash\nOPENAI_BASE_URL=\n'
                'CAPSTONE_APP_PORT=19173\n')
    for name in ['.env', '.env.example']:
        (deployment / name).write_text(settings)
    # Config IDs intentionally give storage a conservative new data identity.
    # The existing data guard must block upgrades from unverified registry refs.
    (deployment / 'install.sh').write_text('#!/bin/sh\nprintf "%s\\n" "Use the original offline package install-offline.sh to install a version." >&2\nexit 1\n')
    (deployment / 'README.txt').write_text(
        'Capstone user-local offline package\nSource: ' + revision + '\n'
        'Linux AMD64 and Docker Compose v2 are required. Models are in the backend image.\n'
        'Set OPENAI_API_KEY in the startup environment. Edit .env for OPENAI_BASE_URL and OPENAI_MODEL.\n'
        'Keep the installation directory and its private state. Stop preserves all data.\n'
        'Use capstone.sh start, status, logs, stop or versions.\n'
        'The data contract blocks unverified backend and storage changes.\n')
    archive = output / 'deployment.tar.gz'
    with tarfile.open(archive, 'w:gz') as target:
        for path in sorted(deployment.iterdir()):
            target.add(path, arcname=path.name, recursive=False)
    for path in deployment.iterdir():
        path.unlink()
    deployment.rmdir()
    (output / 'images.tsv').write_text(''.join(f'{kind}\t{identities[kind]}\tlinux/amd64\t{kind}.tar\n' for kind in KINDS))
    for kind in KINDS:
        subprocess.run(['docker', 'image', 'save', '--output', str(output / (kind + '.tar')), identities[kind]], check=True)
    version = 'user-local-' + revision[:12]
    script = (context / 'deploy/dev-trial/install-version.sh').read_text()
    for key, value in {'@VERSION@': version, '@ARCHIVE_URL@': 'offline', '@ARCHIVE_SHA256@': checksum(archive), '@SOURCE_REVISION@': revision}.items():
        script = script.replace(key, value)
    (output / 'install-version.sh').write_text(script)
    shutil.copyfile(context / 'deploy/dev-trial/install-offline.sh', output / 'install-offline.sh')
    (output / 'versions.tsv').write_text(f'{revision}\t{version}\thttps://github.com/uukuguy/capstone/releases/download/{version}/install.sh\t{checksum(output / "install-version.sh")}\t{date.today().isoformat()}\n')
    (output / 'manifest.json').write_text(json.dumps(document, indent=2, sort_keys=True) + '\n')
    (output / 'README.txt').write_text(
        'Capstone user-local offline installation\nSource: ' + revision + '\n\n'
        'Prerequisites: Linux AMD64, Docker Engine and Docker Compose v2.\n'
        'The package includes all four images and the six model assets. No public download is required.\n'
        'Compare the SHA256SUMS file hash with the delivery receipt. The installer verifies every listed file.\n'
        'Set OPENAI_API_KEY in the startup environment. Do not put the Key in command arguments.\n'
        'Set OPENAI_BASE_URL to your internal OpenAI-compatible endpoint in the startup environment.\n'
        'Default Provider: openai. Default OPENAI_MODEL: deepseek-flash.\n'
        'Run: sh install-offline.sh\n'
        'Default installation: $HOME/capstone. Set CAPSTONE_TRIAL_DIRECTORY to select another directory.\n'
        'Default App URL: http://127.0.0.1:19173/\n'
        'Edit the installation .env to change the endpoint, model or App port; restart with capstone.sh start.\n'
        'Run sh "$HOME/capstone/capstone.sh" status, logs, stop, start or versions.\n'
        'Stop retains all data. Preserve the installation directory and its private configuration.\n'
        'Repeat installation preserves .env, receipts, private credentials and Docker volumes.\n'
        'An existing installation with a different data format is blocked before its services stop.\n'
        'Use a new installation directory for separate data, or obtain a verified migration. Do not remove the data guard.\n'
        'Packaging checks do not call a real Provider. Configure access to your internal LLM before startup.\n')
    names = ['deployment.tar.gz', 'images.tsv', 'versions.tsv', 'manifest.json', 'install-version.sh', 'install-offline.sh', 'README.txt'] + [kind + '.tar' for kind in KINDS]
    (output / 'SHA256SUMS').write_text(''.join(checksum(output / name) + '  ' + name + '\n' for name in names))
    return document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--context', type=Path, required=True)
    parser.add_argument('--source-revision', required=True)
    parser.add_argument('--image-manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        identity = json.loads(args.image_manifest.read_text())
        if identity.get('source_revision') != args.source_revision:
            raise ValueError('Image source differs')
        output = _builder()._new_output(args.root, args.output)
        document = export_bundle(args.context, output, args.source_revision, identity['images'])
        print(json.dumps({'output': str(output), 'manifest': document, 'checksums_sha256': checksum(output / 'SHA256SUMS')}))
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        parser.exit(1, 'Offline export failed. Check the frozen source and four local AMD64 images.\n')


if __name__ == '__main__':
    main()
