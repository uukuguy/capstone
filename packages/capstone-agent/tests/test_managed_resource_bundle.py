import io
import json
from pathlib import Path
import tarfile

import pytest

from capstone_agent.managed_resource_bundle import apply_bundle, export_bundle
from capstone_agent.managed_resource_installation import InstallRequest, ManagedResourceInstaller
from capstone_agent.managed_resource_manifest import RuntimeSpec, SourceIdentity
from capstone_agent.managed_resource_service import ManagedResourceService
from capstone_agent.managed_resources import ManagedResourceStore, ResourceConflict
from capstone_agent.resource_permissions import RESOURCE_ACTIONS, ResourcePermissions, ResourcePrincipal

P = ResourcePrincipal('operator', ())


@pytest.fixture
def setup(tmp_path):
    policy = tmp_path / 'policy.json'
    policy.write_text(json.dumps({'version': 1, 'profiles': {'test': {'rules': [
        {'effect': 'allow', 'actions': sorted(RESOURCE_ACTIONS)}]}}}))
    source = tmp_path / 'source'; source.mkdir()
    (source / 'SKILL.md').write_text('---\nname: bundle-skill\ndescription: Offline package.\n---\nRead local data.')
    probes = []
    def verify(package, runtime):
        probes.append((package / 'SKILL.md').read_text())
        return {'skills': [{'path': 'SKILL.md', 'name': 'bundle-skill'}]}
    def service(name):
        store = ManagedResourceStore(tmp_path / name, ResourcePermissions(policy, 'test'))
        installer = ManagedResourceInstaller(store, staged_sources={'fixtures/bundle': source}, verify_skill=verify,
            fetch_git=lambda *_: pytest.fail('bundle must not download'),
            check_network=lambda *_: pytest.fail('local bundle must not use network'))
        return ManagedResourceService(store, installer)
    origin = service('origin'); target = service('target')
    request = InstallRequest('skill', SourceIdentity('fixtures/bundle', 'v1'), RuntimeSpec('SKILL.md'))
    receipt = origin.installer.install(P, 'w', 'original', 'example', request)
    assert receipt['status'] == 'succeeded'
    origin.store.set_preinstall_draft(P, 'w', 'default', 'example')
    manifest = origin.store.publish_preinstall(P, 'w', 'default')
    yield origin, target, manifest, probes, tmp_path
    for root in (origin.store.root, target.store.root):
        for path in root.rglob('*'):
            if not path.is_symlink():
                path.chmod(0o755 if path.is_dir() else 0o644)


def bundle(setup):
    origin, _, _, _, root = setup
    path = root / 'bundle.tar'
    export_bundle(origin, P, 'w', 'default', path)
    return path


def test_bundle_reverifies_offline_bytes_and_records_only_applied_manifest(setup):
    _, target, manifest, probes, _ = setup
    path = bundle(setup)
    before = len(probes)
    result = apply_bundle(target, P, 'w', path, {})
    assert result['status'] == 'applied'
    assert len(probes) == before + 1
    installed = target.store.get_resource(P, 'w', 'example')
    assert installed['version'] == manifest['entries'][0]['version']
    assert target.store.preinstall_status(P, 'w', 'default')['application_receipt'] == result['application_receipt']


def test_conflict_requires_explicit_current_version_before_verification(setup):
    origin, target, _, probes, _ = setup
    path = bundle(setup)
    request = InstallRequest('skill', SourceIdentity('fixtures/bundle', 'v1'), RuntimeSpec('SKILL.md'))
    current = target.installer.install(P, 'w', 'existing', 'example', request)['result']
    before = len(probes)
    with pytest.raises(ResourceConflict):
        apply_bundle(target, P, 'w', path, {})
    assert len(probes) == before
    result = apply_bundle(target, P, 'w', path, {'example': current['version']})
    assert result['status'] == 'applied'


def rewrite(path, mutate):
    with tarfile.open(path) as source:
        members = [(m, source.extractfile(m).read() if m.isfile() else None) for m in source]
    with tarfile.open(path, 'w') as target:
        for member, data in members:
            if member.name == 'bundle.json':
                document = json.loads(data); mutate(document)
                data = json.dumps(document).encode(); member.size = len(data)
            target.addfile(member, io.BytesIO(data) if data is not None else None)


