from __future__ import annotations

import os
import uuid
import json
from collections.abc import Generator
from unittest.mock import MagicMock

import psycopg
import pytest

from capstone_agent.thread_service import PostgresThreadService, ThreadResyncRequired, ThreadModelDescriptor
from capstone_model_capability_spi import ModelCapabilitySelection
from capstone_agent.thread_protocol import CommandReceipt, ThreadSnapshot
from capstone_agent.network_diagram import MAX_EVENT_PAGE_BYTES, normalize_network_diagram
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


def test_model_preparation_survives_restart_and_fences_newer_requests(postgres_thread_service):
    service, thread_id = postgres_thread_service
    service.create_thread(_snapshot(thread_id))
    service.request_model_preparation(thread_id)
    restarted = PostgresThreadService(service.dsn)
    assert restarted.claim_model_preparation("pypsa") is None
    snapshot, generation, lease = restarted.claim_model_preparation("pandapower")
    assert snapshot.thread_id == thread_id
    assert snapshot.current_attempt is None
    assert restarted.claim_model_preparation("pandapower") is None
    service.request_model_preparation(thread_id)
    restarted.finish_model_preparation(thread_id, generation, lease, succeeded=True)
    assert service.has_pending_model_preparation("pandapower")
    snapshot, generation, lease = service.claim_model_preparation("pandapower")
    service.finish_model_preparation(thread_id, generation, lease, succeeded=True)
    assert not service.has_pending_model_preparation("pandapower")
    assert service.read_events(thread_id, 0).events == ()


@pytest.mark.parametrize("pending_kind", ["model", "selection"])
def test_pending_model_preparation_identity_is_used_by_first_instruction(postgres_thread_service, pending_kind):
    from test_task_recognition import pending_snapshot
    service, thread_id = postgres_thread_service
    before = pending_snapshot(_snapshot(thread_id), pending_kind)
    service.create_thread(before)
    service.request_model_preparation(thread_id)
    prepared, generation, lease = service.claim_model_preparation()
    assert prepared.active_model_context != before.active_model_context
    assert prepared.current_attempt is None
    service.finish_model_preparation(thread_id, generation, lease, succeeded=True)
    assert service.submit_command(_command(thread_id)).status == "accepted"
    claim = service.claim_attempt("worker", 30)
    assert claim.model_context == prepared.active_model_context


def test_worker_drains_more_than_one_preparation_batch_without_another_wake(postgres_thread_service):
    from dataclasses import replace
    from threading import Event, Thread
    from capstone_agent.thread_worker import serve_thread_attempts
    service, thread_id = postgres_thread_service
    stop, wake = Event(), Event()
    ids = [thread_id + "_" + str(index) for index in range(5)]
    seen = []

    class Factory:
        def __call__(self, claim):
            pytest.fail("preparation must not execute a task")

        def prepare_model(self, snapshot):
            seen.append(snapshot.thread_id)
            if len(seen) == 5:
                stop.set()

    try:
        for index, identity in enumerate(ids):
            snapshot = _snapshot(identity)
            service.create_thread(replace(snapshot, run=replace(snapshot.run, run_id="run_" + identity[4:])))
            service.request_model_preparation(identity)
        worker = Thread(target=serve_thread_attempts, args=(service, Factory()),
                        kwargs={"stop_event": stop, "wake_event": wake, "implementation_family": "pandapower"})
        worker.start()
        worker.join(5)
        assert not worker.is_alive()
        assert set(seen) == set(ids)
    finally:
        stop.set()
        wake.set()
        if "worker" in locals():
            worker.join(2)
        with psycopg.connect(service.dsn) as connection:
            connection.execute("DELETE FROM capstone_threads WHERE thread_id = ANY(%s)", (ids,))


