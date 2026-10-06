"""Function trials can open the actual Thread API without a login screen."""
from fastapi.testclient import TestClient

from capstone_agent.host_api import create_host_app
from capstone_agent.session import WorkerRegistry
from test_thread_http_api import _Ledger, _service


def _app(open_access=False):
    return create_host_app(
        _Ledger(), WorkerRegistry(()), operator_token="hosted-secret",
        allowed_hosts={"localhost"}, allowed_origins={"http://localhost:5173"},
        thread_service=_service(), thread_open_access=open_access,
    )


def test_open_access_allows_anonymous_thread_history_and_management():
    with TestClient(_app(True), base_url="http://localhost") as client:
        entry = client.get("/api/v1/thread-access")
        assert entry.json() == {"schema": "capstone-thread-access/1", "mode": "open"}
        assert "hosted-secret" not in entry.text
        assert client.get("/api/v1/threads/thr_demo_39").status_code == 200
        assert client.get("/api/v1/threads").status_code == 422
        assert client.get("/api/v1/threads?current_thread_id=thr_demo_39").status_code == 200
        assert client.get("/api/v1/threads?current_thread_id=thr_other_user").status_code == 404
        metadata = client.get('/api/v1/threads/thr_demo_39/metadata').json()
        assert metadata['user_id'].startswith('usr_')
        assert client.get("/api/v1/threads/thr_demo_39/history").status_code == 200
        archived = client.post("/api/v1/threads/thr_demo_39/archive", json={"archived": True})
        assert archived.status_code == 200 and archived.json()["archived"]
        assert client.post("/api/v1/threads/thr_demo_39/archive", json={"archived": False}).status_code == 200


def test_operator_access_remains_available_without_open_mode():
    with TestClient(_app(), base_url="http://localhost") as client:
        assert client.get("/api/v1/thread-access").json()["mode"] == "operator"
        assert client.get("/api/v1/threads").status_code == 401
        assert client.get("/api/v1/threads", headers={"Authorization": "Bearer hosted-secret"}).status_code == 200


def test_open_mode_keeps_host_and_origin_checks():
    with TestClient(_app(True), base_url="http://localhost") as client:
        assert client.get("/api/v1/threads", headers={"Origin": "https://other.example"}).status_code == 403
        assert client.get("/api/v1/thread-access", headers={"Host": "other.example"}).status_code == 400


def test_open_mode_accepts_conversation_commands_once():
    command = {"schema": "capstone-command/1", "thread_id": "thr_demo_39",
               "run_id": "run_001", "command_id": "cmd_open_001",
               "idempotency_key": "idem_open_001", "kind": "send_ordinary",
               "expected_event_seq": 0, "payload": {"text": "hello"}}
    with TestClient(_app(True), base_url="http://localhost") as client:
        first = client.post("/api/v1/threads/thr_demo_39/commands", json=command)
        second = client.post("/api/v1/threads/thr_demo_39/commands", json=command)
        assert first.status_code == second.status_code == 202
        assert first.json() == second.json()
        assert first.json()["status"] == "accepted"
        assert first.json()["accepted_event_seq"] == 1
