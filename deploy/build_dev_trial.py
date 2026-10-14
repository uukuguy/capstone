"""Operator-only exact-source contexts and source-free trial bundles."""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile


def _git(root: Path, *arguments: str) -> bytes:
    return subprocess.run(['git', '-C', str(root), *arguments], check=True,
                          capture_output=True, timeout=60).stdout


def _new_output(root: Path, output: Path) -> Path:
    root = root.resolve()
    output = Path(output.absolute())
    if output.exists() or any(path.is_symlink() for path in [output, *output.parents]):
        raise ValueError('Output must be new and must not pass through a symlink')
    try:
        output.relative_to(root)
    except ValueError:
        raise ValueError('Output must be inside the checkout') from None
    if subprocess.run(['git', '-C', str(root), 'check-ignore', '--quiet', str(output)],
                      capture_output=True).returncode:
        raise ValueError('Output must be ignored')
    return output


def prepare_context(root: Path, revision: str, output: Path) -> dict:
    root = root.resolve()
    if not re.fullmatch(r'[a-f0-9]{40}', revision):
        raise ValueError('Select an exact committed source revision')
    if _git(root, 'rev-parse', revision + '^{commit}').decode().strip() != revision:
        raise ValueError('Source revision differs')
    output = _new_output(root, output)
    selected = ['Dockerfile', '.dockerignore', 'packages', 'configs', 'validation', 'tools',
                'scripts', 'schemas', 'third-party-notices', 'deploy']
    archive = _git(root, 'archive', '--format=tar', revision, '--', *selected)
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:
        for member in source.getmembers():
            path = Path(member.name)
            if path.is_absolute() or '..' in path.parts or not (member.isfile() or member.isdir()):
                raise ValueError('Source archive contains an unsafe entry')
        output.mkdir(parents=True, mode=0o700)
        source.extractall(output, filter='data')
    app = output / 'trial-app'
    spec = importlib.util.spec_from_file_location('trial_prepare_app', root / 'deploy/prepare_app_source.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.prepare_app_source(root, revision, 'local-dev', '', app)
    for original, destination in [('App.Dockerfile', 'Dockerfile'), ('Caddyfile', 'Caddyfile')]:
        shutil.copyfile(output / 'deploy/dev-trial' / original, app / destination)
    return {'source_revision': revision, 'backend_context': str(output), 'app_context': str(app)}


def write_bundle(source: Path, output: Path, revision: str, images: dict,
                 platforms: list[str], *, candidate: bool = False) -> dict:
    if output.exists() or output.is_symlink():
        raise ValueError('Bundle output already exists')
    if not re.fullmatch(r'[a-f0-9]{40}', revision) or set(images) != {'backend', 'app', 'postgres', 'objects'}:
        raise ValueError('Bundle requires an exact source and four images')
    if candidate:
        if platforms not in [['linux/amd64'], ['linux/arm64']]:
            raise ValueError('Candidate must select one validation platform')
    elif platforms != ['linux/amd64', 'linux/arm64'] or not all(
            re.fullmatch(r'[a-z0-9][a-z0-9._:/-]*@sha256:[a-f0-9]{64}', value) for value in images.values()):
        raise ValueError('Published bundle requires both platforms and exact image digests')
    output.mkdir(parents=True, mode=0o700)
    for name in ['compose.yaml', 'start.sh']:
        shutil.copyfile(source / 'deploy/dev-trial' / name, output / name)
    (output / 'start.sh').chmod(0o755)
    registry = json.loads((source / 'configs/llm-providers.json').read_text())
    settings = (source / 'deploy/dev-trial/env.example').read_text().replace(
        '@OPENAI_DEFAULT_MODEL@', registry['providers']['openai']['default_model'])
    for name in ['.env', '.env.example']:
        (output / name).write_text(settings)
    document = {'schema': 'capstone-dev-trial/1', 'channel': 'dev-trial-candidate' if candidate else 'dev-trial',
                'source_revision': revision, 'platforms': platforms, 'images': images}
    (output / 'manifest.json').write_text(json.dumps(document, indent=2, sort_keys=True) + '\n')
    names = {'backend': 'BACKEND', 'app': 'APP', 'postgres': 'POSTGRES', 'objects': 'OBJECTS'}
    (output / 'release.env').write_text(''.join('CAPSTONE_' + names[key] + '_IMAGE=' + value + '\n'
                                              for key, value in images.items()))
    (output / 'README.txt').write_text(
        'Capstone temporary dev trial\nSource: ' + revision + '\n'
        'Requires Docker Engine or Docker Desktop with Docker Compose v2.\n'
        'Linux and macOS: set DEEPSEEK_API_KEY in the startup environment, then run ./start.sh.\n'
        'Edit .env to change Provider/model or the App port. OpenAI example is in comments.\n'
        'Startup environment values override .env. Do not put keys in shell command arguments.\n'
        'Run ./start.sh status, ./start.sh logs or ./start.sh stop. Stop preserves all data.\n'
        'Keep the original directory and .capstone-trial private configuration.\n'
        'Use a separate CAPSTONE_INSTANCE starting with capstone-user- for another instance.\n'
        'Windows WSL2 is a target; it has not been verified. This is not a stable release.\n')
    return document


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--source-revision', required=True)
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    try:
        print(json.dumps(prepare_context(arguments.root, arguments.source_revision, arguments.output)))
    except (OSError, ValueError, subprocess.SubprocessError):
        parser.exit(1, 'Trial preparation failed: select an exact source and new ignored output.\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
