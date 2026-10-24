"""Application-owned control; never exposed as an agent tool."""
import httpx
from fastapi import HTTPException, Request
from starlette.concurrency import run_in_threadpool


def register_network_policy_routes(app, *, executor_provider, authorize):
    def executor():
        value = executor_provider()
        if value is None or not callable(getattr(value, 'network_policy', None)):
            raise HTTPException(503, 'network policy unavailable')
        return value

    async def invoke(method, *args):
        try:
            state = await run_in_threadpool(method, *args)
            if (not isinstance(state, dict) or state.get('enforced') is not True
                    or type(state.get('external_access')) is not bool):
                raise ValueError('invalid enforcement state')
            return {'external_access': state['external_access'], 'enforced': True}
        except (httpx.HTTPError, ValueError, RuntimeError, OSError) as error:
            raise HTTPException(503, 'network policy unavailable') from error

    @app.get('/api/v1/network-policy')
    async def read(request: Request):
        authorize(request)
        return await invoke(executor().network_policy)

    @app.post('/api/v1/network-policy')
    async def update(request: Request):
        authorize(request)
        body = bytearray()
        async for part in request.stream():
            body.extend(part)
            if len(body) > 128:
                raise HTTPException(400, 'invalid network policy')
        try:
            import json
            document = json.loads(body)
        except ValueError as error:
            raise HTTPException(400, 'invalid network policy') from error
        if (not isinstance(document, dict) or set(document) != {'external_access'}
                or type(document['external_access']) is not bool):
            raise HTTPException(400, 'invalid network policy')
        return await invoke(executor().set_network_policy, document['external_access'])
