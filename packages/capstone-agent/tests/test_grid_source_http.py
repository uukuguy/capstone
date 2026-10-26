import threading
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import httpx

from test_grid_source_topology import Gateway


def test_protected_host_executor_and_public_api_share_fixed_source_contract(tmp_path):
    from capstone_agent.general_pi_server import GeneralPiHost, make_server
    from capstone_agent.grid_source_http import register_grid_source_routes
    from capstone_agent.pi_delegation import HttpGeneralPiExecutor
    gateway = Gateway()
    identity = {'engine': 'pi', 'config_revision': 'test'}
    host = GeneralPiHost(root=tmp_path, identity=identity, run_task=lambda *_: ('Answer', {}))
    server = make_server(host, control_token='host-secret', address=('127.0.0.1', 0),
                         runner=SimpleNamespace(gateway=gateway))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    executor = HttpGeneralPiExecutor(origin, identity=identity, capability={}, control_token='host-secret')
    app = FastAPI()
    def authorize(request):
        if request.headers.get('Authorization') != 'Bearer operator':
            raise HTTPException(403, 'not permitted')
    register_grid_source_routes(app, executor_provider=lambda: executor, authorize=authorize)
    client = TestClient(app)
    headers = {'Authorization': 'Bearer operator'}
    path = '/api/v1/grid-sources/data-gateway'
    try:
        assert httpx.get(origin + '/grid-sources', trust_env=False).status_code == 401
        assert httpx.post(origin + '/grid-sources/data-gateway/topology', json={'scope_id': 'north'}, trust_env=False).status_code == 401
        assert client.get('/api/v1/grid-sources').status_code == 403
        assert client.get('/api/v1/grid-sources', headers=headers).json()['sources'][0]['available'] is True
        assert client.post(path + '/topology', headers=headers, json={'scope_id': 'north', 'limit': 3}).json()['total_edges'] == 1003
        assert len(gateway.calls) == 1
        assert client.post(path + '/topology', headers=headers, json={'scope_id': 'north', 'tool': 'build_network_model'}).status_code == 400
        assert client.post(path + '/topology', headers=headers, json={'scope_id': 'north', 'node_offset': 10}).status_code == 400
        assert client.post(path + '/topology', headers=headers, content='x' * 17000).status_code == 400
        assert len(gateway.calls) == 1
        changed = client.post(path + '/topology', headers=headers,
                             json={'scope_id': 'north', 'expected_view_ref': 'old-view'})
        assert changed.status_code == 409
        assert changed.json()['detail'] == 'grid_source_view_changed'
        assert client.post('/api/v1/grid-sources/other/topology', headers=headers, json={}).status_code == 404
        scope = gateway.data['scope']
        gateway.data = {'scopes': [scope]}
        assert client.get(path + '/scopes', headers=headers).json()['scopes'] == [scope]
        gateway.data = scope
        assert client.post(path + '/resolve-scope', headers=headers, json={'scope': 'North'}).json()['scope'] == scope
        assert [call[0] for call in gateway.calls][-2:] == [
            'data_gateway_discover_region_scopes', 'data_gateway_resolve_region_scope']
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_unconfigured_provider_is_explicitly_unavailable(tmp_path):
    from capstone_agent.general_pi_server import GeneralPiHost, make_server
    from capstone_agent.pi_delegation import HttpGeneralPiExecutor
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=lambda *_: ('Answer', {}))
    server = make_server(host, control_token='host-secret', address=('127.0.0.1', 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        executor = HttpGeneralPiExecutor(f'http://127.0.0.1:{server.server_port}',
            identity=host.identity, capability={}, control_token='host-secret')
        assert executor.grid_source_catalog()['sources'][0]['available'] is False
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_real_application_registration_preserves_operator_and_demo_access_boundaries():
    from capstone_agent.host_api import create_host_app
    from capstone_agent.session import WorkerRegistry
    from test_thread_http_api import _Ledger, _service
    class Executor:
        def grid_source_catalog(self):
            return {'schema': 'capstone-grid-source-catalog/1', 'sources': []}
    app = create_host_app(_Ledger(), WorkerRegistry(()), operator_token='hosted-secret',
        allowed_hosts={'localhost'}, allowed_origins={'http://localhost:5173'},
        thread_service=_service(), native_artifact_executor=Executor(), public_demo=True)
    with TestClient(app, base_url='http://localhost') as client:
        path = '/api/v1/grid-sources'
        assert client.get(path).status_code == 401
        assert client.get(path, headers={'Authorization': 'Bearer hosted-secret'}).status_code == 200
        credential = client.get('/api/v1/demo-credential').json()
        assert client.get(path, headers={'Authorization': 'Bearer ' + credential['token']}).status_code == 404


def test_frozen_electrical_api_crosses_both_auth_boundaries_and_preserves_typed_errors(tmp_path):
    from capstone_agent.general_pi_server import GeneralPiHost, make_server
    from capstone_agent.grid_source_http import register_grid_source_routes
    from capstone_agent.pi_delegation import HttpGeneralPiExecutor
    from test_grid_electrical_view import Gateway as ElectricalGateway, page
    gateway = ElectricalGateway()
    identity = {'engine': 'pi', 'config_revision': 'test'}
    host = GeneralPiHost(root=tmp_path, identity=identity, run_task=lambda *_: ('Answer', {}))
    server = make_server(host, control_token='protected', address=('127.0.0.1', 0), runner=SimpleNamespace(gateway=gateway))
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    executor = HttpGeneralPiExecutor(origin, identity=identity, capability={}, control_token='protected')
    app = FastAPI()
    def authorize(request):
        if request.headers.get('Authorization') != 'Bearer operator':
            raise HTTPException(403, 'not permitted')
    register_grid_source_routes(app, executor_provider=lambda: executor, authorize=authorize)
    client = TestClient(app); headers = {'Authorization': 'Bearer operator'}
    path = '/api/v1/grid-sources/data-gateway/electrical'
    try:
        assert client.post(path + '/open', json={'model_ref': 'model:one'}).status_code == 403
        assert httpx.post(origin + '/grid-sources/data-gateway/electrical/open', json={'model_ref': 'model:one'}, trust_env=False).status_code == 401
        opened = client.post(path + '/open', headers=headers, json={'model_ref': 'model:one'})
        assert opened.status_code == 200 and opened.json()['view_ref'] == 'view-one'
        gateway.data = page()
        response = client.post(path + '/read', headers=headers, json={'view_ref': 'view-one', 'stream': 'devices'})
        assert response.status_code == 200 and response.json()['records'][0]['switch_position']['value'] == 'unknown'
        assert 'Authorization' not in response.text
        gateway.data = {'count': 1, 'listing_complete': True, 'scopes': [{'scope_id': 'arbitrary',
            'model_ref': 'registered:actual', 'name': 'Arbitrary model', 'model_revision': None}],
            'electrical_views': {'schema': 'gateway-electrical-view/1', 'targets': ['model', 'station', 'device']}}
        catalog = client.get(path + '/models', headers=headers)
        assert catalog.status_code == 200 and catalog.json()['scopes'][0]['model_ref'] == 'registered:actual'
        gateway.data = {'schema': 'gateway-electrical-view/1', 'state': 'preparing', 'model_ref': 'model:one',
                        'preparation_ref': 'prepare-one'}
        assert client.post(path + '/open', headers=headers, json={'model_ref': 'model:one'}).json()['state'] == 'preparing'
        gateway.data = {'job_ref': 'prepare-one', 'task_type': 'view_preparation', 'model_ref': 'model:one',
                        'state': 'running', 'stage': 'indexing_structure', 'owner_pid': 1}
        job = client.post(path + '/job', headers=headers, json={'job_ref': 'prepare-one'})
        assert job.status_code == 200 and job.json()['task_type'] == 'view_preparation' and 'owner_pid' not in job.text
        count = len(gateway.calls)
        assert client.post(path + '/read', headers=headers, json={'view_ref': 'view-one', 'stream': 'devices', 'limit': 1001}).status_code == 400
        invalid = client.post(path + '/open', headers=headers, content='x' * 17000)
        assert invalid.status_code == 400 and invalid.json()['detail']['code'] == 'grid_electrical_request_invalid'
        assert len(gateway.calls) == count
        gateway.error = {'status': 'error', 'gaps': [{'reason': 'view_expired', 'message': 'private-secret'}]}
        response = client.post(path + '/read', headers=headers, json={'view_ref': 'expired', 'stream': 'groups'})
        assert response.status_code == 410
        assert response.json()['detail'] == {'code': 'view_expired', 'retryable': False, 'recovery_action': 'reopen_view'}
        assert 'private-secret' not in response.text
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)
