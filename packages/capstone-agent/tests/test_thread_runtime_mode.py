from dataclasses import replace

import pytest

from capstone_agent.thread_protocol import ThreadProtocolError, ThreadSnapshot
from capstone_agent.thread_commands import ThreadCommandFactory
from capstone_agent.thread_service import InMemoryThreadService
from test_thread_attempts import _service


def command(service, kind, payload, name):
    snapshot = service.snapshot("thr_attempts")
    return {"schema": "capstone-command/1", "thread_id": snapshot.thread_id,
            "command_id": name, "idempotency_key": "idem_" + name,
            "kind": kind, "payload": payload, "expected_event_seq": snapshot.last_event_seq}


def test_switch_replays_and_retry_retains_accepted_runtime():
    service = _service()
    original = service.snapshot("thr_attempts")
    switch = command(service, "switch_runtime", {"runtime_mode": "pi_reference"}, "cmd_switch")
    receipt = service.submit_command(switch)
    assert receipt.status == "accepted"
    assert service.submit_command(switch) == receipt
    assert service.snapshot("thr_attempts").runtime_mode == "pi_reference"
    assert service.snapshot("thr_attempts").active_model_context == original.active_model_context
    service.submit_command(command(service, "send_auto", {"text": "hello"}, "cmd_send"))
    claim = service.claim_attempt("test", lease_seconds=30)
    assert claim.attempt.runtime_mode == "pi_reference"
    blocked = service.submit_command(command(service, "switch_runtime", {"runtime_mode": "capstone"}, "cmd_blocked"))
    assert blocked.rejection == "attempt_in_progress"
    service.finish_attempt(claim, phase="failed", payload={"error_code": "test_failure"})
    assert service.submit_command(command(service, "switch_runtime", {"runtime_mode": "capstone"}, "cmd_back")).status == "accepted"
    assert service.submit_command(command(service, "retry_new_attempt", {"attempt_id": claim.attempt.attempt_id}, "cmd_retry")).status == "accepted"
    retried = service.claim_attempt("test", lease_seconds=30)
    assert retried.attempt.runtime_mode == "pi_reference"
    assert retried.instruction == "hello"


@pytest.mark.parametrize("payload", [{}, {"runtime_mode": "other"}, {"runtime_mode": "pi_reference", "extra": True}])
def test_runtime_payload_is_exact(payload):
    service = _service()
    assert service.submit_command(command(service, "switch_runtime", payload, "cmd_invalid")).rejection == "runtime_mode_invalid"


def test_legacy_default_and_strict_runtime_projection():
    snapshot = _service().snapshot("thr_attempts")
    assert snapshot.runtime_mode == "capstone"
    document = snapshot.to_document()
    document["runtime_mode"] = "other"
    with pytest.raises(ThreadProtocolError):
        ThreadSnapshot.from_document(document)
    factory = ThreadCommandFactory("thr_attempts")
    assert factory.switch_runtime("pi_reference", command_id="cmd_switch", idempotency_key="idem_switch", expected_event_seq=0)["payload"] == {"runtime_mode": "pi_reference"}


@pytest.mark.parametrize("status", ["created", "running", "waiting_step", "blocked"])
def test_switch_rejects_active_case(status):
    initial = _service().snapshot("thr_attempts")
    service = InMemoryThreadService(replace(initial, application_state={"case_execution": {"status": status}}))
    receipt = service.submit_command(command(service, "switch_runtime", {"runtime_mode": "pi_reference"}, "cmd_case"))
    assert receipt.rejection == "case_execution_active"
    assert service.snapshot("thr_attempts").runtime_mode == "capstone"
