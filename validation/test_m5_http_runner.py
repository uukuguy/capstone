from __future__ import annotations

import httpx
import pytest

from capstone_agent.thread_protocol import EventPage, ThreadSnapshot
from validation.thread.http_runner import HttpThreadSession, ThreadResyncRequired, wait_for_terminal


def _snapshot() -> dict[str, object]:
    return {
        "schema": "capstone-thread-snapshot/1", "thread_id": "thr_demo_39",
        "run": {"run_id": "run_001", "state": "open"},
        "active_model_context": {
            "id": "ctx_ieee39_7", "model_id": "ieee39", "model_revision": "7",
            "implementation_family": "pandapower", "selection_revision": "sel_2",
        },
        "active_grid_page_id": "page_ieee39", "current_attempt": None,
        "last_event_seq": 0, "base_event_seq": 0,
    }


def _catalog() -> dict[str, object]:
    return {"schema": "capstone-thread-catalog/1", "models": [], "profiles": []}


def test_http_session_parses_typed_documents_and_sends_scoped_auth() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "POST" and request.url.path == "/api/v1/threads":
            return httpx.Response(201, json=_snapshot())
        if request.method == "GET" and request.url.path == "/api/v1/threads/thr_demo_39":
            return httpx.Response(200, json=_snapshot())
        if request.url.path.endswith("/catalog"):
            return httpx.Response(200, json=_catalog())
        if request.url.path.endswith("/events"):
            return httpx.Response(200, json={
                "schema": "capstone-thread-events/1", "thread_id": "thr_demo_39",
                "after_event_seq": 0, "next_event_seq": 0, "has_more": False, "events": [],
            })
        if request.method == "POST" and request.url.path.endswith("/commands"):
            return httpx.Response(202, json={
                "schema": "capstone-command-receipt/1", "command_id": "cmd_001",
                "idempotency_key": "idem_001", "thread_id": "thr_demo_39", "run_id": "run_001",
                "status": "accepted", "accepted_event_seq": 1,
            })
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        session = HttpThreadSession("http://localhost", "operator-secret", client=client)
        snapshot = session.create()
        assert snapshot.thread_id == "thr_demo_39"
        assert session.catalog().models == ()
        assert session.events().next_event_seq == 0
        receipt = session.command("send_ordinary", {"text": "hello"}, command_id="cmd_001", idempotency_key="idem_001")
        assert receipt.status == "accepted"
    assert seen[0].headers["authorization"] == "Bearer operator-secret"
    assert all(request.url.host == "localhost" for request in seen)


def test_http_session_rejects_resync_as_a_typed_recovery_signal() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"error": "resync_required", "base_event_seq": 3, "snapshot": _snapshot()})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        session = HttpThreadSession("http://localhost", "secret", client=client, thread_id="thr_demo_39")
        with pytest.raises(ThreadResyncRequired) as error:
            session.events(after=0)
    assert error.value.snapshot.thread_id == "thr_demo_39"


def test_http_session_rejects_receipt_identity_mismatch() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/api/v1/threads/thr_demo_39":
            return httpx.Response(200, json=_snapshot())
        return httpx.Response(202, json={
            "schema": "capstone-command-receipt/1", "command_id": "other",
            "idempotency_key": "idem_001", "thread_id": "thr_demo_39", "status": "accepted",
        })

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        session = HttpThreadSession("http://localhost", "secret", client=client, thread_id="thr_demo_39", run_id="run_001")
        with pytest.raises(RuntimeError, match="receipt identity"):
            session.command("send_ordinary", {"text": "hello"}, command_id="cmd_001", idempotency_key="idem_001")


def test_http_session_rejects_run_identity_change_after_create() -> None:
    changed = _snapshot()
    changed["run"] = {"run_id": "run_other", "state": "open"}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/api/v1/threads":
            return httpx.Response(201, json=_snapshot())
        return httpx.Response(200, json=changed)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        session = HttpThreadSession("http://localhost", "secret", client=client)
        session.create()
        with pytest.raises(RuntimeError, match="run identity"):
            session.snapshot()


def test_wait_for_terminal_requires_matching_terminal_event() -> None:
    document = _snapshot()
    document["current_attempt"] = {
        "turn_id": "turn_001", "attempt_id": "attempt_001", "phase": "running",
        "target_model_context_id": "ctx_ieee39_7",
    }
    snapshot = ThreadSnapshot.from_document(document)

    class _NoTerminalSession:
        def snapshot(self) -> ThreadSnapshot:
            return snapshot

        def events(self, *, after: int = 0) -> EventPage:
            return EventPage.from_document({
                "schema": "capstone-thread-events/1", "thread_id": "thr_demo_39",
                "after_event_seq": after, "next_event_seq": after, "has_more": False, "events": [],
            }, expected_after_seq=after)

    with pytest.raises(TimeoutError, match="did not reach"):
        wait_for_terminal(_NoTerminalSession(), timeout_seconds=0.01)  # type: ignore[arg-type]
