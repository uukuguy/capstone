"""Application-owned template versions over the shared ledger and object store."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re
import secrets
from tempfile import SpooledTemporaryFile
from zipfile import ZipFile, BadZipFile
from xml.etree import ElementTree

from .thread_materials import _mutate, _write_event
from .thread_resources import ResourceUploads
from .presentation_template_contract import (
    CHUNK_BYTES, PROCESSING_BYTES, EXPANDED_BYTES, checked_template_reference as _reference,
)

KINDS = ('presentation_template_added', 'presentation_template_published', 'presentation_template_selected')


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


class PresentationTemplates:
    def __init__(self, service, objects, *, builtin: Path, uploads=None):
        self.service, self.objects, self.builtin_path = service, objects, Path(builtin)
        self.uploads = uploads or ResourceUploads(service, objects)
        self._builtin_template = None
        if hasattr(service, '_lock') and not hasattr(service, '_presentation_templates'):
            service._presentation_templates = {}

    def _scope(self, thread, workspace):
        self.service.require_workspace(thread, workspace)

    def _events(self, thread, *, connection=None, request_id=None, latest_selection=False):
        if connection is None and not hasattr(self.service, '_lock'):
            with self.service._connect() as opened:
                return self._events(thread, connection=opened, request_id=request_id, latest_selection=latest_selection)
        if connection is None:
            events = [e for e in self.service._events if e.thread_id == thread and e.event_type in KINDS]
            if request_id is not None:
                events = [e for e in events if e.payload.get('request_id') == request_id]
            if latest_selection:
                events = [e for e in events if e.event_type == 'presentation_template_selected'][-1:]
            return [deepcopy(e.payload) for e in events]
        query = 'SELECT payload FROM capstone_thread_events WHERE thread_id=%s AND event_type=ANY(%s)'
        params = [thread, list(KINDS)]
        if request_id is not None:
            query += " AND payload->>'request_id'=%s"
            params.append(request_id)
        if latest_selection:
            query += " AND event_type='presentation_template_selected' ORDER BY event_seq DESC LIMIT 1"
        else:
            query += ' ORDER BY event_seq'
        return [dict(row['payload']) for row in connection.execute(query, params).fetchall()]

    def _duplicate(self, thread, request_id, fingerprint, connection=None):
        if not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,127}', request_id):
            raise ValueError('template_request_invalid')
        records = self._events(thread, connection=connection, request_id=request_id)
        if records:
            if records[0]['request_hash'] != fingerprint:
                raise ValueError('template_request_conflict')
            return deepcopy(records[0]['result'])
        return None

    @staticmethod
    def _validate(stream):
        try:
            with ZipFile(stream) as archive:
                entries = archive.infolist()
                names = {e.filename for e in entries}
                if (len(entries) > 10000 or len(names) != len(entries)
                        or sum(e.file_size for e in entries) > EXPANDED_BYTES
                        or not {'[Content_Types].xml', 'ppt/presentation.xml'} <= names
                        or any(e.flag_bits & 1 or e.filename.startswith(('/', '\\'))
                               or '..' in Path(e.filename).parts
                               or e.filename.lower().endswith(('vbaproject.bin', '.exe', '.dll')) for e in entries)):
                    raise ValueError('invalid_template')
                # Read the two bounded package descriptors, not embedded content.
                for name in ('[Content_Types].xml', 'ppt/presentation.xml'):
                    if archive.getinfo(name).file_size > 1024 * 1024:
                        raise ValueError('invalid_template')
                    root = ElementTree.fromstring(archive.read(name))
                    expected = ('{http://schemas.openxmlformats.org/package/2006/content-types}Types'
                                if name == '[Content_Types].xml' else
                                '{http://schemas.openxmlformats.org/presentationml/2006/main}presentation')
                    if root.tag != expected:
                        raise ValueError('invalid_template')
        except (BadZipFile, KeyError, OSError, ValueError, ElementTree.ParseError) as error:
            raise ValueError('invalid_template') from error

    @staticmethod
    def _prefix(workspace, template):
        owner = 'builtin' if template['template_id'] == 'state-grid' else sha256(workspace.encode()).hexdigest()
        return f"presentation-templates/{owner}/{template['template_id']}/{template['sha256']}"

    def _copy(self, workspace, template, chunks):
        if template['size_bytes'] > PROCESSING_BYTES:
            raise ValueError('template_processing_limit')
        size = 0
        digest = sha256()
        # Spooling is a processing budget. Original upload/storage quotas stay independent.
        with SpooledTemporaryFile(max_size=CHUNK_BYTES) as temporary:
            for chunk in chunks:
                size += len(chunk)
                if size > template['size_bytes'] or size > PROCESSING_BYTES:
                    raise ValueError('template_source_changed')
                digest.update(chunk)
                temporary.write(chunk)
            if size != template['size_bytes'] or digest.hexdigest() != template['sha256']:
                raise ValueError('template_source_changed')
            temporary.seek(0)
            self._validate(temporary)
            temporary.seek(0)
            prefix = self._prefix(workspace, template)
            index = 0
            while chunk := temporary.read(CHUNK_BYTES):
                self.objects.put(prefix + f'/part-{index}', chunk, 'application/octet-stream')
                index += 1
        self.objects.put(prefix + '/manifest.json', _canonical(template).encode(), 'application/json')

    def builtin(self):
        if self._builtin_template is not None:
            return deepcopy(self._builtin_template)
        with self.builtin_path.open('rb') as incoming:
            data = incoming.read(PROCESSING_BYTES + 1)
        if len(data) > PROCESSING_BYTES:
            raise ValueError('template_processing_limit')
        digest = sha256(data).hexdigest()
        template = {'schema': 'capstone-presentation-template/1', 'template_id': 'state-grid',
                    'version': 'sha256:' + digest, 'sha256': digest, 'size_bytes': len(data),
                    'file_name': 'state-grid.pptx', 'name': 'State Grid', 'scope': 'builtin'}
        self._copy('', template, [data])
        self._builtin_template = deepcopy(template)
        return template

    def _row(self, thread, workspace, reference, connection=None):
        reference = _reference(reference)
        if reference['template_id'] == 'state-grid':
            try:
                value = json.loads(self.objects.get(self._prefix('', reference) + '/manifest.json', 4096))
            except (KeyError, ValueError):
                value = self.builtin()
            if _reference({k: value[k] for k in reference}) != reference:
                raise ValueError('template_identity_changed')
            return value
        if connection is None and not hasattr(self.service, '_lock'):
            with self.service._connect() as opened:
                return self._row(thread, workspace, reference, opened)
        if connection is None:
            row = self.service._presentation_templates.get((workspace, reference['template_id'], reference['version']))
        else:
            row = connection.execute('SELECT * FROM capstone_presentation_templates WHERE workspace=%s AND template_id=%s AND version=%s',
                                     (workspace, reference['template_id'], reference['version'])).fetchone()
        if row is None or not (row['published'] or row['owner_thread_id'] == thread):
            raise ValueError('template_not_found')
        value = deepcopy(dict(row['metadata']))
        if value['sha256'] != reference['sha256']:
            raise ValueError('template_identity_changed')
        value['scope'] = 'library' if row['published'] else 'session'
        return value

    def catalog(self, thread, workspace, *, limit=20, after=None):
        self._scope(thread, workspace)
        if type(limit) is not int or not 1 <= limit <= 128 or after is not None and (
                not isinstance(after, str) or not re.fullmatch(r'tpl_[a-f0-9]{32}', after)):
            raise ValueError('template_cursor_invalid')
        if hasattr(self.service, '_lock'):
            rows = sorted((r for (w, _, _), r in self.service._presentation_templates.items()
                           if w == workspace and (r['published'] or r['owner_thread_id'] == thread)
                           and (after is None or r['template_id'] > after)), key=lambda r: r['template_id'])[:limit+1]
        else:
            with self.service._connect() as connection:
                rows = connection.execute('SELECT * FROM capstone_presentation_templates WHERE workspace=%s AND (published OR owner_thread_id=%s) AND template_id>%s ORDER BY template_id LIMIT %s',
                                          (workspace, thread, after or '', limit+1)).fetchall()
        page = [{**dict(r['metadata']), 'scope': 'library' if r['published'] else 'session'} for r in rows[:limit]]
        return {'schema': 'capstone-presentation-template-catalog/1', 'builtin': self.builtin(),
                'templates': page, 'has_more': len(rows) > limit,
                'next_after': page[-1]['template_id'] if len(rows) > limit else None}

    def add(self, thread, workspace, resource, *, name, request_id):
        self._scope(thread, workspace)
        if not isinstance(name, str) or not name.strip() or len(name) > 160 or not isinstance(resource, dict):
            raise ValueError('template_request_invalid')
        fingerprint = sha256(_canonical({'operation': 'add', 'resource': resource, 'name': name}).encode()).hexdigest()
        duplicate = self._duplicate(thread, request_id, fingerprint)
        if duplicate is not None:
            return duplicate
        actual = next((r for r in self.uploads.resources(thread, draft=True) + self.uploads.resources(thread)
                       if r['resource_id'] == resource.get('resource_id')), None)
        reference_fields = {'resource_id', 'version', 'sha256'}
        valid_reference = (set(resource) == reference_fields and actual is not None
                           and all(resource[k] == actual[k] for k in reference_fields))
        if actual is None or not (valid_reference or actual == resource):
            raise ValueError('template_source_changed')
        if Path(actual['file_name']).suffix.lower() != '.pptx':
            raise ValueError('invalid_template')
        template = {'schema': 'capstone-presentation-template/1', 'template_id': 'tpl_' + secrets.token_hex(16),
                    'version': 'sha256:' + actual['sha256'], 'sha256': actual['sha256'], 'size_bytes': actual['size_bytes'],
                    'file_name': actual['file_name'], 'name': name.strip(), 'scope': 'session'}
        self._copy(workspace, template, self.uploads.read(thread, actual['resource_id']))
        def apply(snapshot, connection):
            duplicate = self._duplicate(thread, request_id, fingerprint, connection)
            if duplicate is not None:
                return duplicate
            row = {'workspace': workspace, 'template_id': template['template_id'], 'version': template['version'],
                   'owner_thread_id': thread, 'published': False, 'metadata': template}
            if connection is not None:
                from psycopg.types.json import Jsonb
                connection.execute('INSERT INTO capstone_presentation_templates (workspace,template_id,version,owner_thread_id,published,metadata) VALUES (%s,%s,%s,%s,%s,%s)',
                                   (workspace, template['template_id'], template['version'], thread, False, Jsonb(template)))
            _write_event(self.service, snapshot, 'presentation_template_added',
                         {'request_id': request_id, 'request_hash': fingerprint, 'result': template}, connection)
            if connection is None:
                self.service._presentation_templates[(workspace, template['template_id'], template['version'])] = row
            return deepcopy(template)
        return _mutate(self.service, thread, apply)

    def publish(self, thread, workspace, reference, *, request_id):
        self._scope(thread, workspace)
        fingerprint = sha256(_canonical({'operation': 'publish', 'reference': reference}).encode()).hexdigest()
        def apply(snapshot, connection):
            duplicate = self._duplicate(thread, request_id, fingerprint, connection)
            if duplicate is not None:
                return duplicate
            template = self._row(thread, workspace, reference, connection)
            if template['template_id'] == 'state-grid':
                raise ValueError('builtin_template_is_already_published')
            template['scope'] = 'library'
            if connection is not None:
                connection.execute('UPDATE capstone_presentation_templates SET published=true WHERE workspace=%s AND template_id=%s AND version=%s',
                                   (workspace, template['template_id'], template['version']))
            _write_event(self.service, snapshot, 'presentation_template_published',
                         {'request_id': request_id, 'request_hash': fingerprint, 'result': template}, connection)
            if connection is None:
                self.service._presentation_templates[(workspace, template['template_id'], template['version'])]['published'] = True
            return template
        return _mutate(self.service, thread, apply)

    def selection(self, thread, workspace):
        self._scope(thread, workspace)
        events = self._events(thread, latest_selection=True)
        if not events:
            return {'revision': 0, 'template': self.builtin()}
        selected = events[0]['result']
        reference = {k: selected['template'][k] for k in ('template_id', 'version', 'sha256')}
        return {'revision': selected['revision'], 'template': self._row(thread, workspace, reference)}

    def select(self, thread, workspace, reference, *, expected_revision, request_id):
        self._scope(thread, workspace)
        fingerprint = sha256(_canonical({'operation': 'select', 'reference': reference, 'revision': expected_revision}).encode()).hexdigest()
        def apply(snapshot, connection):
            duplicate = self._duplicate(thread, request_id, fingerprint, connection)
            if duplicate is not None:
                return duplicate
            events = self._events(thread, connection=connection, latest_selection=True)
            revision = events[0]['result']['revision'] if events else 0
            if type(expected_revision) is not int or expected_revision != revision:
                raise ValueError('template_revision_conflict')
            result = {'revision': revision + 1, 'template': self._row(thread, workspace, reference, connection)}
            _write_event(self.service, snapshot, 'presentation_template_selected',
                         {'request_id': request_id, 'request_hash': fingerprint, 'result': result}, connection)
            return result
        return _mutate(self.service, thread, apply)

    def freeze(self, thread, workspace, *, override=None):
        self._scope(thread, workspace)
        if override is None:
            current = self.selection(thread, workspace)['template']
            selected = {k: current[k] for k in ('template_id', 'version', 'sha256')}
        else:
            selected = override
        return self._row(thread, workspace, selected)

    def read(self, thread, workspace, reference):
        self._scope(thread, workspace)
        template = self._row(thread, workspace, reference)
        prefix = self._prefix(workspace, template)
        digest, size = sha256(), 0
        for index in range((template['size_bytes'] + CHUNK_BYTES - 1) // CHUNK_BYTES):
            data = self.objects.get(prefix + f'/part-{index}', CHUNK_BYTES)
            size += len(data)
            if len(data) > CHUNK_BYTES or size > template['size_bytes']:
                raise ValueError('template_identity_changed')
            digest.update(data)
            yield data
        if size != template['size_bytes'] or digest.hexdigest() != template['sha256']:
            raise ValueError('template_identity_changed')
