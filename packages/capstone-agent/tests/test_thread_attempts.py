from __future__ import annotations

import pytest

from dataclasses import replace
import time
import json
from capstone_model_capability_spi import ModelCapabilitySelection
from capstone_agent.network_diagram import MAX_EVENT_PAGE_BYTES, normalize_network_diagram
from capstone_agent.thread_protocol import ThreadProtocolError

from capstone_agent.thread_service import (
    InMemoryThreadService,
    ThreadModelDescriptor,
    ThreadExecutionError,
)


class _SelectionCatalog:
    def resolve(
        self,
        model: ThreadModelDescriptor,
        selection: ModelCapabilitySelection | None = None,
    ) -> ModelCapabilitySelection:
        assert model.implementation_family == "pandapower"
        assert selection is not None
        return selection


class _AnySelectionCatalog:
    def resolve(
        self,
        model: ThreadModelDescriptor,
        selection: ModelCapabilitySelection | None = None,
    ) -> ModelCapabilitySelection:
        del model
        return ModelCapabilitySelection.empty() if selection is None else selection


class _ModelCatalog:
    default_model_id = "ieee39"

    def resolve(self, model_id: str | None) -> ThreadModelDescriptor:
        if model_id == "pypsa39":
            return ThreadModelDescriptor(
                "pypsa39", "revision:sha256:" + "b" * 64, "pypsa",
            )
        return ThreadModelDescriptor(
            "ieee39", "revision:sha256:" + "a" * 64, "pandapower",
        )


def _service() -> InMemoryThreadService:
    return InMemoryThreadService.from_document({
        "schema": "capstone-thread-snapshot/1",
        "thread_id": "thr_attempts",
        "run": {"run_id": "run_attempts", "state": "open"},
        "active_model_context": {
            "id": "ctx_ieee39", "model_id": "ieee39", "model_revision": "revision:sha256:" + "a" * 64,
            "implementation_family": "pandapower", "selection_revision": "sel_0",
        },
        "active_grid_page_id": "page_ieee39",
        "current_attempt": None, "last_event_seq": 0, "base_event_seq": 0,
    })


def _selection_service() -> InMemoryThreadService:
    return InMemoryThreadService.from_document({
        "schema": "capstone-thread-snapshot/1",
        "thread_id": "thr_attempts",
        "run": {"run_id": "run_attempts", "state": "open"},
        "active_model_context": {
            "id": "ctx_ieee39", "model_id": "ieee39", "model_revision": "revision:sha256:" + "a" * 64,
            "implementation_family": "pandapower", "selection_revision": "sel_0",
        },
        "active_grid_page_id": "page_ieee39",
        "current_attempt": None, "last_event_seq": 0, "base_event_seq": 0,
    }, capability_catalog=_SelectionCatalog())


def _model_service() -> InMemoryThreadService:
    return InMemoryThreadService.from_document({
        "schema": "capstone-thread-snapshot/1",
        "thread_id": "thr_attempts",
        "run": {"run_id": "run_attempts", "state": "open"},
        "active_model_context": {
            "id": "ctx_ieee39", "model_id": "ieee39", "model_revision": "revision:sha256:" + "a" * 64,
            "implementation_family": "pandapower", "selection_revision": "sel_0",
        },
        "active_grid_page_id": "page_ieee39",
        "current_attempt": None, "last_event_seq": 0, "base_event_seq": 0,
    }, capability_catalog=_AnySelectionCatalog(), model_catalog=_ModelCatalog())


def _command(command_id: str = "cmd_attempt_001") -> dict[str, object]:
    return {
        "schema": "capstone-command/1", "command_id": command_id,
        "idempotency_key": "idem_" + command_id, "thread_id": "thr_attempts",
        "run_id": "run_attempts", "kind": "send_ordinary", "expected_event_seq": 0,
        "payload": {"text": "inspect the current model"},
    }


