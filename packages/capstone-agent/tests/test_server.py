from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

from capstone_agent.server import create_app
from capstone_agent.registry import build_registry
from capstone_agent.session import WorkerRegistry, WorkerSpec


def _worker(tmp_path: Path) -> tuple[str, ...]:
    script = tmp_path / "server_worker.py"
    script.write_text('''
import json
import sys
import time
session = None
sequence = 0
turns = []
def send(kind, payload):
    global sequence
    sequence += 1
    print(json.dumps({"schema": "capstone-worker/1.0", "session_id": session,
                      "sequence": sequence, "kind": kind, "payload": payload}), flush=True)
for line in sys.stdin:
    frame = json.loads(line)
    session = frame["session_id"]
    if frame["kind"] == "open":
        send("ready", {"run_id": "run-server"})
    elif frame["kind"] == "turn":
        turns.append(frame["payload"]["instruction"])
        time.sleep(0.1)
        send("answer_committed", {"ordinal": len(turns), "turn_id": f"run-server-t{len(turns):03d}",
             "answer_output": "done", "answer_ref": f"answer:{len(turns)}",
             "result_refs": [], "evidence_refs": ["evidence:current"]})
    elif frame["kind"] == "close":
        send("completed", {"run_id": "run-server", "result": {"turns": turns}})
    elif frame["kind"] == "evidence":
        ref = frame["payload"]["ref"]
        send("evidence_result", {"ref": ref,
             "value": {"ref": ref} if ref == "evidence:current" else None})
''', encoding="utf-8")
    return (sys.executable, "-u", str(script))


def test_http_session_turns_sse_result_and_evidence(tmp_path: Path) -> None:
    registry = WorkerRegistry((WorkerSpec("fixture-app", _worker(tmp_path)),))
    app = create_app(registry, operator_token="local-secret")
    auth = {"Authorization": "Bearer local-secret"}

    with TestClient(app, base_url="http://localhost") as client:
        created = client.post("/api/v1/sessions", json={
            "application_id": "fixture-app", "mode": "scripted-demo",
        }, headers=auth)
        assert created.status_code == 201
        session_id = created.json()["session_id"]
        assert client.post(f"/api/v1/sessions/{session_id}/turns",
                           json={"instruction": "first"}, headers=auth).status_code == 202
        assert client.post(f"/api/v1/sessions/{session_id}/turns",
                           json={"instruction": "overlap"}, headers=auth).status_code == 409
        for _ in range(100):
            turn = client.get(f"/api/v1/sessions/{session_id}/turns/1", headers=auth)
            if turn.status_code == 200:
                break
            time.sleep(0.01)
        assert turn.json()["answer_output"] == "done"
        assert turn.json()["evidence_refs"] == ["evidence:current"]
        assert client.post(f"/api/v1/sessions/{session_id}/close", headers=auth).status_code == 202
        for _ in range(100):
            result = client.get(f"/api/v1/sessions/{session_id}/result", headers=auth)
            if result.status_code == 200:
                break
            time.sleep(0.01)
        assert result.json() == {"turns": ["first"]}
        stream = client.get(f"/api/v1/sessions/{session_id}/events?after=0", headers=auth)
        assert stream.status_code == 200
        assert "event: answer_committed" in stream.text
        assert "event: completed" in stream.text
        assert client.get(f"/api/v1/sessions/{session_id}/evidence",
                          params={"ref": "evidence:current"}, headers=auth).json() == {
                              "ref": "evidence:current"
                          }
        assert client.get(f"/api/v1/sessions/{session_id}/evidence",
                          params={"ref": "evidence:foreign"}, headers=auth).status_code == 404


def test_http_write_routes_require_token_and_local_origin(tmp_path: Path) -> None:
    registry = WorkerRegistry((WorkerSpec("fixture-app", _worker(tmp_path)),))
    app = create_app(registry, operator_token="local-secret")
    with TestClient(app, base_url="http://localhost") as client:
        body = {"application_id": "fixture-app", "mode": "scripted-demo"}
        assert client.post("/api/v1/sessions", json=body).status_code == 401
        assert client.post("/api/v1/sessions", json=body,
                           headers={"Authorization": "Bearer local-secret",
                                    "Origin": "http://evil.example"}).status_code == 403
        assert client.post("/api/v1/sessions", json=body,
                           headers={"Authorization": "Bearer local-secret",
                                    "Host": "evil.example"}).status_code == 400


def test_http_rejects_unregistered_case_before_starting_worker(tmp_path: Path) -> None:
    app = create_app(build_registry(tmp_path), operator_token="local-secret")
    with TestClient(app, base_url="http://localhost") as client:
        response = client.post("/api/v1/sessions", json={
            "application_id": "pypsa-business-cases", "mode": "scripted-demo",
            "case_id": "unregistered",
        }, headers={"Authorization": "Bearer local-secret"})
        assert response.status_code == 422


def test_http_reports_worker_crash_with_safe_error_code(tmp_path: Path) -> None:
    script = tmp_path / "crash_worker.py"
    script.write_text('''
import json
import sys
for line in sys.stdin:
    frame = json.loads(line)
    if frame["kind"] == "open":
        print(json.dumps({"schema": "capstone-worker/1.0", "session_id": frame["session_id"],
                          "sequence": 1, "kind": "ready", "payload": {"run_id": "run-crash"}}), flush=True)
    else:
        break
''', encoding="utf-8")
    app = create_app(WorkerRegistry((WorkerSpec("fixture-app", (sys.executable, str(script))),)),
                     operator_token="local-secret")
    auth = {"Authorization": "Bearer local-secret"}
    with TestClient(app, base_url="http://localhost") as client:
        created = client.post("/api/v1/sessions", json={
            "application_id": "fixture-app", "mode": "scripted-demo",
        }, headers=auth)
        session_id = created.json()["session_id"]
        assert client.post(f"/api/v1/sessions/{session_id}/turns",
                           json={"instruction": "crash"}, headers=auth).status_code == 202
        for _ in range(100):
            status = client.get(f"/api/v1/sessions/{session_id}", headers=auth)
            if status.json()["state"] == "failed":
                break
            time.sleep(0.01)
        assert status.json()["state"] == "failed"
        assert status.json()["error_code"] == "worker_disconnected"


def test_http_limits_live_session_count(tmp_path: Path) -> None:
    app = create_app(WorkerRegistry((WorkerSpec("fixture-app", _worker(tmp_path)),)),
                     operator_token="local-secret", max_sessions=1)
    auth = {"Authorization": "Bearer local-secret"}
    with TestClient(app, base_url="http://localhost") as client:
        body = {"application_id": "fixture-app", "mode": "scripted-demo"}
        assert client.post("/api/v1/sessions", json=body, headers=auth).status_code == 201
        assert client.post("/api/v1/sessions", json=body, headers=auth).status_code == 429
