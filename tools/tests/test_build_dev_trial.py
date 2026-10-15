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


def test_bundle_has_no_source_or_keys_and_uses_provider_registry(tmp_path, monkeypatch):
    module = builder()
    source = 'a' * 40
    images = {key: 'registry.cn-beijing.aliyuncs.com/uukuguy/' + key + '@sha256:' + 'b' * 64
              for key in ['backend', 'app', 'postgres', 'objects']}
    context = tmp_path / 'context'
    context.mkdir()
    for name in ['deploy/dev-trial', 'configs']:
        import shutil
        shutil.copytree(ROOT / name, context / name)
    for name in ['pyproject.toml', 'uv.lock', 'packages/backend/pyproject.toml',
                 'packages/backend/src/store.py', 'schemas/store.json', 'deploy/dev_trial_runtime.py']:
        path = context / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name)
    inputs = ['deploy/dev-trial/capstone.sh', 'deploy/dev-trial/install.sh', 'deploy/dev-trial/compose.yaml', 'deploy/dev-trial/start.sh',
              'deploy/dev-trial/env.example', 'configs/llm-providers.json',
              'deploy/dev-trial/offline-validation-samples.txt']
    if (context / 'deploy/dev-trial/install-version.sh').exists():
        inputs.append('deploy/dev-trial/install-version.sh')
    import hashlib
    (context / 'trial-context.json').write_text(json.dumps({'source_revision': source,
        'data_inputs': {p.relative_to(context).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in context.rglob('*') if p.is_file() and module.data_contract.selected(p.relative_to(context).as_posix())},
        'inputs': {name: hashlib.sha256((context / name).read_bytes()).hexdigest() for name in inputs}}))
    platforms = ['linux/amd64', 'linux/arm64']
    acceptance = {'schema': 'capstone-dev-trial-acceptance/1', 'source_revision': source,
        'images': images, 'platforms': {platform: {key: 'passed' for key in ['readiness', 'cases', 'replay', 'restart', 'browser', 'anonymous_pull']} for platform in platforms},
        'image_metadata': {key: {'reference': value, 'platforms': platforms,
                                'source_revision': source if key in {'backend', 'app'} else None}
                           for key, value in images.items()}}
    with pytest.raises(ValueError, match='acceptance'):
        module.write_bundle(context, tmp_path / 'unverified', source, images, platforms)
    with pytest.raises(ValueError, match='compatibility'):
        module.write_bundle(context, tmp_path / 'no-data-receipt', source, images, platforms, acceptance=acceptance)
    acceptance['data_compatibility'] = {
        'source_revision': source, 'previous_source_revisions': ['783213489abd383bbf79225b29d9d718451dc597'],
        'format_sha256': module.data_contract.generate_descriptor(context, source, images)['CAPSTONE_DATA_FORMAT_SHA256'],
        **{key: 'passed' for key in ['upgrade', 'read', 'replay', 'rollback']}}
    for field, invalid in [('format_sha256', '0' * 64), ('source_revision', '0' * 40),
                           ('previous_source_revisions', []),
                           ('previous_source_revisions', [source]), ('rollback', 'failed')]:
        bad = dict(acceptance, data_compatibility=dict(acceptance['data_compatibility'], **{field: invalid}))
        with pytest.raises(ValueError, match='compatibility'):
            module.write_bundle(context, tmp_path / ('bad-' + field), source, images, platforms, acceptance=bad)
    module.write_bundle(context, tmp_path / 'candidate', source, images, ['linux/amd64'], candidate=True)
    assert 'full data compatibility has not been accepted' in (tmp_path / 'candidate/README.txt').read_text()
    module.write_bundle(context, tmp_path / 'bundle', source, images, platforms, acceptance=acceptance)
    bundle = tmp_path / 'bundle'
    assert {p.name for p in bundle.iterdir()} == {'.env', '.env.example', 'release.env', 'manifest.json', 'compose.yaml', 'start.sh', 'capstone.sh', 'install.sh', 'data-contract.env', 'README.txt', 'README.md'}
    guide = (bundle / 'README.md').read_text()
    assert guide.index('默认使用 pandapower 的 IEEE39 电网') < guide.index('## 安装前提')
    assert guide.index('## 可选电网示例') > guide.index('## 可复制的测试案例')
    assert all(name in guide.split('## 可选电网示例')[1] for name in [
        'AC-DC Meshed', 'Storage-HVDC', 'SciGrid-DE', 'Model-Energy', 'Stochastic-Network', 'Carbon Management'])
    samples_path = context / 'deploy/dev-trial/offline-validation-samples.txt'
    samples = samples_path.read_text()
    assert samples in guide
    assert all(term in guide for term in ['OPENAI_BASE_URL', 'OPENAI_MODEL', 'OPENAI_API_KEY',
                                         'PROVIDER=openai', 'DEEPSEEK_API_KEY', 'capstone.sh', '19173'])
    installer = 'curl -fsSL https://raw.githubusercontent.com/uukuguy/capstone/dev/deploy/dev-trial/install.sh | sh'
    assert installer in guide
    assert guide.index('export OPENAI_API_KEY') < guide.index(installer) < guide.index('sh "$HOME/capstone/capstone.sh" start')
    samples_path.write_text('changed samples')
    with pytest.raises(ValueError, match='input'):
        module.write_bundle(context, tmp_path / 'changed-samples', source, images, ['linux/amd64'], candidate=True)
    samples_path.write_text(samples)
    text = (bundle / '.env').read_text()
    registry = json.loads((ROOT / 'configs/llm-providers.json').read_text())
    assert registry['providers']['openai']['default_model'] in text
    assert 'API_KEY=' not in text and '@OPENAI' not in text
    assert (bundle / 'capstone.sh').stat().st_mode & 0o111
    assert len((bundle / 'data-contract.env').read_text().splitlines()) == 3
    assert json.loads((bundle / 'manifest.json').read_text())['source_revision'] == source
    with pytest.raises(ValueError):
        module.write_bundle(context, bundle, source, images, platforms, acceptance=acceptance)
    with pytest.raises(ValueError, match='source'):
        module.write_bundle(context, tmp_path / 'wrong-source', 'c' * 40, images, platforms, acceptance=acceptance)
    (context / 'packages/backend/src/store.py').write_text('tampered backend')
    with pytest.raises(ValueError, match='persistence'):
        module.write_bundle(context, tmp_path / 'changed-backend', source, images, ['linux/amd64'], candidate=True)
    (context / 'deploy/dev-trial/start.sh').write_text('tampered')
    with pytest.raises(ValueError, match='input'):
        module.write_bundle(context, tmp_path / 'changed-input', source, images, ['linux/amd64', 'linux/arm64'])