def test_changed_publication_cannot_be_admitted_as_verified_resource(setup):
    _, target, _, _, _ = setup
    path = bundle(setup)
    rewrite(path, lambda d: d['entries']['example']['publication']['skills'][0].update(name='forged'))
    result = apply_bundle(target, P, 'w', path, {})
    assert result['status'] == 'partial' and result['application_receipt'] is None
    with pytest.raises(KeyError):
        target.store.get_resource(P, 'w', 'example')
    assert not target.store.preinstall_status(P, 'w', 'default')['deployed']


@pytest.mark.parametrize('name,kind,link', [('../escaped', tarfile.REGTYPE, ''),
    ('/absolute', tarfile.REGTYPE, ''), ('packages/example/link', tarfile.SYMTYPE, '../../../escaped'),
    ('packages/example/link', tarfile.LNKTYPE, 'bundle.json'),
    ('packages/example/.env', tarfile.REGTYPE, '')])
def test_unsafe_archive_never_invokes_a_verifier(setup, name, kind, link):
    _, target, _, probes, _ = setup
    path = bundle(setup)
    with tarfile.open(path, 'a') as archive:
        member = tarfile.TarInfo(name); member.type = kind; member.linkname = link
        archive.addfile(member)
    before = len(probes)
    with pytest.raises((ValueError, OSError)):
        apply_bundle(target, P, 'w', path, {})
    assert len(probes) == before


def test_bundle_limits_and_existing_operator_output_are_preserved(setup):
    origin, target, _, probes, root = setup
    path = bundle(setup)
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        export_bundle(origin, P, 'w', 'default', path)
    assert path.read_bytes() == before
    target.installer.max_bytes = 1
    with pytest.raises(ValueError, match='limit'):
        apply_bundle(target, P, 'w', path, {})


def test_missing_install_spec_cannot_be_reconstructed_from_metadata(setup):
    origin, _, _, _, root = setup
    with origin.store._transaction() as db:
        db.execute('DELETE FROM installation_specs')
    with pytest.raises(ValueError, match='installation_spec_missing'):
        export_bundle(origin, P, 'w', 'default', root / 'missing.tar')


def test_export_rejects_corrupt_installed_package(setup):
    origin, _, manifest, _, root = setup
    path = origin.store.root / manifest['entries'][0]['resource']['package_ref'] / 'SKILL.md'
    path.chmod(0o644); path.write_text('corrupted')
    with pytest.raises(ValueError, match='package_mismatch'):
        export_bundle(origin, P, 'w', 'default', root / 'corrupt.tar')
    assert not (root / 'corrupt.tar').exists()


def test_failed_target_verification_keeps_the_existing_version(setup):
    _, target, _, _, _ = setup
    path = bundle(setup)
    request = InstallRequest('skill', SourceIdentity('fixtures/bundle', 'v1'), RuntimeSpec('SKILL.md'))
    current = target.installer.install(P, 'w', 'existing', 'example', request)['result']
    target.installer.verify_skill = lambda *_: {'skills': []}
    result = apply_bundle(target, P, 'w', path, {'example': current['version']})
    assert result['status'] == 'partial'
    assert result['application_receipt'] is None
    assert target.store.get_resource(P, 'w', 'example')['version'] == current['version']
    assert not target.store.preinstall_status(P, 'w', 'default')['deployed']


def test_safe_package_symlink_roundtrips_without_following_host_paths(setup):
    origin, target, _, probes, root = setup
    source = origin.installer.staged_sources['fixtures/bundle']
    (source / 'alias.md').symlink_to('SKILL.md')
    (source / ('long-' + 'x' * 120 + '.txt')).write_text('long path remains bounded')
    current = origin.store.get_resource(P, 'w', 'example')
    request = InstallRequest('skill', SourceIdentity('fixtures/bundle', 'v1'), RuntimeSpec('SKILL.md'))
    result = origin.installer.install(P, 'w', 'with-link', 'example', request, current['version'])
    assert result['status'] == 'succeeded'
    origin.store.set_preinstall_draft(P, 'w', 'default', 'example')
    origin.store.publish_preinstall(P, 'w', 'default')
    result = apply_bundle(target, P, 'w', bundle(setup), {})
    assert result['status'] == 'applied'
    installed = target.store.get_resource(P, 'w', 'example')
    alias = target.store.root / installed['package_ref'] / 'alias.md'
    assert alias.is_symlink() and alias.read_text().startswith('---')


