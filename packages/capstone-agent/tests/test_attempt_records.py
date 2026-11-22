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


def test_request_context_is_scoped_and_reads_one_redacted_entry(monkeypatch):
    from types import SimpleNamespace
    from capstone_agent.artifacts import MemoryObjectStore
    from capstone_agent.host_api import create_host_app
    from capstone_agent.model_context_diagnostics import checked_snapshot, save_snapshot
    from test_thread_http_api import _Ledger, WorkerRegistry

    monkeypatch.setenv('CAPSTONE_CONTEXT_DIAGNOSTICS', '1')
    service, claim = completed_task()
    objects = MemoryObjectStore()
    snapshot = checked_snapshot({
        'request_id': 'ctx-1', 'dispatch_id': 'request-1', 'kind': 'main', 'total_entries': 2,
        'entries': [
            {'index': 1, 'carrier': 'system', 'role': 'system', 'text': 'Retained instruction', 'truncated': False},
            {'index': 2, 'carrier': 'tool_results', 'role': 'toolResult', 'text': 'api_key: example-secret',
             'truncated': False, 'source_id': 'call-real',
             'origin': {'kind': 'file', 'id': 'resource_test', 'revision': '2', 'delivery': 'reference',
                        'digest': '1' * 64, 'offset': 256, 'length': 64}},
        ],
    })
    attempt = claim.attempt.attempt_id
    ref = save_snapshot(objects, claim.thread_id, attempt, snapshot)
    app = create_host_app(_Ledger(), WorkerRegistry(()), operator_token='hosted-secret',
        allowed_hosts={'localhost'}, allowed_origins={'http://localhost:5173'}, thread_open_access=True,
        thread_service=service, artifacts=SimpleNamespace(store=objects))
    auth = {'Authorization': 'Bearer hosted-secret'}
    path = f'/api/v1/threads/{claim.thread_id}/attempts/{attempt}/context-snapshots/{ref}'
    with TestClient(app, base_url='http://localhost') as client:
        assert client.get(path).status_code == 403
        listing = client.get(path, headers=auth)
        assert listing.status_code == 200
        assert listing.headers['Cache-Control'] == 'no-store'
        assert all('text' not in item for item in listing.json()['entries'])
        assert client.get(path, params={'index': 1}, headers=auth).json()['entry']['text'] == 'Retained instruction'
        tool = client.get(path, params={'index': 2}, headers=auth).json()['entry']
        assert tool['source_id'] == 'call-real'
        assert tool['origin']['offset'] == 256 and tool['origin']['length'] == 64
        assert tool['redacted'] is True and 'example-secret' not in tool['text']
        assert client.get(path.replace(f'/attempts/{attempt}/', '/attempts/other_attempt/'), headers=auth).status_code == 404
        assert client.get(path, params={'index': 3}, headers=auth).status_code == 404
