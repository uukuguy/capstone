"""Authenticated App routes for source displays; never agent calculation tools."""
import json

import httpx
from fastapi import HTTPException, Request
from starlette.concurrency import run_in_threadpool

from .grid_source_topology import GridSourceError, REQUEST_BYTES, PAGE_BYTES, checked_topology_request
from .pi_delegation import PiHTTPFailure


def register_grid_source_routes(app, *, executor_provider, authorize):
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
