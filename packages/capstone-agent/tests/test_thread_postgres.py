from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from unittest.mock import MagicMock

import psycopg
import pytest

from capstone_agent.thread_service import PostgresThreadService, ThreadResyncRequired
from capstone_agent.thread_protocol import CommandReceipt, ThreadSnapshot
from capstone_agent.thread_application_transition import (
    ApplicationEvent,
    ThreadApplicationTransition,
    application_transition_hash,
)


@pytest.fixture
def postgres_thread_service() -> Generator[tuple[PostgresThreadService, str], None, None]:
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


@pytest.mark.parametrize("same_hash", [True, False])
def test_postgres_application_transition_rechecks_idempotency_under_thread_lock(
    monkeypatch: pytest.MonkeyPatch, same_hash: bool,
) -> None:
    thread_id = "thr_fake_transition"
    transition = ThreadApplicationTransition(
        command={
            "schema": "capstone-command/1", "command_id": "cmd_fake_transition",
            "idempotency_key": "idem_fake_transition", "thread_id": thread_id,
            "run_id": "run_fake_transition", "kind": "case_execution_created",
            "expected_event_seq": 0, "payload": {"case_id": "demo"},
        },
        state={"case_execution": {"case_id": "demo", "status": "running"}},
        events=(),
    )
    stored_receipt = CommandReceipt(
        command_id="cmd_fake_transition", idempotency_key="idem_fake_transition",
        thread_id=thread_id, run_id="run_fake_transition", status="accepted",
        accepted_event_seq=None, rejection=None, target=None,
    )
    existing_row = {
        "request_hash": application_transition_hash(transition) if same_hash else "different",
        "receipt": stored_receipt.to_document(),
    }

    def result(row: object) -> MagicMock:
        cursor = MagicMock()
        cursor.fetchone.return_value = row
        return cursor

    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.execute.side_effect = [
        result(None),
        result({"thread_id": thread_id}),
        result(existing_row),
    ]
    service = PostgresThreadService("fake-dsn")
    monkeypatch.setattr(service, "_connect", lambda: connection)
    monkeypatch.setattr(
        service, "_snapshot_from_row",
        lambda _row: pytest.fail("admission ran after the locked idempotency hit"),
    )

    receipt = service.apply_application_transition(transition)
    expected = stored_receipt if same_hash else service._receipt(
        transition.command, status="rejected", rejection="idempotency_conflict",
    )
    assert receipt == expected
    calls = connection.execute.call_args_list
    assert len(calls) == 3
    assert "FOR UPDATE" in calls[1][0][0]
    assert "idempotency_key" in calls[2][0][0]


def test_postgres_application_transition_rejects_existing_command_without_duplicate_insert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    thread_id = "thr_fake_command_conflict"
    transition = ThreadApplicationTransition(
        command={
            "schema": "capstone-command/1", "command_id": "cmd_existing",
            "idempotency_key": "idem_new", "thread_id": thread_id,
            "run_id": "run_fake", "kind": "case_execution_created",
            "expected_event_seq": 0, "payload": {"case_id": "demo"},
        },
        state={"case_execution": {"case_id": "demo", "status": "running"}},
        events=(),
    )

    def result(row: object) -> MagicMock:
        cursor = MagicMock()
        cursor.fetchone.return_value = row
        return cursor

    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.execute.side_effect = [
        result(None), result({"thread_id": thread_id}), result(None), result({"exists": 1}),
    ]
    service = PostgresThreadService("fake-dsn")
    monkeypatch.setattr(service, "_connect", lambda: connection)
    monkeypatch.setattr(service, "_snapshot_from_row", lambda _row: _snapshot(thread_id))

    receipt = service.apply_application_transition(transition)
    assert receipt.rejection == "command_id_conflict"
    assert len(connection.execute.call_args_list) == 4


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
    assert claim.model_context == _snapshot(thread_id).active_model_context

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


@pytest.mark.parametrize("damage", ["missing", "drift"])
def test_postgres_context_integrity_fails_closed_before_runtime_claim(
    postgres_thread_service: tuple[PostgresThreadService, str], damage: str,
) -> None:
    service, thread_id = postgres_thread_service
    service.create_thread(_snapshot(thread_id))
    service.submit_command(_command(thread_id))
    with psycopg.connect(service.dsn) as connection:
        if damage == "missing":
            connection.execute(
                "UPDATE capstone_thread_attempts SET model_context_snapshot = NULL WHERE thread_id = %s",
                (thread_id,),
            )
        else:
            connection.execute(
                "UPDATE capstone_threads SET model_revision = 'changed' WHERE thread_id = %s",
                (thread_id,),
            )
    fresh = PostgresThreadService(service.dsn)
    assert fresh.claim_attempt("thread-worker", lease_seconds=30) is None
    assert fresh.snapshot(thread_id).current_attempt is None
    event = fresh.read_events(thread_id, 0).events[-1]
    assert event.event_type == "attempt_interrupted"
    assert event.payload["reason"] == "model_context_snapshot_unavailable"


def test_postgres_application_transition_reconstructs_state_and_is_idempotent(
    postgres_thread_service: tuple[PostgresThreadService, str],
) -> None:
    service, thread_id = postgres_thread_service
    service.create_thread(_snapshot(thread_id))
    transition = ThreadApplicationTransition(
        command={
            "schema": "capstone-command/1", "command_id": "cmd_case_1",
            "idempotency_key": "idem_case_1", "thread_id": thread_id,
            "run_id": "run_test_001", "kind": "case_execution_created",
            "expected_event_seq": 0, "payload": {"case_id": "demo"},
        },
        state={"case_execution": {"case_id": "demo", "status": "running"}},
        events=(ApplicationEvent("case_execution_created", {"case_id": "demo"}),),
    )
    accepted = service.apply_application_transition(transition)
    assert accepted.status == "accepted"
    assert service.apply_application_transition(transition) == accepted

    state_conflict = ThreadApplicationTransition(
        command=transition.command,
        state={"case_execution": {"case_id": "demo", "status": "completed"}},
        events=transition.events,
    )
    assert service.apply_application_transition(state_conflict).rejection == "idempotency_conflict"

    events_conflict = ThreadApplicationTransition(
        command=transition.command,
        state=transition.state,
        events=(ApplicationEvent("case_execution_changed", {"case_id": "demo"}),),
    )
    assert service.apply_application_transition(events_conflict).rejection == "idempotency_conflict"

    fresh = PostgresThreadService(service.dsn)
    assert fresh.snapshot(thread_id).application_state == transition.state
    assert fresh.read_events(thread_id, 0).events[-1].event_type == "case_execution_created"
