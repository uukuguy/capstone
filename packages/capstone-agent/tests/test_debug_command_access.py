from fastapi.testclient import TestClient
from capstone_agent.host_api import create_host_app
from test_harness import _thread_service
from test_thread_http_api import _Ledger, WorkerRegistry


def test_open_development_access_and_release_block(monkeypatch):
    monkeypatch.setenv('CAPSTONE_DEPLOYMENT_STAGE', 'local')
    monkeypatch.delenv('CAPSTONE_DEBUG_COMMANDS', raising=False)
    service = _thread_service()
    app = create_host_app(_Ledger(), WorkerRegistry(()), operator_token='hosted-secret',
                          allowed_hosts={'localhost'}, allowed_origins={'http://localhost:5173'},
                          thread_open_access=True, thread_service=service)
    path = '/api/v1/threads/thr_harness'
    with TestClient(app, base_url='http://localhost') as client:
        assert client.get(path + '/debug/status').json()['enabled'] is True
        monkeypatch.setenv('CAPSTONE_DEPLOYMENT_STAGE', 'user-trial')
        assert client.get(path + '/debug/status').status_code == 403
        command = {'thread_id': 'thr_harness', 'kind': 'send_message',
                   'payload': {'text': '/debug start test'}}
        assert client.post(path + '/commands', json=command).status_code == 403
