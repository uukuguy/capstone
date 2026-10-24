"""App-owned sealed graph inputs over the existing native host transport."""
from __future__ import annotations

from hashlib import sha256
import json
import mimetypes
import os
from pathlib import Path, PurePosixPath
import re
import stat
from threading import RLock
from uuid import uuid4

from .application_capacity import current_capacity, require_capacity
from .general_pi_storage import sync_directory
from .native_product_roles import publishable_product_path, file_artifact_id
from .native_document_types import TEXT_DOCUMENT_TYPES
from .native_research_bridge import checked_graph_progress, read_json, write_json

SCHEMA = 'capstone-enterprise-graph-context/1'
_IDENTITY = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z')


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def _stamp(value):
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


class NativeGraphContext:
    def __init__(self, *, root, workspace, uid, task_id, attempt_id, owner, view_provider, storage):
        if uid == os.geteuid() or not _IDENTITY.fullmatch(task_id):
            raise ValueError('Graph context requires a separate host owner')
        self.root, self.workspace = Path(root), Path(workspace).resolve()
        self.uid, self.task_id, self.attempt_id = uid, task_id, attempt_id
        self.owner = json.loads(_json(owner))
        self.view_provider, self.storage = view_provider, storage
        self.lock, self.grants, self.observations = RLock(), {}, {}
        for path in (self.root.parent, self.root, self.root / 'responses', self.root / 'results', self.root / 'grants', self.root / 'observations', self.root / 'observation-grants'):
            path.mkdir(parents=True, mode=0o750, exist_ok=True)
            self._protect(path, 0o711 if path == self.root.parent else 0o700 if path.name in {'grants', 'observation-grants'} else 0o750,
                          shared=path == self.root.parent)
        for path in (self.root / 'grants').glob('*.json'):
            grant = read_json(path)
            self._check_grant(grant)
            self.grants[grant['product']['ref']] = grant
        for path in (self.root / 'observation-grants').glob('*.json'):
            grant = read_json(path)
            self._check_observation(grant)
            self.observations[grant['ref']] = grant

    def admit_observation(self, source_ref, source_id, observation_sha256, *, action_id):
        """HOST ONLY: seal an already persisted, call-bound native observation."""
        with self.lock:
            if (not isinstance(source_ref, str) or not re.fullmatch(re.escape('native-observation:' + self.task_id + ':') + r'[a-f0-9]{64}', source_ref)
                    or not isinstance(source_id, str) or not _IDENTITY.fullmatch(source_id)
                    or not re.fullmatch(r'[a-f0-9]{64}', observation_sha256)):
                raise ValueError('Graph observation identity is invalid')
            previous = self.observations.get(source_ref)
            if previous is not None:
                if previous['sha256'] != observation_sha256 or previous['action_id'] != action_id or previous['source_id'] != source_id:
                    raise ValueError('Graph observation identity changed')
                self._check_observation(previous)
                return
            view = self.view_provider()['view']
            candidates = []
            for note in view.get('state', {}).get('notes', []):
                if not note.get('note_id', '').startswith('runtime.checkpoint.'): continue
                saved = json.loads(note['text'])
                if saved.get('schema') == 'capstone-enterprise-graph-checkpoint/1' and saved.get('runId') == self.task_id:
                    candidates.append((saved['committed_revision'], note['note_id']))
            if not candidates: raise ValueError('Graph observation has no committed lease')
            revision, ref = max(candidates)
            self._saved({'checkpoint': {'ref': ref, 'revision': revision}, 'action_id': action_id})
            source = self.storage.root / 'observations' / self.task_id / (source_id + '.json')
            temporary = self.root / 'observations' / ('.' + uuid4().hex)
            target = self.root / 'observations' / sha256(source_ref.encode()).hexdigest()
            fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                with os.fdopen(fd, 'rb') as incoming, temporary.open('xb') as outgoing:
                    before = os.fstat(incoming.fileno())
                    if not stat.S_ISREG(before.st_mode): raise ValueError('Graph observation file is invalid')
                    digest, size = sha256(), 0
                    while chunk := incoming.read(1024 * 1024):
                        size += len(chunk)
                        if size > before.st_size: raise ValueError('Graph observation changed')
                        digest.update(chunk)
                        outgoing.write(chunk)
                    after = os.fstat(incoming.fileno())
                    if (_stamp(before) != _stamp(after) or _stamp(after) != _stamp(source.lstat())
                            or size != before.st_size or digest.hexdigest() != observation_sha256):
                        raise ValueError('Graph observation bytes changed')
                    outgoing.flush()
                    os.fsync(outgoing.fileno())
                os.link(temporary, target)
                temporary.unlink()
                self._protect(target, 0o440)
                grant = {'ref': source_ref, 'source_id': source_id, 'sha256': observation_sha256, 'bytes': size,
                    'action_id': action_id, 'attempt_id': self.attempt_id, 'owner': self.owner,
                    'path': str(target), 'stamp': list(_stamp(target.stat()))}
                index = self.root / 'observation-grants' / (sha256(source_ref.encode()).hexdigest() + '.json')
                write_json(index, grant)
                self._protect(index, 0o400)
                self.observations[source_ref] = grant
                sync_directory(target.parent)
            finally:
                temporary.unlink(missing_ok=True)

    def _check_observation(self, grant):
        path = Path(grant['path'])
        info = path.lstat()
        if (path.parent != self.root / 'observations' or not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.geteuid() or info.st_mode & 0o222 or list(_stamp(info)) != grant['stamp']
                or grant['owner'] != self.owner or grant['attempt_id'] != self.attempt_id):
            raise ValueError('Graph observation handle is unavailable')

    def _protect(self, path, mode, *, shared=False):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or info.st_uid != os.geteuid():
            raise ValueError('Graph context path has an invalid owner')
        if os.geteuid() == 0:
            os.chown(path, 0, 0 if shared else self.uid)
        path.chmod(mode)

    def _saved(self, request):
        document = self.view_provider()
        binding, view = document['binding'], document['view']
        checkpoint = request['checkpoint']
        notes = view.get('state', {}).get('notes', [])
        note = next((item for item in notes if item.get('note_id') == checkpoint.get('ref')), None)
        if note is None: raise ValueError('Graph context checkpoint is unavailable')
        saved = json.loads(note['text'])
        checked_graph_progress({**saved['public_progress'], 'checkpoint': checkpoint}, binding=binding,
            task_id=self.task_id, attempt_id=self.attempt_id, view=view)
        snapshot = saved['snapshot']
        action = next((item for item in snapshot.get('actions', []) if item.get('id') == request['action_id']), None)
        if (action is None or action.get('owner') != self.owner or action.get('attempt_id') != self.attempt_id
                or action.get('kind') != 'execute'):
            raise ValueError('Graph context action is unavailable')
        latest = saved
        for item in notes:
            if not item.get('note_id', '').startswith('runtime.checkpoint.'): continue
            candidate = json.loads(item['text'])
            if candidate.get('schema') == saved['schema'] and candidate.get('runId') == self.task_id and candidate.get('committed_revision', 0) > latest['committed_revision']:
                latest = candidate
        current = latest['snapshot'].get('node_states', {}).get(action['step_id'], {})
        if (current.get('execute_action_id') != action['id']
                or current.get('applicability', 'current') != 'current'
                or current.get('execution_revision') != action.get('execution_revision')
                or current.get('definition_ref') != action.get('definition_ref')):
            raise ValueError('Graph context action version is stale')
        node = next((item for item in snapshot.get('nodes', []) if item.get('id') == action['step_id']), None)
        if node is None: raise ValueError('Graph context node is unavailable')
        return saved, action, node

    def handle(self, request):
        """Write one bounded retained receipt. Replays never repeat inspection."""
        with self.lock:
            request = json.loads(_json(request))
            request_id = request.get('request_id')
            if not isinstance(request_id, str) or not _IDENTITY.fullmatch(request_id):
                raise ValueError('Graph context request identity is invalid')
            digest = sha256(_json(request).encode()).hexdigest()
            base = {'schema': SCHEMA, 'request_id': request_id, 'request_sha256': digest}
            response_path = self.root / 'responses' / (request_id + '.json')
            if response_path.exists():
                previous = read_json(response_path)
                if previous['request_sha256'] == digest: return previous
                return {**base, 'ok': False, 'code': 'selection_invalid', 'error': 'Graph context request identity changed'}
            rejection_code = 'selection_invalid'
            try:
                require_capacity('research_request_bytes', len(_json(request).encode()), 'graph_context')
                if (set(request) != {'type', 'schema', 'owner', 'attempt_id', 'task_id', 'action_id', 'checkpoint', 'request_id', 'operation', 'selection'}
                        or request['type'] != 'enterprise_graph_context_request' or request['schema'] != SCHEMA
                        or request['owner'] != self.owner or request['attempt_id'] != self.attempt_id or request['task_id'] != self.task_id):
                    rejection_code = 'owner_invalid'
                    raise ValueError('Graph context request owner is invalid')
                rejection_code = 'action_unavailable'
                saved, action, node = self._saved(request)
                rejection_code = 'selection_invalid'
                if request['operation'] == 'freeze': result = self._freeze(request['selection'], action, node)
                elif request['operation'] == 'resolve': result = self._resolve(request['selection'], saved, action)
                elif request['operation'] == 'read': result = self._read_reference(request['selection'], saved, action)
                else: raise ValueError('Graph context operation is invalid')
                receipt = {**base, 'ok': True, 'result': result}
            except (ValueError, OSError, KeyError, TypeError) as error:
                receipt = {**base, 'ok': False, 'code': 'source_unavailable' if isinstance(error, OSError) else rejection_code,
                    'error': 'Graph context selection was rejected'}
                # Protected RPC provenance stays in this existing receipt only.
                # The JS client exposes fixed categories, never this selection.
                diagnostic = {key: request[key] for key in ('operation', 'action_id', 'checkpoint', 'selection') if key in request}
                limits = current_capacity().values
                if len(_json(diagnostic).encode()) <= min(limits['research_request_bytes'], limits['research_response_bytes'] // 2):
                    receipt['diagnostic'] = diagnostic
            write_json(response_path, receipt)
            self._protect(response_path, 0o440)
            return receipt

    def _open_source(self, parts):
        descriptors = [os.open(self.workspace, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)]
        try:
            for part in parts[:-1]:
                descriptors.append(os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptors[-1]))
            fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptors[-1])
            return fd, descriptors
        except BaseException:
            for descriptor in reversed(descriptors): os.close(descriptor)
            raise

    def _freeze(self, selection, action, node):
        if (set(selection) - {'products', 'retain_available'} or not isinstance(selection.get('products'), list)
                or not selection['products'] or type(selection.get('retain_available', False)) is not bool):
            raise ValueError('Graph products are required')
        require_capacity('artifact_count', len(selection['products']), 'graph_context')
        products, selections, seen, unavailable = [], [], set(), []
        for item in selection['products']:
            path, role = item['path'], item['role']
            relative = PurePosixPath(path)
            if (set(item) != {'path', 'role'} or not isinstance(path, str) or relative.is_absolute()
                    or '\\' in path or any(ord(char) < 32 for char in path)
                    or relative.as_posix() != path or any(part in {'.', '..'} for part in relative.parts)
                    or not publishable_product_path(path) or role not in {'primary', 'support', 'reproduction'} or path in seen):
                raise ValueError('Graph product path is invalid')
            seen.add(path)
            prefix = ['.research-workers', sha256(action['id'].encode()).hexdigest()] if node.get('execution') == 'delegated' else []
            if node.get('execution') not in {'parent', 'delegated'}: raise ValueError('Graph execution mode is invalid')
            parts = [*prefix, *relative.parts]
            try:
                fd, parents = self._open_source(parts)
            except OSError as error:
                if not selection.get('retain_available'): raise
                unavailable.append({'path': path, 'code': 'source_missing' if isinstance(error, FileNotFoundError) else 'source_unavailable'})
                continue
            temporary = self.root / 'results' / ('.' + uuid4().hex)
            try:
                with os.fdopen(fd, 'rb') as incoming, temporary.open('xb') as outgoing:
                    before = os.fstat(incoming.fileno())
                    if not stat.S_ISREG(before.st_mode) or before.st_size < 1:
                        if not selection.get('retain_available'): raise ValueError('Graph product must be a regular nonempty file')
                        unavailable.append({'path': path, 'code': 'source_unavailable'})
                        continue
                    digest, size = sha256(), 0
                    while chunk := incoming.read(1024 * 1024):
                        digest.update(chunk)
                        size += len(chunk)
                        if size > before.st_size: raise ValueError('Graph product changed during inspection')
                        outgoing.write(chunk)
                    after = os.fstat(incoming.fileno())
                    reopened, checks = self._open_source(parts)
                    try:
                        if (_stamp(before) != _stamp(after) or size != before.st_size or _stamp(after) != _stamp(os.fstat(reopened))
                                or [os.fstat(p).st_ino for p in parents] != [os.fstat(p).st_ino for p in checks]):
                            raise ValueError('Graph product changed during inspection')
                    finally:
                        os.close(reopened)
                        for descriptor in reversed(checks): os.close(descriptor)
                    outgoing.flush()
                    os.fsync(outgoing.fileno())
                digest = digest.hexdigest()
                public_path = '/'.join(('context-results', sha256(action['id'].encode()).hexdigest(), digest,
                    sha256(path.encode()).hexdigest()[:16] + '-' + relative.name))
                ref = 'workspace-product:' + sha256(json.dumps([public_path, digest, size], ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
                product = {'ref': ref, 'path': public_path, 'sha256': digest, 'bytes': size, 'roles': [role], 'status': 'ready',
                    'owner': self.owner, 'attempt_id': self.attempt_id, 'action_id': action['id']}
                existing = self.grants.get(ref)
                if existing is not None:
                    self._check_grant(existing)
                    if existing['product'] != product: raise ValueError('Graph product grant changed')
                    products.append(product)
                    selections.append({'path': path, 'ref': ref})
                    continue
                target = self.root / 'results' / sha256(ref.encode()).hexdigest()
                grant_path = self.root / 'grants' / (sha256(ref.encode()).hexdigest() + '.json')
                if grant_path.exists() or grant_path.is_symlink():
                    raise ValueError('Graph product grant already exists')
                os.link(temporary, target)
                try:
                    temporary.unlink()
                    self._protect(target, 0o440)
                    row = {'artifact_id': file_artifact_id(public_path, digest), 'task_id': self.task_id,
                        'parent_attempt_id': self.attempt_id, 'kind': 'workspace_file',
                        'metadata': {'path': public_path, 'sha256': digest, 'size_bytes': size}}
                    self.storage.artifact_file(self.task_id, target, row)
                    grant = {'product': product, 'path': str(target), 'stamp': list(_stamp(target.stat())), 'artifact': row}
                    write_json(grant_path, grant)
                    self._protect(grant_path, 0o440)
                    sync_directory(target.parent)
                    sync_directory(grant_path.parent)
                except BaseException:
                    # Both paths were absent before this operation's exclusive
                    # link. Roll back only its ungranted files. Saved artifact
                    # blobs remain immutable and can be reused on explicit retry.
                    grant_path.unlink(missing_ok=True)
                    target.unlink(missing_ok=True)
                    raise
                self.grants[ref] = grant
                products.append(product)
                selections.append({'path': path, 'ref': ref})
            finally:
                for descriptor in reversed(parents): os.close(descriptor)
                temporary.unlink(missing_ok=True)
        return {'ready': True, 'products': products, 'selections': selections,
            **({'unavailable': unavailable} if selection.get('retain_available') else {})}

    def _check_grant(self, grant):
        path, product = Path(grant['path']), grant['product']
        info = path.lstat()
        if (path.parent != self.root / 'results' or not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.geteuid() or info.st_mode & 0o222 or list(_stamp(info)) != grant['stamp']
                or product['owner'] != self.owner or product['attempt_id'] != self.attempt_id):
            raise ValueError('Graph sealed handle is unavailable')

    def _resolve(self, selection, saved, action):
        if set(selection) != {'result_refs', 'product_refs'} or any(not isinstance(selection[key], list) for key in selection):
            raise ValueError('Graph result selection is invalid')
        snapshot = saved['snapshot']
        refs, product_refs = selection['result_refs'], selection['product_refs']
        require_capacity('context_references', len(refs) + len(product_refs), 'graph_context')
        if len(set(product_refs)) != len(product_refs): raise ValueError('Graph product refs must be unique')
        allowed = {item['result_ref'] for item in action['input_bindings']}
        if len(set(refs)) != len(refs) or not set(refs) <= allowed: raise ValueError('Graph input version is undeclared')
        results = snapshot.get('results', []) + snapshot.get('external_results', [])
        def grants_producer(manifest, product, field='artifact_refs', seen=None):
            seen = set() if seen is None else seen
            if manifest['result_ref'] in seen: return False
            seen.add(manifest['result_ref'])
            if product['ref'] not in manifest.get(field, []): return False
            if (product['action_id'] == manifest['producer']['action_id']
                    and product['attempt_id'] == manifest['producer']['attempt_id']): return True
            return any(grants_producer(prior, product, field, seen) for prior in results
                       if prior['result_ref'] in manifest.get('consumed_results', []) and prior.get('owner') == self.owner)
        manifests, handles = [], []
        for ref in refs:
            manifest = next((item for item in results if item['result_ref'] == ref), None)
            if manifest is None or manifest.get('owner') != self.owner: raise ValueError('Graph result version is unavailable')
            selected = next(item for item in action['input_bindings'] if item['result_ref'] == ref)
            acceptance = selected.get('accepted_limitations')
            if acceptance is not None:
                producer = next((item for item in snapshot.get('executions', [])
                    if item.get('execute_action_id') == manifest['producer']['action_id']), None)
                if (not (snapshot.get('work_edition') == 'capstone-graph-work/1'
                         or snapshot.get('selected_limited_inputs') is True) or producer is None
                        or producer.get('phase') != 'limited' or producer.get('settled_status') != 'completed'
                        or producer.get('assessment', {}).get('outcome') != 'limited'
                        or not isinstance(acceptance, dict) or not isinstance(acceptance.get('rationale'), str)
                        or not acceptance['rationale'].strip()
                        or not isinstance(acceptance.get('assessment_summary'), str) or not acceptance['assessment_summary'].strip()
                        or acceptance != {'result_ref': ref, 'producer_action_id': producer['execute_action_id'],
                            'producer_execution_revision': producer['execution_revision'],
                            'assessment_ref': producer.get('assessment_ref'),
                            'assessment_summary': producer['assessment'].get('summary'),
                            'record_limitations': producer['record']['limitations'],
                            'unmet_checks': [item for item in producer['assessment']['checks'] if item['status'] != 'passed'],
                            'rationale': acceptance['rationale']}
                        or not producer.get('assessment_ref')
                        or not any(item.get('result_ref') == ref for item in producer.get('output_bindings', []))):
                    raise ValueError('Graph limited input acceptance is unavailable')
            manifests.append(manifest)
            for observation_ref in manifest.get('observation_refs', []):
                grant = self.observations.get(observation_ref)
                if grant is None or not grants_producer(manifest, grant, 'observation_refs'):
                    raise ValueError('Graph observation producer is unavailable')
                if not any(item.get('ref') == observation_ref and item.get('owner') == self.owner
                           and item.get('attempt_id') == grant['attempt_id'] and item.get('action_id') == grant['action_id']
                           for item in saved.get('receipts', [])):
                    raise ValueError('Graph observation receipt is not committed')
                self._check_observation(grant)
                handles.append({'ref': observation_ref, 'result_ref': ref, 'immutable': True, 'read_only': True, 'path': grant['path']})
            for artifact_ref in manifest['artifact_refs']:
                grant = self.grants.get(artifact_ref)
                if grant is None: raise ValueError('Graph sealed input is unavailable')
                self._check_grant(grant)
                if not grants_producer(manifest, grant['product']):
                    raise ValueError('Graph result producer changed')
                product = grant['product']
                # Public product names retain the original filename after a host hash prefix.
                file_name = re.sub(r'^[a-f0-9]{16}-', '', PurePosixPath(product['path']).name)
                handles.append({'ref': artifact_ref, 'result_ref': ref, 'immutable': True, 'read_only': True,
                    'path': grant['path'], 'file_name': file_name,
                    'media_type': TEXT_DOCUMENT_TYPES.get(PurePosixPath(file_name).suffix.lower())
                        or mimetypes.guess_type(file_name)[0] or 'application/octet-stream',
                    'size_bytes': product['bytes'], 'sha256': product['sha256'],
                    'roles': list(product['roles']), 'output_slot': manifest.get('slot')})
        products = []
        for ref in product_refs:
            grant = self.grants.get(ref)
            if grant is None or grant['product']['action_id'] != action['id']: raise ValueError('Graph product grant is unavailable')
            self._check_grant(grant)
            products.append(grant['product'])
        return {'manifests': manifests, 'handles': handles, 'products': products}

    def _read_reference(self, selection, saved, action):
        metadata_only = set(selection) == {'ref'}
        if not metadata_only and set(selection) != {'ref', 'offset_bytes', 'length_bytes'}:
            raise ValueError('Graph reference range is invalid')
        ref, offset, length = selection['ref'], selection.get('offset_bytes', 0), selection.get('length_bytes', 1)
        if (not isinstance(ref, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}', ref)
                or type(offset) is not int or offset < 0 or type(length) is not int or length < 1):
            raise ValueError('Graph reference range is invalid')
        require_capacity('product_excerpt_bytes', length, 'graph_reference_read')
        own_products = {item['ref'] for item in saved.get('products', []) if item.get('owner') == self.owner
            and item.get('action_id') == action['id'] and item.get('attempt_id') == self.attempt_id}
        own_observations = {item['ref'] for item in saved.get('receipts', []) if item.get('owner') == self.owner
            and item.get('action_id') == action['id'] and item.get('attempt_id') == self.attempt_id and item.get('status') == 'completed'}
        inherited = set()
        if ref not in own_products | own_observations:
            selected = self._resolve({'result_refs': [item['result_ref'] for item in action['input_bindings']], 'product_refs': []}, saved, action)
            inherited = {item['ref'] for item in selected['handles']}
        if ref in self.grants and ref in own_products | inherited:
            grant = self.grants[ref]
            self._check_grant(grant)
            product = grant['product']
            metadata = {'ref': ref, 'kind': 'product', 'logical_path': product['path'], 'roles': product['roles'],
                        'sha256': product['sha256'], 'bytes': product['bytes']}
        elif ref in self.observations and ref in own_observations | inherited:
            grant = self.observations[ref]
            self._check_observation(grant)
            metadata = {key: grant[key] for key in ('ref', 'sha256', 'bytes')}
            metadata['kind'] = 'observation'
        else:
            raise ValueError('Graph reference is not granted to this action')
        if metadata_only or metadata['kind'] == 'product' and PurePosixPath(metadata['logical_path']).suffix.lower() not in TEXT_DOCUMENT_TYPES:
            return {**metadata, 'content_status': 'metadata_only',
                    **({} if metadata_only else {'content_reason': 'unsupported_text_type'})}
        fd = os.open(grant['path'], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            before = os.fstat(fd)
            if list(_stamp(before)) != grant['stamp'] or offset > before.st_size:
                raise ValueError('Graph reference version changed')
            data = os.pread(fd, min(length, before.st_size - offset), offset)
            if _stamp(before) != _stamp(os.fstat(fd)) or list(_stamp(Path(grant['path']).lstat())) != grant['stamp']:
                raise ValueError('Graph reference version changed')
        finally:
            os.close(fd)
        content = {}
        try:
            text = data.decode('utf-8')
        except UnicodeDecodeError as error:
            trailing = error.reason == 'unexpected end of data' and error.end == len(data) and offset + len(data) < metadata['bytes']
            if trailing and error.start > 0:
                data = data[:error.start]
                text = data.decode('utf-8')
                content['utf8_boundary_trimmed'] = True
            else:
                text = None
                boundary = trailing or error.start == 0 and offset > 0 and bool(data) and 0x80 <= data[0] <= 0xbf
                content.update(content_status='metadata_only', content_reason='utf8_range_boundary' if boundary else 'invalid_utf8')
        if text is not None:
            if '\x00' in text: content.update(content_status='metadata_only', content_reason='binary_content')
            else: content.update(content_status='text', text=text)
        result = {**metadata, 'offset_bytes': offset, 'read_bytes': len(data),
                  'next_offset_bytes': offset + len(data) if offset + len(data) < metadata['bytes'] else None, **content}
        require_capacity('research_response_bytes', len(_json(result).encode()), 'graph_reference_read')
        return result

    def artifacts(self, presentation=None):
        with self.lock:
            selected = {item['path']: item for item in presentation['products']} if presentation else {}
            rows = []
            for grant in self.grants.values():
                self._check_grant(grant)
                row = json.loads(_json(grant['artifact']))
                metadata = row['metadata']
                item = selected.get(metadata['path'])
                if presentation and item and item['sha256'] == metadata['sha256'] and item['size_bytes'] == metadata['size_bytes']:
                    metadata.update(presentation_role=item['presentation_role'], delivery_status=presentation['delivery_status'],
                        delivery_limitations=presentation['delivery_limitations'])
                rows.append(row)
            return rows
