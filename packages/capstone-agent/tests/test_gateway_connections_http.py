import asyncio
import threading

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import httpx
import pytest

from capstone_agent.pi_delegation import PiHTTPFailure

BASE = '/api/v1/workspace/gateways'
SECRET = 'private-token-do-not-return'


def snapshot():
    return {'schema': 'capstone-gateway-connections/1', 'revision': 1, 'selected_id': 'local',
            'checking': False, 'entries': [{'id': 'local', 'label': 'Local', 'url': 'http://localhost:18001/mcp',
                'status': 'connected', 'identity': {'available': True, 'display_address': 'localhost:18001',
                'server_name': 'Actual', 'headers': {'Authorization': SECRET}}, 'token': SECRET}], 'headers': SECRET}


def app_for(executor):
    from capstone_agent.gateway_connections_http import register_gateway_connection_routes
    app = FastAPI()
    def authorize(request):
        if request.headers.get('Authorization') != 'Bearer operator':
            raise HTTPException(403, 'not permitted')
    register_gateway_connection_routes(app, executor_provider=lambda: executor, authorize=authorize)
    return app


class Executor:
    def __init__(self):
        self.calls = []
        self.failure = None

    def gateway_connections(self):
        return snapshot()

    def control_gateway_connections(self, action, document):
        self.calls.append((action, document))
        if self.failure:
            raise self.failure
        if action == 'probe':
            return {'url': document['url'], 'identity': snapshot()['entries'][0]['identity'], 'token': SECRET}
        return snapshot()


@pytest.fixture
def client():
    executor = Executor()
    with TestClient(app_for(executor)) as client:
        client.headers['Authorization'] = 'Bearer operator'
        yield client, executor


def test_all_routes_authorized_and_project_only_public_metadata(client):
    client, executor = client
    assert SECRET not in client.get(BASE).text
    public = client.get(BASE).json()
    assert public['entries'][0]['identity'] == {'available': True, 'server_name': 'Actual', 'endpoint': 'localhost:18001'}
    for action, data in [('refresh', {}), ('select', {'id': 'local'}),
                         ('probe', {'url': 'http://localhost:18001/mcp', 'token': SECRET}),
                         ('add', {'url': 'http://localhost:18001/mcp', 'name': 'Local'})]:
        assert client.post(BASE + '/' + action, json=data).status_code == 200
        assert client.post(BASE + '/' + action, headers={'Authorization': ''}, json=data).status_code == 403
    assert client.get(BASE, headers={'Authorization': ''}).status_code == 403
    assert len(executor.calls) == 4


@pytest.mark.parametrize('action,data', [('refresh', {'token': SECRET}), ('select', {'id': 1}),
    ('select', {'id': 'x', 'url': 'http://x'}), ('probe', {'url': 'x', 'token': []}),
    ('add', {'url': 'x', 'name': 'x' * 257}), ('probe', {'url': 'x' * 2049}),
    ('probe', {'url': 'x', 'token': 'x' * 8193})])
def test_closed_bounded_input_without_echo_or_execution(client, action, data):
    client, executor = client
    response = client.post(BASE + '/' + action, json=data)
    assert response.status_code == 400
    assert SECRET not in response.text
    assert executor.calls == []


def test_oversized_or_invalid_json(client):
    client, executor = client
    for data in [b'{', b'[]', b'null', b' ' * 16385]:
        assert client.post(BASE + '/refresh', content=data).status_code == 400
    assert executor.calls == []


@pytest.mark.parametrize('code,status', [('gateway_connections_busy', 409),
    ('gateway_authentication_failed', 400), ('gateway_connection_input_invalid', 400),
    ('gateway_timeout', 503), ('secret-' + SECRET, 503)])
def test_safe_failure_keeps_previous_selection(client, code, status):
    client, executor = client
    executor.failure = PiHTTPFailure(409, code)
    response = client.post(BASE + '/select', json={'id': 'other'})
    assert response.status_code == status
    assert SECRET not in response.text
    assert client.get(BASE).json()['selected_id'] == 'local'
    executor.failure = RuntimeError(SECRET)
    assert client.post(BASE + '/refresh', json={}).status_code == 503
    assert SECRET not in client.post(BASE + '/refresh', json={}).text


def test_malformed_remote_payload_fails_closed(client, monkeypatch):
    client, executor = client
    value = snapshot()
    value['entries'][0]['url'] = 'http://user:' + SECRET + '@example/mcp'
    monkeypatch.setattr(executor, 'gateway_connections', lambda: value)
    response = client.get(BASE)
    assert response.status_code == 503
    assert SECRET not in response.text


def test_remote_error_metadata_is_sanitized(client, monkeypatch):
    client, executor = client
    value = snapshot()
    value['entries'][0].update(status='disconnected', error=SECRET)
    value['entries'][0]['identity']['display_address'] = 'user:' + SECRET + '@host:18001'
    monkeypatch.setattr(executor, 'gateway_connections', lambda: value)
    response = client.get(BASE)
    assert response.status_code == 200
    assert SECRET not in response.text
    assert response.json()['entries'][0]['error'] == 'gateway_connections_unavailable'
    assert 'endpoint' not in response.json()['entries'][0]['identity']


def test_slow_native_call_does_not_block_async_requests():
    gate, started = threading.Event(), threading.Event()
    executor = Executor()
    def control(action, document):
        started.set()
        assert gate.wait(2)
        return snapshot()
    executor.control_gateway_connections = control
    app = app_for(executor)
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test',
                                    headers={'Authorization': 'Bearer operator'}) as client:
            pending = asyncio.create_task(client.post(BASE + '/refresh', json={}))
            try:
                await asyncio.wait_for(asyncio.to_thread(started.wait), .5)
                response = await asyncio.wait_for(client.get(BASE), .5)
                assert response.status_code == 200
            finally:
                gate.set()
                assert (await pending).status_code == 200
    asyncio.run(scenario())
