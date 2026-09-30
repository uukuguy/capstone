from __future__ import annotations

import pytest

from capstone_agent.thread_protocol import (
    CommandReceipt,
    EventPage,
    ThreadProtocolError,
    ThreadSnapshot,
)


def valid_snapshot() -> dict[str, object]:
    return {
        "schema": "capstone-thread-snapshot/1",
        "thread_id": "thr_demo_39",
        "run": {"run_id": "run_001", "state": "open"},
        "active_model_context": {
            "id": "ctx_ieee39_7",
            "model_id": "ieee39",
            "model_revision": "7",
            "implementation_family": "pandapower",
            "selection_revision": "sel_2",
        },
        "active_grid_page_id": "page_ieee39",
        "current_attempt": {
            "turn_id": "turn_004",
            "attempt_id": "attempt_004a",
            "phase": "running",
            "target_model_context_id": "ctx_ieee39_7",
        },
        "last_event_seq": 183,
        "base_event_seq": 180,
    }


def event(sequence: int) -> dict[str, object]:
    return {
        "event_id": f"evt_{sequence}",
        "event_seq": sequence,
        "event_type": "attempt_progress",
        "event_version": 1,
        "thread_id": "thr_demo_39",
        "run_id": "run_001",
        "turn_id": "turn_004",
        "attempt_id": "attempt_004a",
        "model_context_id": "ctx_ieee39_7",
        "selection_revision": "sel_2",
        "occurred_at": "2026-09-30T00:00:00Z",
        "visibility": "public",
        "payload": {"phase": "running"},
    }


def valid_page(*, events: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema": "capstone-thread-events/1",
        "thread_id": "thr_demo_39",
        "after_event_seq": 180,
        "next_event_seq": events[-1]["event_seq"] if events else 180,
        "has_more": False,
        "events": events,
    }


def valid_receipt() -> dict[str, object]:
    return {
        "schema": "capstone-command-receipt/1",
        "command_id": "cmd_switch_005",
        "idempotency_key": "idem_switch_005",
        "thread_id": "thr_demo_39",
        "run_id": "run_001",
        "status": "accepted",
        "accepted_event_seq": 184,
        "target": {"model_id": "pypsa39", "model_revision": "3"},
    }


def test_snapshot_round_trips_with_active_context_and_attempt() -> None:
    snapshot = ThreadSnapshot.from_document(valid_snapshot())

    assert snapshot.thread_id == "thr_demo_39"
    assert snapshot.active_model_context.model_revision == "7"
    assert snapshot.to_document()["schema"] == "capstone-thread-snapshot/1"


def test_model_context_round_trips_enabled_profile_selection() -> None:
    document = valid_snapshot()
    document["active_model_context"]["enabled_profiles"] = {
        "schema": "capstone-model-capability-selection/1",
        "enabled_profiles": [
            {"profile_id": "static-analysis", "profile_version": "1.0.0"},
        ],
    }
    snapshot = ThreadSnapshot.from_document(document)
    assert snapshot.active_model_context.enabled_profiles == (("static-analysis", "1.0.0"),)
    assert snapshot.to_document()["active_model_context"]["enabled_profiles"] == document["active_model_context"]["enabled_profiles"]


def test_model_context_rejects_null_profile_selection() -> None:
    document = valid_snapshot()
    document["active_model_context"]["enabled_profiles"] = None
    with pytest.raises(ThreadProtocolError):
        ThreadSnapshot.from_document(document)


def test_snapshot_round_trips_a_pending_selection_without_changing_active_context() -> None:
    document = valid_snapshot()
    document["pending_selection"] = {
        "command_id": "cmd_profile_006",
        "selection": {
            "schema": "capstone-model-capability-selection/1",
            "enabled_profiles": [
                {"profile_id": "static-analysis", "profile_version": "1.0.0"},
            ],
        },
    }

    snapshot = ThreadSnapshot.from_document(document)

    assert snapshot.pending_selection is not None
    assert snapshot.pending_selection.command_id == "cmd_profile_006"
    assert snapshot.pending_selection.enabled_profiles == (("static-analysis", "1.0.0"),)
    assert snapshot.to_document()["pending_selection"] == document["pending_selection"]


def test_snapshot_round_trips_a_pending_model_switch() -> None:
    document = valid_snapshot()
    document["pending_model_switch"] = {
        "command_id": "cmd_model_007",
        "model_id": "pypsa39",
        "model_revision": "revision:sha256:" + "b" * 64,
        "implementation_family": "pypsa",
        "selection": {
            "schema": "capstone-model-capability-selection/1",
            "enabled_profiles": [],
        },
    }

    snapshot = ThreadSnapshot.from_document(document)

    assert snapshot.pending_model_switch is not None
    assert snapshot.pending_model_switch.model_id == "pypsa39"
    assert snapshot.pending_model_switch.implementation_family == "pypsa"
    assert snapshot.to_document()["pending_model_switch"] == document["pending_model_switch"]


def test_snapshot_accepts_real_hierarchical_model_id() -> None:
    document = valid_snapshot()
    document["active_model_context"]["model_id"] = "pypsa-example/scigrid_de"
    snapshot = ThreadSnapshot.from_document(document)
    assert snapshot.active_model_context.model_id == "pypsa-example/scigrid_de"


def test_event_page_rejects_a_gap_after_the_snapshot() -> None:
    with pytest.raises(ThreadProtocolError, match="contiguous"):
        EventPage.from_document(
            valid_page(events=[event(181), event(183)]),
            expected_after_seq=180,
        )


def test_snapshot_rejects_provider_or_native_runtime_payload_fields() -> None:
    document = valid_snapshot()
    document["provider_token"] = "secret"

    with pytest.raises(ThreadProtocolError, match="unknown field"):
        ThreadSnapshot.from_document(document)


def test_receipt_preserves_command_identity_and_status() -> None:
    receipt = CommandReceipt.from_document(valid_receipt())

    assert receipt.command_id == "cmd_switch_005"
    assert receipt.status == "accepted"
