"""Immutable UTF-8 session materials over the existing ObjectStore and ledger."""
import base64
from dataclasses import replace
from hashlib import sha256
from pathlib import PurePosixPath
import re
import secrets

from fastapi import HTTPException, Request

from .thread_protocol import EventEnvelope
from .thread_service import ThreadNotFound, _now
from .native_document_types import TEXT_DOCUMENT_TYPES

MAX_SELECTED_MATERIALS = 4
from .application_capacity import limits, require_capacity, observe_capacity, CapacityExceeded
TYPES = TEXT_DOCUMENT_TYPES
EVENTS = ['material_uploaded', 'material_removed']


def _key(thread_id, item):
    return 'thread-materials/' + sha256(thread_id.encode()).hexdigest() + '/' + item['material_id'] + '/' + item['sha256']


def _active(service, thread_id, connection=None):
    if connection is None:
        if hasattr(service, '_lock'):
            service._check_thread(thread_id)
            events = [event.to_document() for event in service._events if event.event_type in EVENTS]
        else:
            with service._connect() as opened:
                return _active(service, thread_id, opened)
    else:
        rows = connection.execute("SELECT * FROM capstone_thread_events WHERE thread_id=%s AND event_type=ANY(%s) ORDER BY event_seq",
                                  (thread_id, EVENTS)).fetchall()
        events = [service._event_from_row(row).to_document() for row in rows]
    active = {}
    for event in events:
        payload = event['payload']
        if event['event_type'] == 'material_uploaded':
            active[payload['material']['material_id']] = payload['material']
        else:
            active.pop(payload['material_id'], None)
    return active


def material_page(service, thread_id):
    service.snapshot(thread_id)
    return {'schema': 'capstone-thread-materials/1', 'thread_id': thread_id,
            'materials': list(_active(service, thread_id).values()),
            'limits': {'max_file_bytes': limits.inline_material_bytes, 'max_selected_bytes': limits.inline_material_bytes,
                       'max_selected_files': limits.inline_material_count, 'supported_extensions': list(TYPES)}}


def _write_event(service, snapshot, kind, payload, connection=None):
    if connection is None:
        event = service._append_control_event(event_type=kind, payload=payload)
        service._snapshot = replace(snapshot, last_event_seq=event.event_seq)
    else:
        event = EventEnvelope('evt_' + secrets.token_hex(8), snapshot.last_event_seq + 1, kind, 1,
            snapshot.thread_id, snapshot.run.run_id, None, None, None, None, _now(), 'public', payload)
        service._insert_event(connection, event)
        connection.execute('UPDATE capstone_threads SET last_event_seq=%s WHERE thread_id=%s',
                           (event.event_seq, snapshot.thread_id))


def _mutate(service, thread_id, apply):
    if hasattr(service, '_lock'):
        with service._lock:
            service._check_thread(thread_id)
            if service._archived or service._snapshot.run.state != 'open':
                raise ValueError('session materials are not editable')
            return apply(service._snapshot, None)
    with service._connect() as connection:
        row = connection.execute('SELECT * FROM capstone_threads WHERE thread_id=%s FOR UPDATE', (thread_id,)).fetchone()
        if row is None:
            raise ThreadNotFound(thread_id)
        snapshot = service._snapshot_from_row(row)
        if row['archived'] or snapshot.run.state != 'open':
            raise ValueError('session materials are not editable')
        return apply(snapshot, connection)


def upload_material(service, objects, thread_id, filename, data):
    if (not isinstance(filename, str) or not filename or len(filename.encode()) > 255
            or PurePosixPath(filename).name != filename or '\\' in filename
            or any(ord(c) < 32 or ord(c) == 127 for c in filename)
            or PurePosixPath(filename).suffix.lower() not in TYPES):
        raise ValueError('only UTF-8 txt/md/csv/html/htm/svg/json text documents are supported')
    if isinstance(data, bytes):
        require_capacity('inline_material_bytes', len(data), phase='material.upload')
    if not isinstance(data, bytes) or not data or len(data) > limits.inline_material_bytes:
        raise ValueError(f'material exceeds configured capacity: {limits.inline_material_bytes} bytes')
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        raise ValueError('material must be UTF-8 text; PDF and OCR are not supported') from None
    if '\0' in text:
        raise ValueError('binary material is not supported')
    digest = sha256(data).hexdigest()
    material_id = 'material_' + sha256((thread_id + '\0' + filename + '\0' + digest).encode()).hexdigest()[:32]
    def apply(snapshot, connection):
        active = _active(service, thread_id, connection)
        if material_id in active:
            return active[material_id]
        require_capacity('inline_material_count', len(active) + 1, 'upload_material')
        require_capacity('inline_material_bytes', sum(item['size_bytes'] for item in active.values()) + len(data), 'upload_material')
        item = {'schema': 'capstone-thread-material/1', 'thread_id': thread_id, 'material_id': material_id,
            'file_name': filename, 'display_name': filename, 'media_type': TYPES[PurePosixPath(filename).suffix.lower()],
            'sha256': digest, 'size_bytes': len(data), 'created_at': _now()}
        key = _key(thread_id, item)
        try:
            existing = objects.get(key, limits.inline_material_bytes)
        except Exception:
            existing = None
        if existing is None:
            objects.put(key, data, item['media_type'])
        elif existing != data:
            raise ValueError('material integrity check failed')
        _write_event(service, snapshot, 'material_uploaded', {'material': item}, connection)
        return item
    return _mutate(service, thread_id, apply)


