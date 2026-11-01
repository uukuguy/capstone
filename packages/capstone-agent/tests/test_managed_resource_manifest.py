import copy

import pytest

from capstone_agent.managed_resource_manifest import RuntimeSpec, SourceIdentity, VerifiedResource, validate_manifest
from capstone_agent.managed_resources import ManagedResourceStore, ResourceConflict
from test_managed_resources import P, install, store, verified


def test_draft_is_exact_snapshot_and_removal_does_not_uninstall(store):
    first = install(store)
    store.set_preinstall_draft(P, 'w', 'demo', 'sample')
    draft = store.preinstall_manifest(P, 'w', 'demo')
    second = install(store, 'update', verified('b'), first['version'])
    assert store.preinstall_manifest(P, 'w', 'demo') == draft
    assert draft['entries'][0]['version'] == first['version']
    published = store.publish_preinstall(P, 'w', 'demo')
    assert store.preinstall_status(P, 'w', 'demo')['deployed'] is False
    store.set_preinstall_draft(P, 'w', 'demo', 'sample', include=False)
    assert store.require_use(P, 'w', 'sample') == second
    assert store.published_manifest(P, 'w', 'demo', published['version']) == published


def test_import_requires_explicit_override_and_never_installs(store, tmp_path):
    first = install(store)
    store.set_preinstall_draft(P, 'w', 'demo', 'sample')
    manifest = store.publish_preinstall(P, 'w', 'demo')
    target = ManagedResourceStore(tmp_path / 'target', store.permissions)
    target.import_preinstall_draft(P, 'other', manifest)
    assert target.list_resources(P, 'other') == []
    install(store, 'update', verified('b'), first['version'])
    store.set_preinstall_draft(P, 'w', 'demo', 'sample')
    changed = store.preinstall_manifest(P, 'w', 'demo')
    with pytest.raises(ResourceConflict, match='override_required'):
        target.import_preinstall_draft(P, 'other', changed)
    assert target.preinstall_manifest(P, 'other', 'demo') == manifest
    target.import_preinstall_draft(P, 'other', changed, replace=True)
    assert target.preinstall_manifest(P, 'other', 'demo') == changed


@pytest.mark.parametrize('source', ['https://user:password@example.org/mcp', 'https://example.org/mcp?token=abc', 'https://example.org/mcp#secret', 'https://example.org/%2e%2e/private', 'https://example.org/%0aheader', '../escape', '/tmp/task/SKILL.md', 'file:///private/key'])
def test_unsafe_source_rejected(source):
    with pytest.raises(ValueError):
        SourceIdentity(source, 'pinned')


@pytest.mark.parametrize('runtime', [lambda: RuntimeSpec('../escape'), lambda: RuntimeSpec('safe', ('--token=secret',)), lambda: RuntimeSpec('safe', ('--token', 'value')), lambda: RuntimeSpec('safe', secret_refs=('actual-credential',)), lambda: RuntimeSpec('/tmp/task/run')])
def test_unsafe_runtime_rejected(runtime):
    with pytest.raises(ValueError):
        runtime()


def test_manifest_rejects_extra_secret_fields_and_wrong_digest(store):
    install(store)
    store.set_preinstall_draft(P, 'w', 'demo', 'sample')
    manifest = store.preinstall_manifest(P, 'w', 'demo')
    modified = copy.deepcopy(manifest)
    modified['entries'][0]['resource']['runtime']['environment'] = {'TOKEN': 'secret'}
    with pytest.raises(ValueError):
        validate_manifest(modified)
    modified = copy.deepcopy(manifest)
    modified['entries'][0]['version'] = 'sha256:' + '0' * 64
    with pytest.raises(ValueError, match='version_mismatch'):
        validate_manifest(modified)


def test_remote_has_no_package_and_only_secret_reference():
    receipt = VerifiedResource('mcp_remote', SourceIdentity('http://127.0.0.1:18001/mcp', 'contract-v1'), 'sha256:' + 'a' * 64, '', RuntimeSpec(secret_refs=('secret:SERVICE_TOKEN',)))
    assert receipt.to_dict()['runtime']['secret_refs'] == ['secret:SERVICE_TOKEN']