def test_worker_recovers_failed_preparation_without_another_wake(postgres_thread_service):
    from threading import Event, Thread
    from capstone_agent.thread_worker import serve_thread_attempts
    service, thread_id = postgres_thread_service
    service.create_thread(_snapshot(thread_id))
    service.request_model_preparation(thread_id)
    stop, wake = Event(), Event()
    seen = []

    class Factory:
        def __call__(self, claim):
            pytest.fail("preparation must not execute a task")

        def prepare_model(self, snapshot):
            seen.append(snapshot.thread_id)
            if len(seen) == 1:
                raise RuntimeError("transient preparation failure")
            stop.set()

    worker = Thread(target=serve_thread_attempts, args=(service, Factory()),
                    kwargs={"stop_event": stop, "wake_event": wake, "implementation_family": "pandapower"})
    try:
        worker.start()
        worker.join(8)
        assert not worker.is_alive()
        assert seen == [thread_id, thread_id]
        assert not service.has_pending_model_preparation("pandapower")
    finally:
        stop.set()
        wake.set()
        worker.join(2)


def test_expired_preparation_lease_is_reclaimed_and_old_ack_is_fenced(postgres_thread_service):
    service, thread_id = postgres_thread_service
    service.create_thread(_snapshot(thread_id))
    service.request_model_preparation(thread_id)
    _, generation, old_lease = service.claim_model_preparation()
    with psycopg.connect(service.dsn) as connection:
        connection.execute("UPDATE capstone_model_preparations SET lease_until = now() - interval '1 second' WHERE thread_id = %s", (thread_id,))
    _, new_generation, new_lease = PostgresThreadService(service.dsn).claim_model_preparation()
    service.finish_model_preparation(thread_id, generation, old_lease, succeeded=True)
    assert service.has_pending_model_preparation()
    service.finish_model_preparation(thread_id, new_generation, new_lease, succeeded=True)
    assert not service.has_pending_model_preparation()


