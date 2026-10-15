"""Operator-only exact-source contexts and source-free trial bundles."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import os
import posixpath
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

_contract_spec = importlib.util.spec_from_file_location('user_data_compatibility',
                                                     Path(__file__).with_name('user_data_compatibility.py'))
data_contract = importlib.util.module_from_spec(_contract_spec)
_contract_spec.loader.exec_module(data_contract)

BUNDLE_INPUTS = {'deploy/dev-trial/compose.yaml', 'deploy/dev-trial/start.sh',
                'deploy/dev-trial/capstone.sh', 'deploy/dev-trial/install.sh',
                'deploy/dev-trial/env.example', 'configs/llm-providers.json'}


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


def stage_models(root: Path, context: Path, library: Path) -> dict:
    executable = root / 'packages/pypsa-agent/.venv/bin/python'
    if not executable.is_file() or not library.is_dir():
        raise ValueError('Prepare the managed PyPSA runtime and verified model library first')
    program = '''
import hashlib, json, shutil, sys
from pathlib import Path
context, library = map(Path, sys.argv[1:])
sys.path.insert(0, str(context / 'packages/pypsa-model-authority/src'))
from pypsa_model_authority.model_library import list_official_examples, verified_asset_path
assets = list_official_examples()
if len(assets) != 6: raise ValueError('six pinned model assets required')
stage = context / 'deploy/local-model-assets'
stage.mkdir(parents=True, exist_ok=True)
receipt = {}
for item in assets:
    source = verified_asset_path(item.catalog_id, root=library)
    shutil.copy2(source, stage / source.name)
    receipt[source.name] = hashlib.sha256(source.read_bytes()).hexdigest()
print(json.dumps(receipt, sort_keys=True))
'''
    environment = {key: value for key, value in os.environ.items()
                   if key in {'PATH', 'HOME', 'LANG', 'SSL_CERT_FILE', 'REQUESTS_CA_BUNDLE'}}
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    result = subprocess.run([str(executable), '-c', program, str(context), str(library)],
                            env=environment, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise ValueError('Pinned model asset verification failed')
    return json.loads(result.stdout)


def prepare_context(root: Path, revision: str, output: Path, model_library: Path | None = None) -> dict:
    root = root.resolve()
    if not re.fullmatch(r'[a-f0-9]{40}', revision):
        raise ValueError('Select an exact committed source revision')
    if _git(root, 'rev-parse', revision + '^{commit}').decode().strip() != revision:
        raise ValueError('Source revision differs')
    output = _new_output(root, output)
    selected = ['Dockerfile', '.dockerignore', 'packages', 'configs', 'validation', 'tools',
                'scripts', 'schemas', 'third-party-notices', 'deploy', 'pyproject.toml', 'uv.lock']
    selected.extend(name for name in _git(root, 'ls-tree', '--name-only', revision).decode().splitlines()
                    if '/' not in name and data_contract.selected(name) and name not in selected)
    archive = _git(root, 'archive', '--format=tar', revision, '--', *selected)
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:
        for member in source.getmembers():
            path = Path(member.name)
            if member.issym():
                target = posixpath.normpath(posixpath.join(str(path.parent), member.linkname))
                if member.linkname.startswith('/') or target.startswith('../') or target == '..':
                    raise ValueError('Source archive contains an unsafe symlink')
            if path.is_absolute() or '..' in path.parts or not (member.isfile() or member.isdir() or member.issym()):
                raise ValueError('Source archive contains an unsafe entry')
        output.mkdir(parents=True, mode=0o700)
        source.extractall(output, filter='data')
    app = output / 'trial-app'
    spec = importlib.util.spec_from_file_location('trial_prepare_app', output / 'deploy/prepare_app_source.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.prepare_app_source(root, revision, 'local-dev', '', app)
    for original, destination in [('App.Dockerfile', 'Dockerfile'), ('Caddyfile', 'Caddyfile')]:
        shutil.copyfile(output / 'deploy/dev-trial' / original, app / destination)
    assets = stage_models(root, output, model_library or root / '.grid-agent/runtime/pypsa-models')
    inputs = BUNDLE_INPUTS | {'deploy/prepare_app_source.py'}
    if (output / 'deploy/dev-trial/install-version.sh').exists():
        inputs = inputs | {'deploy/dev-trial/install-version.sh'}
    (output / 'trial-context.json').write_text(json.dumps({'source_revision': revision,
        'data_inputs': {name: hashlib.sha256(content).hexdigest()
                        for name, content in data_contract.context_files(output).items()},
        'model_assets': assets, 'inputs': {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                                         for name in inputs}}, indent=2, sort_keys=True) + '\n')
    return {'source_revision': revision, 'backend_context': str(output), 'app_context': str(app)}


def verify_acceptance(revision: str, images: dict, platforms: list[str], acceptance: dict | None,
                      format_sha256: str) -> None:
    if (not isinstance(acceptance, dict) or acceptance.get('schema') != 'capstone-dev-trial-acceptance/1'
            or acceptance.get('source_revision') != revision or acceptance.get('images') != images
            or set(acceptance.get('platforms', {})) != set(platforms)):
        raise ValueError('Final bundle requires matching two-platform acceptance receipts')
    for receipt in acceptance['platforms'].values():
        if not isinstance(receipt, dict) or any(receipt.get(key) != 'passed'
                for key in ['readiness', 'cases', 'replay', 'restart', 'browser', 'anonymous_pull']):
            raise ValueError('Final platform acceptance is incomplete')
    metadata = acceptance.get('image_metadata', {})
    if set(metadata) != set(images):
        raise ValueError('Final acceptance requires all image metadata')
    for key, reference in images.items():
        item = metadata[key]
        if (not isinstance(item, dict) or item.get('reference') != reference or item.get('platforms') != platforms
                or (key in {'backend', 'app'} and item.get('source_revision') != revision)):
            raise ValueError('Final image acceptance differs from the source or platform manifests')
    data = acceptance.get('data_compatibility')
    if (not isinstance(data, dict) or data.get('source_revision') != revision
            or data.get('format_sha256') != format_sha256
            or not isinstance(data.get('previous_source_revisions'), list)
            or not data['previous_source_revisions']
            or any(not isinstance(item, str) or item == revision or not re.fullmatch(r'[a-f0-9]{40}', item)
                   for item in data['previous_source_revisions'])
            or any(data.get(key) != 'passed' for key in ['upgrade', 'read', 'replay', 'rollback'])):
        raise ValueError('Final data compatibility acceptance is incomplete or differs from the descriptor')


def write_bundle(source: Path, output: Path, revision: str, images: dict,
                 platforms: list[str], *, candidate: bool = False, acceptance: dict | None = None) -> dict:
    if output.exists() or output.is_symlink():
        raise ValueError('Bundle output already exists')
    if not re.fullmatch(r'[a-f0-9]{40}', revision) or set(images) != {'backend', 'app', 'postgres', 'objects'}:
        raise ValueError('Bundle requires an exact source and four images')
    receipt = json.loads((source / 'trial-context.json').read_text())
    if receipt.get('source_revision') != revision:
        raise ValueError('Bundle source differs from its prepared context')
    inputs = receipt.get('inputs', {})
    required = BUNDLE_INPUTS.copy()
    if ('deploy/dev-trial/install-version.sh' in inputs
            or (source / 'deploy/dev-trial/install-version.sh').exists()):
        required.add('deploy/dev-trial/install-version.sh')
    if not required <= inputs.keys() or any(
            not (source / name).is_file() or (source / name).is_symlink()
            or hashlib.sha256((source / name).read_bytes()).hexdigest() != inputs[name] for name in required):
        raise ValueError('Bundle inputs differ from the exact source context')
    if candidate:
        if platforms not in [['linux/amd64'], ['linux/arm64']]:
            raise ValueError('Candidate must select one validation platform')
    elif platforms != ['linux/amd64', 'linux/arm64'] or not all(
            re.fullmatch(r'[a-z0-9][a-z0-9._:/-]*@sha256:[a-f0-9]{64}', value) for value in images.values()):
        raise ValueError('Published bundle requires both platforms and exact image digests')
    descriptor = data_contract.generate_descriptor(source, revision, images)
    data_inputs = {name: hashlib.sha256(content).hexdigest()
                   for name, content in data_contract.context_files(source).items()}
    if receipt.get('data_inputs') != data_inputs:
        raise ValueError('Frozen persistence inputs differ from the source context receipt')
    if not candidate:
        verify_acceptance(revision, images, platforms, acceptance,
                          descriptor['CAPSTONE_DATA_FORMAT_SHA256'])
    output.mkdir(parents=True, mode=0o700)
    for name in ['compose.yaml', 'start.sh', 'capstone.sh', 'install.sh']:
        shutil.copyfile(source / 'deploy/dev-trial' / name, output / name)
    for name in ['start.sh', 'capstone.sh', 'install.sh']:
        (output / name).chmod(0o755)
    (output / 'data-contract.env').write_text(data_contract.render_descriptor(descriptor))
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
                                              for key, value in images.items())
                                      + 'CAPSTONE_TRIAL_PLATFORM=' + (platforms[0] if candidate else '') + '\n')
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
    with (output / 'README.txt').open('a') as notes:
        notes.write('Manage versions with ./capstone.sh. The frozen ./start.sh runs this version.\n'
                    'The data contract blocks unverified backend and dependency changes.\n'
                    'It does not replace migration tests or tests with old data.\n'
                    + ('Candidate: full data compatibility has not been accepted.\n' if candidate else ''))
    return document


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--source-revision', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--model-library', type=Path)
    parser.add_argument('--image-manifest', type=Path)
    parser.add_argument('--bundle-output', type=Path)
    parser.add_argument('--candidate-platform', choices=('linux/amd64', 'linux/arm64'))
    parser.add_argument('--acceptance', type=Path)
    arguments = parser.parse_args()
    try:
        context = prepare_context(arguments.root, arguments.source_revision, arguments.output,
                                  arguments.model_library)
        if arguments.image_manifest or arguments.bundle_output:
            if not arguments.image_manifest or not arguments.bundle_output:
                raise ValueError('Image manifest and bundle output must be supplied together')
            identity = json.loads(arguments.image_manifest.read_text())
            if identity.get('source_revision') != arguments.source_revision:
                raise ValueError('Image manifest source differs')
            output = _new_output(arguments.root, arguments.bundle_output)
            acceptance = json.loads(arguments.acceptance.read_text()) if arguments.acceptance else None
            write_bundle(Path(context['backend_context']), output, arguments.source_revision, identity['images'],
                         [arguments.candidate_platform] if arguments.candidate_platform else ['linux/amd64', 'linux/arm64'],
                         candidate=bool(arguments.candidate_platform), acceptance=acceptance)
            context['bundle_output'] = str(output)
        print(json.dumps(context))
    except (OSError, ValueError, subprocess.SubprocessError):
        parser.exit(1, 'Trial preparation failed: select an exact source and new ignored output.\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