def test_large_diagrams_have_bound_model_identity_and_byte_paged_replay() -> None:
    service = _service()
    service.submit_command(_command())
    claim = service.claim_attempt("worker", lease_seconds=120)
    assert claim is not None
    diagram = normalize_network_diagram({
        "schema": "capstone-network-diagram/1.0",
        "model": {"id": claim.model_context.model_id, "revision": claim.model_context.model_revision, "source": "gridctl"},
        "coordinate_system": "schematic",
        "buses": [{"id": str(i), "label": "Grid bus " + "x" * 180, "x": None, "y": None, "vn_kv": 220}
                  for i in range(9241)], "branches": [],
    })
    for _ in range(3):
        service.append_runtime_event(claim, event_type="network_diagram", payload={"diagram": diagram})
    with pytest.raises(ThreadProtocolError, match="too large"):
        service.append_runtime_event(claim, event_type="assistant_delta", payload={"text": "x" * 65537})
    foreign = {**diagram, "model": {**diagram["model"], "id": "foreign"}}
    foreign.pop("ref"); foreign.pop("fingerprint")
    with pytest.raises(ThreadProtocolError, match="claimed model"):
        service.append_runtime_event(claim, event_type="network_diagram", payload={"diagram": foreign})
    cursor = 0
    collected = []
    pages = 0
    while True:
        page = service.read_events("thr_attempts", cursor)
        assert len(json.dumps(page.to_document(), ensure_ascii=False).encode()) <= MAX_EVENT_PAGE_BYTES
        assert page.next_event_seq > cursor
        pages += 1
        collected.extend(page.events)
        cursor = page.next_event_seq
        if not page.has_more:
            break
    assert pages >= 3
    assert [event.event_seq for event in collected] == list(range(1, cursor + 1))
    assert sum(event.event_type == "network_diagram" for event in collected) == 3


def test_command_creates_an_immutable_attempt_target_before_runtime_claim() -> None:
    service = _service()
    receipt = service.submit_command(_command())

    assert receipt.status == "accepted"
    assert receipt.target is not None
    assert set(receipt.target) == {"turn_id", "attempt_id"}
    snapshot = service.snapshot("thr_attempts")
    assert snapshot.current_attempt is not None
    assert snapshot.current_attempt.phase == "accepted"
    event = service.read_events("thr_attempts", 0).events[0]
    assert event.event_type == "command_accepted"
    assert event.turn_id == receipt.target["turn_id"]
    assert event.attempt_id == receipt.target["attempt_id"]


def test_worker_claim_contains_the_exact_admitted_model_context() -> None:
    service = _service()
    context = service.snapshot("thr_attempts").active_model_context
    service.submit_command(_command())
    claim = service.claim_attempt("thread-worker", lease_seconds=30)
    assert claim is not None
    assert claim.model_context == context
    assert claim.model_context.model_revision == "revision:sha256:" + "a" * 64


def test_worker_claim_carries_the_application_model_catalog_context() -> None:
    service = _model_service()
    service.set_catalog_context({
        "schema": "capstone-thread-catalog/1",
        "models": [
            {
                "model_id": "ieee39",
                "display_name": "IEEE-39",
                "implementation_family": "pandapower",
                "available": True,
            },
            {
                "model_id": "regional-six-bus",
                "display_name": "Regional six-bus",
                "implementation_family": "pypsa",
                "available": True,
            },
        ],
        "profiles": [],
    })
    service.submit_command(_command())

    claim = service.claim_attempt("thread-worker", lease_seconds=30)

    assert claim is not None
    assert claim.application_catalog is not None
    assert [item["model_id"] for item in claim.application_catalog["models"]] == [
        "ieee39", "regional-six-bus",
    ]


def test_context_drift_interrupts_attempt_before_worker_execution() -> None:
    service = _service()
    service.submit_command(_command())
    context = service.snapshot("thr_attempts").active_model_context
    service._snapshot = replace(
        service._snapshot, active_model_context=replace(context, model_revision="changed"),
    )
    assert service.claim_attempt("thread-worker", lease_seconds=30) is None
    assert service.snapshot("thr_attempts").current_attempt is None
    assert service.read_events("thr_attempts", 0).events[-1].event_type == "attempt_interrupted"
    assert service.read_events("thr_attempts", 0).events[-1].payload == {
        "reason": "model_context_snapshot_unavailable",
    }


