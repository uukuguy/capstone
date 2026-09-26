from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from capstone_agent.artifacts import ArtifactService, MemoryObjectStore
from capstone_agent.host_api import create_host_app
from capstone_agent.host_worker import run_claimed_session
from capstone_agent.ledger import Ledger
from capstone_agent.protocol import Frame
from capstone_agent.session import WorkerRegistry, WorkerSpec

from test_host_worker import _worker
from test_network_view import _view


@pytest.fixture
def ledger() -> Ledger:
    dsn = os.environ.get("CAPSTONE_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("CAPSTONE_TEST_DATABASE_URL is required")
    store = Ledger(dsn)
    store.initialize()
    with psycopg.connect(dsn) as connection:
        connection.execute("TRUNCATE session_events, session_commands, sessions CASCADE")
    return store


def _app(ledger: Ledger, registry: WorkerRegistry,
         artifacts: ArtifactService | None = None):
    return create_host_app(
        ledger, registry, operator_token="hosted-secret",
        allowed_hosts={"localhost"}, allowed_origins={"http://localhost:5173"},
        artifacts=artifacts,
    )


def test_host_api_reads_completed_run_across_instances(ledger: Ledger, tmp_path: Path) -> None:
    registry = WorkerRegistry((WorkerSpec("fixture-app", _worker(tmp_path)),))
    objects = MemoryObjectStore()
    artifacts = ArtifactService(ledger, objects, tmp_path / "runs")
    auth = {"Authorization": "Bearer hosted-secret", "Origin": "http://localhost:5173"}
    with TestClient(_app(ledger, registry, artifacts), base_url="http://localhost") as first:
        created = first.post("/api/v1/sessions", headers=auth,
                             json={"application_id": "fixture-app", "mode": "scripted-demo"})
        assert created.status_code == 201
        session_id = created.json()["session_id"]
        assert created.json()["state"] == "pending"
        claim = ledger.claim_pending("worker-test", 30)
        assert claim is not None
        thread = threading.Thread(target=run_claimed_session, args=(ledger, registry, claim),
                                  kwargs={"poll_seconds": 0.01, "artifacts": artifacts}, daemon=True)
        thread.start()
        for _ in range(100):
            if first.get(f"/api/v1/sessions/{session_id}", headers=auth).json()["state"] == "ready":
                break
            time.sleep(0.02)
        accepted = first.post(f"/api/v1/sessions/{session_id}/turns", headers={
            **auth, "Idempotency-Key": "turn-1",
        }, json={"instruction": "first"})
        assert accepted.status_code == 202
        assert first.post(f"/api/v1/sessions/{session_id}/turns", headers={
            **auth, "Idempotency-Key": "turn-1",
        }, json={"instruction": "first"}).json() == accepted.json()
        for _ in range(100):
            if first.get(f"/api/v1/sessions/{session_id}/turns/1", headers=auth).status_code == 200:
                break
            time.sleep(0.02)
        assert first.post(f"/api/v1/sessions/{session_id}/close", headers={
            **auth, "Idempotency-Key": "close-1",
        }).status_code == 202
        thread.join(timeout=5)

    fresh_ledger = Ledger(ledger.dsn)
    fresh_artifacts = ArtifactService(fresh_ledger, objects, tmp_path / "runs")
    with TestClient(_app(fresh_ledger, registry, fresh_artifacts), base_url="http://localhost") as second:
        status = second.get(f"/api/v1/sessions/{session_id}", headers=auth).json()
        assert status["state"] == "completed"
        assert status["completed_turns"] == 1
        assert second.get(f"/api/v1/sessions/{session_id}/result", headers=auth).json() == {
            "turns": ["first"]
        }
        stream = second.get(f"/api/v1/sessions/{session_id}/events?after=1", headers=auth)
        assert "event: answer_committed" in stream.text
        assert "event: completed" in stream.text
        assert "event: ready" not in stream.text
        assert second.get(f"/api/v1/sessions/{session_id}/report", headers=auth).text == (
            "# Run report\n"
        )
        assert second.get(f"/api/v1/sessions/{session_id}/evidence", headers=auth,
                          params={"ref": "evidence:current"}).json() == {
                              "ref": "evidence:current"
                          }
        assert second.get(f"/api/v1/sessions/{session_id}/evidence", headers=auth,
                          params={"ref": "evidence:foreign"}).status_code == 404


def test_host_api_requires_token_and_explicit_origin(ledger: Ledger, tmp_path: Path) -> None:
    registry = WorkerRegistry((WorkerSpec("fixture-app", _worker(tmp_path)),))
    with TestClient(_app(ledger, registry), base_url="http://localhost") as client:
        assert client.get("/health/ready").status_code == 200
        assert client.get("/health/ready", headers={"Host": "probe.internal"}).status_code == 200
        assert client.get("/api/v1/catalog", headers={
            "Host": "probe.internal", "Authorization": "Bearer hosted-secret",
        }).status_code == 400
        assert client.get("/api/v1/catalog").status_code == 401
        assert client.get("/api/v1/catalog", headers={
            "Authorization": "Bearer hosted-secret", "Origin": "https://evil.example",
        }).status_code == 403
        preflight = client.options("/api/v1/catalog", headers={
            "Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET",
        })
        assert preflight.status_code == 204
        assert preflight.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_network_view_is_authenticated_and_replayable(ledger: Ledger, tmp_path: Path) -> None:
    registry = WorkerRegistry((WorkerSpec("fixture-app", _worker(tmp_path)),))
    session = ledger.create_session("fixture-app", "scripted-demo", None, None, None)
    claim = ledger.claim_pending("network-test", 30)
    assert claim is not None and claim.lease_token is not None
    ledger.append_event(session.session_id, claim.lease_token,
                        Frame(session.session_id, 1, "ready", {"run_id": "run-network"}))
    ledger.accept_turn(session.session_id, "inspect", "network-turn")
    ledger.append_event(session.session_id, claim.lease_token,
                        Frame(session.session_id, 2, "answer_committed", {
                            "ordinal": 1, "turn_id": "run-network-t001", "answer_output": "done",
                            "answer_ref": "answer:one", "result_refs": [], "evidence_refs": [],
                        }))
    view = _view()
    ledger.append_event(session.session_id, claim.lease_token,
                        Frame(session.session_id, 3, "network_view", {"ordinal": 1, "view": view}))
    route = f"/api/v1/sessions/{session.session_id}/network?ordinal=1"
    with TestClient(_app(Ledger(ledger.dsn), registry), base_url="http://localhost") as client:
        assert client.get(route).status_code == 401
        auth = {"Authorization": "Bearer hosted-secret"}
        assert client.get(route, headers=auth).json() == view
        assert client.get(route.replace("ordinal=1", "ordinal=2"), headers=auth).status_code == 404
