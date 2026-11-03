import json

import pytest

from capstone_agent.managed_resource_dependencies import (
    IsolatedDependencyInstaller, dependency_environment,
)
from capstone_agent.managed_resource_installation import InstallationError


COMPATIBILITY = {'python': '3.12.8', 'node': '22.1.0', 'platform': 'linux', 'machine': 'x86_64'}


def adapter(calls, *, network=lambda: None, runner=None):
    def record(argv, cwd, refs, **options):
        calls.append((argv, cwd, refs, options))
        return ''
    return IsolatedDependencyInstaller(runner or record, check_network=network,
                                       compatibility=COMPATIBILITY)


def test_exact_python_pins_and_requirements_use_vendored_binary_only_install(tmp_path):
    (tmp_path / 'requirements.txt').write_text('# Locked dependencies\nalpha==1.2.3\n')
    calls = []
    receipt = adapter(calls)(tmp_path, ('beta==2.0',))
    argv, cwd, refs, options = calls[0]
    assert argv == ('python3', '-m', 'pip', 'install', '--disable-pip-version-check',
                    '--no-input', '--no-compile', '--only-binary=:all:', '--no-deps',
                    '--target', '.managed-python', '--requirement', '.managed-python-requirements.txt')
    assert cwd == tmp_path and refs == () and options == {'sync_output': True}
    assert receipt['compatibility'] == COMPATIBILITY
    assert receipt['python']['pins'] == ['alpha==1.2.3', 'beta==2.0']
    assert (tmp_path / '.managed-python-requirements.txt').read_text() == 'alpha==1.2.3\nbeta==2.0\n'
    assert json.loads((tmp_path / '.managed-dependencies.json').read_text()) == receipt
    assert dependency_environment(tmp_path) == {'PYTHONPATH': str(tmp_path / '.managed-python')}


@pytest.mark.parametrize('lock', ['package-lock.json', 'npm-shrinkwrap.json'])
def test_npm_ci_uses_lock_and_disables_scripts(tmp_path, lock):
    (tmp_path / 'package.json').write_text('{"dependencies":{"alpha":"^1.0"}}')
    (tmp_path / lock).write_text('{"lockfileVersion":3,"packages":{}}')
    calls = []
    receipt = adapter(calls)(tmp_path)
    assert calls[0] == (('npm', 'ci', '--ignore-scripts', '--no-audit', '--no-fund'),
                         tmp_path, (), {'sync_output': True})
    assert receipt['npm']['lockfile'] == lock
    assert dependency_environment(tmp_path) == {}


@pytest.mark.parametrize('name,text', [
    ('requirements.txt', 'alpha>=1.0'), ('requirements.txt', '-r elsewhere.txt'),
    ('requirements.txt', 'alpha @ https://example.org/a.whl'),
    ('requirements.txt', 'alpha==1.0 --index-url https://example.org'),
    ('pyproject.toml', '[project]\ndependencies=["alpha==1"]'),
    ('uv.lock', 'version=1'), ('poetry.lock', ''), ('Pipfile', ''),
    ('environment.yml', ''), ('package.json', '{"dependencies":{"alpha":"1"}}'),
])
def test_unsupported_or_unpinned_inputs_fail_before_runner(tmp_path, name, text):
    (tmp_path / name).write_text(text)
    calls = []
    with pytest.raises(InstallationError):
        adapter(calls)(tmp_path)
    assert calls == []
    assert not (tmp_path / '.managed-dependencies.json').exists()


def test_network_refusal_has_no_runner_or_receipt(tmp_path):
    def deny():
        raise InstallationError('resource_network_disabled')
    calls = []
    with pytest.raises(InstallationError, match='network_disabled'):
        adapter(calls, network=deny)(tmp_path, ('alpha==1',))
    assert calls == []
    assert not (tmp_path / '.managed-dependencies.json').exists()


def test_runner_failure_does_not_publish_success_receipt(tmp_path):
    def fail(*args, **kwargs):
        raise RuntimeError('private package manager output')
    with pytest.raises(InstallationError, match='resource_dependency_install_failed'):
        adapter([], runner=fail)(tmp_path, ('alpha==1',))
    assert not (tmp_path / '.managed-dependencies.json').exists()


def test_all_declarations_are_validated_before_any_command(tmp_path):
    (tmp_path / 'package.json').write_text('{"dependencies":{"alpha":"1"}}')
    calls = []
    with pytest.raises(InstallationError):
        adapter(calls)(tmp_path, ('beta==1',))
    assert calls == []


def test_nested_declaration_and_preexisting_vendor_are_rejected(tmp_path):
    nested = tmp_path / 'nested'
    nested.mkdir()
    (nested / 'requirements.txt').write_text('alpha==1')
    with pytest.raises(InstallationError, match='unsupported'):
        adapter([])(tmp_path)
    (nested / 'requirements.txt').unlink()
    (tmp_path / '.managed-python').mkdir()
    with pytest.raises(InstallationError, match='reserved'):
        adapter([])(tmp_path, ('alpha==1',))


def test_runtime_rejects_changed_target_compatibility(tmp_path):
    adapter([])(tmp_path, ('alpha==1',))
    assert dependency_environment(tmp_path, compatibility=COMPATIBILITY)['PYTHONPATH']
    with pytest.raises(InstallationError, match='resource_dependency_runtime_incompatible'):
        dependency_environment(tmp_path, compatibility={**COMPATIBILITY, 'machine': 'aarch64'})


def test_three_field_runtime_compatibility_is_supported(tmp_path):
    compatibility = {key: value for key, value in COMPATIBILITY.items() if key != 'node'}
    installer = IsolatedDependencyInstaller(lambda *a, **k: '', check_network=lambda: None,
                                             compatibility=compatibility)
    assert installer(tmp_path, ('alpha==1',))['compatibility'] == compatibility
    assert dependency_environment(tmp_path, compatibility=compatibility)['PYTHONPATH']


def test_failed_npm_after_python_does_not_write_completed_receipt(tmp_path):
    (tmp_path / 'package.json').write_text('{"dependencies":{"alpha":"1"}}')
    (tmp_path / 'package-lock.json').write_text('{"lockfileVersion":3,"packages":{}}')
    calls = []
    def runner(argv, *args, **kwargs):
        calls.append(argv[0])
        if argv[0] == 'npm':
            raise RuntimeError('private registry diagnostics')
    with pytest.raises(InstallationError, match='resource_dependency_install_failed'):
        adapter([], runner=runner)(tmp_path, ('beta==1',))
    assert calls == ['python3', 'npm']
    assert not (tmp_path / '.managed-dependencies.json').exists()


@pytest.mark.parametrize('resolved', ['file:../private', 'git+ssh://example.org/repo',
                                    'https://user:password@example.org/a.tgz',
                                    'https://example.org/a.tgz?token=private'])
def test_lock_sources_cannot_supply_credentials_or_local_packages(tmp_path, resolved):
    (tmp_path / 'package.json').write_text('{"dependencies":{"alpha":"1"}}')
    (tmp_path / 'package-lock.json').write_text(json.dumps({'lockfileVersion': 3,
        'packages': {'node_modules/alpha': {'resolved': resolved}}}))
    calls = []
    with pytest.raises(InstallationError, match='lock_invalid'):
        adapter(calls)(tmp_path)
    assert not calls
