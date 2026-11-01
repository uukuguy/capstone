import json
from pathlib import Path

import pytest

from capstone_agent.managed_resource_installation import InstallRequest, ManagedResourceInstaller, PinnedGitFetcher
from capstone_agent.managed_resource_manifest import RuntimeSpec, SourceIdentity
from capstone_agent.managed_resources import ManagedResourceStore
from capstone_agent.resource_permissions import RESOURCE_ACTIONS, ResourcePermissionDenied, ResourcePermissions, ResourcePrincipal


P = ResourcePrincipal('operator', ())


@pytest.fixture
def context(tmp_path):
    policy = tmp_path / 'policy.json'
    policy.write_text(json.dumps({'version': 1, 'profiles': {'test': {'rules': [{'effect': 'allow', 'actions': sorted(RESOURCE_ACTIONS)}]}}}))
    store = ManagedResourceStore(tmp_path / 'persistent', ResourcePermissions(policy, 'test'))
    source = tmp_path / 'trusted'
    source.mkdir()
    (source / 'SKILL.md').write_text('---\nname: example\ndescription: Example skill.\n---\nUse the bundled script.')
    (source / 'script.py').write_text('print(42)')
    yield store, source, policy
    # Restore only test-owned immutable trees for pytest's temporary cleanup.
    for path in (store.root / 'packages').rglob('*'):
        if not path.is_symlink():
            path.chmod(0o755 if path.is_dir() else 0o644)


def request():
    return InstallRequest('skill', SourceIdentity('fixtures/example', 'v1'), RuntimeSpec('SKILL.md'))


def installer(context, **kwargs):
    store, source, _ = context
    return ManagedResourceInstaller(store, staged_sources={'fixtures/example': source}, verify_skill=lambda path, runtime: {'skills': [{'path': 'SKILL.md', 'name': 'example'}]}, **kwargs)


def test_verified_immutable_install_and_receipt_retry(context):
    service = installer(context)
    receipt = service.install(P, 'w', 'one', 'example', request())
    assert receipt['status'] == 'succeeded'
    item = receipt['result']
    store, source, _ = context
    package = store.root / item['package_ref']
    assert package.is_relative_to(store.root / 'packages')
    assert (package / 'script.py').read_text() == 'print(42)'
    (source / 'script.py').write_text('changed')
    assert (package / 'script.py').read_text() == 'print(42)'
    assert installer(context).install(P, 'w', 'one', 'example', request()) == receipt
    publication = service.publication(item['digest'])
    assert publication['skills'][0]['path'] == 'SKILL.md'


def test_permission_before_side_effects(context):
    store, _, policy = context
    service = installer(context)
    policy.write_text(policy.read_text().replace('"allow"', '"deny"'))
    with pytest.raises(ResourcePermissionDenied):
        service.install(P, 'w', 'one', 'example', request())
    assert not (store.root / 'staging').exists()


def test_revocation_after_real_verification_is_terminal(context):
    store, source, policy = context
    def revoke(path, runtime):
        policy.write_text(policy.read_text().replace('"allow"', '"deny"'))
        return {'skills': [{'path': 'SKILL.md', 'name': 'example'}]}
    service = ManagedResourceInstaller(store, staged_sources={'fixtures/example': source}, verify_skill=revoke)
    receipt = service.install(P, 'w', 'one', 'example', request())
    assert receipt['status'] == 'failed'
    assert receipt['diagnostic'] == 'resource_permission_revoked'
    assert receipt['result'] is None


@pytest.mark.parametrize('unsafe', ['.env', '.env.production', '.grid-agent/auth.json', '.ssh/key'])
def test_credential_files_fail_without_publication(context, unsafe):
    store, source, _ = context
    path = source / unsafe
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('private')
    receipt = installer(context).install(P, 'w', 'one', 'example', request())
    assert receipt['status'] == 'failed'
    assert store.list_resources(P, 'w') == []


def test_symlink_escape_is_rejected(context):
    _, source, policy = context
    (source / 'leak').symlink_to(policy)
    assert installer(context).install(P, 'w', 'one', 'example', request())['status'] == 'failed'


def test_internal_dependency_links_survive_immutable_copy(context):
    _, source, _ = context
    (source / 'bin').mkdir()
    (source / 'bin' / 'script').symlink_to('../script.py')
    result = installer(context).install(P, 'w', 'one', 'example', request())
    assert result['status'] == 'succeeded'
    link = context[0].root / result['result']['package_ref'] / 'bin' / 'script'
    assert link.is_symlink()
    assert link.read_text() == 'print(42)'


def test_cyclic_links_are_rejected(context):
    _, source, _ = context
    (source / 'cycle').symlink_to('cycle')
    assert installer(context).install(P, 'w', 'one', 'example', request())['status'] == 'failed'


