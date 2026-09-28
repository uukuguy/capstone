from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from capstone_agent.host_api import create_host_app
from capstone_agent.ledger import SessionRecord
from capstone_agent.session import WorkerRegistry, WorkerSpec


class DemoLedger:
    def __init__(self) -> None:
        self.sessions: dict[str, SessionRecord] = {}

    def create_session(self, application_id, mode, case_id, provider, model,
                       *, idempotency_key=None):
        session_id = f"session-{len(self.sessions) + 1}"
        record = SessionRecord(session_id, application_id, mode, case_id, provider,
                               model, None, "pending", 0, 0, None, None)
        self.sessions[session_id] = record
        return record

    def get_session(self, session_id):
        return self.sessions.get(session_id)


def test_public_demo_opens_registered_cases_with_fixed_provider() -> None:
    ledger = DemoLedger()
    registry = WorkerRegistry((WorkerSpec(
        "pandapower-static-analysis", ("unused",),
        scripted_cases=("pandapower-scripted-task",),
        provider_cases=("pandapower-scripted-task",),
    ),))
    app = create_host_app(
        ledger, registry, operator_token="hosted-secret", public_demo=True,
        public_provider="deepseek", public_model="deepseek-v4-pro",
        allowed_hosts={"localhost"}, allowed_origins={"http://localhost:5173"},
        repo_root=Path(__file__).resolve().parents[3],
    )
    with TestClient(app, base_url="http://localhost") as client:
        assert client.get("/api/v1/catalog").status_code == 401
        credential = client.get("/api/v1/demo-credential")
        assert credential.status_code == 200
        assert credential.headers["cache-control"] == "no-store"
        token = credential.json()["token"]
        assert token != "hosted-secret"
        demo = {"Authorization": f"Bearer {token}"}
        assert client.get("/api/v1/catalog", headers=demo).status_code == 200
        created = client.post("/api/v1/sessions", json={
            "application_id": "pandapower-static-analysis", "mode": "provider",
            "case_id": "pandapower-scripted-task",
        }, headers=demo)
        assert created.status_code == 201
        assert client.get(f"/api/v1/sessions/{created.json()['session_id']}",
                          headers=demo).status_code == 200
        assert ledger.sessions[created.json()["session_id"]].provider == "deepseek"
        assert ledger.sessions[created.json()["session_id"]].model == "deepseek-v4-pro"
        assert client.post("/api/v1/sessions", json={
            "application_id": "pandapower-static-analysis", "mode": "scripted-demo",
            "case_id": "pandapower-scripted-task",
        }, headers=demo).status_code == 403
        private = ledger.create_session("pandapower-static-analysis", "provider", None, None, None)
        route = f"/api/v1/sessions/{private.session_id}"
        assert client.get(route, headers=demo).status_code == 404
        assert client.post(route + "/turns", json={"instruction": "inspect"},
                           headers=demo).status_code == 404
        assert client.get(route, headers={"Authorization": "Bearer hosted-secret"}).status_code == 200
        assert client.get("/api/v1/catalog", headers={"Origin": "https://other.example"}).status_code == 403