def test_pending_identity_freeze_holds_thread_lock_against_a_new_selection(postgres_thread_service, monkeypatch):
    from dataclasses import replace
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from test_task_recognition import pending_snapshot
    service, thread_id = postgres_thread_service
    before = pending_snapshot(_snapshot(thread_id), "selection")
    service.create_thread(before)
    service.request_model_preparation(thread_id)
    entered, release, writing = Event(), Event(), Event()
    original = PostgresThreadService._pending_preparation_context

    def freeze(connection, snapshot):
        entered.set()
        assert release.wait(3)
        return original(connection, snapshot)

    monkeypatch.setattr(PostgresThreadService, "_pending_preparation_context", staticmethod(freeze))

    def change_selection():
        writing.set()
        pending = replace(before.pending_selection, command_id="cmd_new_selection")
        with psycopg.connect(service.dsn) as connection:
            from psycopg.types.json import Jsonb
            connection.execute("UPDATE capstone_threads SET pending_selection = %s WHERE thread_id = %s",
                               (Jsonb(pending.to_document()), thread_id))
        service.request_model_preparation(thread_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        preparing = pool.submit(service.claim_model_preparation)
        assert entered.wait(1)
        changing = pool.submit(change_selection)
        assert writing.wait(1)
        assert not changing.done()
        release.set()
        first, generation, lease = preparing.result()
        changing.result()
    service.finish_model_preparation(thread_id, generation, lease, succeeded=True)
    second, generation, lease = service.claim_model_preparation()
    service.finish_model_preparation(thread_id, generation, lease, succeeded=True)
    assert service.submit_command(_command(thread_id)).status == "accepted"
    assert service.claim_attempt("worker", 30).model_context == second.active_model_context


def test_postgres_task_decision_survives_restart_and_compaction(postgres_thread_service):
    from capstone_agent.task_recognition import accept_task
    from capstone_agent.task_understanding import recognize_decision
    from test_task_recognition import proposal
    service, thread_id = postgres_thread_service
    service.create_thread(_snapshot(thread_id))
    service.submit_command(_command(thread_id))
    claim = service.claim_attempt("worker", 30)
    task = accept_task(service, claim,
                       lambda bound, **kwargs: recognize_decision(bound.task_request, proposal(), recognizer="controlled"),
                       on_heartbeat=lambda: None)
    changed = task.task_understanding.to_document()
    changed["answer_policy"]["scale"] = "detailed"
    with pytest.raises(Exception, match="immutable"):
        service.append_runtime_event(task, event_type="task_understanding_created", payload={"understanding": changed})
    snapshot = service.finish_attempt(task, phase="failed", payload={"error_code": "controlled_failure"})
    service.compact_before(thread_id, snapshot.last_event_seq)
    restarted = PostgresThreadService(service.dsn)
    command = {**_command(thread_id), "command_id": "cmd_retry", "idempotency_key": "idem_retry",
               "kind": "retry_new_attempt", "expected_event_seq": snapshot.last_event_seq,
               "payload": {"attempt_id": claim.attempt.attempt_id}}
    assert restarted.submit_command(command).status == "accepted"
    replay = restarted.claim_attempt("worker", 30)
    assert replay.task_understanding == task.task_understanding
    assert replay.task_request == task.task_request
    assert replay.task_certification == "recognized"
    assert replay.attempt.attempt_id != replay.task_request.attempt_id


@pytest.mark.parametrize("failure", ["request_write", "cancel_before_request"])
def test_postgres_current_retry_never_bypasses_missing_request(postgres_thread_service, failure):
    from capstone_agent.task_recognition import accept_task, TaskRecognitionFailed, TaskRecognitionCancelled
    from capstone_agent.task_understanding import recognize_decision
    from test_task_recognition import proposal
    service, thread_id = postgres_thread_service
    service.create_thread(_snapshot(thread_id))
    service.submit_command(_command(thread_id))
    claim = service.claim_attempt("worker", 30)
    append = service.append_runtime_event
    if failure == "request_write":
        def fail(bound, *, event_type, **kwargs):
            if event_type == "task_request_created":
                raise OSError("controlled ledger failure")
            return append(bound, event_type=event_type, **kwargs)
        service.append_runtime_event = fail
        error_type = TaskRecognitionFailed
        phase = "failed"
    else:
        service.cancel_requested = lambda bound: True
        error_type = TaskRecognitionCancelled
        phase = "cancelled"
    with pytest.raises(error_type):
        accept_task(service, claim, lambda *args, **kwargs: pytest.fail("recognizer must not run"), on_heartbeat=lambda: None)
    service.append_runtime_event = append
    service.finish_attempt(claim, phase=phase, payload={"error_code": "controlled"})
    restarted = PostgresThreadService(service.dsn)
    later = {**_command(thread_id), "command_id": "cmd_later", "idempotency_key": "idem_later",
             "expected_event_seq": restarted.snapshot(thread_id).last_event_seq, "payload": {"text": "later instruction"}}
    assert restarted.submit_command(later).status == "accepted"
    later_claim = restarted.claim_attempt("worker", 30)
    restarted.finish_attempt(later_claim, phase="completed", payload={"answer": "later answer"})
    retry_command = {**_command(thread_id), "command_id": "cmd_retry", "idempotency_key": "idem_retry",
                     "kind": "retry_new_attempt", "expected_event_seq": restarted.snapshot(thread_id).last_event_seq,
                     "payload": {"attempt_id": claim.attempt.attempt_id}}
    assert restarted.submit_command(retry_command).status == "accepted"
    replay = restarted.claim_attempt("worker", 30)
    assert replay.task_certification == "pending"
    assert replay.task_request == claim.task_request
    assert replay.task_history == claim.task_history is None
    recognized = accept_task(restarted, replay,
                            lambda bound, **kwargs: recognize_decision(bound.task_request, proposal(), recognizer="controlled"),
                            on_heartbeat=lambda: None)
    assert recognized.task_certification == "recognized"


def test_postgres_historical_unmarked_retry_stays_uncertified(postgres_thread_service):
    service, thread_id = postgres_thread_service
    service.create_thread(_snapshot(thread_id))
    service.submit_command(_command(thread_id))
    with psycopg.connect(service.dsn) as connection:
        connection.execute("UPDATE capstone_thread_events SET payload = payload - 'task_recognition' WHERE thread_id = %s", (thread_id,))
    claim = service.claim_attempt("worker", 30)
    snapshot = service.finish_attempt(claim, phase="failed", payload={"error_code": "old_failure"})
    retry_command = {**_command(thread_id), "command_id": "cmd_retry", "idempotency_key": "idem_retry",
                     "kind": "retry_new_attempt", "expected_event_seq": snapshot.last_event_seq,
                     "payload": {"attempt_id": claim.attempt.attempt_id}}
    assert service.submit_command(retry_command).status == "accepted"
    replay = service.claim_attempt("worker", 30)
    assert replay.task_certification == "legacy_uncertified"
    assert replay.task_request is None


@pytest.mark.parametrize("kind", ["send_auto", "send_ordinary", "send_professional"])
@pytest.mark.parametrize("state", ["selection", "model"])
def test_postgres_oversized_instruction_preserves_pending_state(postgres_thread_service, kind, state):
    from test_task_recognition import pending_snapshot
    service, thread_id = postgres_thread_service
    snapshot = pending_snapshot(_snapshot(thread_id), state)
    service.create_thread(snapshot)
    receipt = service.submit_command({**_command(thread_id), "kind": kind, "payload": {"text": "x" * 16385}})
    assert receipt.status == "rejected"
    assert receipt.rejection == "message_text_too_large"
    assert service.snapshot(thread_id) == snapshot
    assert service.read_events(thread_id, 0).events == ()


def test_postgres_unbounded_pending_revision_rejected_before_activation(postgres_thread_service):
    from dataclasses import replace
    from test_task_recognition import pending_snapshot
    service, thread_id = postgres_thread_service
    snapshot = pending_snapshot(_snapshot(thread_id), "model")
    snapshot = replace(snapshot, pending_model_switch=replace(snapshot.pending_model_switch, model_revision="r" * 513))
    service.create_thread(snapshot)
    receipt = service.submit_command(_command(thread_id))
    assert receipt.rejection == "task_context_invalid"
    assert service.snapshot(thread_id) == snapshot
    assert service.read_events(thread_id, 0).events == ()


class _ToolsCatalog:
    def resolve(self, model, selection=None):
        if selection is None:
            return ModelCapabilitySelection.empty()
        expected = "static-analysis" if model.implementation_family == "pandapower" else "operations"
        if any(profile_id != expected or version != "1.0.0" for profile_id, version in selection.enabled_profiles):
            raise ValueError("selection is incompatible")
        return selection


class _ToolsModelCatalog:
    def resolve(self, model_id):
        return ThreadModelDescriptor(model_id, "revision:sha256:" + "a" * 64, "pypsa")


def test_postgres_claim_preparation_preserves_a_full_lease(postgres_thread_service) -> None:
    import time

    class SlowCatalog:
        def resolve(self, _model_id):
            raise AssertionError("claim must retain its already accepted context")

        def list_entries(self):
            time.sleep(1.2)
            return ()

    service, thread_id = postgres_thread_service
    service.create_thread(_snapshot(thread_id))
    service.submit_command(_command(thread_id))
    service.set_model_catalog(SlowCatalog())
    claim = service.claim_attempt("slow-catalog-worker", lease_seconds=1)
    assert claim is not None
    assert service.renew_attempt(claim, lease_seconds=1)


@pytest.mark.parametrize("switch", [False, True])
def test_postgres_message_tools_activate_atomically_for_current_or_pending_model(postgres_thread_service, switch) -> None:
    service, thread_id = postgres_thread_service
    service.set_capability_catalog(_ToolsCatalog())
    service.set_model_catalog(_ToolsModelCatalog())
    service.create_thread(_snapshot(thread_id))
    cursor = 0
    if switch:
        service.submit_command({**_command(thread_id), "kind": "switch_model", "payload": {"model_id": "pypsa39"}})
        cursor = service.snapshot(thread_id).last_event_seq
    selection = [{"profile_id": "operations" if switch else "static-analysis", "profile_version": "1.0.0"}]
    command = {**_command(thread_id), "command_id": "cmd_tools", "idempotency_key": "idem_tools", "expected_event_seq": cursor,
        "payload": {"text": "inspect", "enabled_profiles": selection}}
    receipt = service.submit_command(command)
    assert receipt.status == "accepted"
    assert service.submit_command(command) == receipt
    claim = service.claim_attempt("tools-test", lease_seconds=30)
    assert claim is not None
    assert claim.model_context.enabled_profiles == ((selection[0]["profile_id"], "1.0.0"),)
    assert claim.model_context.implementation_family == ("pypsa" if switch else "pandapower")
    assert service.snapshot(thread_id).active_model_context == claim.model_context


def test_postgres_incompatible_message_tools_create_no_turn_or_selection(postgres_thread_service) -> None:
    service, thread_id = postgres_thread_service
    service.set_capability_catalog(_ToolsCatalog())
    service.create_thread(_snapshot(thread_id))
    before = service.snapshot(thread_id)
    receipt = service.submit_command({**_command(thread_id), "payload": {"text": "hello", "enabled_profiles": [
        {"profile_id": "operations", "profile_version": "1.0.0"},
    ]}})
    assert receipt.status == "rejected" and receipt.rejection == "selection_unavailable"
    assert service.snapshot(thread_id) == before


def test_postgres_large_diagram_replay_is_byte_bounded_and_complete(postgres_thread_service) -> None:
    service, thread_id = postgres_thread_service
    service.create_thread(_snapshot(thread_id))
    service.submit_command(_command(thread_id))
    claim = service.claim_attempt("thread-worker", lease_seconds=120)
    assert claim is not None
    diagram = normalize_network_diagram({
        "schema": "capstone-network-diagram/1.0",
        "model": {"id": "ieee39", "revision": "7", "source": "gridctl"},
        "coordinate_system": "schematic",
        "buses": [{"id": str(i), "label": "x" * 190, "x": None, "y": None, "vn_kv": 220}
                  for i in range(9241)], "branches": [],
    })
    for _ in range(3):
        service.append_runtime_event(claim, event_type="network_diagram", payload={"diagram": diagram})
    cursor, sequences, diagrams = 0, [], 0
    while True:
        page = service.read_events(thread_id, cursor)
        assert len(json.dumps(page.to_document(), ensure_ascii=False).encode()) <= MAX_EVENT_PAGE_BYTES
        assert page.next_event_seq > cursor
        sequences.extend(item.event_seq for item in page.events)
        diagrams += sum(item.event_type == "network_diagram" for item in page.events)
        cursor = page.next_event_seq
        if not page.has_more:
            break
    assert diagrams == 3 and sequences == list(range(1, cursor + 1))


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


def test_postgres_rejected_receipt_and_command_id_survive_service_restart(
    postgres_thread_service: tuple[PostgresThreadService, str],
) -> None:
    service, thread_id = postgres_thread_service
    service.create_thread(_snapshot(thread_id))
    command = _command(thread_id)

    first = service.record_rejected_command(command, rejection="case_model_mismatch")
    restarted = PostgresThreadService(service.dsn)
    second = restarted.record_rejected_command(command, rejection="case_model_mismatch")
    reused_id = dict(command)
    reused_id["idempotency_key"] = "idem_rejected_retry"

    assert first.status == "rejected"
    assert first.rejection == "case_model_mismatch"
    assert second == first
    assert restarted.record_rejected_command(
        reused_id, rejection="case_model_mismatch",
    ).rejection == "command_id_conflict"


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


def test_postgres_family_filter_claims_only_matching_threads(
    postgres_thread_service: tuple[PostgresThreadService, str],
) -> None:
    service, thread_id = postgres_thread_service
    pypsa_id = thread_id + "_pypsa"
    pypsa_snapshot = _snapshot(pypsa_id).to_document()
    pypsa_snapshot["active_model_context"]["implementation_family"] = "pypsa"
    pypsa_snapshot["active_model_context"]["model_id"] = "pypsa39"
    pypsa_snapshot["active_model_context"]["id"] = "ctx_pypsa39"
    pypsa_snapshot["run"]["run_id"] = "run_pypsa_001"
    pypsa_snapshot["active_grid_page_id"] = "page_pypsa39"
    try:
        with psycopg.connect(service.dsn) as connection:
            connection.execute("DELETE FROM capstone_threads WHERE thread_id = %s", (pypsa_id,))
        service.create_thread(_snapshot(thread_id))
        service.create_thread(ThreadSnapshot.from_document(pypsa_snapshot))
        service.submit_command(_command(thread_id))
        pypsa_command = {**_command(pypsa_id), "run_id": "run_pypsa_001", "command_id": "cmd_pypsa_001", "idempotency_key": "idem_pypsa_001"}
        service.submit_command(pypsa_command)
        assert service.claim_attempt("pypsa-worker", 30, implementation_family="pypsa").thread_id == pypsa_id
        assert service.claim_attempt("grid-worker", 30, implementation_family="pandapower").thread_id == thread_id
    finally:
        with psycopg.connect(service.dsn) as connection:
            connection.execute("DELETE FROM capstone_threads WHERE thread_id = %s", (pypsa_id,))


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