def test_context_rejects_a_branch_name_and_existing_output(tmp_path):
    module = builder()
    with pytest.raises(ValueError):
        module.prepare_context(ROOT, 'dev', tmp_path)


def test_exact_context_keeps_the_registered_internal_policy_link(monkeypatch):
    import tempfile
    module = builder()
    calls = []
    monkeypatch.setattr(module, 'stage_models', lambda *args: calls.append(args) or {'test.nc': 'a' * 64})
    original_git = module._git
    def archive_with_manager(root, *args):
        result = original_git(root, *args)
        if args[0] == 'archive':
            import io, tarfile
            out = io.BytesIO()
            with tarfile.open(fileobj=io.BytesIO(result)) as old, tarfile.open(fileobj=out, mode='w') as new:
                for item in old.getmembers():
                    new.addfile(item, old.extractfile(item) if item.isfile() else None)
                for name in ['capstone.sh', 'install.sh']:
                    item = tarfile.TarInfo('deploy/dev-trial/' + name)
                    item.size = 4
                    new.addfile(item, io.BytesIO(b'test'))
            return out.getvalue()
        return result
    monkeypatch.setattr(module, '_git', archive_with_manager)
    revision = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    (ROOT / '.capstone-agent').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / '.capstone-agent') as temporary:
        output = Path(temporary) / 'context'
        module.prepare_context(ROOT, revision, output)
        policy = output / 'configs/agent/system-policy.md'
        assert policy.is_symlink() and policy.is_file()
        assert (output / 'trial-app/build-revision.txt').read_text().strip() == revision
        assert json.loads((output / 'trial-app/build-environment.json').read_text())['api_origin'] == ''
        receipt = json.loads((output / 'trial-context.json').read_text())
        assert receipt['model_assets'] == {'test.nc': 'a' * 64} and len(calls) == 1
