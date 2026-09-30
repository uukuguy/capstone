from __future__ import annotations

import pytest

from capstone_agent.harness import (
    HarnessDSHClient,
    HarnessAttemptRunner,
    HarnessPiClient,
    HarnessRuntimeUnavailable,
    normalize_runtime_event,
)
from capstone_agent.thread_service import InMemoryThreadService


class _PiSession:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def prompt_and_wait(self, question: str, **kwargs: object) -> str:
        assert question == "hello"
        callback = kwargs["on_semantic_event"]
        assert callable(callback)
        callback({"type": "text_delta", "text": "hi"})
        callback({"type": "tool_execution_start", "toolCallId": "call-1", "toolName": "grid_model_list"})
        return "answer"

    def stop(self) -> None:
        self.stopped = True


def _thread_service() -> InMemoryThreadService:
    return InMemoryThreadService.from_document({
        "schema": "capstone-thread-snapshot/1", "thread_id": "thr_harness",
        "run": {"run_id": "run_harness", "state": "open"},
        "active_model_context": {
            "id": "ctx_ieee39", "model_id": "ieee39", "model_revision": "revision:sha256:" + "a" * 64,
            "implementation_family": "pandapower", "selection_revision": "sel_0",
        },
        "active_grid_page_id": "page_ieee39", "current_attempt": None,
        "last_event_seq": 0, "base_event_seq": 0,
    })


def test_pi_client_normalizes_native_events_and_preserves_answer() -> None:
    session = _PiSession()
    events: list[dict[str, object]] = []
    client = HarnessPiClient(session, runtime_mode="capstone")

    client.start()
    answer = client.prompt("hello", on_event=events.append)
    client.stop()

    assert answer == "answer"
    assert session.started and session.stopped
    assert [event["event_type"] for event in events] == [
        "assistant_text_delta", "tool_started",
    ]
    assert events[1]["runtime_mode"] == "capstone"
    assert events[1]["payload"] == {"tool_call_id": "call-1", "tool_name": "grid_model_list"}


def test_normalizer_drops_unbounded_native_payloads() -> None:
    event = normalize_runtime_event(
        {"type": "provider_internal", "messages": [{"secret": "do-not-persist"}], "text": "x" * 10000},
        runtime_mode="pi_reference",
    )

    assert event == {
        "event_type": "runtime_event",
        "runtime_mode": "pi_reference",
        "visibility": "diagnostic",
        "payload": {"native_type": "provider_internal"},
    }


def test_normalizer_preserves_bounded_tool_provenance_and_evidence_refs() -> None:
    event = normalize_runtime_event(
        {
            "type": "tool_result",
            "toolCallId": "call-1",
            "toolName": "grid_powerflow_run",
            "capability": "analysis.powerflow.ac.run",
            "capability_key": {"binding_id": "grid", "capability_id": "powerflow"},
            "projector_id": "pandapower.powerflow",
            "result": {"details": {"result_kind": "powerflow", "secret": "drop"}},
            "evidence_refs": ["evidence:sha256:" + "a" * 64, "x" * 10000],
        },
        runtime_mode="capstone",
    )

    assert event["event_type"] == "tool_completed"
    assert event["payload"] == {
        "tool_call_id": "call-1",
        "tool_name": "grid_powerflow_run",
        "capability": "analysis.powerflow.ac.run",
        "binding_id": "grid",
        "capability_id": "powerflow",
        "projector_id": "pandapower.powerflow",
        "result_kind": "powerflow",
        "evidence_refs": ["evidence:sha256:" + "a" * 64, "x" * 512],
    }


def test_dsh_client_is_an_explicitly_unavailable_shell() -> None:
    client = HarnessDSHClient()
    with pytest.raises(HarnessRuntimeUnavailable, match="DSH"):
        client.start()


def test_harness_attempt_runner_persists_runtime_events_and_terminal_answer() -> None:
    service = _thread_service()
    service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_harness_001",
        "idempotency_key": "idem_harness_001", "thread_id": "thr_harness",
        "run_id": "run_harness", "kind": "send_ordinary", "expected_event_seq": 0,
        "payload": {"text": "hello"},
    })
    claim = service.claim_attempt("worker", lease_seconds=30)
    assert claim is not None
    result = HarnessAttemptRunner(service, HarnessPiClient(_PiSession())).run(claim)

    assert result.status == "completed"
    assert result.answer == "answer"
    assert service.snapshot("thr_harness").current_attempt is None
    assert service.read_events("thr_harness", 0).events[-1].event_type == "attempt_completed"


def test_harness_pi_heartbeat_renews_attempt_lease() -> None:
    service = _thread_service()
    service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_harness_heartbeat",
        "idempotency_key": "idem_harness_heartbeat", "thread_id": "thr_harness",
        "run_id": "run_harness", "kind": "send_ordinary", "expected_event_seq": 0,
        "payload": {"text": "hello"},
    })
    claim = service.claim_attempt("worker", lease_seconds=1)
    assert claim is not None

    class _HeartbeatSession(_PiSession):
        def prompt_and_wait(self, question: str, **kwargs: object) -> str:
            callback = kwargs["on_heartbeat"]
            assert callable(callback)
            callback()
            return super().prompt_and_wait(question, **kwargs)

    result = HarnessAttemptRunner(
        service, HarnessPiClient(_HeartbeatSession()), lease_seconds=30,
    ).run(claim)
    assert result.status == "completed"
