"""Private application routes; models never receive storage keys or credentials."""
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from .presentation_templates import PresentationTemplates
from .thread_service import ThreadNotFound
from .workspace_scope import WORKSPACE_HEADER, workspace_header


def register_presentation_template_routes(app, *, service, objects, authorize, library=None):
    library = library or PresentationTemplates(service, objects,
        builtin=Path(__file__).resolve().parents[4] / 'tools/presentation-templates/state-grid.pptx')

    def context(request):
        authorize(request)
        if objects is None:
            raise HTTPException(503, 'template_storage_unavailable')
        return workspace_header(request.headers.get(WORKSPACE_HEADER))

    async def invoke(method, *args, **kwargs):
        try:
            return await run_in_threadpool(method, *args, **kwargs)
        except ThreadNotFound:
            raise HTTPException(404, 'thread not found') from None
        except ValueError as error:
            # Public codes are fixed by the application, never arbitrary storage errors.
            reason = str(error)
            safe = reason if reason in {
                'template_request_invalid', 'template_request_conflict', 'template_revision_conflict',
                'template_source_changed', 'template_identity_changed', 'template_not_found',
                'template_processing_limit', 'template_cursor_invalid', 'invalid_template',
                'builtin_template_is_already_published',
            } else 'template_request_rejected'
            status = 409 if safe.endswith('_conflict') else 404 if safe == 'template_not_found' else 422
            raise HTTPException(status, safe) from None

    @app.get('/api/v1/threads/{thread_id}/presentation-templates')
    async def catalog(thread_id: str, request: Request, limit: int = 20, after: str | None = None):
        workspace = context(request)
        result = await invoke(library.catalog, thread_id, workspace, limit=limit, after=after)
        return {**result, 'selection': await invoke(library.selection, thread_id, workspace)}

    @app.get('/api/v1/threads/{thread_id}/presentation-templates/operations/{request_id}')
    async def operation(thread_id: str, request_id: str, request: Request):
        workspace = context(request)
        await invoke(library._scope, thread_id, workspace)
        records = await invoke(library._events, thread_id, request_id=request_id)
        if not records:
            raise HTTPException(404, 'template_operation_not_found')
        return {'ok': True, 'result': records[0]['result']}

    @app.post('/api/v1/threads/{thread_id}/presentation-templates/commands')
    async def command(thread_id: str, request: Request):
        workspace = context(request)
        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > 16384:
                raise HTTPException(413, 'template_request_too_large')
            data.extend(chunk)
        import json
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError('duplicate template request field')
                result[key] = value
            return result
        try:
            body = json.loads(data, object_pairs_hook=unique)
        except (ValueError, UnicodeError):
            raise HTTPException(422, 'template_request_invalid') from None
        if not isinstance(body, dict):
            raise HTTPException(422, 'template_request_invalid')
        operation = body.get('operation')
        fields = {'add': {'operation', 'request_id', 'resource', 'name'},
                  'select': {'operation', 'request_id', 'reference', 'expected_revision'},
                  'publish': {'operation', 'request_id', 'reference'},
                  'freeze': {'operation', 'reference'}}
        if not isinstance(operation, str) or operation not in fields or set(body) != fields[operation]:
            raise HTTPException(422, 'template_request_invalid')
        if operation == 'add':
            result = await invoke(library.add, thread_id, workspace, body['resource'],
                                  name=body['name'], request_id=body['request_id'])
        elif operation == 'select':
            result = await invoke(library.select, thread_id, workspace, body['reference'],
                                  expected_revision=body['expected_revision'], request_id=body['request_id'])
        elif operation == 'publish':
            result = await invoke(library.publish, thread_id, workspace, body['reference'], request_id=body['request_id'])
        else:
            result = await invoke(library.freeze, thread_id, workspace, override=body['reference'])
        return {'ok': True, 'result': result}

    @app.get('/api/v1/threads/{thread_id}/presentation-templates/{template_id}/versions/{version}/content')
    async def content(thread_id: str, template_id: str, version: str, request: Request):
        workspace = context(request)
        reference = {'template_id': template_id, 'version': version, 'sha256': version.removeprefix('sha256:')}
        template = await invoke(library.freeze, thread_id, workspace, override=reference)
        return StreamingResponse(library.read(thread_id, workspace, reference),
            media_type='application/vnd.openxmlformats-officedocument.presentationml.presentation',
            headers={'ETag': '"' + template['sha256'] + '"', 'Content-Length': str(template['size_bytes'])})