def test_claim_runtime_events_and_terminal_attempt_are_replayable() -> None:
    service = _service()
    service.submit_command(_command())
    claim = service.claim_attempt("thread-worker", lease_seconds=30)

    assert claim is not None
    assert claim.attempt.phase == "running"
    current = service.snapshot("thr_attempts").current_attempt
    assert current is not None
    assert current.phase == "running"

    runtime_event = service.append_runtime_event(
        claim, event_type="assistant_text_delta", payload={"text": "ready"},
    )
    assert runtime_event.event_seq == 3
    completed = service.finish_attempt(claim, phase="completed", payload={"answer": "ready"})
    assert completed.current_attempt is None
    events = service.read_events("thr_attempts", 0).events
    assert [event.event_type for event in events] == [
        "command_accepted", "attempt_started", "assistant_text_delta", "attempt_completed",
    ]


def test_completed_attempt_admits_result_projection_into_thread_snapshot() -> None:
    service = _service()
    receipt = service.submit_command(_command())
    claim = service.claim_attempt("thread-worker", lease_seconds=30)
    assert claim is not None and receipt.target is not None
    result_ref = "result:sha256:" + "a" * 64
    evidence_ref = "evidence:sha256:" + "b" * 64
    projection = {
        "schema": "capstone-result-projection/1.0",
        "result_id": "powerflow_result_1", "result_ref": result_ref,
        "evidence_refs": [evidence_ref], "thread_id": claim.thread_id,
        "run_id": claim.run_id, "turn_id": claim.attempt.turn_id,
        "attempt_id": claim.attempt.attempt_id,
        "model_context_id": claim.model_context.id, "model_id": "ieee39",
        "model_revision": claim.model_context.model_revision,
        "source": {"capability_id": "analysis_powerflow_ac_run",
                    "domain_pack_id": "pandapower_static_analysis",
                    "implementation_family": "pandapower"},
        "status": "completed", "summary": [], "tables": [], "element_refs": [],
        "overlay": None,
    }

    completed = service.finish_attempt(
        claim, phase="completed", payload={
            "answer": "ready", "result_refs": [result_ref],
            "evidence_refs": [evidence_ref], "result_projections": [projection],
        },
    )

    assert completed.result_projections[0].result_id == "powerflow_result_1"
    assert service.snapshot("thr_attempts").to_document()["result_projections"] == [projection]


def test_result_projection_cannot_claim_an_unadmitted_reference() -> None:
    service = _service()
    service.submit_command(_command())
    claim = service.claim_attempt("thread-worker", lease_seconds=30)
    assert claim is not None
    evidence_ref = "evidence:sha256:" + "b" * 64
    projection = {
        "schema": "capstone-result-projection/1.0",
        "result_id": "powerflow_result_1", "result_ref": "result:sha256:" + "a" * 64,
        "evidence_refs": [evidence_ref], "thread_id": claim.thread_id, "run_id": claim.run_id,
        "turn_id": claim.attempt.turn_id, "attempt_id": claim.attempt.attempt_id,
        "model_context_id": claim.model_context.id, "model_id": "ieee39",
        "model_revision": claim.model_context.model_revision,
        "source": {"capability_id": "analysis_powerflow_ac_run",
                    "domain_pack_id": "pandapower_static_analysis",
                    "implementation_family": "pandapower"},
        "status": "completed", "summary": [], "tables": [], "element_refs": [],
        "overlay": None,
    }

    with pytest.raises(ValueError, match="admitted"):
        service.finish_attempt(
            claim, phase="completed", payload={
                "answer": "ready", "result_refs": [], "evidence_refs": [evidence_ref],
                "result_projections": [projection],
            },
        )