def test_missing_or_failed_real_verifier_never_publishes(context):
    store, source, _ = context
    service = ManagedResourceInstaller(store, staged_sources={'fixtures/example': source})
    assert service.install(P, 'w', 'one', 'example', request())['diagnostic'] == 'resource_skill_verifier_required'
    assert store.list_resources(P, 'w') == []


def test_uncertain_work_is_not_repeated_after_restart(context):
    store, source, _ = context
    calls = []
    def crash(path, runtime):
        calls.append(path)
        raise KeyboardInterrupt()
    service = ManagedResourceInstaller(store, staged_sources={'fixtures/example': source}, verify_skill=crash)
    with pytest.raises(KeyboardInterrupt):
        service.install(P, 'w', 'one', 'example', request())
    assert installer(context).install(P, 'w', 'one', 'example', request())['status'] == 'pending'
    assert len(calls) == 1


def test_git_pin_must_match_and_network_is_checked(context):
    store, _, _ = context
    calls = []
    def fetch(source, destination, secret_refs):
        calls.append(source)
        return 'b' * 40
    service = ManagedResourceInstaller(store, fetch_git=fetch, check_network=lambda source: None)
    remote = InstallRequest('skill', SourceIdentity('https://example.org/repo.git', 'a' * 40))
    assert service.install(P, 'w', 'one', 'example', remote)['diagnostic'] == 'resource_revision_mismatch'
    assert len(calls) == 1
    service = ManagedResourceInstaller(store, fetch_git=fetch)
    assert service.install(P, 'w', 'two', 'other', remote)['diagnostic'] == 'resource_network_disabled'
    assert len(calls) == 1


def test_remote_requires_actual_catalog_and_persists_it(context):
    store, _, _ = context
    catalog = {'schema': 'mcp-catalog/1', 'instructions': 'Use tools.', 'server_info': {'name': 'fixture'}, 'tools': [{'name': 'echo', 'inputSchema': {'type': 'object'}}], 'revision': 'sha256:' + 'a' * 64}
    service = ManagedResourceInstaller(store, check_network=lambda source: None, probe_remote=lambda source, runtime: catalog)
    remote = InstallRequest('mcp_remote', SourceIdentity('http://localhost:8123/mcp', 'v1'))
    receipt = service.install(P, 'w', 'one', 'example', remote)
    assert receipt['status'] == 'succeeded'
    assert receipt['result']['package_ref'] == ''
    assert service.publication(receipt['result']['digest'])['catalog'] == catalog


def test_dependencies_are_not_silently_ignored(context):
    _, source, _ = context
    (source / 'requirements.txt').write_text('requests>=2')
    assert installer(context).install(P, 'w', 'one', 'example', request())['diagnostic'] == 'resource_dependencies_unsupported'


def test_pinned_dependency_install_runs_before_probe(context):
    _, source, _ = context
    (source / 'requirements.txt').write_text('fixture==1.2.3')
    calls = []
    def dependencies(package, pins):
        calls.append('dependencies')
        (package / 'installed.txt').write_text('installed by isolated runner')
    def probe(package, runtime):
        assert (package / 'installed.txt').exists()
        calls.append('probe')
        return {'skills': [{'path': 'SKILL.md', 'name': 'example'}]}
    service = ManagedResourceInstaller(context[0], staged_sources={'fixtures/example': source}, install_dependencies=dependencies, verify_skill=probe, check_network=lambda source: None)
    assert service.install(P, 'w', 'one', 'example', request())['status'] == 'succeeded'
    assert calls == ['dependencies', 'probe']


def test_unpinned_dependencies_and_failed_installer_do_not_publish(context):
    _, source, _ = context
    (source / 'requirements.txt').write_text('fixture>=1')
    def fail(package, pins):
        raise RuntimeError('secret credential must not enter receipt')
    service = installer(context, install_dependencies=fail, check_network=lambda source: None)
    assert service.install(P, 'w', 'one', 'example', request())['diagnostic'] == 'resource_dependencies_unpinned'
    (source / 'requirements.txt').write_text('fixture==1.2.3')
    result = service.install(P, 'w', 'two', 'example', request())
    assert result['diagnostic'] == 'resource_installation_failed'
    assert 'secret' not in json.dumps(result)


def test_failed_local_mcp_upgrade_preserves_active_version(context):
    service = installer(context)
    original = service.install(P, 'w', 'one', 'example', request())['result']
    store, source, _ = context
    def fail(package, runtime):
        raise RuntimeError('probe failed')
    local = InstallRequest('mcp_local', request().source, RuntimeSpec('script.py'))
    service = ManagedResourceInstaller(store, staged_sources={'fixtures/example': source}, probe_local=fail)
    assert service.install(P, 'w', 'two', 'example', local, original['version'])['status'] == 'failed'
    assert store.require_use(P, 'w', 'example') == original


