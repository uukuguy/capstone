from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from capstone_agent.thread_commands import ThreadCommandFactory
from capstone_agent.thread_protocol import ThreadProtocolError
from test_thread_http_api import _app, _auth, _service
from test_thread_postgres import postgres_thread_service, _snapshot, _command


def _message(service, ordinal: int):
    snapshot = service.snapshot("thr_demo_39")
    command = ThreadCommandFactory(snapshot.thread_id, snapshot.run.run_id).send_auto(
        f"question {ordinal}", expected_event_seq=snapshot.last_event_seq,
        command_id=f"cmd_{ordinal}", idempotency_key=f"idem_{ordinal}",
    )
    assert service.submit_command(command).status == "accepted"
    return command


def test_archive_is_reversible_and_does_not_delete_history():
    service = _service()
    _message(service, 1)
    claim = service.claim_attempt("worker", 30)
    service.finish_attempt(claim, phase="failed", payload={"error_code": "test_failure"})
    before = service.read_events("thr_demo_39", 0).to_document()
    with TestClient(_app(service), base_url="http://localhost") as client:
        listing = client.get("/api/v1/threads", headers=_auth())
        assert listing.status_code == 200
        assert listing.json()["threads"][0]["thread_id"] == "thr_demo_39"
        archive = client.post("/api/v1/threads/thr_demo_39/archive", headers=_auth(), json={"archived": True})
        assert archive.status_code == 200
        assert archive.json()["archived"] is True
        assert client.get("/api/v1/threads", headers=_auth()).json()["threads"] == []
        assert len(client.get("/api/v1/threads?archived=true", headers=_auth()).json()["threads"]) == 1
        rejected = service.submit_command({**_message_command(service, 2)})
        assert rejected.rejection == "thread_archived"
        assert client.post("/api/v1/threads/thr_demo_39/archive", headers=_auth(), json={"archived": False}).status_code == 200
    assert service.read_events("thr_demo_39", 0).to_document() == before


def _message_command(service, ordinal: int):
    snapshot = service.snapshot("thr_demo_39")
    return ThreadCommandFactory(snapshot.thread_id, snapshot.run.run_id).send_auto(
        f"question {ordinal}", expected_event_seq=snapshot.last_event_seq,
        command_id=f"cmd_{ordinal}", idempotency_key=f"idem_{ordinal}",
    )


def test_cannot_archive_an_accepted_attempt():
    service = _service()
    _message(service, 1)
    with TestClient(_app(service), base_url="http://localhost") as client:
        response = client.post("/api/v1/threads/thr_demo_39/archive", headers=_auth(), json={"archived": True})
        assert response.status_code == 409
        assert client.get("/api/v1/threads", headers=_auth()).json()["threads"][0]["archived"] is False


def test_reverse_history_pages_preserve_public_events_without_overlap():
    service = _service()
    for ordinal in range(4):
        _message(service, ordinal)
        claim = service.claim_attempt("worker", 30)
        service.append_runtime_event(claim, event_type="runtime_prompt_ack", payload={}, visibility="diagnostic")
        service.finish_attempt(claim, phase="failed", payload={"error_code": "test_failure"})
    expected = [e.event_seq for e in service.read_events("thr_demo_39", 0).events if e.visibility == "public"]
    collected = []
    with TestClient(_app(service), base_url="http://localhost") as client:
        before = None
        while True:
            params = {"limit": 2}
            if before is not None:
                params["before"] = before
            response = client.get("/api/v1/threads/thr_demo_39/history", headers=_auth(), params=params)
            assert response.status_code == 200
            page = response.json()
            assert page["schema"] == "capstone-thread-history/1"
            assert len(page["events"]) <= 2
            collected = [e["event_seq"] for e in page["events"]] + collected
            if not page["has_more"]:
                break
            assert before is None or page["next_before_event_seq"] < before
            before = page["next_before_event_seq"]
    assert collected == expected


def test_management_routes_require_auth_and_validate_input():
    with TestClient(_app(_service()), base_url="http://localhost") as client:
        for route in ["/api/v1/threads", "/api/v1/threads/thr_demo_39/history"]:
            assert client.get(route).status_code == 401
        assert client.get("/api/v1/threads?limit=51", headers=_auth()).status_code == 422
        assert client.get("/api/v1/threads/thr_demo_39/history?before=-1", headers=_auth()).status_code == 422
        assert client.post("/api/v1/threads/thr_demo_39/archive", headers=_auth(), json={"archived": "yes"}).status_code == 422


@pytest.mark.parametrize("limit", [0, 257, True])
def test_history_service_rejects_unbounded_limits(limit):
    with pytest.raises(ThreadProtocolError):
        _service().read_history("thr_demo_39", limit=limit)


def test_network_context_projection_is_bounded_and_separate_from_chat_history():
    service = _service()
    _message(service, 1)
    claim = service.claim_attempt("worker", 30)
    service.append_runtime_event(claim, event_type="network_layer_unavailable", payload={"reason": "no_network_view"}, visibility="public")
    service.finish_attempt(claim, phase="failed", payload={"error_code": "test_failure"})
    with TestClient(_app(service), base_url="http://localhost") as client:
        response = client.get("/api/v1/threads/thr_demo_39/network-events", headers=_auth())
        assert response.status_code == 200
        assert [e["event_type"] for e in response.json()["events"]] == ["network_layer_unavailable"]
        assert len(service.read_history("thr_demo_39")["events"]) > 1


def test_postgres_management_and_history_survive_service_restart(postgres_thread_service):
    from capstone_agent.thread_service import PostgresThreadService, ThreadExecutionError

    service, thread_id = postgres_thread_service
    service.create_thread(_snapshot(thread_id))
    service.submit_command(_command(thread_id))
    with pytest.raises(ThreadExecutionError):
        service.set_archived(thread_id, True)
    claim = service.claim_attempt("management-test", 30)
    service.finish_attempt(claim, phase="failed", payload={"error_code": "test_failure"})
    before = service.read_events(thread_id, 0).to_document()
    first = service.read_history(thread_id, limit=2)
    assert len(first["events"]) == 2 and first["has_more"]
    second = service.read_history(thread_id, before=first["next_before_event_seq"], limit=2)
    assert not {e["event_seq"] for e in first["events"]} & {e["event_seq"] for e in second["events"]}
    service.set_archived(thread_id, True)
    restarted = PostgresThreadService(service.dsn)
    restarted.initialize()
    assert restarted.is_archived(thread_id)
    assert any(t["thread_id"] == thread_id for t in restarted.list_threads(archived=True)["threads"])
    assert restarted.list_threads(before=thread_id, archived=True)["threads"] == []
    restarted.set_archived(thread_id, False)
    assert restarted.read_events(thread_id, 0).to_document() == before