def test_cancel_control_targets_running_attempt_and_is_replayable() -> None:
    service = _service()
    service.submit_command(_command())
    claim = service.claim_attempt("thread-worker", lease_seconds=30)
    assert claim is not None
    receipt = service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_cancel_001",
        "idempotency_key": "idem_cancel_001", "thread_id": "thr_attempts",
        "run_id": "run_attempts", "kind": "cancel_live_attempt",
        "expected_event_seq": 2,
        "payload": {"attempt_id": claim.attempt.attempt_id},
    })

    assert receipt.status == "accepted"
    assert receipt.target == {
        "turn_id": claim.attempt.turn_id,
        "attempt_id": claim.attempt.attempt_id,
    }
    assert service.cancel_requested(claim)
    assert [event.event_type for event in service.read_events("thr_attempts", 0).events] == [
        "command_accepted", "attempt_started", "command_accepted",
        "attempt_cancel_requested",
    ]


def test_retry_control_creates_a_new_attempt_from_an_interrupted_turn() -> None:
    service = _service()
    service.submit_command(_command())
    claim = service.claim_attempt("thread-worker", lease_seconds=30)
    assert claim is not None
    service.finish_attempt(claim, phase="interrupted", payload={"reason": "lease_expired"})

    receipt = service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_retry_001",
        "idempotency_key": "idem_retry_001", "thread_id": "thr_attempts",
        "run_id": "run_attempts", "kind": "retry_new_attempt",
        "expected_event_seq": 3,
        "payload": {"turn_id": claim.attempt.turn_id},
    })

    assert receipt.status == "accepted"
    assert receipt.target is not None
    assert receipt.target["turn_id"] == claim.attempt.turn_id
    assert receipt.target["attempt_id"] != claim.attempt.attempt_id
    current = service.snapshot("thr_attempts").current_attempt
    assert current is not None and current.phase == "accepted"
    event = service.read_events("thr_attempts", 0).events[-1]
    assert event.event_type == "command_accepted"
    assert event.payload["payload"] == {
        "turn_id": claim.attempt.turn_id,
        "retry_of": claim.attempt.attempt_id,
    }


def test_retry_control_rejects_a_turn_after_a_retry_commits() -> None:
    service = _service()
    service.submit_command(_command())
    first = service.claim_attempt("thread-worker", lease_seconds=30)
    assert first is not None
    service.finish_attempt(first, phase="failed", payload={"error_code": "runtime_failed"})

    retry = service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_retry_committed_001",
        "idempotency_key": "idem_retry_committed_001", "thread_id": "thr_attempts",
        "run_id": "run_attempts", "kind": "retry_new_attempt",
        "expected_event_seq": service.snapshot("thr_attempts").last_event_seq,
        "payload": {"turn_id": first.attempt.turn_id},
    })
    assert retry.status == "accepted"
    second = service.claim_attempt("thread-worker", lease_seconds=30)
    assert second is not None
    service.finish_attempt(second, phase="completed", payload={"answer": "retried"})

    rejected = service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_retry_committed_002",
        "idempotency_key": "idem_retry_committed_002", "thread_id": "thr_attempts",
        "run_id": "run_attempts", "kind": "retry_new_attempt",
        "expected_event_seq": service.snapshot("thr_attempts").last_event_seq,
        "payload": {"turn_id": first.attempt.turn_id},
    })
    assert rejected.status == "rejected"
    assert rejected.rejection == "retry_turn_committed"


def test_selection_control_stages_and_activates_on_the_next_turn_boundary() -> None:
    service = _selection_service()
    receipt = service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_enable_001",
        "idempotency_key": "idem_enable_001", "thread_id": "thr_attempts",
        "run_id": "run_attempts", "kind": "enable_profile", "expected_event_seq": 0,
        "payload": {"profile_id": "static-analysis", "profile_version": "1.0.0"},
    })

    assert receipt.status == "accepted"
    before = service.snapshot("thr_attempts")
    assert before.active_model_context.selection_revision == "sel_0"
    assert before.active_model_context.enabled_profiles == ()
    assert before.pending_selection is not None
    assert before.pending_selection.enabled_profiles == (("static-analysis", "1.0.0"),)

    next_turn = service.submit_command({
        **_command("cmd_next_turn"),
        "expected_event_seq": before.last_event_seq,
    })

    assert next_turn.status == "accepted"
    after = service.snapshot("thr_attempts")
    assert after.pending_selection is None
    assert after.active_model_context.selection_revision == "sel_1"
    assert after.active_model_context.enabled_profiles == (("static-analysis", "1.0.0"),)
    assert [event.event_type for event in service.read_events("thr_attempts", 0).events] == [
        "command_accepted", "selection_change_pending", "selection_activated",
        "command_accepted",
    ]


