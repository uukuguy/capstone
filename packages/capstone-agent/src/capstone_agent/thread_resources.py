"""Resumable private resources; file size is independent of model context size."""
from hashlib import sha256
from pathlib import PurePosixPath
import re
import secrets
import time

from .thread_materials import _mutate, _write_event
from .application_capacity import CapacityExceeded, current_capacity, limits

EVENTS = ['resource_upload_started', 'resource_part_reserved', 'resource_part_stored', 'resource_upload_cancelled', 'resource_published', 'command_accepted']


class ResourceUploads:
    def __init__(self, service, objects, *, chunk_bytes=None,
                 max_file_bytes=None, ttl_seconds=None, max_session_bytes=None):
        chunk_bytes = limits.upload_chunk_bytes if chunk_bytes is None else chunk_bytes
        max_file_bytes = limits.upload_file_bytes if max_file_bytes is None else max_file_bytes
        ttl_seconds = limits.retention_seconds if ttl_seconds is None else ttl_seconds
        max_session_bytes = limits.upload_session_bytes if max_session_bytes is None else max_session_bytes
        if not 1 <= chunk_bytes <= limits.upload_chunk_max_bytes or min(max_file_bytes, ttl_seconds, max_session_bytes) < 1:
            raise ValueError('invalid resource limits')
        self.service, self.objects = service, objects
        self.chunk_bytes, self.max_file_bytes, self.ttl_seconds = chunk_bytes, max_file_bytes, ttl_seconds
        self.max_session_bytes = max_session_bytes

    def _events(self, thread, connection=None):
        if connection is not None:
            rows = connection.execute('SELECT * FROM capstone_thread_events WHERE thread_id=%s AND event_type=ANY(%s) ORDER BY event_seq', (thread, EVENTS)).fetchall()
            return [self.service._event_from_row(row) for row in rows]
        if hasattr(self.service, '_lock'):
            self.service._check_thread(thread)
            return [e for e in self.service._events if e.thread_id == thread and e.event_type in EVENTS]
        with self.service._connect() as opened:
            return self._events(thread, opened)

    def _state(self, thread, uid, connection=None, *, events=None):
        state = None
        for event in self._events(thread, connection) if events is None else events:
            p = event.payload
            if state is not None and event.event_type == 'command_accepted' and 'resource_' + uid.removeprefix('upload_') in p.get('attachment_refs', []):
                state['draft'] = False
            if p.get('upload_id') != uid:
                continue
            if event.event_type == 'resource_upload_started':
                state = {**p, 'state': 'uploading', 'parts': {}, 'reserved': {}}
            elif state is not None and event.event_type == 'resource_part_reserved':
                state['reserved'][p['index']] = p
            elif state is not None and event.event_type == 'resource_part_stored':
                state['parts'][p['index']] = p
            elif state is not None and event.event_type == 'resource_upload_cancelled':
                state['state'] = p['state']
            elif state is not None and event.event_type == 'resource_published':
                state.update(state='complete', resource=p['resource'])
        if state is None:
            raise ValueError('upload not found in this session')
        return state

    @staticmethod
    def _public(state):
        return {k: state[k] for k in ('upload_id', 'file_name', 'size_bytes', 'chunk_bytes', 'expires_at', 'state')} | {
            'schema': 'capstone-resource-upload/1', 'received_parts': sorted(state['parts']),
            'part_sha256': {str(i): p['sha256'] for i, p in state['parts'].items()},
            'received_bytes': sum(p['size_bytes'] for p in state['parts'].values()),
            'resource': state.get('resource')}

    @staticmethod
    def _key(thread, uid, part):
        return f"thread-resources/{sha256(thread.encode()).hexdigest()}/{uid}/{part['index']}/{part['sha256']}"

    @staticmethod
    def _editable(state):
        if state['state'] != 'uploading' or state['expires_at'] <= time.time():
            raise ValueError('upload is closed or expired')

    def begin(self, thread, name, size, request_id, draft=False):
        if type(size) is int and size > self.max_file_bytes:
            raise CapacityExceeded('upload_file_bytes', size, self.max_file_bytes, 'resource.upload.begin', mode=current_capacity().mode)
        if (not isinstance(name, str) or not name or len(name.encode()) > 255
                or PurePosixPath(name).name != name or '\\' in name
                or any(ord(c) < 32 or ord(c) == 127 for c in name)
                or type(draft) is not bool or type(size) is not int or not 0 < size <= self.max_file_bytes
                or not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', request_id)):
            raise ValueError('invalid upload metadata or configured capacity exceeded')
        def apply(snapshot, connection):
            reservations = {}
            for event in self._events(thread, connection):
                p = event.payload
                if event.event_type == 'resource_upload_started':
                    reservations[p['upload_id']] = p['size_bytes']
                elif event.event_type == 'resource_upload_cancelled':
                    reservations.pop(p['upload_id'], None)
                if event.event_type == 'resource_upload_started' and p['request_id'] == request_id:
                    if p['file_name'] != name or p['size_bytes'] != size or p.get('draft', False) != draft:
                        raise ValueError('upload request conflict')
                    return self._public(self._state(thread, p['upload_id'], connection))
            if sum(reservations.values()) + size > self.max_session_bytes:
                if current_capacity().mode != 'debug':
                    raise ValueError('session storage quota exceeded; cancel unused uploads')
                raise CapacityExceeded('upload_session_bytes', sum(reservations.values())+size, self.max_session_bytes, 'resource.upload.begin', mode=current_capacity().mode)
            payload = {'upload_id': 'upload_' + secrets.token_hex(16), 'request_id': request_id,
                'file_name': name, 'size_bytes': size, 'chunk_bytes': self.chunk_bytes,
                'expires_at': time.time() + self.ttl_seconds, 'draft': draft}
            _write_event(self.service, snapshot, 'resource_upload_started', payload, connection)
            return self._public({**payload, 'state': 'uploading', 'parts': {}})
        return _mutate(self.service, thread, apply)

    def status(self, thread, uid):
        self.service.snapshot(thread)
        state = self._state(thread, uid)
        if state['state'] in ('cancelled', 'expired') or (state['state'] == 'uploading' and state['expires_at'] <= time.time()):
            self.cancel(thread, uid, expired=True)
            state = self._state(thread, uid)
        return self._public(state)

    def resources(self, thread, draft=False, connection=None):
        self.service.snapshot(thread)
        return [state['resource'] for state in self.resource_states(thread, connection)
                if state['state'] == 'complete' and state.get('draft', False) == draft]

    def resource_states(self, thread, connection=None):
        events = self._events(thread, connection)
        return [self._state(thread, e.payload['upload_id'], connection, events=events)
                for e in events if e.event_type == 'resource_published']

    def part(self, thread, uid, index, data):
        def reserve(snapshot, connection):
            state = self._state(thread, uid, connection)
            self._editable(state)
            if type(index) is not int or index < 0 or index * state['chunk_bytes'] >= state['size_bytes']:
                raise ValueError('invalid part index')
            expected = min(state['chunk_bytes'], state['size_bytes'] - index * state['chunk_bytes'])
            if not isinstance(data, bytes) or len(data) != expected:
                raise ValueError('invalid part size')
            part = {'upload_id': uid, 'index': index, 'size_bytes': len(data), 'sha256': sha256(data).hexdigest()}
            previous = state['parts'].get(index) or state['reserved'].get(index)
            if previous and previous != part:
                raise ValueError('part conflict')
            if not previous:
                _write_event(self.service, snapshot, 'resource_part_reserved', part, connection)
            return part
        # A committed reservation makes a write-before-ack crash reclaimable.
        part = _mutate(self.service, thread, reserve)
        def apply(snapshot, connection):
            state = self._state(thread, uid, connection)
            self._editable(state)
            if index not in state['parts']:
                self.objects.put(self._key(thread, uid, part), data, 'application/octet-stream')
                _write_event(self.service, snapshot, 'resource_part_stored', part, connection)
            return part
        return _mutate(self.service, thread, apply)

    def _bytes(self, thread, uid, part):
        data = self.objects.get(self._key(thread, uid, part), part['size_bytes'])
        if len(data) != part['size_bytes'] or sha256(data).hexdigest() != part['sha256']:
            raise ValueError('resource part integrity failed')
        return data

    def complete(self, thread, uid):
        self.service.snapshot(thread)
        state = self._state(thread, uid)
        if state['state'] == 'complete':
            return state['resource']
        self._editable(state)
        count = (state['size_bytes'] + state['chunk_bytes'] - 1) // state['chunk_bytes']
        if len(state['parts']) != count:
            raise ValueError('upload is incomplete')
        # Whole-file verification is outside the Thread transaction and uses one bounded part.
        digest = sha256()
        for i in range(count):
            digest.update(self._bytes(thread, uid, state['parts'][i]))
        resource = {'schema': 'capstone-resource/1', 'resource_id': 'resource_' + uid.removeprefix('upload_'),
            'version': 1, 'thread_id': thread, 'file_name': state['file_name'],
            'size_bytes': state['size_bytes'], 'sha256': digest.hexdigest(),
            'media_type': 'application/octet-stream', 'processing_state': 'unprocessed'}
        def publish(snapshot, connection):
            latest = self._state(thread, uid, connection)
            if latest['state'] == 'complete':
                return latest['resource']
            self._editable(latest)
            if latest['parts'] != state['parts']:
                raise ValueError('upload changed during verification')
            _write_event(self.service, snapshot, 'resource_published', {'upload_id': uid, 'resource': resource}, connection)
            return resource
        return _mutate(self.service, thread, publish)

    def cancel(self, thread, uid, *, expired=False):
        def apply(snapshot, connection):
            state = self._state(thread, uid, connection)
            if state['state'] == 'complete' and not state.get('draft', False):
                raise ValueError('published resources cannot be cancelled')
            if state['state'] in ('uploading', 'complete'):
                _write_event(self.service, snapshot, 'resource_upload_cancelled',
                    {'upload_id': uid, 'state': 'expired' if expired else 'cancelled'}, connection)
            return state
        state = _mutate(self.service, thread, apply)
        for part in (state['reserved'] | state['parts']).values():
            self.objects.delete(self._key(thread, uid, part))

    def read(self, thread, resource_id, *, start=0, length=None):
        self.service.snapshot(thread)
        if not re.fullmatch(r'resource_[a-f0-9]{32}', resource_id):
            raise ValueError('invalid resource identity')
        uid = 'upload_' + resource_id.removeprefix('resource_')
        state = self._state(thread, uid)
        if state['state'] != 'complete':
            raise ValueError('resource is not published')
        length = state['size_bytes'] - start if length is None else length
        if type(start) is not int or type(length) is not int or min(start, length) < 0 or start + length > state['size_bytes']:
            raise ValueError('invalid resource range')
        end = start + length
        for i in range(start // state['chunk_bytes'], (end + state['chunk_bytes'] - 1) // state['chunk_bytes']):
            data = self._bytes(thread, uid, state['parts'][i])
            offset = i * state['chunk_bytes']
            yield data[max(0, start-offset):min(len(data), end-offset)]
