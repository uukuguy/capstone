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


def access(extra_tools=()):
    catalog = {'revision': 'a' * 64, 'tools': {'data_gateway_discover_data_capabilities': {}},
               'tool_hashes': {'data_gateway_discover_data_capabilities': 'b' * 64}}
    for tool in extra_tools:
        catalog['tools'][tool] = {}
        catalog['tool_hashes'][tool] = 'd' * 64
    resource = DataGatewayAccess(Client(), catalog)
    resource.bind('task-1', 'attempt-1', set(catalog['tools']))
    return resource


def test_task_grant_rejects_catalog_tool_outside_frozen_subset():
    resource = access(['data_gateway_other'])
    allowed = {request()['name']}
    resource.bind('restricted', 'attempt-2', allowed)
    allowed.add('data_gateway_other')
    calls = []
    async def upstream(name, arguments, catalog):
        calls.append((name, catalog))
        return await Client().call(name, arguments, catalog)
    resource.client.call = upstream
    with pytest.raises(GatewayError, match='gateway_tool_not_admitted'):
        asyncio.run(resource.call('restricted', dict(request(), name='data_gateway_other')))
    assert calls == []
    response = asyncio.run(resource.call('restricted', request()))
    assert calls == [(request()['name'], resource.catalog)]
    assert response['observation']['catalog_revision'] == resource.catalog['revision']


@pytest.mark.parametrize('allowed', [None, 'data_gateway_other', {'missing'}, {1}])
def test_task_binding_rejects_invalid_tool_grants(allowed):
    resource = access()
    with pytest.raises(GatewayError, match='gateway_tool_not_admitted'):
        resource.bind('restricted', 'attempt-2', allowed)


def test_empty_task_grant_does_not_inherit_catalog():
    resource = access()
    resource.bind('restricted', 'attempt-2', set())
    with pytest.raises(GatewayError, match='gateway_tool_not_admitted'):
        asyncio.run(resource.call('restricted', request()))


def request():
    return {'call_id': 'call-1', 'name': 'data_gateway_discover_data_capabilities', 'arguments': {}}


def test_only_admitted_successful_observations_reach_connection_bindings():
    resource = access()
    observed = []
    resource.view_bindings = SimpleNamespace(observe=lambda *args: observed.append(args))
    response = asyncio.run(resource.call('task-1', request()))
    assert len(observed) == 1
    name, arguments, result, catalog = observed[0]
    assert name == request()['name'] and arguments == {}
    assert result['structuredContent']['status'] == 'partial'
    assert catalog == resource.catalog
    assert response['observation']['tool'] == name
    with pytest.raises(GatewayError):
        asyncio.run(resource.call('task-1', dict(request(), call_id='bad', name='ungranted')))
    assert len(observed) == 1


def test_validated_failure_reaches_bindings_without_becoming_success():
    resource = access()
    observed = []
    resource.view_bindings = SimpleNamespace(observe=lambda *args: observed.append(args))
    async def upstream(name, arguments, catalog):
        return {'isError': False, 'structuredContent': {'status': 'error',
            'data': {'state': 'failed', 'error': {'reason': 'invalid_revision'}}}}
    resource.client.call = upstream
    response = asyncio.run(resource.call('task-1', request()))
    assert len(observed) == 1
    assert observed[0][2]['structuredContent']['data']['state'] == 'failed'
    assert response['observation']['tool'] == request()['name']


@pytest.mark.parametrize('failed_open', [False, True])
def test_preparation_jobs_require_an_issued_open_in_the_same_task(failed_open):
    resource = access(['data_gateway_open_network_model_view', 'data_gateway_get_network_model_job'])
    resource.catalog['tools']['data_gateway_get_network_model_job'] = {
        'inputSchema': {'type': 'object', 'properties': {'job_ref': {'type': 'string'}}, 'required': ['job_ref']}}
    calls = []
    async def upstream(name, arguments, catalog):
        calls.append(name)
        data = ({'schema': 'gateway-electrical-view/1', 'state': 'preparing',
                 'model_ref': 'grid:test', 'preparation_ref': 'prepare-one'}
                if name.endswith('open_network_model_view') else
                {'job_ref': arguments['job_ref'], 'task_type': 'view_preparation', 'state': 'running'})
        return {'isError': failed_open, 'structuredContent': {'status': 'error' if failed_open else 'ok', 'data': data}}
    resource.client.call = upstream
    def job(task, call, ref='prepare-one'):
        return asyncio.run(resource.call(task, {'call_id': call, 'name': 'data_gateway_get_network_model_job', 'arguments': {'job_ref': ref}}))
    with pytest.raises(GatewayError, match='gateway_tool_not_admitted'):
        job('task-1', 'before')
    assert calls == []
    asyncio.run(resource.call('task-1', {'call_id': 'open', 'name': 'data_gateway_open_network_model_view', 'arguments': {'model_ref': 'grid:test'}}))
    if failed_open:
        with pytest.raises(GatewayError, match='gateway_tool_not_admitted'): job('task-1', 'after')
    else:
        assert job('task-1', 'after')['is_error'] is False
    resource.bind('task-2', 'attempt-2', set(resource.catalog['tools']))
    with pytest.raises(GatewayError, match='gateway_tool_not_admitted'): job('task-2', 'foreign')
    with pytest.raises(GatewayError, match='gateway_tool_not_admitted'): job('task-1', 'build', 'build-job')
    if not failed_open:
        async def wrong_kind(*_):
            return {'structuredContent': {'status':'ok','data':{'job_ref':'other-job','task_type':'build','state':'succeeded'}}}
        resource.client.call = wrong_kind
        with pytest.raises(GatewayError, match='gateway_output_invalid'): job('task-1', 'wrong-kind')
        assert not resource.verify('task-1', 'wrong-kind', 'data_gateway_get_network_model_job', {}, '{}')