def test_selection_controls_compose_against_the_pending_selection() -> None:
    service = _selection_service()
    first = service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_enable_a",
        "idempotency_key": "idem_enable_a", "thread_id": "thr_attempts",
        "run_id": "run_attempts", "kind": "enable_profile", "expected_event_seq": 0,
        "payload": {"profile_id": "static-analysis", "profile_version": "1.0.0"},
    })
    assert first.status == "accepted"
    second = service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_enable_b",
        "idempotency_key": "idem_enable_b", "thread_id": "thr_attempts",
        "run_id": "run_attempts", "kind": "enable_profile",
        "expected_event_seq": service.snapshot("thr_attempts").last_event_seq,
        "payload": {"profile_id": "state-estimation", "profile_version": "1.0.0"},
    })

    assert second.status == "accepted"
    pending = service.snapshot("thr_attempts").pending_selection
    assert pending is not None
    assert pending.enabled_profiles == (
        ("static-analysis", "1.0.0"), ("state-estimation", "1.0.0"),
    )


def test_selection_control_fails_closed_without_an_exact_catalog() -> None:
    service = _service()
    receipt = service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_enable_unbound",
        "idempotency_key": "idem_enable_unbound", "thread_id": "thr_attempts",
        "run_id": "run_attempts", "kind": "enable_profile", "expected_event_seq": 0,
        "payload": {"profile_id": "static-analysis", "profile_version": "1.0.0"},
    })

    assert receipt.status == "rejected"
    assert receipt.rejection == "selection_catalog_unavailable"
    assert service.read_events("thr_attempts", 0).events == ()


def test_selection_preparation_failure_restores_the_previous_effective_revision() -> None:
    service = _selection_service()
    staged = service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_enable_restore",
        "idempotency_key": "idem_enable_restore", "thread_id": "thr_attempts",
        "run_id": "run_attempts", "kind": "enable_profile", "expected_event_seq": 0,
        "payload": {"profile_id": "static-analysis", "profile_version": "1.0.0"},
    })
    assert staged.status == "accepted"
    service.submit_command({
        **_command("cmd_turn_after_selection"),
        "expected_event_seq": service.snapshot("thr_attempts").last_event_seq,
    })
    claim = service.claim_attempt("thread-worker", lease_seconds=30)
    assert claim is not None
    assert claim.model_context.selection_revision == "sel_1"

    assert service.rollback_selection_if_preparation_failed(
        claim, error_code="capability_context_preparation_failed",
    )
    restored = service.snapshot("thr_attempts")
    assert restored.active_model_context.selection_revision == "sel_0"
    assert restored.active_model_context.enabled_profiles == ()
    assert service.read_events("thr_attempts", 0).events[-1].event_type == "selection_reverted"


