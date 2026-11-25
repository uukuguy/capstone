from fastapi.testclient import TestClient
from capstone_agent.host_api import create_host_app
from test_harness import _thread_service
from test_thread_http_api import _Ledger, WorkerRegistry
from test_attempt_records import completed_task


def test_export_requires_permission_and_excludes_event_payloads(monkeypatch):
    monkeypatch.setenv('CAPSTONE_DEPLOYMENT_STAGE', 'local')
    monkeypatch.setenv('CAPSTONE_DEBUG_COMMANDS', '1')
    monkeypatch.setenv('CAPSTONE_DEBUG_TIMELINE_EXPORT', '0')
    service, claim = completed_task()
    app = create_host_app(_Ledger(), WorkerRegistry(()), operator_token='hosted-secret',
                          allowed_hosts={'localhost'}, allowed_origins={'http://localhost:5173'},
                          thread_open_access=True, thread_service=service)
    path = f'/api/v1/threads/{claim.thread_id}/debug/attempts/{claim.attempt.attempt_id}/timeline'
    with TestClient(app, base_url='http://localhost') as client:
        assert client.get(path).status_code == 403
        monkeypatch.setenv('CAPSTONE_DEBUG_TIMELINE_EXPORT', '1')
        response = client.get(path)
        assert response.status_code == 200
        page = response.json()
        assert page['events']
        assert all(set(event) == {'seq', 'type', 'occurred_at'} for event in page['events'])
        assert 'unverified_answer_recorded' not in response.text
        assert 'Input check failed' not in response.text
        assert client.get(path.replace(claim.attempt.attempt_id, 'unknown')).status_code == 404
        monkeypatch.setenv('CAPSTONE_DEBUG_COMMANDS', '0')
        assert client.get(path).status_code == 403


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