def test_catalog_pin_and_subdirectory_escape(context):
    with pytest.raises(ValueError):
        InstallRequest('skill', request().source, subdirectory='../elsewhere')
    store, _, _ = context
    catalog = {'instructions': '', 'server_info': {}, 'tools': [], 'revision': 'sha256:' + 'b' * 64}
    remote = InstallRequest('mcp_remote', SourceIdentity('https://example.org/mcp', 'sha256:' + 'a' * 64))
    service = ManagedResourceInstaller(store, probe_remote=lambda source, runtime: catalog, check_network=lambda source: None)
    assert service.install(P, 'w', 'one', 'example', remote)['diagnostic'] == 'resource_revision_mismatch'


def test_verifier_cannot_change_verified_package(context):
    store, source, _ = context
    def mutate(package, runtime):
        (package / 'script.py').write_text('modified during probe')
        return {'skills': [{'path': 'SKILL.md', 'name': 'example'}]}
    service = ManagedResourceInstaller(store, staged_sources={'fixtures/example': source}, verify_skill=mutate)
    assert service.install(P, 'w', 'one', 'example', request())['diagnostic'] == 'resource_package_changed_during_verification'


def test_existing_package_tampering_is_detected(context):
    service = installer(context)
    first = service.install(P, 'w', 'one', 'example', request())['result']
    package = context[0].root / first['package_ref']
    (package / 'script.py').chmod(0o644)
    (package / 'script.py').write_text('tampered')
    assert service.install(P, 'w', 'two', 'other', request())['diagnostic'] == 'resource_package_corrupt'


def test_pinned_git_fetcher_uses_argv_and_exact_checkout(tmp_path):
    calls = []
    pin = 'a' * 40
    def runner(argv, cwd, secret_refs):
        calls.append((argv, cwd, secret_refs))
        return pin + '\n' if 'rev-parse' in argv else ''
    source = SourceIdentity('https://example.org/repo.git', pin)
    assert PinnedGitFetcher(runner)(source, tmp_path, ('secret:git',)) == pin
    assert all(isinstance(argv, tuple) for argv, _, _ in calls)
    assert any('fetch' in argv and argv[-1] == pin for argv, _, _ in calls)
    assert all('core.hooksPath=/dev/null' in argv for argv, _, _ in calls)


def test_request_parser_rejects_raw_paths_and_credentials(context):
    assert InstallRequest.from_dict(request().to_dict()) == request()
    with pytest.raises(ValueError):
        InstallRequest.from_dict({**request().to_dict(), 'path': '/host/file'})
    with pytest.raises(ValueError):
        InstallRequest.from_dict({**request().to_dict(), 'source': {'locator': 'https://user:token@example.org/repo', 'revision': 'v1'}})


def test_copy_budget_and_file_count_are_enforced(context):
    assert installer(context, max_bytes=8).install(P, 'w', 'one', 'example', request())['diagnostic'] == 'resource_package_limit'
    assert installer(context, max_files=1).install(P, 'w', 'two', 'example', request())['diagnostic'] == 'resource_package_limit'


def test_concurrent_request_does_not_execute_same_resource(context):
    store, source, _ = context
    other = installer(context)
    nested = []
    def verify(package, runtime):
        nested.append(other.install(P, 'w', 'second', 'example', request()))
        return {'skills': [{'path': 'SKILL.md', 'name': 'example'}]}
    service = ManagedResourceInstaller(store, staged_sources={'fixtures/example': source}, verify_skill=verify)
    assert service.install(P, 'w', 'first', 'example', request())['status'] == 'succeeded'
    assert nested[0]['diagnostic'] == 'resource_installation_in_progress'


def test_dependency_acquisition_obeys_network_setting(context):
    _, source, _ = context
    (source / 'requirements.txt').write_text('fixture==1.2.3')
    calls = []
    service = installer(context, install_dependencies=lambda package, pins: calls.append(package))
    assert service.install(P, 'w', 'one', 'example', request())['diagnostic'] == 'resource_network_disabled'
    assert calls == []


def test_dependency_metadata_is_bounded_separately_from_storage(context):
    from capstone_agent.application_capacity import current_capacity
    _, source, _ = context
    with (source / 'package.json').open('wb') as writer:
        writer.truncate(current_capacity().values['control_document_bytes'] + 1)
    receipt = installer(context).install(P, 'w', 'one', 'example', request())
    assert receipt['diagnostic'] == 'resource_declaration_limit'