def test_model_switch_stages_and_activates_a_new_context_at_the_next_turn_boundary() -> None:
    service = _model_service()
    receipt = service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_switch_001",
        "idempotency_key": "idem_switch_001", "thread_id": "thr_attempts",
        "run_id": "run_attempts", "kind": "switch_model", "expected_event_seq": 0,
        "payload": {"model_id": "pypsa39"},
    })

    assert receipt.status == "accepted"
    before = service.snapshot("thr_attempts")
    assert before.active_model_context.model_id == "ieee39"
    assert before.pending_model_switch is not None
    assert before.pending_model_switch.model_id == "pypsa39"

    next_turn = service.submit_command({
        **_command("cmd_switch_turn"),
        "expected_event_seq": before.last_event_seq,
    })

    assert next_turn.status == "accepted"
    after = service.snapshot("thr_attempts")
    assert after.pending_model_switch is None
    assert after.active_model_context.model_id == "pypsa39"
    assert after.active_model_context.implementation_family == "pypsa"
    assert after.active_model_context.id != before.active_model_context.id
    assert [event.event_type for event in service.read_events("thr_attempts", 0).events] == [
        "command_accepted", "model_context_change_pending", "model_context_activated",
        "command_accepted",
    ]


def test_model_switch_preparation_failure_restores_previous_context_and_grid_page() -> None:
    service = _model_service()
    staged = service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_switch_restore",
        "idempotency_key": "idem_switch_restore", "thread_id": "thr_attempts",
        "run_id": "run_attempts", "kind": "switch_model", "expected_event_seq": 0,
        "payload": {"model_id": "pypsa39"},
    })
    assert staged.status == "accepted"
    before = service.snapshot("thr_attempts")
    service.submit_command({
        **_command("cmd_turn_after_switch"),
        "expected_event_seq": before.last_event_seq,
    })
    claim = service.claim_attempt("thread-worker", lease_seconds=30)
    assert claim is not None
    assert claim.model_context.model_id == "pypsa39"

    assert service.rollback_context_if_preparation_failed(
        claim, error_code="capability_context_preparation_failed",
    )
    restored = service.snapshot("thr_attempts")
    assert restored.active_model_context.model_id == "ieee39"
    assert restored.active_model_context.id == "ctx_ieee39"
    assert restored.active_grid_page_id == "page_ieee39"
    assert service.read_events("thr_attempts", 0).events[-1].event_type == "model_context_reverted"


def test_selection_is_rejected_while_another_model_switch_is_pending() -> None:
    service = _model_service()
    service.submit_command({
        **_command("cmd_switch_pending"), "kind": "switch_model",
        "payload": {"model_id": "pypsa39"},
    })
    receipt = service.submit_command({
        **_command("cmd_profile_pending"), "kind": "enable_profile",
        "expected_event_seq": service.snapshot("thr_attempts").last_event_seq,
        "payload": {"profile_id": "static-analysis", "profile_version": "1.0.0"},
    })
    assert receipt.status == "rejected"
    assert receipt.rejection == "context_change_pending"
    assert service.snapshot("thr_attempts").pending_selection is None


def test_later_preparation_failure_cannot_roll_back_a_completed_model_switch() -> None:
    service = _model_service()
    service.submit_command({
        **_command("cmd_switch_success"), "kind": "switch_model",
        "payload": {"model_id": "pypsa39"},
    })
    service.submit_command({
        **_command("cmd_first_switched_turn"),
        "expected_event_seq": service.snapshot("thr_attempts").last_event_seq,
    })
    first = service.claim_attempt("thread-worker", lease_seconds=30)
    assert first is not None
    service.finish_attempt(first, phase="completed", payload={"answer": "ready"})
    service.submit_command({
        **_command("cmd_later_switched_turn"),
        "expected_event_seq": service.snapshot("thr_attempts").last_event_seq,
    })
    later = service.claim_attempt("thread-worker", lease_seconds=30)
    assert later is not None
    assert not service.rollback_context_if_preparation_failed(
        later, error_code="capability_context_preparation_failed",
    )
    assert service.snapshot("thr_attempts").active_model_context == first.model_context


def test_attempt_lease_is_required_for_append_and_finish() -> None:
    service = _service()
    service.submit_command(_command())
    claim = service.claim_attempt("thread-worker", lease_seconds=30)
    assert claim is not None
    forged = replace(claim, lease_token="wrong-lease")

    with pytest.raises(ThreadExecutionError, match="lease"):
        service.append_runtime_event(forged, event_type="assistant_text_delta", payload={"text": "x"})
    with pytest.raises(ThreadExecutionError, match="lease"):
        service.finish_attempt(forged, phase="failed", payload={"error": "lost"})


