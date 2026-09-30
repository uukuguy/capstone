from __future__ import annotations

import pytest

from dataclasses import replace
import time

from capstone_agent.thread_service import (
    InMemoryThreadService,
    ThreadExecutionError,
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


def _command(command_id: str = "cmd_attempt_001") -> dict[str, object]:
    return {
        "schema": "capstone-command/1", "command_id": command_id,
        "idempotency_key": "idem_" + command_id, "thread_id": "thr_attempts",
        "run_id": "run_attempts", "kind": "send_ordinary", "expected_event_seq": 0,
        "payload": {"text": "inspect the current model"},
    }


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


def test_claim_runtime_events_and_terminal_attempt_are_replayable() -> None:
    service = _service()
    receipt = service.submit_command(_command())
    claim = service.claim_attempt("thread-worker", lease_seconds=30)

    assert claim is not None
    assert claim.attempt.phase == "running"
    assert service.snapshot("thr_attempts").current_attempt is not None
    assert service.snapshot("thr_attempts").current_attempt.phase == "running"

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
