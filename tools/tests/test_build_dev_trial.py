from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def builder():
    spec = importlib.util.spec_from_file_location('trial_builder', ROOT / 'deploy/build_dev_trial.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bundle_has_no_source_or_keys_and_uses_provider_registry(tmp_path):
    module = builder()
    source = 'a' * 40
    images = {key: 'registry.cn-beijing.aliyuncs.com/uukuguy/' + key + '@sha256:' + 'b' * 64
              for key in ['backend', 'app', 'postgres', 'objects']}
    module.write_bundle(ROOT, tmp_path / 'bundle', source, images, ['linux/amd64', 'linux/arm64'])
    bundle = tmp_path / 'bundle'
    assert {p.name for p in bundle.iterdir()} == {'.env', '.env.example', 'release.env', 'manifest.json', 'compose.yaml', 'start.sh', 'README.txt'}
    text = (bundle / '.env').read_text()
    registry = json.loads((ROOT / 'configs/llm-providers.json').read_text())
    assert registry['providers']['openai']['default_model'] in text
    assert 'API_KEY=' not in text and '@OPENAI' not in text
    assert json.loads((bundle / 'manifest.json').read_text())['source_revision'] == source
    with pytest.raises(ValueError):
        module.write_bundle(ROOT, bundle, source, images, ['linux/amd64', 'linux/arm64'])


def test_context_rejects_a_branch_name_and_existing_output(tmp_path):
    module = builder()
    with pytest.raises(ValueError):
        module.prepare_context(ROOT, 'dev', tmp_path)


def test_exact_context_keeps_the_registered_internal_policy_link():
    import tempfile
    module = builder()
    revision = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    (ROOT / '.capstone-agent').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / '.capstone-agent') as temporary:
        output = Path(temporary) / 'context'
        module.prepare_context(ROOT, revision, output)
        policy = output / 'configs/agent/system-policy.md'
        assert policy.is_symlink() and policy.is_file()
        assert (output / 'trial-app/build-revision.txt').read_text().strip() == revision
        assert json.loads((output / 'trial-app/build-environment.json').read_text())['api_origin'] == ''