@pytest.mark.parametrize('producer,reader', [
    ('data_gateway_build_network_model', 'data_gateway_get_network_model_job'),
    ('data_gateway_start_export', 'data_gateway_export_status')])
@pytest.mark.parametrize('field', ['job_ref', 'preparation_ref'])
def test_generic_operation_refs_are_task_owned(producer, reader, field):
    resource = access([producer, reader])
    resource.catalog['tools'][reader] = {'inputSchema': {
        'type': 'object', 'properties': {'job_ref': {'type': 'string'}}, 'required': ['job_ref']}}
    calls = []
    async def upstream(name, arguments, catalog):
        calls.append(name)
        data = {field: 'operation-one'} if name == producer else {'job_ref': arguments['job_ref'], 'task_type': 'build'}
        return {'structuredContent': {'status': 'ok', 'data': data}}
    resource.client.call = upstream
    value = {'call_id': 'poll', 'name': reader, 'arguments': {'job_ref': 'operation-one'}}
    with pytest.raises(GatewayError, match='gateway_tool_not_admitted'):
        asyncio.run(resource.call('task-1', value))
    asyncio.run(resource.call('task-1', {'call_id': 'produce', 'name': producer, 'arguments': {}}))
    assert asyncio.run(resource.call('task-1', value))['is_error'] is False
    async def mismatch(*_):
        return {'structuredContent': {'status': 'ok', 'data': {'job_ref': 'foreign-operation'}}}
    resource.client.call = mismatch
    with pytest.raises(GatewayError, match='gateway_output_invalid'):
        asyncio.run(resource.call('task-1', {**value, 'call_id': 'wrong-reply'}))
    assert not resource.verify('task-1', 'wrong-reply', reader, {}, '{}')
    with pytest.raises(GatewayError, match='gateway_tool_not_admitted'):
        asyncio.run(resource.call('task-1', {**value, 'call_id': 'foreign-reply',
            'arguments': {'job_ref': 'foreign-operation'}}))
    async def stopped(*_):
        raise GatewayError('gateway_timeout')
    resource.client.call = stopped
    with pytest.raises(GatewayError, match='gateway_timeout'):
        asyncio.run(resource.call('task-1', {**value, 'call_id': 'timeout'}))
    with pytest.raises(GatewayError, match='gateway_timeout'):
        asyncio.run(resource.call('task-1', {**value, 'call_id': 'after-stop'}))
    resource.bind('foreign', 'attempt-other', {reader})
    with pytest.raises(GatewayError, match='gateway_tool_not_admitted'):
        asyncio.run(resource.call('foreign', value))
    resource.revoke('task-1')
    with pytest.raises(GatewayError, match='gateway_task_not_admitted'):
        asyncio.run(resource.call('task-1', {**value, 'call_id': 'after-revoke'}))
    assert calls == [producer, reader]


@pytest.mark.parametrize('data,status,is_error', [
    ({'rows': [{'job_ref': 'operation-one'}]}, 'ok', False),
    ({'job_ref': 'operation-one'}, 'error', False),
    ({'job_ref': 'operation-one'}, 'ok', True)])
def test_nested_or_failed_results_do_not_issue_operation_refs(data, status, is_error):
    resource = access(['data_gateway_start_export', 'data_gateway_export_status'])
    resource.catalog['tools']['data_gateway_export_status'] = {'inputSchema': {
        'properties': {'job_ref': {'type': 'string'}}}}
    async def upstream(*_):
        return {'isError': is_error, 'structuredContent': {'status': status, 'data': data}}
    resource.client.call = upstream
    asyncio.run(resource.call('task-1', {'call_id': 'produce', 'name': 'data_gateway_start_export', 'arguments': {}}))
    with pytest.raises(GatewayError, match='gateway_tool_not_admitted'):
        asyncio.run(resource.call('task-1', {'call_id': 'poll', 'name': 'data_gateway_export_status',
            'arguments': {'job_ref': 'operation-one'}}))


def test_undeclared_job_parameter_cannot_bypass_operation_ref_check():
    resource = access()
    with pytest.raises(GatewayError, match='gateway_tool_not_admitted'):
        asyncio.run(resource.call('task-1', {**request(), 'arguments': {'job_ref': 'foreign'}}))


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


