"""Private application endpoints for comparison and explicit version adoption."""
import json

from fastapi import HTTPException, Query, Request
from starlette.concurrency import run_in_threadpool

from .thread_service import ThreadNotFound


def register_product_series_routes(app, *, service, authorize, actor_provider):
    async def body(request):
        data = bytearray()
        async for chunk in request.stream():
            if len(data)+len(chunk) > 16384:
                raise HTTPException(413, 'product_series_request_too_large')
            data.extend(chunk)
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError('duplicate field')
                result[key] = value
            return result
        try:
            value = json.loads(data, object_pairs_hook=unique)
            if not isinstance(value, dict):
                raise ValueError('object required')
            return value
        except (ValueError, UnicodeError, RecursionError):
            raise HTTPException(422, 'product_series_request_invalid') from None

    async def invoke(method, *args, **kwargs):
        try:
            return await run_in_threadpool(method, *args, **kwargs)
        except (ThreadNotFound, KeyError):
            raise HTTPException(404, 'product_series_not_found') from None
        except ValueError as error:
            if str(error) in {'series revision conflict', 'idempotency conflict', 'command identity conflict'}:
                raise HTTPException(409, 'product_series_conflict') from None
            raise HTTPException(422, 'product_series_request_rejected') from None
        except OSError:
            raise HTTPException(503, 'product_series_storage_unavailable') from None

    @app.post('/api/v1/threads/{thread_id}/product-series/commands')
    async def command(thread_id: str, request: Request):
        authorize(request)
        actor = actor_provider(request)
        return await invoke(service.command, thread_id, await body(request), actor=actor)

    @app.get('/api/v1/threads/{thread_id}/product-series/{series_id}')
    async def read(thread_id: str, series_id: str, request: Request):
        authorize(request)
        return await invoke(service.read, thread_id, series_id)

    @app.get('/api/v1/threads/{thread_id}/product-series')
    async def listing(thread_id: str, request: Request, limit: int = Query(20, ge=1, le=100), before: str | None = None):
        authorize(request)
        return await invoke(service.list, thread_id, limit=limit, before=before)

    @app.post('/api/v1/threads/{thread_id}/product-series/discover')
    async def discover(thread_id: str, request: Request):
        authorize(request)
        value = await body(request)
        if set(value) != {'product'}: raise HTTPException(422, 'product_series_request_invalid')
        return await invoke(service.discover, thread_id, value['product'])

    @app.post('/api/v1/threads/{thread_id}/product-series/sources')
    async def sources(thread_id: str, request: Request):
        authorize(request)
        value = await body(request)
        if set(value) != {'product'}: raise HTTPException(422, 'product_series_request_invalid')
        return await invoke(service.sources, thread_id, value['product'])

    @app.get('/api/v1/threads/{thread_id}/product-series/{series_id}/members')
    async def members(thread_id: str, series_id: str, request: Request, limit: int = Query(20, ge=1, le=100), after: str | None = None):
        authorize(request)
        return await invoke(service.members, thread_id, series_id, limit=limit, after=after)

    @app.get('/api/v1/threads/{thread_id}/product-series/{series_id}/history')
    async def history(thread_id: str, series_id: str, request: Request,
                      limit: int = Query(20, ge=1, le=100), before: int | None = Query(None, ge=1)):
        authorize(request)
        return await invoke(service.history, thread_id, series_id, limit=limit, before=before)

    @app.post('/api/v1/threads/{thread_id}/product-comparisons')
    async def compare(thread_id: str, request: Request):
        authorize(request)
        value = await body(request)
        if set(value) != {'original_ref', 'revised_ref'}:
            raise HTTPException(422, 'product_comparison_request_invalid')
        return await invoke(service.compare, thread_id, value['original_ref'], value['revised_ref'])
