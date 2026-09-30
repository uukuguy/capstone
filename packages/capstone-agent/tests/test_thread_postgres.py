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


def test_postgres_thread_store_leases_and_completes_one_attempt(
    postgres_thread_service: tuple[PostgresThreadService, str],
) -> None:
    service, thread_id = postgres_thread_service
    service.create_thread(_snapshot(thread_id))

    accepted = service.submit_command(_command(thread_id))
    assert accepted.target is not None
    claim = service.claim_attempt("thread-worker", lease_seconds=30)
    assert claim is not None
    assert claim.attempt.phase == "running"

    event = service.append_runtime_event(
        claim, event_type="assistant_text_delta", payload={"text": "running"},
    )
    assert event.event_seq == 3
    completed = service.finish_attempt(
        claim, phase="completed", payload={"answer": "done"},
    )

    assert completed.current_attempt is None
    assert completed.last_event_seq == 4
    assert [item.event_type for item in service.read_events(thread_id, 0).events] == [
        "command_accepted", "attempt_started", "assistant_text_delta", "attempt_completed",
    ]


def test_postgres_thread_store_interrupts_expired_attempt(
    postgres_thread_service: tuple[PostgresThreadService, str],
) -> None:
    service, thread_id = postgres_thread_service
    service.create_thread(_snapshot(thread_id))
    service.submit_command(_command(thread_id))
    claim = service.claim_attempt("thread-worker", lease_seconds=30)
    assert claim is not None

    with psycopg.connect(service.dsn) as connection:
        connection.execute(
            "UPDATE capstone_thread_attempts SET lease_deadline = clock_timestamp() - interval '1 second' WHERE attempt_id = %s",
            (claim.attempt.attempt_id,),
        )

    assert service.interrupt_expired_attempts() == 1
    assert service.snapshot(thread_id).current_attempt is None
    assert service.read_events(thread_id, 0).events[-1].event_type == "attempt_interrupted"
