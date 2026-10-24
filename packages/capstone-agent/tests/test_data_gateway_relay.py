import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest

from capstone_agent.data_gateway_mcp import GatewayError
from capstone_agent.data_gateway_relay import DataGatewayAccess


class Client:
    async def call(self, name, arguments, catalog):
        return {'isError': False, 'content': [{'type': 'text', 'text': 'source-data'}],
                'structuredContent': {'status': 'partial', 'gaps': ['missing'], 'provenance': {'id': 'actual'}}}


def access():
    catalog = {'revision': 'a' * 64, 'tools': {'data_gateway_discover_data_capabilities': {}},
               'tool_hashes': {'data_gateway_discover_data_capabilities': 'b' * 64}}
    resource = DataGatewayAccess(Client(), catalog)
    resource.bind('task-1', 'attempt-1')
    return resource


def request():
    return {'call_id': 'call-1', 'name': 'data_gateway_discover_data_capabilities', 'arguments': {}}


def test_issued_receipt_binds_exact_task_call_and_result():
    resource = access()
    result = asyncio.run(resource.call('task-1', request()))
    assert result['observation']['parent_attempt_id'] == 'attempt-1'
    assert resource.verify('task-1', 'call-1', request()['name'], result['observation'], result['result_json'])
    assert not resource.verify('task-2', 'call-1', request()['name'], result['observation'], result['result_json'])
    assert not resource.verify('task-1', 'call-other', request()['name'], result['observation'], result['result_json'])
    assert not resource.verify('task-1', 'call-1', request()['name'], result['observation'], '{}')


def test_unknown_task_duplicate_call_and_model_tool_are_refused():
    resource = access()
    for task, value in [('other-task', request()), ('task-1', dict(request(), name='data_gateway_build_network_model')),
                        ('task-1', dict(request(), url='http://untrusted'))]:
        with pytest.raises(GatewayError):
            asyncio.run(resource.call(task, value))
    asyncio.run(resource.call('task-1', request()))
    with pytest.raises(GatewayError, match='gateway_call_already_started'):
        asyncio.run(resource.call('task-1', request()))
    resource.revoke('task-1')
    with pytest.raises(GatewayError):
        asyncio.run(resource.call('task-1', request()))


def test_failed_call_is_not_replayed_or_issued_as_source():
    resource = access()

    async def failed(*_):
        raise GatewayError('gateway_call_failed_no_retry')

    resource.client.call = failed
    with pytest.raises(GatewayError):
        asyncio.run(resource.call('task-1', request()))
    with pytest.raises(GatewayError, match='gateway_call_already_started'):
        asyncio.run(resource.call('task-1', request()))
    assert not resource.verify('task-1', 'call-1', request()['name'], {}, '{}')


def test_http_route_requires_task_grant_and_revocation(tmp_path):
    import threading
    import time
    import httpx
    from capstone_agent.general_pi_server import GeneralPiHost, make_server
    from capstone_agent.general_pi_relay import ProviderRelay
    resource = access()
    relay = ProviderRelay()
    relay.register('task-1', 'task-grant', time.monotonic() + 10)
    runner = SimpleNamespace(gateway=resource, relay=relay)
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=lambda *_: ('', {}))
    server = make_server(host, control_token='host-secret', address=('127.0.0.1', 0), runner=runner)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f'http://127.0.0.1:{server.server_port}/data-gateway/task-1'
    try:
        with httpx.Client(trust_env=False) as client:
            assert client.post(url, json=request()).status_code == 401
            assert client.post(url, json=request(), headers={'Authorization': 'Bearer host-secret'}).status_code == 401
            response = client.post(url, json=request(), headers={'Authorization': 'Bearer task-grant'})
            assert response.status_code == 200
            assert response.json()['observation']['tool_call_id'] == 'call-1'
            relay.revoke('task-1')
            assert client.post(url, json=dict(request(), call_id='call-2'),
                               headers={'Authorization': 'Bearer task-grant'}).status_code == 401
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)