def test_verified_arguments_are_host_owned_and_available_only_for_exact_receipt():
    resource=access()
    arguments={'scope_id':'north','level':'equipment','selected_object_id':'station:one','voltage_min_kv':None}
    result=asyncio.run(resource.call('task-1',{**request(),'arguments':arguments}))
    arguments['voltage_min_kv']=330
    saved=resource.verified_arguments('task-1','call-1',request()['name'],result['observation'],result['result_json'])
    assert saved['voltage_min_kv'] is None
    saved['level']='region'
    assert resource.verified_arguments('task-1','call-1',request()['name'],result['observation'],result['result_json'])['level']=='equipment'
    assert 'arguments' not in result and 'arguments' not in result['observation']
    with pytest.raises(GatewayError):
        resource.verified_arguments('task-1','call-1',request()['name'],result['observation'],'forged')
    resource.revoke('task-1')
    with pytest.raises(GatewayError):
        resource.verified_arguments('task-1','call-1',request()['name'],result['observation'],result['result_json'])


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


def test_transport_failure_stops_other_probes_only_for_the_failed_task():
    other = 'data_gateway_discover_business_services'
    resource = access([other])
    calls = []

    async def failed(name, *_):
        calls.append(name)
        raise GatewayError('gateway_timeout')

    resource.client.call = failed
    for value in [request(), dict(request(), call_id='call-2', name=other)]:
        with pytest.raises(GatewayError, match='gateway_timeout'):
            asyncio.run(resource.call('task-1', value))
    assert calls == [request()['name']]
    assert not resource.verify('task-1', 'call-2', other, {}, '{}')
    resource.bind('task-2', 'attempt-2', set(resource.catalog['tools']))
    resource.client = Client()
    assert asyncio.run(resource.call('task-2', request()))['is_error'] is False


def test_argument_failure_does_not_stop_a_corrected_call():
    resource = access()

    async def failed(*_):
        raise GatewayError('gateway_arguments_invalid')

    resource.client.call = failed
    with pytest.raises(GatewayError, match='gateway_arguments_invalid'):
        asyncio.run(resource.call('task-1', request()))
    resource.client = Client()
    assert asyncio.run(resource.call('task-1', dict(request(), call_id='call-2')))['is_error'] is False


def test_changed_tool_publication_does_not_stop_another_granted_tool():
    other = 'data_gateway_other'
    resource = access([other])
    calls = []
    async def upstream(name, arguments, catalog):
        calls.append(name)
        if name == request()['name']:
            raise GatewayError('gateway_publication_changed')
        return await Client().call(name, arguments, catalog)
    resource.client.call = upstream
    with pytest.raises(GatewayError, match='gateway_publication_changed'):
        asyncio.run(resource.call('task-1', request()))
    with pytest.raises(GatewayError, match='gateway_call_already_started'):
        asyncio.run(resource.call('task-1', request()))
    assert not resource.verify('task-1', 'call-1', request()['name'], {}, '{}')
    response = asyncio.run(resource.call('task-1', dict(request(), call_id='call-2', name=other)))
    assert response['is_error'] is False
    assert calls == [request()['name'], other]


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
    started, stopped, released = threading.Event(), threading.Event(), threading.Event()

    async def waiting(*_):
        started.set()
        try:
            await asyncio.sleep(20)
        finally:
            stopped.set()

    resource.client.call = waiting
    relay = ProviderRelay()
    release = relay.release
    def release_and_signal(lease):
        release(lease)
        released.set()
    relay.release = release_and_signal
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
        # The cancelled coroutine and socket finish before the handler's finally
        # block. Wait for actual lease release, not merely client disconnection.
        assert released.wait(2)
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


def test_unavailable_gateway_retains_only_configured_identity(tmp_path, monkeypatch):
    import os
    import json
    from capstone_agent.data_gateway_mcp import DataGatewayMcp, GatewayError
    from capstone_agent.data_gateway_relay import load_container_gateway
    root = tmp_path / 'private'
    root.mkdir(mode=0o700)
    directory = root / 'data-gateway'
    directory.mkdir()
    connection = directory / 'connection.json'
    connection.write_text(json.dumps({'name': 'Configured gateway', 'transport': 'streamable-http',
        'url': 'https://gateway.test/mcp', 'headers': {'Authorization': 'Bearer secret-canary'}}))
    connection.chmod(0o600)
    policy = tmp_path / 'policy.json'
    policy.write_text(json.dumps({'schema': 'capstone-data-gateway/2', 'resource_id': 'data-gateway',
        'namespace': 'data_gateway_', 'admission': 'trusted-service-safe-effects'}))
    async def unavailable(self):
        raise GatewayError('gateway_timeout')
    monkeypatch.setattr(DataGatewayMcp, 'prepare', unavailable)
    resource, publication = load_container_gateway(str(connection), policy, private_root=root, owner_uid=os.getuid())
    assert resource is None
    assert publication['identity'] == {'connection_name': 'Configured gateway', 'display_address': 'gateway.test:443'}
    assert publication['available'] is False
    assert 'secret-canary' not in json.dumps(publication)
