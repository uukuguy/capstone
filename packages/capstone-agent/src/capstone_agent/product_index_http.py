"""Authenticated, bounded routes for application paragraph indexes."""
import json

from fastapi import HTTPException, Query, Request
from starlette.concurrency import run_in_threadpool

from .application_capacity import limits
from .thread_service import ThreadNotFound
from .thread_protocol import ThreadProtocolError


def register_product_index_routes(app, *, service, authorize):
    async def invoke(method, *args, **kwargs):
        try:
            return await run_in_threadpool(method, *args, **kwargs)
        except (ThreadNotFound, KeyError):
            raise HTTPException(404, 'product_index_not_found') from None
        except (ValueError, TypeError, ThreadProtocolError):
            raise HTTPException(422, 'product_index_request_rejected') from None
        except OSError:
            raise HTTPException(503, 'product_index_storage_unavailable') from None

    @app.post('/api/v1/threads/{thread_id}/product-block-indexes', status_code=202)
    async def create(thread_id: str, request: Request):
        authorize(request)
        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > 16384:
                raise HTTPException(413, 'product_index_request_too_large')
            data.extend(chunk)

        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError('duplicate field')
                result[key] = value
            return result

        try:
            body = json.loads(data, object_pairs_hook=unique)
            if not isinstance(body, dict) or set(body) != {'ref'} or not isinstance(body['ref'], dict):
                raise ValueError('invalid request')
        except (ValueError, UnicodeError, RecursionError):
            raise HTTPException(422, 'product_index_request_invalid') from None
        return await invoke(service.request, thread_id, body['ref'])

    @app.get('/api/v1/threads/{thread_id}/product-block-indexes/{job_id}')
    async def status(thread_id: str, job_id: str, request: Request):
        authorize(request)
        return await invoke(service.status, thread_id, job_id)

    @app.get('/api/v1/threads/{thread_id}/product-block-indexes/{job_id}/blocks')
    async def blocks(thread_id: str, job_id: str, request: Request,
                     offset: int = Query(0, ge=0),
                     limit: int = Query(20, ge=1, le=limits.product_page_items)):
        authorize(request)
        return await invoke(service.blocks, thread_id, job_id, offset=offset, limit=limit)
