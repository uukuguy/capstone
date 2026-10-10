"""Prepare exact, secret-free App source and public stage identity; never deploy."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit


def _git(root: Path, *arguments: str) -> bytes:
    result = subprocess.run(['git', '-C', str(root), *arguments], capture_output=True, timeout=30)
    if result.returncode:
        raise ValueError('Selected App source is unavailable')
    return result.stdout


def _origin(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {'', '/'}:
        raise ValueError('App API origin must be a public HTTPS origin without credentials')
    if not re.fullmatch(r'[a-z0-9.-]+(?::[0-9]+)?', parsed.netloc):
        raise ValueError('App API origin must use a canonical HTTPS hostname')
    port = parsed.port
    if port is not None and not 1 <= port <= 65535:
        raise ValueError('App API origin port is invalid')
    return 'https://' + parsed.hostname + (f':{port}' if port not in {None, 443} else '')


def prepare_app_source(root: Path, revision: str, environment: str, api_origin: str, output: Path) -> dict:
    root = Path(root).resolve()
    if not re.fullmatch(r'[a-f0-9]{40}', revision) or environment not in {'cloud-dev', 'cloud-demo'}:
        raise ValueError('An exact source commit and explicit cloud environment are required')
    origin = _origin(api_origin)
    if _git(root, 'rev-parse', '--verify', revision + '^{commit}').decode().strip() != revision:
        raise ValueError('Selected App source does not match the commit')
    output = Path(os.path.abspath(root / output))
    try:
        output.relative_to(root)
    except ValueError:
        raise ValueError('App output must be a new ignored directory in this checkout') from None
    current = output
    while current != root:
        if current.is_symlink():
            raise ValueError('App output must not pass through a symlink')
        current = current.parent
    if output.exists():
        raise ValueError('App output already exists; it is never overwritten')
    ignored = subprocess.run(['git', '-C', str(root), 'check-ignore', '--quiet', '--', str(output)], capture_output=True, timeout=10)
    if ignored.returncode:
        raise ValueError('App output must be ignored')
    entries = []
    for entry in _git(root, 'ls-tree', '-r', '-z', revision, '--', 'packages/capstone-app').split(b'\0'):
        if not entry:
            continue
        metadata, name = entry.split(b'\t', 1)
        mode, kind, blob = metadata.decode().split()
        relative = Path(name.decode()).relative_to('packages/capstone-app')
        if relative != Path('.dockerignore') and (any(part.startswith('.') or part in {'node_modules', 'var', 'runs', 'auth'} for part in relative.parts) or relative.suffix.lower() in {'.key', '.pem', '.sqlite', '.db'} or relative.name in {'auth.json', 'credentials.json', 'operator.json', 'build-revision.txt', 'build-environment.json'}):
            continue
        if kind != 'blob' or mode not in {'100644', '100755'}:
            raise ValueError('Selected App source contains a non-regular file')
        entries.append((relative, blob, mode))
    if not any(path == Path('package.json') for path, _, _ in entries):
        raise ValueError('Selected App source is incomplete')
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        output.mkdir(mode=0o700)
    except FileExistsError:
        raise ValueError('App output already exists; it is never overwritten') from None
    for relative, blob, mode in entries:
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_git(root, 'cat-file', 'blob', blob))
        target.chmod(0o755 if mode == '100755' else 0o644)
    receipt = {'schema': 'capstone-app-environment/1', 'environment': environment,
               'source_revision': revision, 'api_origin': origin}
    (output / 'build-revision.txt').write_text(revision + '\n')
    (output / 'build-environment.json').write_text(json.dumps(receipt, sort_keys=True) + '\n')
    return {**receipt, 'output': str(output), 'source_files': len(entries), 'deployed': False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--source-ref', required=True)
    parser.add_argument('--environment', choices=('cloud-dev', 'cloud-demo'), required=True)
    parser.add_argument('--api-origin', required=True)
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    try:
        print(json.dumps(prepare_app_source(arguments.root, arguments.source_ref, arguments.environment, arguments.api_origin, arguments.output)))
    except (OSError, ValueError):
        parser.exit(1, 'App source preparation rejected: check the commit, public identity and new ignored output path.\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
