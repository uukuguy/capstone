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
    augmented = dict(result['observation'], native_research_source={'source_ref': 'host-wrapper'})
    assert resource.verify('task-1', 'call-1', request()['name'], augmented, result['result_json'])
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
    runner = SimpleNamespace(gateway=resource, relay=relay)
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=lambda *_: ('', {}))
    server = make_server(host, control_token='host-secret', address=('127.0.0.1', 0), runner=runner)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f'http://127.0.0.1:{server.server_port}/data-gateway/task-1'
    try:
        with httpx.Client(trust_env=False) as client:
            # Start task lifetime after host/server/client initialization. Cold
            # runner startup must not consume the authorization under test.
            relay.register('task-1', 'task-grant', time.monotonic() + 10)
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


def test_host_publishes_gateway_only_for_explicit_enterprise_admission(tmp_path):
    from capstone_agent.data_gateway_relay import research_gateway_tools
    from capstone_agent.native_task_context import CURRENT_RESEARCH_POLICY_TEXT, GENERAL_CHAT_POLICY_TEXT
    from capstone_agent.general_pi_server import GeneralPiHost
    class Runner:
        gateway = access()
        def __call__(self, *_):
            return '', {}
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=Runner())
    publication = host.capability['data_gateway']
    assert publication['available']
    native = {'policy': {'system_policy': CURRENT_RESEARCH_POLICY_TEXT}}
    assert research_gateway_tools(native, publication) == {'data_gateway_discover_data_capabilities'}
    native['policy']['system_policy'] = GENERAL_CHAT_POLICY_TEXT
    assert research_gateway_tools(native, publication) == set()
    assert research_gateway_tools(None, publication) == set()
    assert research_gateway_tools({'policy': {'system_policy': CURRENT_RESEARCH_POLICY_TEXT}}, {'available': False}) == set()


def test_actual_sdk_child_calls_protected_http_relay_and_has_host_receipt(tmp_path):
    import json
    from pathlib import Path
    import subprocess
    import threading
    import time
    from capstone_agent.general_pi_server import GeneralPiHost, make_server
    from capstone_agent.general_pi_relay import ProviderRelay
    resource = access()
    schema = {'name': 'discover_data_capabilities', 'inputSchema': {'type': 'object', 'properties': {}}}
    resource.catalog['tools']['data_gateway_discover_data_capabilities'] = schema
    relay = ProviderRelay()
    runner = SimpleNamespace(gateway=resource, relay=relay)
    host = GeneralPiHost(root=tmp_path / 'host', identity={'engine': 'pi'}, run_task=lambda *_: ('', {}))
    server = make_server(host, control_token='host-control', address=('127.0.0.1', 0), runner=runner)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    try:
        fixture = Path(__file__).parent / 'fixtures/data-gateway-child-sdk.mjs'
        relay.register('task-1', 'task-grant', time.monotonic() + 20)
        config = {'workspace': str(workspace), 'gateway': {'url': f'http://127.0.0.1:{server.server_port}/data-gateway/task-1',
            'grant': 'task-grant', 'taskId': 'task-1', 'catalog': resource.catalog}}
        process = subprocess.run(['node', str(fixture)], cwd=Path(__file__).resolve().parents[3],
            input=json.dumps(config), text=True, capture_output=True, timeout=20)
        assert process.returncode == 0, process.stderr
        value = json.loads(process.stdout)
        event = value['event']
        assert value['turns'] == 2
        assert resource.verify('task-1', event['tool_call_id'], event['tool_name'],
                               event['result']['details'], event['result']['content'][0]['text'])
        assert value['receipt']['ref'] == event['result']['details']['native_research_source']['source_ref']
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)


def test_revocation_cancels_inflight_gateway_and_issues_no_receipt(tmp_path):
    import concurrent.futures
    import threading
    import time
    import httpx
    from capstone_agent.general_pi_server import GeneralPiHost, make_server
    from capstone_agent.general_pi_relay import ProviderRelay
    resource = access()
    started, stopped = threading.Event(), threading.Event()

    async def waiting(*_):
        started.set()
        try:
            await asyncio.sleep(20)
        finally:
            stopped.set()

    resource.client.call = waiting
    relay = ProviderRelay()
    runner = SimpleNamespace(gateway=resource, relay=relay)
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=lambda *_: ('', {}))
    server = make_server(host, control_token='host-control', address=('127.0.0.1', 0), runner=runner)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            relay.register('task-1', 'task-grant', time.monotonic() + 5)
            future = pool.submit(httpx.post, f'http://127.0.0.1:{server.server_port}/data-gateway/task-1',
                json=request(), headers={'Authorization': 'Bearer task-grant'}, trust_env=False, timeout=3)
            assert started.wait(2)
            relay.revoke('task-1')
            assert stopped.wait(2)
            with pytest.raises(httpx.HTTPError):
                future.result(timeout=2)
        assert not resource.verify('task-1', 'call-1', request()['name'], {}, '{}')
        assert not relay.active
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)


def test_container_gateway_refuses_unprotected_mount_parent(tmp_path, monkeypatch):
    import os
    from pathlib import Path
    from capstone_agent import data_gateway_mcp
    from capstone_agent.data_gateway_relay import load_container_gateway
    root = tmp_path / 'private'
    root.mkdir(mode=0o700)
    selected = root / 'data-gateway/connection.json'
    calls = []
    class Prepared:
        def __init__(self, *_):
            calls.append('constructed')
        async def prepare(self):
            return access().catalog
    policy = tmp_path / 'policy.json'
    policy.write_text('{}')
    monkeypatch.setattr(data_gateway_mcp, 'DataGatewayMcp', Prepared)
    resource, publication = load_container_gateway(str(selected), policy, private_root=root, owner_uid=os.getuid())
    assert resource and publication['available']
    root.chmod(0o755)
    resource, publication = load_container_gateway(str(selected), policy, private_root=root, owner_uid=os.getuid())
    assert resource is None and publication['reason'] == 'gateway_private_mount_invalid'
    root.chmod(0o700)
    resource, publication = load_container_gateway(str(tmp_path / 'public/connection.json'), policy,
        private_root=root, owner_uid=os.getuid())
    assert resource is None and publication['reason'] == 'gateway_private_mount_invalid'
    assert len(calls) == 1
