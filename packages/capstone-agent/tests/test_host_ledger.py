from __future__ import annotations

import os
import hashlib
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

from capstone_agent.ledger import Conflict, Ledger
from capstone_agent.protocol import Frame


@pytest.fixture
def ledger() -> Ledger:
    dsn = os.environ.get("CAPSTONE_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("CAPSTONE_TEST_DATABASE_URL is required")
    store = Ledger(dsn)
    store.initialize()
    with psycopg.connect(dsn) as connection:
        connection.execute("TRUNCATE session_events, session_commands, sessions CASCADE")
    return store


def test_session_turn_idempotency_and_cross_connection_reads(ledger: Ledger) -> None:
    session = ledger.create_session("fixture-app", "scripted-demo", "fixture-case", None, None)
    assert session.session_id.startswith("session-")
    assert session.state == "pending"
    assert Ledger(ledger.dsn).get_session(session.session_id) == session

    lease = ledger.claim_pending("worker-one", 30)
    assert lease is not None and lease.session_id == session.session_id
    assert ledger.claim_pending("worker-two", 30) is None
    ledger.append_event(session.session_id, lease.lease_token,
                        Frame(session.session_id, 1, "ready", {"run_id": "run-test"}))
    first = ledger.accept_turn(session.session_id, "first instruction", "retry-key-1")
    assert first.ordinal == 1 and first.state == "pending"
    assert ledger.accept_turn(session.session_id, "first instruction", "retry-key-1") == first
    with pytest.raises(Conflict):
        ledger.accept_turn(session.session_id, "changed instruction", "retry-key-1")
    with pytest.raises(Conflict):
        ledger.accept_turn(session.session_id, "overlap", "retry-key-2")

    frame = Frame(session.session_id, 2, "answer_committed", {
        "ordinal": 1, "turn_id": "run-test-t001", "answer_output": "done",
        "answer_ref": "answer:one", "result_refs": [], "evidence_refs": [],
    })
    ledger.append_event(session.session_id, lease.lease_token, frame)
    assert [(event.sequence, event.kind) for event in
            Ledger(ledger.dsn).events_after(session.session_id, 1)] == [(2, "answer_committed")]
    assert ledger.accept_turn(session.session_id, "second instruction", "retry-key-2").ordinal == 2


def test_session_creation_idempotency_reuses_run_and_rejects_different_case(ledger: Ledger) -> None:
    first = ledger.create_session("fixture-app", "scripted-demo", "case-one", None, None,
                                  idempotency_key="browser-tab-case-key")
    repeated = Ledger(ledger.dsn).create_session(
        "fixture-app", "scripted-demo", "case-one", None, None,
        idempotency_key="browser-tab-case-key",
    )
    assert repeated.session_id == first.session_id
    with pytest.raises(Conflict):
        ledger.create_session("fixture-app", "scripted-demo", "case-two", None, None,
                              idempotency_key="browser-tab-case-key")


@pytest.mark.parametrize("public_demo", [False, True])
def test_session_creation_scope_survives_restart_and_isolates_keys(ledger: Ledger, public_demo: bool) -> None:
    args = ("fixture-app", "scripted-demo", "case-one", None, None)
    record = ledger.create_session(*args, idempotency_key="scoped-key", public_demo=public_demo)
    fresh = Ledger(ledger.dsn)
    assert fresh.get_session(record.session_id).public_demo is public_demo
    assert fresh.create_session(*args, idempotency_key="scoped-key", public_demo=public_demo) == record
    with pytest.raises(Conflict):
        fresh.create_session(*args, idempotency_key="scoped-key", public_demo=not public_demo)
    if not public_demo:
        with psycopg.connect(ledger.dsn) as connection:
            stored = connection.execute("SELECT create_hash FROM sessions WHERE session_id = %s",
                                        (record.session_id,)).fetchone()[0]
        assert stored == hashlib.sha256(repr(args).encode()).hexdigest()


def test_stale_lease_interrupts_without_discarding_committed_events(ledger: Ledger) -> None:
    session = ledger.create_session("fixture-app", "scripted-demo", None, None, None)
    lease = ledger.claim_pending("worker-one", 30)
    assert lease is not None
    ledger.append_event(session.session_id, lease.lease_token,
                        Frame(session.session_id, 1, "ready", {"run_id": "run-stale"}))
    future = datetime.now(timezone.utc) + timedelta(seconds=31)
    assert ledger.mark_interrupted_stale(now=future) == 1
    assert ledger.get_session(session.session_id).state == "interrupted"
    assert ledger.events_after(session.session_id, 0)[0].kind == "ready"
    with pytest.raises(Conflict):
        ledger.accept_turn(session.session_id, "late turn", "late-key")


def test_idle_timeout_interrupts_only_ready_session_without_pending_command(ledger: Ledger) -> None:
    session = ledger.create_session("fixture-app", "scripted-demo", None, None, None)
    claim = ledger.claim_pending("worker-one", 30)
    assert claim is not None and claim.lease_token is not None
    assert not ledger.mark_interrupted_idle(session.session_id, claim.lease_token)
    ledger.append_event(session.session_id, claim.lease_token,
                        Frame(session.session_id, 1, "ready", {"run_id": "run-idle"}))
    ledger.accept_turn(session.session_id, "first instruction", "key-1")
    assert not ledger.mark_interrupted_idle(session.session_id, claim.lease_token)
    ledger.append_event(session.session_id, claim.lease_token,
                        Frame(session.session_id, 2, "answer_committed", {
                            "ordinal": 1, "turn_id": "turn-one", "answer_output": "done",
                            "answer_ref": "answer:one", "result_refs": [], "evidence_refs": [],
                        }))
    assert ledger.mark_interrupted_idle(session.session_id, claim.lease_token)
    result = ledger.get_session(session.session_id)
    assert result is not None
    assert result.state == "interrupted"
    assert result.error_code == "session_idle_timeout"
    assert result.completed_turns == 1
    assert [event.kind for event in ledger.events_after(session.session_id, 0)] == [
        "ready", "answer_committed",
    ]
    with pytest.raises(Conflict):
        ledger.accept_turn(session.session_id, "late instruction", "key-2")


def test_disconnect_releases_session_and_is_idempotent(ledger: Ledger) -> None:
    session = ledger.create_session("fixture-app", "scripted-demo", None, None, None)
    claim = ledger.claim_pending("worker-one", 30)
    assert claim is not None and claim.lease_token is not None
    ledger.append_event(session.session_id, claim.lease_token,
                        Frame(session.session_id, 1, "ready", {"run_id": "run-disconnect"}))
    disconnected = ledger.disconnect_session(session.session_id, "disconnect-key")
    assert disconnected.state == "interrupted"
    assert disconnected.error_code == "session_disconnected"
    assert disconnected.lease_token is None
    assert ledger.disconnect_session(session.session_id, "disconnect-key") == disconnected
    with pytest.raises(Conflict):
        ledger.disconnect_session(session.session_id, "another-key")
    with pytest.raises(Conflict):
        ledger.accept_turn(session.session_id, "late instruction", "late-key")


def test_capacity_eviction_selects_longest_idle_ready_session(ledger: Ledger) -> None:
    first = ledger.create_session("fixture-app", "scripted-demo", None, None, None)
    second = ledger.create_session("fixture-app", "scripted-demo", None, None, None)
    first_claim = ledger.claim_pending("worker-one", 30)
    second_claim = ledger.claim_pending("worker-one", 30)
    assert first_claim is not None and first_claim.lease_token is not None
    assert second_claim is not None and second_claim.lease_token is not None
    ledger.append_event(first.session_id, first_claim.lease_token,
                        Frame(first.session_id, 1, "ready", {"run_id": "run-first"}))
    ledger.append_event(second.session_id, second_claim.lease_token,
                        Frame(second.session_id, 1, "ready", {"run_id": "run-second"}))
    ledger.accept_turn(first.session_id, "first instruction", "key-1")
    ledger.append_event(first.session_id, first_claim.lease_token,
                        Frame(first.session_id, 2, "answer_committed", {
                            "ordinal": 1, "turn_id": "turn-first", "answer_output": "done",
                            "answer_ref": "answer:first", "result_refs": [], "evidence_refs": [],
                        }))
    assert Ledger(ledger.dsn).evict_oldest_idle(minimum_idle_seconds=0,
                                                minimum_wait_seconds=0) is None
    waiting = ledger.create_session("fixture-app", "scripted-demo", None, None, None)
    assert ledger.evict_oldest_idle(minimum_wait_seconds=0) is None
    assert ledger.evict_oldest_idle(minimum_idle_seconds=0,
                                    minimum_wait_seconds=0) == second.session_id
    assert ledger.get_session(second.session_id).error_code == "session_capacity_evicted"
    assert ledger.get_session(first.session_id).completed_turns == 1
    assert ledger.get_session(waiting.session_id).state == "pending"
    assert Ledger(ledger.dsn).evict_oldest_idle(minimum_idle_seconds=0,
                                                minimum_wait_seconds=0) is None
