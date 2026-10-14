from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from capstone_agent.thread_service import ThreadNotFound
from test_harness import _thread_service
from test_attempt_failure_delivery import claim_attempt
from test_thread_http_api import _app


def completed_task():
    service = _thread_service()
    claim = claim_attempt(service)
    service.append_runtime_event(claim, event_type="validation_observation",
        payload={"status": "failed", "message": "Input check failed"}, visibility="public")
    service.append_runtime_event(claim, event_type="unverified_answer_recorded",
        payload={"text": "Unverified product", "status": "not_admitted"}, visibility="diagnostic")
    service.finish_attempt(claim, phase="completed", payload={"answer": "The check remains unresolved."})
    return service, claim


def test_attempt_records_page_preserves_identity_failures_and_diagnostic_products():
    service, claim = completed_task()
    seen = []
    after = 0
    while True:
        page = service.read_attempt_records("thr_harness", claim.attempt.attempt_id, after=after, limit=2)
        assert page["model_context"] == claim.model_context.to_document()
        assert page["instruction"] == claim.instruction
        assert len(page["events"]) <= 2
        seen.extend(page["events"])
        if not page["has_more"]:
            break
        assert page["next_after"] > after
        after = page["next_after"]
    assert any(e["event_type"] == "validation_observation" for e in seen)
    assert any(e["event_type"] == "unverified_answer_recorded" for e in seen)
    assert all(e["attempt_id"] == claim.attempt.attempt_id for e in seen)
    assert len({e["event_seq"] for e in seen}) == len(seen)
    with pytest.raises(ThreadNotFound):
        service.read_attempt_records("thr_harness", "other_attempt")


def test_attempt_records_http_requires_access_and_does_not_start_work():
    service, claim = completed_task()
    before = service.snapshot("thr_harness").last_event_seq
    client = TestClient(_app(service), base_url="http://localhost")
    path = f"/api/v1/threads/thr_harness/attempts/{claim.attempt.attempt_id}/records"
    assert client.get(path).status_code == 401
    response = client.get(path, headers={"Authorization": "Bearer hosted-secret"})
    assert response.status_code == 200
    assert response.json()["attempt_id"] == claim.attempt.attempt_id
    assert service.snapshot("thr_harness").last_event_seq == before
