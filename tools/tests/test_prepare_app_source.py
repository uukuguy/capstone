import importlib.util
import json
from pathlib import Path
import subprocess

import pytest


HELPER = Path(__file__).resolve().parents[2] / 'deploy/prepare_app_source.py'


def prepare(*args):
    assert HELPER.is_file(), 'Stage-aware App source helper is missing'
    spec = importlib.util.spec_from_file_location('prepare_app_source', HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.prepare_app_source(*args)


@pytest.fixture
def source(tmp_path):
    subprocess.run(['git', 'init', '-b', 'main', str(tmp_path)], check=True, capture_output=True)
    (tmp_path / '.gitignore').write_text('.capstone-agent/\n')
    app = tmp_path / 'packages/capstone-app'
    (app / 'src').mkdir(parents=True)
    (app / 'package.json').write_text('{"version":"0.1.0"}')
    (app / 'src/App.tsx').write_text('export const value = "committed"\n')
    (app / '.env.secret').write_text('PRIVATE_KEY=never-export-this\n')
    subprocess.run(['git', '-C', str(tmp_path), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(tmp_path), '-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '-m', 'source'], check=True, capture_output=True)
    sha = subprocess.check_output(['git', '-C', str(tmp_path), 'rev-parse', 'HEAD'], text=True).strip()
    (app / 'src/App.tsx').write_text('export const value = "dirty"\n')
    return tmp_path, sha


@pytest.mark.parametrize('environment', ['cloud-dev', 'cloud-demo'])
def test_helper_exports_exact_source_and_public_receipt_without_secrets(source, environment):
    root, sha = source
    output = root / '.capstone-agent/app-builds' / environment
    result = prepare(root, sha, environment, 'https://api.example.com', output)
    assert result['source_revision'] == sha
    assert (output / 'src/App.tsx').read_text() == 'export const value = "committed"\n'
    assert (output / 'build-revision.txt').read_text().strip() == sha
    assert json.loads((output / 'build-environment.json').read_text()) == {
        'schema': 'capstone-app-environment/1', 'environment': environment,
        'source_revision': sha, 'api_origin': 'https://api.example.com',
    }
    assert not (output / '.env.secret').exists()
    assert not (output / '.git').exists()
    assert (root / 'packages/capstone-app/src/App.tsx').read_text().endswith('"dirty"\n')


def test_helper_does_not_overwrite_an_existing_output(source):
    root, sha = source
    output = root / '.capstone-agent/app-builds/existing'
    output.mkdir(parents=True)
    (output / 'preserve').write_text('user data')
    with pytest.raises(ValueError, match='exists|overwrite'):
        prepare(root, sha, 'cloud-demo', 'https://api.example.com', output)
    assert (output / 'preserve').read_text() == 'user data'


@pytest.mark.parametrize('origin', ['http://api.example.com', 'https://user:secret@api.example.com', 'https://api.example.com/path', 'https://api.example.com?token=secret', 'https://api.example.com#secret'])
def test_helper_rejects_non_origin_or_credential_input(source, origin):
    root, sha = source
    output = root / '.capstone-agent/app-builds/rejected'
    with pytest.raises(ValueError):
        prepare(root, sha, 'cloud-demo', origin, output)
    assert not output.exists()


def test_helper_requires_exact_revision_cloud_stage_and_ignored_output(source):
    root, sha = source
    for revision, stage, output in [
        ('main', 'cloud-demo', root / '.capstone-agent/app-builds/ref'),
        (sha, 'local-demo', root / '.capstone-agent/app-builds/local'),
        (sha, 'cloud-demo', root / 'public-app'),
    ]:
        with pytest.raises(ValueError):
            prepare(root, revision, stage, 'https://api.example.com', output)
        assert not output.exists()


def test_helper_rejects_symlink_output_ancestors(source, tmp_path_factory):
    root, sha = source
    outside = tmp_path_factory.mktemp('outside-app')
    (root / '.capstone-agent').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match='symlink'):
        prepare(root, sha, 'cloud-dev', 'https://api.example.com', root / '.capstone-agent/new-app')
    assert not (outside / 'new-app').exists()


def test_helper_rejects_non_regular_source_before_creating_output(source):
    root, _ = source
    (root / 'packages/capstone-app/src/linked.ts').symlink_to('/private/host-data')
    subprocess.run(['git', '-C', str(root), 'add', 'packages/capstone-app/src/linked.ts'], check=True)
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '-m', 'linked'], check=True, capture_output=True)
    sha = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    output = root / '.capstone-agent/new-app'
    with pytest.raises(ValueError, match='non-regular'):
        prepare(root, sha, 'cloud-dev', 'https://api.example.com', output)
    assert not output.exists()
