from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from fastapi.testclient import TestClient

from capstone_agent.worker_wake import WorkerWakeClient, create_wake_app, wake_token


def test_private_model_preparation_uses_thread_identity_without_provider_or_model_input():
    prepared = []
    app = create_wake_app(threading.Event(), 'operator-secret', prepare_model=prepared.append)
    auth = {'Authorization': f"Bearer {wake_token('operator-secret')}"}
    with TestClient(app) as client:
        assert client.post('/prepare-model', json={'thread_id': 'thr_test'}).status_code == 401
        assert client.post('/prepare-model', headers=auth, json={'thread_id': 'thr_test', 'model_id': 'wrong'}).status_code == 422
        assert client.post('/prepare-model', headers=auth, json={'thread_id': 'thr_test'}).status_code == 204
    assert prepared == ['thr_test']


def test_model_preparation_selects_only_matching_family_worker(monkeypatch):
    from capstone_agent.worker_wake import configured_model_preparation
    calls = []
    monkeypatch.setattr(WorkerWakeClient, 'prepare_model', lambda self, thread_id: calls.append((self.url, thread_id)) or True)
    prepare = configured_model_preparation(None, 'pandapower=http://grid:8080,pypsa=http://pypsa:8080', 'operator-secret')
    assert prepare('thr_test', 'pandapower')
    assert calls == [('http://grid:8080/wake', 'thr_test')]
    assert not prepare('thr_test', 'unknown')


def test_worker_health_reports_fixed_runtime_identity() -> None:
    with TestClient(create_wake_app(threading.Event(), "operator-secret",
                                   runtime_mode="m11-provider-free",
                                   implementation_family="pypsa")) as client:
        assert client.get("/health").json() == {
            "status": "ready", "runtime_mode": "m11-provider-free",
            "implementation_family": "pypsa",
        }


def test_worker_health_exposes_resource_counts_without_thread_data():
    with TestClient(create_wake_app(threading.Event(), 'operator-secret',
                                   resource_status=lambda: {'retained': 2, 'active': 1})) as client:
        assert client.get('/health').json()['thread_contexts'] == {'retained': 2, 'active': 1}


def test_private_wake_requires_derived_token() -> None:
    wake = threading.Event()
    with TestClient(create_wake_app(wake, "operator-secret")) as client:
        assert client.get("/health").status_code == 200
        assert client.post("/wake").status_code == 401
        assert client.post("/wake", headers={
            "Authorization": "Bearer operator-secret",
        }).status_code == 401
        assert not wake.is_set()
        assert client.post("/wake", headers={
            "Authorization": f"Bearer {wake_token('operator-secret')}",
        }).status_code == 204
        assert wake.is_set()


def test_authenticated_wake_signals_legacy_and_thread_schedulers():
    legacy, thread = threading.Event(), threading.Event()
    with TestClient(create_wake_app(legacy, 'operator-secret', additional_wake_events=(thread,))) as client:
        assert client.post('/wake').status_code == 401
        assert not legacy.is_set() and not thread.is_set()
        assert client.post('/wake', headers={'Authorization': f"Bearer {wake_token('operator-secret')}"}).status_code == 204
        assert legacy.is_set() and thread.is_set()


def test_domain_tool_route_follows_the_worker_pack_and_rejects_other_packs():
    class Pack:
        def catalog(self, profile_id, profile_version):
            if (profile_id, profile_version) != ('pandapower-static-analysis', '1.0.1'):
                raise KeyError(profile_id)
            return {'schema': 'capstone-domain-tool-catalog/1', 'tools': {'grid_context_open': {}}}

        def invoke(self, body):
            return {'ok': True, 'result': {'tool': body['name']}}

    app = create_wake_app(threading.Event(), 'operator-secret', implementation_family='pandapower', domain_tools=Pack())
    auth = {'Authorization': f"Bearer {wake_token('operator-secret')}"}
    with TestClient(app) as client:
        assert client.get('/domain-tools/catalog', params={'profile_id': 'other', 'profile_version': '1'}).status_code == 401
        assert client.get('/domain-tools/catalog', headers=auth, params={'profile_id': 'other', 'profile_version': '1'}).status_code == 404
        assert client.get('/domain-tools/catalog', headers=auth, params={
            'profile_id': 'pandapower-static-analysis', 'profile_version': '1.0.1'}).json()['tools']['grid_context_open'] == {}
        assert client.post('/domain-tools/invoke', headers=auth, json={
            'task_id': 'pi-1', 'call_id': 'call-1', 'name': 'grid_context_open', 'arguments': {}}).json()['ok'] is True
    bare = create_wake_app(threading.Event(), 'operator-secret', implementation_family='native')
    with TestClient(bare) as client:
        assert client.get('/domain-tools/catalog', headers=auth, params={'profile_id': 'x', 'profile_version': '1'}).status_code == 404


def test_wake_cannot_report_ready_when_a_scheduler_has_stopped():
    wake = threading.Event()
    with TestClient(create_wake_app(wake, 'operator-secret', health_check=lambda: False)) as client:
        response = client.post('/wake', headers={'Authorization': f"Bearer {wake_token('operator-secret')}"})
        assert response.status_code == 503
        assert not wake.is_set()


def test_family_wake_reaches_only_the_receiving_worker(monkeypatch):
    from capstone_agent.worker_wake import configured_family_wake
    calls = []

    def wake(self, **_kwargs):
        calls.append(self.url)
        return True

    monkeypatch.setattr(WorkerWakeClient, 'wake', wake)
    callback = configured_family_wake(
        'http://native:8766',
        'native=http://native:8766,pandapower=http://grid:8766,pypsa=http://pypsa:8766',
        'operator-secret')
    assert callback('pandapower') is True
    assert calls == ['http://grid:8766/wake']


def test_federated_wake_reaches_every_family_even_when_one_is_unavailable(monkeypatch):
    from capstone_agent.worker_wake import configured_worker_wake
    calls = []
    def wake(self, **_kwargs):
        calls.append(self.url)
        return 'pypsa' in self.url
    monkeypatch.setattr(WorkerWakeClient, 'wake', wake)
    callback = configured_worker_wake('http://grid:8080', 'pandapower=http://grid:8080,pypsa=http://pypsa:8080', 'operator-secret')
    assert callback() is False
    assert calls == ['http://grid:8080/wake', 'http://pypsa:8080/wake']


def test_wake_client_retries_transient_cold_start_response() -> None:
    class Handler(BaseHTTPRequestHandler):
        calls = 0

        def do_POST(self) -> None:
            assert self.path == "/wake"
            assert self.headers["Authorization"] == f"Bearer {wake_token('operator-secret')}"
            Handler.calls += 1
            self.send_response(502 if Handler.calls < 3 else 204)
            self.end_headers()

        def log_message(self, *_args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = WorkerWakeClient(f"http://127.0.0.1:{server.server_port}",
                                  "operator-secret")
        assert client.wake(attempts=3, backoff_seconds=0)
        assert Handler.calls == 3
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()
