"""Authenticated bounded-chunk transport for enterprise resources."""
from fastapi import HTTPException, Request
from starlette.concurrency import run_in_threadpool

from .thread_resources import ResourceUploads
from .thread_service import ThreadNotFound
from .application_capacity import CapacityExceeded, current_capacity, require_capacity, limits as capacity_limits


def register_resource_routes(app, *, service, objects, authorize, uploads=None):
    import os
    uploads = uploads or ResourceUploads(service, objects,
        max_file_bytes=int(os.getenv('CAPSTONE_RESOURCE_MAX_FILE_BYTES', str(capacity_limits.upload_file_bytes))),
        max_session_bytes=int(os.getenv('CAPSTONE_RESOURCE_MAX_SESSION_BYTES', str(capacity_limits.upload_session_bytes))),
        ttl_seconds=int(os.getenv('CAPSTONE_RESOURCE_UPLOAD_TTL_SECONDS', str(capacity_limits.retention_seconds))))

    def check(request):
        authorize(request)
        if objects is None:
            raise HTTPException(503, 'resource storage is unavailable')

    async def invoke(fn, *args):
        try:
            return await run_in_threadpool(fn, *args)
        except ThreadNotFound:
            raise HTTPException(404, 'thread not found') from None
        except CapacityExceeded:
            raise
        except ValueError as error:
            raise HTTPException(409, str(error)) from None

    @app.get('/api/v1/threads/{thread_id}/resource-uploads')
    async def limits(thread_id: str, request: Request):
        check(request)
        await invoke(service.snapshot, thread_id)
        return {'schema': 'capstone-resource-upload-limits/1', 'chunk_bytes': uploads.chunk_bytes,
            'max_file_bytes': uploads.max_file_bytes, 'max_session_bytes': uploads.max_session_bytes,
            'ttl_seconds': uploads.ttl_seconds}

    @app.get('/api/v1/threads/{thread_id}/resources')
    async def resources(thread_id: str, request: Request, draft: bool = False):
        check(request)
        return {'schema': 'capstone-resources/1', 'resources': await invoke(uploads.resources, thread_id, draft)}

    @app.post('/api/v1/threads/{thread_id}/resource-uploads', status_code=201)
    async def begin(thread_id: str, request: Request):
        check(request)
        data = bytearray()
        async for chunk in request.stream():
            require_capacity('control_document_bytes', len(data)+len(chunk), phase='resource.upload.metadata')
            data.extend(chunk)
        import json
        try:
            body = json.loads(data)
            if not isinstance(body, dict) or not {'file_name', 'size_bytes', 'request_id'} <= set(body) or set(body) - {'file_name', 'size_bytes', 'request_id', 'draft'}:
                raise ValueError()
        except (ValueError, TypeError):
            raise HTTPException(422, 'invalid upload metadata') from None
        return await invoke(uploads.begin, thread_id, body['file_name'], body['size_bytes'], body['request_id'], body.get('draft', False))

    @app.get('/api/v1/threads/{thread_id}/resource-uploads/{upload_id}')
    async def status(thread_id: str, upload_id: str, request: Request):
        check(request)
        return await invoke(uploads.status, thread_id, upload_id)

    @app.put('/api/v1/threads/{thread_id}/resource-uploads/{upload_id}/parts/{index}')
    async def part(thread_id: str, upload_id: str, index: int, request: Request):
        check(request)
        state = await invoke(uploads.status, thread_id, upload_id)
        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > state['chunk_bytes']:
                error = CapacityExceeded('upload_chunk_bytes', len(data)+len(chunk), state['chunk_bytes'], 'resource.upload.part', mode=current_capacity().mode)
                if error.mode == 'debug':
                    raise error
                raise HTTPException(413, error.to_document())
            data.extend(chunk)
        return await invoke(uploads.part, thread_id, upload_id, index, bytes(data))

    @app.post('/api/v1/threads/{thread_id}/resource-uploads/{upload_id}/complete')
    async def complete(thread_id: str, upload_id: str, request: Request):
        check(request)
        return await invoke(uploads.complete, thread_id, upload_id)

    @app.delete('/api/v1/threads/{thread_id}/resource-uploads/{upload_id}')
    async def cancel(thread_id: str, upload_id: str, request: Request):
        check(request)
        await invoke(uploads.cancel, thread_id, upload_id)
        return await invoke(uploads.status, thread_id, upload_id)