def remove_material(service, thread_id, material_id):
    if not isinstance(material_id, str) or not re.fullmatch(r'material_[a-f0-9]{32}', material_id):
        raise ValueError('invalid material identity')
    def apply(snapshot, connection):
        if material_id not in _active(service, thread_id, connection):
            return
        _write_event(service, snapshot, 'material_removed', {'material_id': material_id}, connection)
    _mutate(service, thread_id, apply)


def _process_files(service, snapshot, work_id, source_id, connection):
    if not work_id or work_id == 'new':
        return []
    if connection is None:
        rows = [event.to_document() for event in reversed(service._events)
                if event.event_type == 'native_artifact_published'
                and event.thread_id == snapshot.thread_id
                and event.payload['artifact'].get('work_id') == work_id
                and ((event.attempt_id == source_id) if source_id else
                     event.attempt_id in service._attempts and service._attempts[event.attempt_id]['attempt'].phase in {'completed', 'failed', 'cancelled'})]
    else:
        selection = "DISTINCT ON (e.payload->'artifact'->>'file_name') e.*" if source_id is None else 'e.*'
        query = f"""SELECT {selection} FROM capstone_thread_events e
            JOIN capstone_thread_attempts a ON a.attempt_id=e.attempt_id AND a.thread_id=e.thread_id
            WHERE e.thread_id=%s AND e.event_type='native_artifact_published'
            AND e.payload->'artifact'->>'work_id'=%s
            AND ((%s::text IS NOT NULL AND e.attempt_id=%s) OR (%s::text IS NULL AND a.phase IN ('completed','failed','cancelled')))"""
        if source_id is None:
            # Keep the latest version of each path, including earlier saved
            # work that a failed continuation did not replace.
            query += " ORDER BY e.payload->'artifact'->>'file_name', e.event_seq DESC"
            query = 'SELECT * FROM (' + query + ') latest ORDER BY event_seq DESC LIMIT %s'
        else:
            query += ' ORDER BY e.event_seq DESC LIMIT %s'
        values = connection.execute(query, (snapshot.thread_id, work_id, source_id, source_id, source_id, limits.artifact_count+1)).fetchall()
        rows = [service._event_from_row(row).to_document() for row in values]
    if not rows:
        return []
    latest = {}
    for event in rows:
        source = event['payload']['artifact']
        latest.setdefault(source['file_name'], source)
        if len(latest) > limits.artifact_count:
            observe_capacity('artifact_count', len(latest), phase='material.continuation.files')
            latest.pop(source['file_name'])
            break
    return list(reversed(list(latest.values())))


def _adopted_file_bytes(service, snapshot, source, connection, *, objects=None):
    """Reuse an explicit durable adoption of these exact process bytes.

    This does not adopt or promote another process artifact. The immutable
    process descriptor still controls ownership and the expected content hash.
    """
    if connection is None and not hasattr(service, '_events'):
        with service._connect() as opened:
            return _adopted_file_bytes(service, snapshot, source, opened, objects=objects)
    if connection is None:
        deliveries = (event.payload['delivery'] for event in reversed(service._events)
                      if event.event_type == 'delivery_published')
    else:
        rows = connection.execute('''SELECT payload->'delivery' AS delivery
            FROM capstone_thread_events WHERE thread_id=%s AND event_type='delivery_published'
            AND payload->'delivery'->'source_artifact'->>'attempt_id'=%s
            AND payload->'delivery'->'source_artifact'->>'artifact_id'=%s
            ORDER BY event_seq DESC''', (snapshot.thread_id, source['attempt_id'], source['artifact_id']))
        deliveries = (row['delivery'] for row in rows)
    from .thread_deliveries import _key as delivery_key
    objects = service._material_objects if objects is None else objects
    for delivery in deliveries:
        if (delivery.get('format') != 'native-file' or delivery.get('scope') != 'task'
                or delivery.get('thread_id') != snapshot.thread_id or delivery.get('work_id') != source['work_id']
                or delivery.get('source_artifact') != source
                or delivery.get('byte_size') != source['size_bytes']
                or delivery.get('content_digest') != source['sha256']):
            continue
        try:
            data = objects.get(delivery_key(snapshot.thread_id, delivery), limits.artifact_file_bytes)
            if len(data) == source['size_bytes'] and sha256(data).hexdigest() == source['sha256']:
                return data
        except Exception:
            continue
    raise OSError('no verified durable adoption is available')


