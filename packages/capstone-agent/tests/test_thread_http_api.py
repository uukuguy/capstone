from __future__ import annotations

from fastapi.testclient import TestClient

from capstone_agent.host_api import create_host_app
from capstone_agent.session import WorkerRegistry
from capstone_agent.thread_service import InMemoryThreadService


def _service() -> InMemoryThreadService:
    return InMemoryThreadService.from_document({
        "schema": "capstone-thread-snapshot/1",
        "thread_id": "thr_demo_39",
        "run": {"run_id": "run_001", "state": "open"},
        "active_model_context": {
            "id": "ctx_ieee39_7", "model_id": "ieee39", "model_revision": "7",
            "implementation_family": "pandapower", "selection_revision": "sel_2",
        },
        "active_grid_page_id": "page_ieee39",
        "current_attempt": None,
        "last_event_seq": 0,
        "base_event_seq": 0,
    })


class _Ledger:
    def ping(self) -> bool:
        return True


def _app(service: InMemoryThreadService):
    return create_host_app(
        _Ledger(), WorkerRegistry(()), operator_token="hosted-secret",
        allowed_hosts={"localhost"}, allowed_origins={"http://localhost:5173"},
        thread_service=service,
    )


def _auth() -> dict[str, str]:
    return {"Authorization": "Bearer hosted-secret", "Origin": "http://localhost:5173"}


def test_thread_snapshot_and_event_page_are_exposed_as_capstone_protocol() -> None:
    service = _service()
    with TestClient(_app(service), base_url="http://localhost") as client:
        snapshot = client.get("/api/v1/threads/thr_demo_39", headers=_auth())
        assert snapshot.status_code == 200
        assert snapshot.json()["schema"] == "capstone-thread-snapshot/1"

        events = client.get("/api/v1/threads/thr_demo_39/events", headers=_auth())
        assert events.status_code == 200
        assert events.json() == {
            "schema": "capstone-thread-events/1",
            "thread_id": "thr_demo_39",
            "after_event_seq": 0,
            "next_event_seq": 0,
            "has_more": False,
            "events": [],
        }


def test_thread_command_is_idempotent_and_emits_a_replayable_event() -> None:
    service = _service()
    command = {
        "schema": "capstone-command/1",
        "command_id": "cmd_turn_001",
        "idempotency_key": "idem_turn_001",
        "thread_id": "thr_demo_39",
        "run_id": "run_001",
        "kind": "send_ordinary",
        "expected_event_seq": 0,
        "payload": {"text": "hello"},
    }
    with TestClient(_app(service), base_url="http://localhost") as client:
        first = client.post("/api/v1/threads/thr_demo_39/commands", headers=_auth(), json=command)
        second = client.post("/api/v1/threads/thr_demo_39/commands", headers=_auth(), json=command)
        assert first.status_code == second.status_code == 202
        assert first.json() == second.json()
        assert first.json()["status"] == "accepted"
        assert first.json()["accepted_event_seq"] == 1

        events = client.get("/api/v1/threads/thr_demo_39/events", headers=_auth()).json()
        assert events["next_event_seq"] == 1
        assert events["events"][0]["event_type"] == "command_accepted"


def test_thread_cursor_gap_returns_verified_resync_snapshot() -> None:
    service = _service()
    service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_turn_001",
        "idempotency_key": "idem_turn_001", "thread_id": "thr_demo_39",
        "run_id": "run_001", "kind": "send_ordinary", "expected_event_seq": 0,
        "payload": {"text": "hello"},
    })
    service.compact_before(1)
    with TestClient(_app(service), base_url="http://localhost") as client:
        response = client.get(
            "/api/v1/threads/thr_demo_39/events?after=0", headers=_auth(),
        )
        assert response.status_code == 409
        assert response.json()["error"] == "resync_required"
        assert response.json()["snapshot"]["schema"] == "capstone-thread-snapshot/1"


def test_thread_sse_reuses_the_same_event_cursor() -> None:
    service = _service()
    command = {
        "schema": "capstone-command/1", "command_id": "cmd_turn_001",
        "idempotency_key": "idem_turn_001", "thread_id": "thr_demo_39",
        "run_id": "run_001", "kind": "send_ordinary", "expected_event_seq": 0,
        "payload": {"text": "hello"},
    }
    with TestClient(_app(service), base_url="http://localhost") as client:
        client.post("/api/v1/threads/thr_demo_39/commands", headers=_auth(), json=command)
        stream = client.get("/api/v1/threads/thr_demo_39/events/stream?after=0", headers=_auth())
        assert stream.status_code == 200
        assert stream.headers["content-type"].startswith("text/event-stream")
        assert "id: 1" in stream.text
        assert "event: command_accepted" in stream.text


def test_thread_rejects_unknown_command_kind_without_emitting_an_acceptance_event() -> None:
    service = _service()
    command = {
        "schema": "capstone-command/1", "command_id": "cmd_unknown_001",
        "idempotency_key": "idem_unknown_001", "thread_id": "thr_demo_39",
        "run_id": "run_001", "kind": "execute_shell", "expected_event_seq": 0,
        "payload": {"command": "echo unsafe"},
    }
    receipt = service.submit_command(command)

    assert receipt.status == "rejected"
    assert receipt.rejection == "unsupported_command"
    assert service.snapshot("thr_demo_39").last_event_seq == 0


def test_thread_rejects_message_without_nonempty_text() -> None:
    service = _service()
    command = {
        "schema": "capstone-command/1", "command_id": "cmd_empty_001",
        "idempotency_key": "idem_empty_001", "thread_id": "thr_demo_39",
        "run_id": "run_001", "kind": "send_ordinary", "expected_event_seq": 0,
        "payload": {"text": "   "},
    }

    receipt = service.submit_command(command)

    assert receipt.status == "rejected"
    assert receipt.rejection == "message_text_required"
    assert service.read_events("thr_demo_39", 0).events == ()


def test_thread_rejects_non_json_command_payload_as_protocol_error() -> None:
    service = _service()
    command = {
        "schema": "capstone-command/1", "command_id": "cmd_bad_json_001",
        "idempotency_key": "idem_bad_json_001", "thread_id": "thr_demo_39",
        "run_id": "run_001", "kind": "send_ordinary", "expected_event_seq": 0,
        "payload": {"text": object()},
    }

    from capstone_agent.thread_protocol import ThreadProtocolError

    import pytest
    with pytest.raises(ThreadProtocolError, match="not JSON"):
        service.submit_command(command)
