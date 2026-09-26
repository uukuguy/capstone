from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from capstone_agent.registry import build_registry
from capstone_agent.server import create_app
from capstone_agent.session import WorkerSession


ROOT = Path(__file__).resolve().parents[3]


def test_pandapower_scripted_worker_commits_three_live_turns() -> None:
    document = json.loads((ROOT / "validation/application/pandapower-scripted-task.json").read_text())
    instructions = [question["text"] for question in document["questions"]]
    spec = build_registry(ROOT).resolve("pandapower-static-analysis")

    with WorkerSession(spec, mode="scripted-demo", case_id="pandapower-scripted-task",
                       timeout=120.0) as session:
        answers = []
        layers = []
        for instruction in instructions:
            answer = session.submit_and_wait(instruction)
            answers.append(answer)
            layers.append(session.wait_for("network_layer", after=answer.sequence).payload["layer"])
        diagrams = [event.payload["diagram"] for event in session.events
                    if event.kind == "network_diagram"]
        assert [layer["ordinal"] for layer in layers] == [1, 2, 3]
        assert len(diagrams) == 1
        assert len(diagrams[0]["buses"]) == 39
        assert len(diagrams[0]["branches"]) == 46
        assert any(branch["id"] == "line:11" for branch in diagrams[0]["branches"])
        assert layers[2]["overlay"]["metric"] == "loading_percent"
        outcome = session.close()
        assert [answer.payload["ordinal"] for answer in answers] == [1, 2, 3]
        assert all(answer.payload["answer_ref"] for answer in answers)
        evidence_refs = [ref for answer in answers for ref in answer.payload["evidence_refs"]]
        assert evidence_refs
        evidence = session.read_evidence(evidence_refs[0])
        assert isinstance(evidence, dict)
        assert evidence.get("evidence_type")
        assert outcome.payload["result"]["schema"] == "capability-agent-output/1.0"
        assert outcome.payload["result"]["core"]["status"] == "completed"


def test_pypsa_scripted_worker_commits_three_live_turns() -> None:
    catalog = json.loads((ROOT / "validation/pypsa-cases/cases.json").read_text())
    case = next(item for item in catalog["cases"] if item["id"] == "regional-demand-stress")
    instructions = case["introduction"]["demo_instructions"]
    spec = build_registry(ROOT).resolve("pypsa-business-cases")

    with WorkerSession(spec, mode="scripted-demo", case_id=case["id"],
                       timeout=180.0) as session:
        answers = []
        layers = []
        for instruction in instructions:
            answer = session.submit_and_wait(instruction)
            answers.append(answer)
            layers.append(session.wait_for("network_layer", after=answer.sequence).payload["layer"])
        diagrams = [event.payload["diagram"] for event in session.events
                    if event.kind == "network_diagram"]
        assert [layer["ordinal"] for layer in layers] == [1, 2, 3]
        assert len(diagrams[0]["buses"]) == 6
        assert layers[2]["overlay"] is not None
        evidence_ref = next(
            ref for answer in answers for ref in answer.payload["evidence_refs"]
        )
        assert session.read_evidence(evidence_ref) is not None
        outcome = session.close()
        assert [answer.payload["ordinal"] for answer in answers] == [1, 2, 3]
        assert any(answer.payload["evidence_refs"] for answer in answers)
        assert outcome.payload["result"]["schema"] == "capability-agent-output/1.0"
        assert set(outcome.payload["result"]["domains"]) == {"source", "operations"}
        report = (ROOT / "runs/capstone-agent/pypsa" / session.run_id
                  / "output/report.md").read_text(encoding="utf-8")
        assert evidence_ref in report


def test_http_session_uses_real_pandapower_worker_and_evidence() -> None:
    document = json.loads((ROOT / "validation/application/pandapower-scripted-task.json").read_text())
    instructions = [question["text"] for question in document["questions"]]
    app = create_app(build_registry(ROOT), operator_token="local-test-token")
    with TestClient(app, base_url="http://localhost",
                    headers={"Authorization": "Bearer local-test-token"}) as client:
        created = client.post("/api/v1/sessions", json={
            "application_id": "pandapower-static-analysis", "mode": "scripted-demo",
            "case_id": "pandapower-scripted-task",
        })
        assert created.status_code == 201
        session_id = created.json()["session_id"]
        evidence_refs: list[str] = []
        for ordinal, instruction in enumerate(instructions, start=1):
            accepted = client.post(f"/api/v1/sessions/{session_id}/turns",
                                   json={"instruction": instruction})
            assert accepted.status_code == 202
            deadline = time.monotonic() + 120
            while True:
                answer = client.get(f"/api/v1/sessions/{session_id}/turns/{ordinal}")
                if answer.status_code == 200:
                    break
                assert time.monotonic() < deadline
                time.sleep(0.1)
            assert answer.json()["answer_ref"]
            evidence_refs.extend(answer.json()["evidence_refs"])
        reference = evidence_refs[0]
        evidence = client.get(f"/api/v1/sessions/{session_id}/evidence", params={"ref": reference})
        assert evidence.status_code == 200, (reference, evidence.text)
        assert evidence.json()["evidence_type"]
        assert client.post(f"/api/v1/sessions/{session_id}/close").status_code == 202
        deadline = time.monotonic() + 120
        while True:
            result = client.get(f"/api/v1/sessions/{session_id}/result")
            if result.status_code == 200:
                break
            assert time.monotonic() < deadline
            time.sleep(0.1)
        assert result.json()["schema"] == "capability-agent-output/1.0"
