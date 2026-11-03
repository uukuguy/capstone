"""Durable resource metadata. Package installation belongs to executor adapters.

SQLite serializes writers across store instances. Versions and operation receipts
are retained after uninstall. This ledger does not schedule task execution.
"""

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3

from .managed_resource_manifest import (
    VerifiedResource, canonical, content_digest, identifier, parse_verified,
    validate_manifest,
)
from .resource_permissions import ResourcePermissions, ResourcePrincipal


class ResourceConflict(ValueError):
    pass


class ResourceStateError(RuntimeError):
    pass


class ManagedResourceStore:
    def __init__(self, root: Path, permissions: ResourcePermissions):
        self.root = Path(root).resolve()
        self.permissions = permissions
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / 'packages').mkdir(exist_ok=True)
        self.database = self.root / 'resources.sqlite3'
        try:
            with self._transaction() as db:
                version = db.execute('PRAGMA user_version').fetchone()[0]
                if version not in (0, 1, 2):
                    raise ResourceStateError('unsupported_resource_schema')
                db.execute('CREATE TABLE IF NOT EXISTS resources (workspace TEXT, id TEXT, current TEXT, enabled INTEGER NOT NULL, installed INTEGER NOT NULL, PRIMARY KEY(workspace,id))')
                db.execute('CREATE TABLE IF NOT EXISTS versions (workspace TEXT, id TEXT, version TEXT, metadata TEXT NOT NULL, PRIMARY KEY(workspace,id,version))')
                db.execute('CREATE TABLE IF NOT EXISTS operations (workspace TEXT, request TEXT, subject TEXT NOT NULL, resource TEXT NOT NULL, expected TEXT, action TEXT NOT NULL, payload TEXT NOT NULL, policy TEXT NOT NULL, status TEXT NOT NULL, result TEXT, diagnostic TEXT, PRIMARY KEY(workspace,request))')
                db.execute('CREATE TABLE IF NOT EXISTS drafts (workspace TEXT, profile TEXT, id TEXT, entry TEXT NOT NULL, PRIMARY KEY(workspace,profile,id))')
                db.execute('CREATE TABLE IF NOT EXISTS manifests (workspace TEXT, profile TEXT, version TEXT, manifest TEXT NOT NULL, PRIMARY KEY(workspace,profile,version))')
                db.execute('CREATE TABLE IF NOT EXISTS installation_specs (workspace TEXT,id TEXT,version TEXT,spec TEXT NOT NULL,PRIMARY KEY(workspace,id,version))')
                db.execute('CREATE TABLE IF NOT EXISTS applications (workspace TEXT, profile TEXT, version TEXT, receipt TEXT NOT NULL, PRIMARY KEY(workspace,profile,version))')
                for table, fields in {
                    'resources': 'workspace,id,current,enabled,installed',
                    'versions': 'workspace,id,version,metadata',
                    'operations': 'workspace,request,subject,resource,expected,action,payload,policy,status,result,diagnostic',
                    'drafts': 'workspace,profile,id,entry',
                    'manifests': 'workspace,profile,version,manifest',
                    'applications': 'workspace,profile,version,receipt',
                    'installation_specs': 'workspace,id,version,spec',
                }.items():
                    db.execute(f'SELECT {fields} FROM {table} LIMIT 0')
                db.execute('PRAGMA user_version = 2')
                if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                    raise ResourceStateError('resource_database_corrupt')
        except sqlite3.Error:
            raise ResourceStateError('resource_database_invalid') from None

    @contextmanager
    def _transaction(self):
        db = sqlite3.connect(self.database, timeout=15, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _authorize(self, principal, workspace, action):
        revision = self.permissions.require(principal, workspace, action)
        identifier(workspace)
        return revision

    @staticmethod
    def _resource(db, workspace, resource_id):
        identifier(resource_id)
        row = db.execute('SELECT * FROM resources WHERE workspace=? AND id=?', (workspace, resource_id)).fetchone()
        if row is None:
            raise KeyError('resource_not_found')
        return row

    @staticmethod
    def _operation(db, workspace, request_id, principal):
        identifier(request_id)
        row = db.execute('SELECT * FROM operations WHERE workspace=? AND request=?', (workspace, request_id)).fetchone()
        if row is None or row['subject'] != principal.subject:
            raise KeyError('resource_operation_not_found')
        return row

    @staticmethod
    def _operation_dict(row):
        return {'request_id': row['request'], 'resource_id': row['resource'], 'action': row['action'], 'status': row['status'], 'expected_version': row['expected'], 'policy_revision': row['policy'], 'result': json.loads(row['result']) if row['result'] else None, 'diagnostic': row['diagnostic']}

    @staticmethod
    def _catalog_item(db, row, version=None):
        selected = version or row['current']
        record = db.execute('SELECT metadata FROM versions WHERE workspace=? AND id=? AND version=?', (row['workspace'], row['id'], selected)).fetchone()
        if record is None:
            raise KeyError('resource_version_not_found')
        metadata = parse_verified(json.loads(record['metadata'])).to_dict()
        if content_digest(metadata) != selected:
            raise ResourceStateError('resource_version_corrupt')
        spec=db.execute('SELECT spec FROM installation_specs WHERE workspace=? AND id=? AND version=?',
                        (row['workspace'],row['id'],selected)).fetchone()
        return {'resource_id': row['id'], 'version': selected, 'installed': bool(row['installed']), 'enabled': bool(row['enabled']),
                **metadata, **({'installation':json.loads(spec[0])} if spec is not None else {})}

    def begin_install(self, principal: ResourcePrincipal, workspace: str, request_id: str,
                      resource_id: str, payload: dict, expected_version: str | None = None) -> dict:
        action = 'resources.update' if expected_version is not None else 'resources.install'
        policy = self._authorize(principal, workspace, action)
        identifier(request_id)
        identifier(resource_id)
        # Persist only a hash of caller input: request bodies may contain secrets.
        if not isinstance(payload, dict):
            raise ValueError('invalid_resource_request')
        digest = content_digest(payload)
        with self._transaction() as db:
            prior = db.execute('SELECT * FROM operations WHERE workspace=? AND request=?', (workspace, request_id)).fetchone()
            if prior:
                if (prior['subject'], prior['resource'], prior['expected'], prior['payload'], prior['action']) != (principal.subject, resource_id, expected_version, digest, action):
                    raise ResourceConflict('resource_request_id_conflict')
                return self._operation_dict(prior)
            row = db.execute('SELECT * FROM resources WHERE workspace=? AND id=?', (workspace, resource_id)).fetchone()
            current = row['current'] if row and row['installed'] else None
            if current != expected_version:
                raise ResourceConflict('resource_version_conflict')
            db.execute('INSERT INTO operations VALUES (?,?,?,?,?,?,?,?,?,?,?)', (workspace, request_id, principal.subject, resource_id, expected_version, action, digest, policy, 'pending', None, None))
            return self._operation_dict(self._operation(db, workspace, request_id, principal))

    def publish_verified(self, principal: ResourcePrincipal, workspace: str,
                         request_id: str, verified: VerifiedResource, *, install_request=None) -> dict:
        """Internal only: the trusted installer must verify bytes and load first."""
        if not isinstance(verified, VerifiedResource):
            raise TypeError('internal_verifier_receipt_required')
        from .managed_resource_installation import InstallRequest
        if install_request is not None and not isinstance(install_request,InstallRequest):
            raise TypeError('parsed_install_request_required')
        metadata = verified.to_dict()
        version = content_digest(metadata)
        with self._transaction() as db:
            operation = self._operation(db, workspace, request_id, principal)
            self._authorize(principal, workspace, operation['action'])
            if operation['status'] == 'succeeded':
                result = json.loads(operation['result'])
                if result['version'] != version:
                    raise ResourceConflict('resource_verification_conflict')
                return result
            if operation['status'] != 'pending':
                raise ResourceConflict('resource_operation_closed')
            resource_id = operation['resource']
            row = db.execute('SELECT * FROM resources WHERE workspace=? AND id=?', (workspace, resource_id)).fetchone()
            current = row['current'] if row and row['installed'] else None
            if current != operation['expected']:
                raise ResourceConflict('resource_version_conflict')
            # Preserve disabled state across upgrades. A reinstall starts enabled.
            enabled = row['enabled'] if row and row['installed'] else 1
            db.execute('INSERT OR IGNORE INTO versions VALUES (?,?,?,?)', (workspace, resource_id, version, canonical(metadata)))
            db.execute('INSERT INTO resources VALUES (?,?,?,?,1) ON CONFLICT(workspace,id) DO UPDATE SET current=excluded.current,enabled=excluded.enabled,installed=1', (workspace, resource_id, version, enabled))
            if install_request is not None:
                db.execute('INSERT OR IGNORE INTO installation_specs VALUES (?,?,?,?)',
                    (workspace,resource_id,version,canonical(install_request.to_dict())))
            result = self._catalog_item(db, self._resource(db, workspace, resource_id))
            db.execute("UPDATE operations SET status='succeeded',result=? WHERE workspace=? AND request=?", (canonical(result), workspace, request_id))
            return result

    def fail_operation(self, principal, workspace, request_id, diagnostic_code):
        """Internal terminal receipt, permitted after management revocation.

        Only the trusted original subject can close its pending operation. This
        path cannot publish a version or change an installed resource binding.
        """
        identifier(diagnostic_code)
        with self._transaction() as db:
            row = self._operation(db, workspace, request_id, principal)
            if row['status'] == 'pending':
                db.execute("UPDATE operations SET status='failed',diagnostic=? WHERE workspace=? AND request=?", (diagnostic_code, workspace, request_id))
            return self._operation_dict(self._operation(db, workspace, request_id, principal))

    def operation(self, principal, workspace, request_id):
        self._authorize(principal, workspace, 'resources.use')
        with self._transaction() as db:
            return self._operation_dict(self._operation(db, workspace, request_id, principal))

    def list_resources(self, principal, workspace):
        self._authorize(principal, workspace, 'resources.use')
        with self._transaction() as db:
            return [self._catalog_item(db, row) for row in db.execute('SELECT * FROM resources WHERE workspace=? ORDER BY id', (workspace,))]

    def get_resource(self, principal, workspace, resource_id, version=None):
        self._authorize(principal, workspace, 'resources.use')
        with self._transaction() as db:
            return self._catalog_item(db, self._resource(db, workspace, resource_id), version)

    def require_use(self, principal, workspace, resource_id, version=None):
        item = self.get_resource(principal, workspace, resource_id, version)
        if not item['installed'] or not item['enabled'] or not item['available']:
            raise ResourceStateError('resource_unavailable')
        return item

    def set_enabled(self, principal, workspace, resource_id, enabled, expected_version):
        if type(enabled) is not bool:
            raise ValueError('invalid_resource_enabled')
        return self._change_state(principal, workspace, resource_id, expected_version, 'resources.enable' if enabled else 'resources.disable', enabled)

    def uninstall(self, principal, workspace, resource_id, expected_version):
        return self._change_state(principal, workspace, resource_id, expected_version, 'resources.uninstall', False)

    def _change_state(self, principal, workspace, resource_id, expected, action, enabled):
        self._authorize(principal, workspace, action)
        with self._transaction() as db:
            row = self._resource(db, workspace, resource_id)
            if not row['installed'] or row['current'] != expected:
                raise ResourceConflict('resource_version_conflict')
            db.execute('UPDATE resources SET enabled=?,installed=? WHERE workspace=? AND id=?', (int(enabled), int(action != 'resources.uninstall'), workspace, resource_id))
            return self._catalog_item(db, self._resource(db, workspace, resource_id))

    def set_preinstall_draft(self, principal, workspace, profile, resource_id, *, include=True):
        self._authorize(principal, workspace, 'resources.preinstall.manage')
        identifier(profile)
        identifier(resource_id)
        if type(include) is not bool:
            raise ValueError('invalid_draft_membership')
        with self._transaction() as db:
            if not include:
                db.execute('DELETE FROM drafts WHERE workspace=? AND profile=? AND id=?', (workspace, profile, resource_id))
                return
            row = self._resource(db, workspace, resource_id)
            if not row['installed']:
                raise ResourceStateError('resource_not_installed')
            item = self._catalog_item(db, row)
            entry = {'resource_id': resource_id, 'version': item['version'], 'enabled': item['enabled'], 'resource': {key: item[key] for key in ('kind', 'source', 'digest', 'package_ref', 'runtime', 'available', 'diagnostics')}}
            db.execute('INSERT INTO drafts VALUES (?,?,?,?) ON CONFLICT(workspace,profile,id) DO UPDATE SET entry=excluded.entry', (workspace, profile, resource_id, canonical(entry)))

    def preinstall_manifest(self, principal, workspace, profile):
        self._authorize(principal, workspace, 'resources.preinstall.manage')
        identifier(profile)
        with self._transaction() as db:
            entries = [json.loads(row[0]) for row in db.execute('SELECT entry FROM drafts WHERE workspace=? AND profile=? ORDER BY id', (workspace, profile))]
        body = {'schema': 'capstone-preinstall/1', 'profile': profile, 'entries': entries}
        return validate_manifest({**body, 'version': content_digest(body)})

    def publish_preinstall(self, principal, workspace, profile):
        manifest = self.preinstall_manifest(principal, workspace, profile)
        with self._transaction() as db:
            self._authorize(principal, workspace, 'resources.preinstall.manage')
            db.execute('INSERT OR IGNORE INTO manifests VALUES (?,?,?,?)', (workspace, profile, manifest['version'], canonical(manifest)))
        return manifest

    def import_preinstall_draft(self, principal, workspace, manifest, *, replace=False):
        self._authorize(principal, workspace, 'resources.preinstall.manage')
        manifest = validate_manifest(manifest)
        profile = manifest['profile']
        with self._transaction() as db:
            for entry in manifest['entries']:
                old = db.execute('SELECT entry FROM drafts WHERE workspace=? AND profile=? AND id=?', (workspace, profile, entry['resource_id'])).fetchone()
                if old and old['entry'] != canonical(entry) and not replace:
                    raise ResourceConflict('preinstall_override_required')
                db.execute('INSERT INTO drafts VALUES (?,?,?,?) ON CONFLICT(workspace,profile,id) DO UPDATE SET entry=excluded.entry', (workspace, profile, entry['resource_id'], canonical(entry)))
        # Imported metadata is a desired pin only. It never enters versions or
        # installed resources until the installer verifies it in this environment.
        return manifest

    def published_manifest(self, principal, workspace, profile, version):
        self._authorize(principal, workspace, 'resources.preinstall.manage')
        with self._transaction() as db:
            row = db.execute('SELECT manifest FROM manifests WHERE workspace=? AND profile=? AND version=?', (workspace, profile, version)).fetchone()
            if row is None:
                raise KeyError('preinstall_manifest_not_found')
            return validate_manifest(json.loads(row[0]))

    def record_preinstall_application(self, principal, workspace, profile, version, receipt_id):
        """Internal deployment adapter receipt; publishing a draft cannot call this."""
        identifier(receipt_id)
        self.published_manifest(principal, workspace, profile, version)
        with self._transaction() as db:
            self._authorize(principal, workspace, 'resources.preinstall.manage')
            db.execute('INSERT INTO applications VALUES (?,?,?,?)', (workspace, profile, version, receipt_id))

    def preinstall_status(self, principal, workspace, profile):
        manifest = self.preinstall_manifest(principal, workspace, profile)
        with self._transaction() as db:
            published = bool(db.execute('SELECT 1 FROM manifests WHERE workspace=? AND profile=? AND version=?', (workspace, profile, manifest['version'])).fetchone())
            row = db.execute('SELECT receipt FROM applications WHERE workspace=? AND profile=? AND version=?', (workspace, profile, manifest['version'])).fetchone()
        return {'draft_version': manifest['version'], 'published': published, 'deployed': row is not None, 'application_receipt': row[0] if row else None}

    def preinstall_memberships(self, principal, workspace):
        """Read-only presentation metadata; publication does not imply deployment."""
        self._authorize(principal, workspace, 'resources.use')
        result = {}
        with self._transaction() as db:
            current = {row['id']: row['current'] for row in db.execute(
                'SELECT id,current FROM resources WHERE workspace=? AND installed=1', (workspace,))}
            for row in db.execute('SELECT profile,id,entry FROM drafts WHERE workspace=? ORDER BY profile', (workspace,)):
                if json.loads(row['entry'])['version'] == current.get(row['id']):
                    result.setdefault(row['id'], {'drafts': [], 'published': []})['drafts'].append(row['profile'])
            for row in db.execute('SELECT profile,manifest FROM manifests WHERE workspace=?', (workspace,)):
                for entry in json.loads(row['manifest'])['entries']:
                    if entry['version'] != current.get(entry['resource_id']):
                        continue
                    value = result.setdefault(entry['resource_id'], {'drafts': [], 'published': []})
                    if row['profile'] not in value['published']:
                        value['published'].append(row['profile'])
        return result
