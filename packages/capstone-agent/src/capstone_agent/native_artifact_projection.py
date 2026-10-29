"""Process-scoped native files from verified child results and the Thread ledger."""
from hashlib import sha256
import json
from pathlib import PurePosixPath
import re
from urllib.parse import quote

from fastapi import HTTPException, Request, Response
from .native_document_types import TEXT_DOCUMENT_TYPES

MAX_FILE_BYTES = 4 * 1024 * 1024
ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}')
MEDIA = {**TEXT_DOCUMENT_TYPES, '.pdf': 'application/pdf', '.png': 'image/png',
         '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}

from .application_capacity import limits, require_capacity


def _identity_digest(identity):
    from .native_task_context import public_document
    return sha256(json.dumps(public_document(identity), sort_keys=True, separators=(',', ':'),
                             ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _id(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError('invalid native artifact identity')
    return value


def _url(thread_id, attempt_id, artifact_id):
    return f'/api/v1/threads/{_id(thread_id)}/attempts/{_id(attempt_id)}/artifacts/{_id(artifact_id)}'


def project_native_artifacts(claim, result, *, expected_parent_attempt_id=None):
    """Bind host file identities to the accepted Attempt, never promote delivery."""
    document = result.to_document()
    return _project_artifact_document(claim, document, expected_parent_attempt_id=expected_parent_attempt_id)


def project_native_artifact_capture(claim, request, event):
    """A running capture is an available version, not a terminal task result."""
    expected = {'type', 'schema', 'task_id', 'parent_attempt_id', 'executor_identity', 'artifact'}
    if (not isinstance(event, dict) or set(event) - {'event_id'} != expected
            or event.get('type') != 'native_artifact_captured'
            or event.get('schema') != 'capstone-pi-artifact-capture/1'
            or event['task_id'] != request.task_id or event['parent_attempt_id'] != request.parent_attempt_id
            or event['executor_identity'] != request.to_document()['executor_identity']):
        raise ValueError('native capture task identity changed')
    artifact = event['artifact']
    if (not isinstance(artifact, dict)
            or set(artifact) != {'artifact_id','task_id','parent_attempt_id','kind','metadata'}
            or artifact.get('kind') != 'workspace_file'
            or not isinstance(artifact.get('metadata'), dict)
            or set(artifact['metadata']) - {'path','sha256','size_bytes','presentation_role'}):
        raise ValueError('native capture file descriptor is invalid')
    return _project_artifact_document(claim, {'task_id':event['task_id'],
        'parent_attempt_id':event['parent_attempt_id'], 'executor_identity':event['executor_identity'],
        'status':'running', 'artifacts':[artifact]}, expected_parent_attempt_id=request.parent_attempt_id)


def _project_artifact_document(claim, document, *, expected_parent_attempt_id=None):
    if not document['artifacts']:
        return []
    parent = claim.attempt.attempt_id
    producer = parent if expected_parent_attempt_id is None else _id(expected_parent_attempt_id)
    if document['parent_attempt_id'] != producer:
        raise ValueError('native file parent differs from the accepted Attempt')
    context = claim.task_context
    if context is not None and context.binding.thread_id != claim.thread_id:
        raise ValueError('native file Work differs from the accepted Thread')
    artifacts = []
    for item in document['artifacts']:
        if item['kind'] != 'workspace_file':
            continue
        if item['task_id'] != document['task_id'] or item['parent_attempt_id'] != producer:
            raise ValueError('native file differs from the executed child task')
        metadata = item['metadata']
        path = metadata.get('path')
        if (not isinstance(path, str) or not path or len(path.encode()) > 1024
                or '\\' in path or any(ord(c) < 32 or ord(c) == 127 for c in path)
                or PurePosixPath(path).is_absolute() or '..' in PurePosixPath(path).parts):
            raise ValueError('native file name is invalid')
        name = PurePosixPath(path).name
        digest, size = metadata.get('sha256'), metadata.get('size_bytes')
        if type(size) is int:
            require_capacity('artifact_file_bytes', size, phase='artifact.projection')
        if (not isinstance(digest, str) or not re.fullmatch(r'[a-f0-9]{64}', digest)
                or type(size) is not int or not 0 <= size <= limits.artifact_file_bytes
                or not name or len(name.encode()) > 255):
            raise ValueError('native file content identity is invalid')
        expected_id = 'file-' + sha256(path.encode()).hexdigest()[:16] + '-' + digest
        if item['artifact_id'] != expected_id:
            raise ValueError('native file receipt identity changed')
        # Native host IDs use relative name and bytes, so equal files from two
        # child tasks share one host ID. Namespace the public ID by child task.
        public_id = 'file-' + sha256((document['task_id'] + '\0' + item['artifact_id']).encode()).hexdigest()[:16] + '-' + digest
        descriptor = {'schema': 'capstone-process-artifact/1', 'scope': 'instruction',
            'thread_id': claim.thread_id, 'run_id': claim.run_id, 'turn_id': claim.attempt.turn_id,
            'attempt_id': parent, 'work_id': None if context is None else context.binding.work_id,
            'producer_attempt_id': producer,
            'task_snapshot_id': None if context is None else context.snapshot_id,
            'goal_revision': None if context is None else context.goal_revision,
            'task_id': document['task_id'], 'artifact_id': public_id, 'host_artifact_id': item['artifact_id'],
            'executor_identity_sha256': _identity_digest(document['executor_identity']), 'source_status': document['status'],
            'file_name': name, 'media_type': MEDIA.get(PurePosixPath(name).suffix.lower(), 'application/octet-stream'),
            'sha256': digest, 'size_bytes': size,
            'download_url': _url(claim.thread_id, parent, public_id)}
        artifacts.append(descriptor)
        # A producer-declared purpose is presentation metadata, not acceptance.
        if metadata.get('presentation_role') in {'primary', 'support', 'reproduction'}:
            descriptor['presentation_role'] = metadata['presentation_role']
            if metadata.get('delivery_status') in {'limited', 'completed'}:
                warnings = metadata.get('delivery_limitations')
                if not isinstance(warnings, list) or any(not isinstance(text, str) for text in warnings):
                    raise ValueError('native delivery limitations are invalid')
                descriptor.update(delivery_status=metadata['delivery_status'], delivery_limitations=warnings)
    require_capacity('artifact_count', len(artifacts), phase='artifact.projection')
    if len({item['artifact_id'] for item in artifacts}) != len(artifacts):
        raise ValueError('native file receipt count is invalid')
    return artifacts


def native_artifact_page(service, thread_id, attempt_id, *, after=0):
    """Read one bounded existing Attempt-record page, with the same cursor."""
    _id(thread_id); _id(attempt_id)
    page = service.read_attempt_records(thread_id, attempt_id, after=after, limit=128)
    artifacts = []
    presentation_cache = {}
    for event in page['events']:
        if event['event_type'] != 'native_artifact_published' or event['visibility'] != 'public':
            continue
        item = event['payload']['artifact']
        if (event['thread_id'] != thread_id or event['attempt_id'] != attempt_id
                or item['thread_id'] != thread_id or item['attempt_id'] != attempt_id
                or item['schema'] != 'capstone-process-artifact/1' or item['scope'] != 'instruction'
                or item['download_url'] != _url(thread_id, attempt_id, item['artifact_id'])):
            raise ValueError('native file ledger ownership changed')
        from .native_product_roles import presentation_for_artifact
        artifacts.append(presentation_for_artifact(item, getattr(service, '_material_objects', None), presentation_cache))
    return {'schema': 'capstone-process-artifacts/1', 'thread_id': thread_id, 'attempt_id': attempt_id,
            'artifacts': artifacts, 'has_more': page['has_more'], 'next_after': page['next_after']}


def artifact_object_key(item):
    return ('native-process-artifacts/' + _id(item['thread_id']) + '/' + _id(item['attempt_id'])
            + '/' + _id(item['artifact_id']) + '/' + item['sha256'])


def _verified_bytes(item, data):
    if len(data) != item['size_bytes'] or sha256(data).hexdigest() != item['sha256']:
        raise OSError('native file content verification failed')
    return data


def _saved_artifact(objects, item):
    if objects is None:
        return None
    try:
        data = objects.get(artifact_object_key(item), limits.artifact_file_bytes)
    except Exception:
        return None
    return _verified_bytes(item, data)


def retain_native_artifact(objects, executor, item, *, check=lambda:None):
    """Keep exact process bytes in the host store without promoting delivery."""
    check()
    saved = _saved_artifact(objects, item)
    check()
    if saved is not None:
        return saved
    if executor is None:
        raise OSError('native file executor is unavailable')
    # The endpoint is host-selected and protected. Image/config identity may
    # advance while old files remain valid: ledger ownership and exact bytes
    # determine a saved file's identity, not the current executor revision.
    data = _verified_bytes(item, executor.read_artifact(item['task_id'], item['host_artifact_id'],
        expected_sha256=item['sha256'], expected_size=item['size_bytes']))
    check()
    if objects is not None:
        objects.put(artifact_object_key(item), data, item['media_type'])
        check()
        _verified_bytes(item, objects.get(artifact_object_key(item), limits.artifact_file_bytes))
    return data


def read_native_artifact(service, executor, thread_id, attempt_id, artifact_id, *, objects=None):
    """Authorize against durable process ownership before private host access."""
    _id(artifact_id)
    after = 0
    while True:
        page = native_artifact_page(service, thread_id, attempt_id, after=after)
        item = next((item for item in page['artifacts'] if item['artifact_id'] == artifact_id), None)
        if item is not None:
            if objects is None:
                objects = getattr(service, '_material_objects', None)
            data = retain_native_artifact(objects, executor, item)
            return item, data
        if not page['has_more']:
            raise KeyError('native file not found in this Attempt')
        if page['next_after'] <= after:
            raise ValueError('native file records made no progress')
        after = page['next_after']


def register_native_artifact_routes(app, *, service, executor_provider, authorize):
    """Register same-origin private Thread routes; no client-selected host."""
    from .thread_service import ThreadNotFound
    from .thread_protocol import ThreadProtocolError

    @app.get('/api/v1/threads/{thread_id}/attempts/{attempt_id}/artifacts')
    def list_files(thread_id: str, attempt_id: str, request: Request, after: int = 0):
        authorize(request)
        try:
            return native_artifact_page(service, thread_id, attempt_id, after=after)
        except (ThreadNotFound, KeyError):
            raise HTTPException(404, 'process files not found') from None
        except (ValueError, ThreadProtocolError):
            raise HTTPException(422, 'process file cursor is invalid') from None

    @app.get('/api/v1/threads/{thread_id}/attempts/{attempt_id}/artifacts/{artifact_id}')
    def download_file(thread_id: str, attempt_id: str, artifact_id: str, request: Request):
        authorize(request)
        try:
            item, data = read_native_artifact(service, executor_provider(), thread_id, attempt_id, artifact_id)
            return Response(data, media_type=item['media_type'], headers={
                'Content-Disposition': "attachment; filename*=UTF-8''" + quote(item['file_name'], safe=''),
                'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'private, no-store'})
        except (ThreadNotFound, KeyError):
            raise HTTPException(404, 'process file not found') from None
        except (OSError, RuntimeError, TimeoutError):
            raise HTTPException(410, 'process file content is unavailable') from None
        except (ValueError, ThreadProtocolError):
            raise HTTPException(422, 'process file identity is invalid') from None
