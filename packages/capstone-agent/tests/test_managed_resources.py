import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from capstone_agent.managed_resource_manifest import RuntimeSpec, SourceIdentity, VerifiedResource
from capstone_agent.managed_resources import ManagedResourceStore, ResourceConflict, ResourceStateError
from capstone_agent.resource_permissions import RESOURCE_ACTIONS, ResourcePermissionDenied, ResourcePermissions, ResourcePrincipal


P = ResourcePrincipal('operator', ())


@pytest.fixture
def store(tmp_path):
    path = tmp_path / 'policy.json'
    path.write_text(json.dumps({'version': 1, 'profiles': {'test': {'rules': [{'effect': 'allow', 'actions': sorted(RESOURCE_ACTIONS)}]}}}))
    return ManagedResourceStore(tmp_path / 'persistent', ResourcePermissions(path, 'test'))


def verified(revision='a'):
    return VerifiedResource('skill', SourceIdentity('https://example.org/package', revision), 'sha256:' + revision * 64, revision + '/package', RuntimeSpec('SKILL.md'))


def install(store, request='first', receipt=None, expected=None, workspace='w', resource='sample'):
    receipt = receipt or verified()
    store.begin_install(P, workspace, request, resource, {'revision': receipt.source.revision}, expected)
    return store.publish_verified(P, workspace, request, receipt)


def test_reopening_and_receipt_replay(store):
    item = install(store)
    again = ManagedResourceStore(store.root, store.permissions)
    assert again.require_use(P, 'w', 'sample') == item
    assert install(again) == item
    assert again.operation(P, 'w', 'first')['status'] == 'succeeded'
    with pytest.raises(ResourceConflict, match='request_id_conflict'):
        again.begin_install(P, 'w', 'first', 'sample', {'different': True})
    with pytest.raises(ResourceConflict, match='verification_conflict'):
        again.publish_verified(P, 'w', 'first', verified('b'))


def test_denied_operation_leaves_no_metadata_and_revocation_blocks_publish(store):
    policy = store.permissions.path
    original = policy.read_text()
    policy.write_text(original.replace('"allow"', '"deny"'))
    with pytest.raises(ResourcePermissionDenied):
        store.begin_install(P, 'w', 'denied', 'sample', {})
    policy.write_text(original)
    assert store.list_resources(P, 'w') == []
    with pytest.raises(KeyError):
        store.operation(P, 'w', 'denied')
    store.begin_install(P, 'w', 'pending', 'sample', {})
    policy.write_text(original.replace('"allow"', '"deny"'))
    with pytest.raises(ResourcePermissionDenied):
        store.publish_verified(P, 'w', 'pending', verified())
    assert store.fail_operation(P, 'w', 'pending', 'permission_revoked')['status'] == 'failed'
    policy.write_text(original)
    assert store.operation(P, 'w', 'pending')['status'] == 'failed'
    assert store.list_resources(P, 'w') == []


def test_concurrent_publication_is_atomic_and_preserves_old_version(store):
    first = install(store)
    for request in ('left', 'right'):
        store.begin_install(P, 'w', request, 'sample', {'request': request}, first['version'])
    other = ManagedResourceStore(store.root, store.permissions)
    def publish(args):
        instance, request, receipt = args
        try:
            return instance.publish_verified(P, 'w', request, receipt)
        except ResourceConflict:
            return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(publish, [(store, 'left', verified('b')), (other, 'right', verified('c'))]))
    assert results.count('conflict') == 1
    assert store.get_resource(P, 'w', 'sample', first['version'])['digest'] == first['digest']
    with pytest.raises(ResourceConflict):
        store.begin_install(P, 'w', 'stale', 'sample', {}, first['version'])


def test_disabled_and_uninstalled_resources_retain_history(store):
    first = install(store)
    store.set_enabled(P, 'w', 'sample', False, first['version'])
    with pytest.raises(ResourceStateError):
        store.require_use(P, 'w', 'sample')
    second = install(store, 'second', verified('b'), first['version'])
    assert second['enabled'] is False
    store.uninstall(P, 'w', 'sample', second['version'])
    with pytest.raises(ResourceStateError):
        store.require_use(P, 'w', 'sample', first['version'])
    assert store.get_resource(P, 'w', 'sample', first['version'])['version'] == first['version']
    assert store.operation(P, 'w', 'first')['result'] == first
    assert store.get_resource(P, 'w', 'sample')['installed'] is False


def test_workspace_and_subject_isolation(store):
    install(store)
    with pytest.raises(KeyError):
        store.get_resource(P, 'other', 'sample')
    with pytest.raises(KeyError):
        store.operation(P, 'other', 'first')
    with pytest.raises(KeyError):
        store.operation(ResourcePrincipal('another', ()), 'w', 'first')
    assert install(store, workspace='other')['installed']


def test_failure_retains_active_version(store):
    first = install(store)
    store.begin_install(P, 'w', 'update', 'sample', {}, first['version'])
    assert store.fail_operation(P, 'w', 'update', 'load_failed')['status'] == 'failed'
    with pytest.raises(ResourceConflict):
        store.publish_verified(P, 'w', 'update', verified('b'))
    assert store.require_use(P, 'w', 'sample') == first


def test_corrupt_database_fails_closed(store):
    store.database.write_bytes(b'not sqlite')
    with pytest.raises(ResourceStateError, match='database_invalid'):
        ManagedResourceStore(store.root, store.permissions)


def test_schema_corruption_fails_closed(store):
    import sqlite3
    with sqlite3.connect(store.database) as db:
        db.execute('ALTER TABLE versions RENAME COLUMN metadata TO broken')
    with pytest.raises(ResourceStateError, match='database_invalid'):
        ManagedResourceStore(store.root, store.permissions)


def test_installed_unavailable_resource_cannot_run(store):
    receipt = VerifiedResource('mcp_remote', SourceIdentity('http://localhost/mcp', 'v1'), 'sha256:' + 'd' * 64, '', RuntimeSpec(), False, ('disconnected',))
    assert install(store, receipt=receipt)['available'] is False
    with pytest.raises(ResourceStateError):
        store.require_use(P, 'w', 'sample')


def test_valid_but_modified_version_metadata_fails_closed(store):
    import sqlite3
    install(store)
    with sqlite3.connect(store.database) as db:
        row = db.execute('SELECT metadata FROM versions').fetchone()
        metadata = json.loads(row[0])
        metadata['source']['revision'] = 'changed'
        db.execute('UPDATE versions SET metadata=?', (json.dumps(metadata),))
    with pytest.raises(ResourceStateError, match='version_corrupt'):
        store.require_use(P, 'w', 'sample')