def freeze_material_submission(service, snapshot, payload, submission, *, connection=None, work_id=None):
    """Freeze trusted bytes before command admission; missing refs reuse session objects."""
    active = _active(service, snapshot.thread_id, connection)
    refs = payload.get('material_refs', list(active))
    if (not isinstance(refs, list) or len(refs) > limits.inline_material_count
            or any(not isinstance(ref, str) or ref not in active for ref in refs) or len(set(refs)) != len(refs)):
        return submission, 'material_unavailable'
    if snapshot.active_model_context is not None:
        return submission, 'material_execution_unsupported' if payload.get('material_refs') or payload.get('attachment_refs') else None
    frozen = []
    try:
        for ref in refs:
            item = active[ref]
            data = service._material_objects.get(_key(snapshot.thread_id, item), limits.inline_material_bytes)
            if len(data) != item['size_bytes'] or sha256(data).hexdigest() != item['sha256']:
                raise ValueError('material integrity check failed')
            frozen.append({**item, 'content_base64': base64.b64encode(data).decode('ascii')})
    except CapacityExceeded:
        raise
    except Exception:
        return submission, 'material_unavailable'
    notices, deferred = [], []
    if not payload.get('context_product_refs'):
        from .native_artifact_projection import read_native_artifact
        for source in _process_files(service, snapshot, work_id, payload.get('source_attempt_id'), connection):
            # Choose the transport before admission. A resource reference does
            # not consume inline bytes; large continuation files are expected.
            if (payload.get('material_refs') == [] or len(frozen) >= limits.inline_material_count
                    or sum(item['size_bytes'] for item in frozen) + source['size_bytes'] > limits.inline_material_bytes
                    or PurePosixPath(source['file_name']).suffix.lower() not in TYPES):
                if source['size_bytes'] > 0:
                    deferred.append(source)
                continue
            try:
                try:
                    descriptor, data = read_native_artifact(service, service._native_executor, snapshot.thread_id,
                                                           source['attempt_id'], source['artifact_id'])
                except Exception:
                    data = _adopted_file_bytes(service, snapshot, source, connection)
                    descriptor = source
                data.decode('utf-8')
            except Exception:
                notices.append(source['file_name'] + ': not staged; original file is unavailable')
                continue
            frozen.append({'schema': 'capstone-thread-material/1', 'thread_id': snapshot.thread_id,
                'material_id': 'material_' + sha256(source['artifact_id'].encode()).hexdigest()[:32],
                'file_name': source['file_name'], 'display_name': source['file_name'],
                'sha256': source['sha256'], 'size_bytes': len(data), 'media_type': source['media_type'],
                'source_artifact': descriptor, 'content_base64': base64.b64encode(data).decode('ascii')})
    from .thread_resources import ResourceUploads
    from .resource_manifest import checked_resource
    states = ResourceUploads(service, service._material_objects).resource_states(snapshot.thread_id, connection)
    available = {state['resource']['resource_id']: state for state in states if state['state'] == 'complete'}
    attachments = payload.get('attachment_refs', [])
    if (not isinstance(attachments, list) or len(attachments) > limits.context_references
            or any(not isinstance(ref, str) or ref not in available for ref in attachments)
            or len(set(attachments)) != len(attachments)):
        return submission, 'attachment_unavailable'
    resources = [checked_resource(dict(state['resource'])) for ref, state in available.items()
                 if not state.get('draft', False) or ref in attachments]
    from .continuation_resources import artifact_resource
    resources.extend(artifact_resource(source) for source in deferred)
    return {**(submission or {}), 'material_refs': refs, '_materials': frozen, '_material_notices': notices,
        'attachment_refs': attachments,
        **({'_continuation_artifacts': deferred} if deferred else {}),
        **({'_resource_manifests': resources} if resources else {})}, None


def register_material_routes(app, *, service, objects, authorize):
    @app.get('/api/v1/threads/{thread_id}/materials')
    def list_materials(thread_id: str, request: Request):
        authorize(request)
        try:
            return material_page(service, thread_id)
        except ThreadNotFound:
            raise HTTPException(404, 'thread not found') from None

    @app.post('/api/v1/threads/{thread_id}/materials', status_code=201)
    async def upload(thread_id: str, request: Request, filename: str):
        authorize(request)
        if objects is None:
            raise HTTPException(503, 'material storage is unavailable')
        content = bytearray()
        async for chunk in request.stream():
            content.extend(chunk)
            require_capacity('inline_material_bytes', len(content), phase='material.upload.request')
        from starlette.concurrency import run_in_threadpool
        try:
            return await run_in_threadpool(upload_material, service, objects, thread_id, filename, bytes(content))
        except ThreadNotFound:
            raise HTTPException(404, 'thread not found') from None
        except CapacityExceeded:
            raise
        except ValueError as error:
            raise HTTPException(422, str(error)) from None

    @app.delete('/api/v1/threads/{thread_id}/materials/{material_id}')
    def remove(thread_id: str, material_id: str, request: Request):
        authorize(request)
        try:
            remove_material(service, thread_id, material_id)
            return {'removed': material_id}
        except ThreadNotFound:
            raise HTTPException(404, 'thread not found') from None
        except CapacityExceeded:
            raise
        except ValueError as error:
            raise HTTPException(422, str(error)) from None
