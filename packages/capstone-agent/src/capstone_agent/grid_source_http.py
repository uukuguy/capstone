"""Authenticated App routes for source displays; never agent calculation tools."""
import json

import httpx
from fastapi import HTTPException, Request
from starlette.concurrency import run_in_threadpool

from .grid_source_topology import GridSourceError, REQUEST_BYTES, PAGE_BYTES, checked_topology_request
from .pi_delegation import PiHTTPFailure
from .grid_electrical_view import ElectricalViewError, checked_electrical_request


def register_grid_source_routes(app, *, executor_provider, authorize):
    async def electrical_invoke(operation, document=None):
        if operation != 'models':
            try:
                document = checked_electrical_request(operation, document)
            except ElectricalViewError as error:
                raise HTTPException(error.status, error.detail()) from None
        method = getattr(executor_provider(), 'grid_electrical_' + operation, None)
        if not callable(method):
            error = ElectricalViewError('grid_electrical_unavailable')
            raise HTTPException(error.status, error.detail())
        try:
            result = await run_in_threadpool(method, *([] if document is None else [document]))
            if not isinstance(result, dict) or len(json.dumps(result, allow_nan=False).encode()) > PAGE_BYTES:
                raise ValueError()
            return result
        except PiHTTPFailure as cause:
            error = ElectricalViewError(cause.diagnostic['protocol_code'])
            raise HTTPException(error.status, error.detail()) from None
        except ElectricalViewError as error:
            raise HTTPException(error.status, error.detail()) from None
        except (httpx.HTTPError, ValueError, RuntimeError, OSError, TimeoutError):
            error = ElectricalViewError('grid_electrical_observation_unavailable')
            raise HTTPException(error.status, error.detail()) from None

    async def invoke(name, *arguments):
        executor = executor_provider()
        method = getattr(executor, name, None)
        if not callable(method):
            raise HTTPException(503, 'grid_source_unavailable')
        try:
            result = await run_in_threadpool(method, *arguments)
            if not isinstance(result, dict) or len(json.dumps(result, allow_nan=False).encode()) > PAGE_BYTES:
                raise ValueError()
            return result
        except PiHTTPFailure as error:
            code = error.diagnostic['protocol_code']
            status = 409 if code == 'grid_source_view_changed' else 400 if code == 'grid_source_request_invalid' else 503
            raise HTTPException(status, code if code.startswith('grid_source_') else 'grid_source_unavailable') from None
        except (httpx.HTTPError, ValueError, RuntimeError, OSError, TimeoutError):
            raise HTTPException(503, 'grid_source_unavailable') from None

    async def body(request):
        data = bytearray()
        async for part in request.stream():
            data.extend(part)
            if len(data) > REQUEST_BYTES:
                raise HTTPException(400, 'grid_source_request_invalid')
        try:
            value = json.loads(data)
            if not isinstance(value, dict):
                raise ValueError()
            return value
        except (ValueError, UnicodeDecodeError):
            raise HTTPException(400, 'grid_source_request_invalid') from None

    async def electrical_body(request):
        try:
            return await body(request)
        except HTTPException:
            error = ElectricalViewError('grid_electrical_request_invalid')
            raise HTTPException(error.status, error.detail()) from None

    @app.get('/api/v1/grid-sources')
    async def catalog(request: Request):
        authorize(request)
        return await invoke('grid_source_catalog')

    @app.get('/api/v1/grid-sources/data-gateway/scopes')
    async def scopes(request: Request):
        authorize(request)
        return await invoke('grid_source_scopes')

    @app.post('/api/v1/grid-sources/data-gateway/resolve-scope')
    async def resolve(request: Request):
        authorize(request)
        return await invoke('grid_source_resolve_scope', await body(request))

    @app.post('/api/v1/grid-sources/data-gateway/topology')
    async def topology(request: Request):
        authorize(request)
        try:
            document = checked_topology_request(await body(request))
        except GridSourceError:
            raise HTTPException(400, 'grid_source_request_invalid') from None
        return await invoke('grid_source_topology', document)

    @app.get('/api/v1/grid-sources/data-gateway/electrical/models')
    async def electrical_models(request: Request):
        authorize(request)
        return await electrical_invoke('models')

    @app.post('/api/v1/grid-sources/data-gateway/electrical/open')
    async def electrical_open(request: Request):
        authorize(request)
        return await electrical_invoke('open', await electrical_body(request))

    @app.post('/api/v1/grid-sources/data-gateway/electrical/read')
    async def electrical_read(request: Request):
        authorize(request)
        return await electrical_invoke('read', await electrical_body(request))

    @app.post('/api/v1/grid-sources/data-gateway/electrical/job')
    async def electrical_job(request: Request):
        authorize(request)
        return await electrical_invoke('job', await electrical_body(request))
