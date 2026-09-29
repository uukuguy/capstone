from __future__ import annotations

import os
import uuid

import psycopg
import pytest

from capstone_agent.thread_service import PostgresThreadService, ThreadResyncRequired
from capstone_agent.thread_protocol import ThreadSnapshot


@pytest.fixture
def postgres_thread_service() -> tuple[PostgresThreadService, str]:
    dsn = os.environ.get("CAPSTONE_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("CAPSTONE_TEST_DATABASE_URL is required")
    service = PostgresThreadService(dsn)
    service.initialize()
    thread_id = "thr_test_" + uuid.uuid4().hex[:16]
    yield service, thread_id
    with psycopg.connect(dsn) as connection:
        connection.execute("DELETE FROM capstone_threads WHERE thread_id = %s", (thread_id,))


def _snapshot(thread_id: str) -> ThreadSnapshot:
    return ThreadSnapshot.from_document({
        "schema": "capstone-thread-snapshot/1", "thread_id": thread_id,
        "run": {"run_id": "run_test_001", "state": "open"},
        "active_model_context": {
            "id": "ctx_ieee39_7", "model_id": "ieee39", "model_revision": "7",
            "implementation_family": "pandapower", "selection_revision": "sel_2",
        },
        "active_grid_page_id": "page_ieee39", "current_attempt": None,
        "last_event_seq": 0, "base_event_seq": 0,
    })


def _command(thread_id: str) -> dict[str, object]:
    return {
        "schema": "capstone-command/1", "command_id": "cmd_test_001",
        "idempotency_key": "idem_test_001", "thread_id": thread_id,
        "run_id": "run_test_001", "kind": "send_ordinary",
        "expected_event_seq": 0, "payload": {"text": "hello"},
    }


def test_postgres_thread_store_persists_snapshot_events_and_receipts(
    postgres_thread_service: tuple[PostgresThreadService, str],
) -> None:
    service, thread_id = postgres_thread_service
    service.create_thread(_snapshot(thread_id))

    accepted = service.submit_command(_command(thread_id))
    assert accepted.status == "accepted"
    assert service.submit_command(_command(thread_id)) == accepted
    assert service.snapshot(thread_id).last_event_seq == 1
    page = service.read_events(thread_id, 0)
    assert page.next_event_seq == 1
    assert page.events[0].event_type == "command_accepted"

    service.compact_before(thread_id, 1)
    with pytest.raises(ThreadResyncRequired):
        service.read_events(thread_id, 0)