def secret_bundle(setup):
    from capstone_agent.managed_resource_secrets import ProtectedResourceBindings
    origin, _, _, _, root = setup
    secret = root / 'protected-secret'; secret.write_text('private-value-never-export'); secret.chmod(0o600)
    binding = root / 'protected-bindings.json'
    binding.write_text(json.dumps({'schema': 'capstone-managed-resource-bindings/1', 'bindings': {
        'secret:target-token': {'workspace': 'w', 'resource_id': 'example', 'source_locator': 'fixtures/bundle',
            'kind': 'skill', 'headers': {}, 'environment': {'SERVICE_TOKEN': str(secret)}}}}))
    binding.chmod(0o600)
    verify = origin.installer.verify_skill
    def verify_bound(package, runtime):
        resolved = ProtectedResourceBindings(binding).resolve(runtime.secret_refs, workspace='w', resource_id='example',
            source_locator='fixtures/bundle', kind='skill')
        assert resolved['environment']['SERVICE_TOKEN'] == 'private-value-never-export'
        return verify(package, runtime)
    origin.installer.verify_skill = verify_bound
    current = origin.store.get_resource(P, 'w', 'example')
    request = InstallRequest('skill', SourceIdentity('fixtures/bundle', 'v1'),
                             RuntimeSpec('SKILL.md', secret_refs=('secret:target-token',)))
    assert origin.installer.install(P, 'w', 'with-secret', 'example', request, current['version'])['status'] == 'succeeded'
    origin.store.set_preinstall_draft(P, 'w', 'default', 'example')
    origin.store.publish_preinstall(P, 'w', 'default')
    return bundle(setup)


def test_secret_references_export_without_binding_files_or_plaintext(setup):
    path = secret_bundle(setup)
    assert b'private-value-never-export' not in path.read_bytes()
    with tarfile.open(path) as archive:
        assert all('protected-' not in member.name for member in archive)
        document = json.loads(archive.extractfile('bundle.json').read())
    assert document['entries']['example']['request']['runtime']['secret_refs'] == ['secret:target-token']
    assert document['manifest']['entries'][0]['resource']['runtime']['secret_refs'] == ['secret:target-token']
    assert 'protected-bindings.json' not in json.dumps(document)


def test_missing_target_binding_does_not_replace_existing_resource_or_record_application(setup):
    from capstone_agent.managed_resource_secrets import ProtectedResourceBindings
    _, target, _, _, _ = setup
    current = target.installer.install(P, 'w', 'existing', 'example',
        InstallRequest('skill', SourceIdentity('fixtures/bundle', 'v1'), RuntimeSpec('SKILL.md')))['result']
    path = secret_bundle(setup)
    verify = target.installer.verify_skill
    def verify_bound(package, runtime):
        ProtectedResourceBindings().resolve(runtime.secret_refs, workspace='w', resource_id='example',
            source_locator='fixtures/bundle', kind='skill')
        return verify(package, runtime)
    target.installer.verify_skill = verify_bound
    result = apply_bundle(target, P, 'w', path, {'example': current['version']})
    assert result['status'] == 'partial' and result['application_receipt'] is None
    assert result['receipts'][0]['status'] == 'failed'
    assert target.store.get_resource(P, 'w', 'example')['version'] == current['version']
    assert not target.store.preinstall_status(P, 'w', 'default')['deployed']


def test_remote_bundle_reconnects_and_requires_exact_contract_without_local_bytes(setup):
    origin, target, _, _, root = setup
    catalog = {'tools': [], 'instructions': '', 'server_info': {}, 'revision': 'sha256:' + 'a' * 64}
    probes = []
    def probe(source, runtime):
        probes.append(source)
        return catalog
    for service in (origin, target):
        service.installer.check_network = lambda *_: None
        service.installer.probe_remote = probe
    request = InstallRequest('mcp_remote', SourceIdentity('https://example.test/mcp', 'discover'))
    assert origin.installer.install(P, 'w', 'remote', 'remote', request)['status'] == 'succeeded'
    origin.store.set_preinstall_draft(P, 'w', 'remote-profile', 'remote')
    origin.store.publish_preinstall(P, 'w', 'remote-profile')
    path = root / 'remote.tar'
    export_bundle(origin, P, 'w', 'remote-profile', path)
    with tarfile.open(path) as archive:
        assert archive.getnames() == ['bundle.json']
    before = len(probes)
    assert apply_bundle(target, P, 'w', path, {})['status'] == 'applied'
    assert len(probes) == before + 1
    assert probes[-1].revision == catalog['revision']
