from types import SimpleNamespace

from fastapi.testclient import TestClient

from capstone_agent.host_api import create_host_app
from capstone_agent.session import WorkerRegistry
from test_thread_http_api import _Ledger, _service, _auth


def app(executor=None):
    service = _service()
    result = create_host_app(_Ledger(), WorkerRegistry(()), operator_token='hosted-secret',
        allowed_hosts={'localhost'}, allowed_origins={'http://localhost:5173'},
        thread_service=service, native_artifact_executor=executor)
    return result, service


def test_global_connection_identity_does_not_read_a_thread_or_expose_credentials(monkeypatch):
    executor = SimpleNamespace(capability={'data_gateway': {'available': True, 'headers': 'secret-canary',
        'identity': {'instance_id': 'instance-one', 'instance_name': 'Test instance',
            'display_address': 'gateway.test:18001', 'offline': False, 'token': 'secret-canary'}}})
    application, service = app(executor)
    with TestClient(application, base_url='http://localhost') as client:
        monkeypatch.setattr(service, 'snapshot', lambda *_: (_ for _ in ()).throw(AssertionError('Thread read')))
        response = client.get('/api/v1/workspace/connections',
            headers={**_auth(), 'Capstone-Thread-Version': '2'})
        assert response.status_code == 200
        assert response.headers['Capstone-Thread-Version'] == '2'
        assert response.headers['Cache-Control'] == 'no-store'
        assert response.json() == {'schema': 'capstone-workspace-connections/1', 'data_gateway': {
            'available': True, 'instance_id': 'instance-one', 'instance_name': 'Test instance',
            'endpoint': 'gateway.test:18001', 'offline': False}}
        assert 'secret-canary' not in response.text
        assert client.get('/api/v1/workspace/connections').status_code == 401
        assert client.get('/api/v1/workspace/connections',
            headers={**_auth(), 'Capstone-Thread-Version': '99'}).status_code == 406


def test_missing_gateway_registration_stays_unknown_in_global_metadata():
    application, _ = app()
    with TestClient(application, base_url='http://localhost') as client:
        response = client.get('/api/v1/workspace/connections', headers=_auth())
        assert response.status_code == 200
        assert response.json() == {'schema': 'capstone-workspace-connections/1'}