def test_runtime_event_payload_is_bounded_before_persistence() -> None:
    service = _service()
    service.submit_command(_command())
    claim = service.claim_attempt("thread-worker", lease_seconds=30)
    assert claim is not None

    with pytest.raises(ValueError, match="too large"):
        service.append_runtime_event(
            claim, event_type="assistant_message_update", payload={"text": "x" * 70_000},
        )


def test_attempt_lease_can_be_renewed_and_expired_attempt_is_interrupted(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service()
    service.submit_command(_command())
    claim = service.claim_attempt("thread-worker", lease_seconds=1)
    assert claim is not None

    assert service.renew_attempt(claim, lease_seconds=30)
    clock = time.monotonic()
    monkeypatch.setattr(time, "monotonic", lambda: clock + 2)
    assert service.interrupt_expired_attempts() == 0
    assert service.snapshot("thr_attempts").current_attempt is not None

    monkeypatch.setattr(time, "monotonic", lambda: clock + 31)
    with pytest.raises(ThreadExecutionError, match="lease"):
        service.append_runtime_event(claim, event_type="assistant_text_delta", payload={"text": "late"})
    assert service.interrupt_expired_attempts() == 1
    snapshot = service.snapshot("thr_attempts")
    assert snapshot.current_attempt is None
    events = service.read_events("thr_attempts", 0).events
    assert events[-1].event_type == "attempt_interrupted"
    assert events[-1].payload == {"reason": "lease_expired"}

    with pytest.raises(ThreadExecutionError, match="lease"):
        service.finish_attempt(claim, phase="completed", payload={"answer": "late"})


def test_snapshot_never_presents_an_expired_running_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service()
    service.submit_command(_command("cmd_snapshot_expired"))
    claim = service.claim_attempt("thread-worker", lease_seconds=1)
    assert claim is not None
    clock = time.monotonic()
    monkeypatch.setattr(time, "monotonic", lambda: clock + 2)

    snapshot = service.snapshot("thr_attempts")

    assert snapshot.current_attempt is None
    assert service.read_events("thr_attempts", 0).events[-1].event_type == "attempt_interrupted"

def test_reopen_same_model_context_creates_fresh_context_at_turn_boundary() -> None:
    service = _model_service()
    first = service.snapshot("thr_attempts").active_model_context.id
    receipt = service.submit_command({
        **_command("cmd_reopen"), "kind": "reopen_model_context",
        "payload": {"model_id": "ieee39", "reason": "user_requested_fresh_context"},
    })
    assert receipt.status == "accepted"
    service.submit_command({
        **_command("cmd_reopen_turn"),
        "expected_event_seq": service.snapshot("thr_attempts").last_event_seq,
    })
    claim = service.claim_attempt("thread-worker", 30)
    assert claim is not None
    current = service.snapshot("thr_attempts").active_model_context
    assert current.id != first
    events = service.read_events("thr_attempts", 0).events
    activation = [e for e in events if e.event_type == "model_context_reopened"][-1]
    assert activation.payload["reason"] == "explicit_reopen"


def test_same_model_switch_is_rejected_and_context_identity_is_reused() -> None:
    service = _model_service()
    before = service.snapshot("thr_attempts").active_model_context.id
    receipt = service.submit_command({
        **_command("cmd_same_model"), "kind": "switch_model",
        "payload": {"model_id": "ieee39"},
    })
    assert receipt.status == "rejected"
    assert receipt.rejection == "model_already_active"
    assert service.snapshot("thr_attempts").active_model_context.id == before


def test_model_switch_rejects_a_family_without_a_ready_worker() -> None:
    service = _model_service()
    service.set_available_families(frozenset({"pandapower"}))
    receipt = service.submit_command({
        **_command("cmd_unavailable_family"), "kind": "switch_model",
        "payload": {"model_id": "pypsa39"},
    })
    assert receipt.status == "rejected"
    assert receipt.rejection == "worker_unavailable"
