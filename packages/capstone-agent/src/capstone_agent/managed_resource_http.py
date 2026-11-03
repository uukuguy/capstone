"""Workspace-scoped resource management over the application-owned executor."""
import logging
import re
from fastapi import HTTPException, Request
from starlette.concurrency import run_in_threadpool
from .application_capacity import limits
from .native_failure_origin import native_failure_origin
from .resource_permissions import ResourcePermissionDenied
from .managed_resources import ResourceConflict, ResourceStateError
from .managed_resource_mcp import ManagedMcpError


def register_managed_resource_routes(app, *, executor_provider, authorize):
    async def invoke(request, operation, document):
        authorize(request)
        executor = executor_provider()
        method = getattr(executor, 'managed_resources', None)
        if not callable(method):
            raise HTTPException(503, detail={'code': 'resource_management_unavailable'})
        try:
            return await run_in_threadpool(method, request.state.workspace_name, operation, document)
        except ManagedMcpError as error:
            raise HTTPException(422,detail={'code':error.code,'stage':error.stage,'executed':error.executed}) from error
        except ResourcePermissionDenied as error:
            raise HTTPException(403, detail={'code': error.code}) from error
        except ResourceConflict as error:
            raise HTTPException(409, detail={'code': str(error)}) from error
        except KeyError as error:
            raise HTTPException(404, detail={'code': 'resource_not_found'}) from error
        except (ValueError, ResourceStateError) as error:
            # Do not return arbitrary adapter messages, URLs or credentials.
            logging.getLogger(__name__).warning('Resource management rejected; origin=%s', native_failure_origin(error))
            code = str(error) if re.fullmatch(r'(?:resource|invalid_resource|preinstall)_[a-z_]{1,80}', str(error)) else 'resource_request_rejected'
            raise HTTPException(422, detail={'code': code}) from error

    async def body(request):
        authorize(request)
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > limits.control_document_bytes:
                raise HTTPException(413, detail={'code': 'resource_request_too_large'})
        import json
        try:
            value = json.loads(raw)
        except ValueError as error:
            raise HTTPException(422, detail={'code': 'resource_request_invalid'}) from error
        if not isinstance(value, dict):
            raise HTTPException(422, detail={'code': 'resource_request_invalid'})
        return value

    @app.get('/api/v1/managed-resources')
    async def listing(request: Request):
        return await invoke(request, 'list', {})

    @app.post('/api/v1/managed-resources/operations/{operation}')
    async def mutate(operation: str, request: Request):
        if operation not in {'install', 'state', 'uninstall', 'preinstall_draft', 'preinstall_export', 'preinstall_publish', 'preinstall_import'}:
            raise HTTPException(404, detail={'code': 'resource_operation_unknown'})
        return await invoke(request, operation, await body(request))

    @app.get('/api/v1/managed-resources/operations/{request_id}')
    async def status(request_id: str, request: Request):
        return await invoke(request, 'operation', {'request_id': request_id})
