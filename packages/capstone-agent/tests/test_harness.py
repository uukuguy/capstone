from __future__ import annotations

import pytest

from capstone_agent.harness import (
    AdmittedAttemptAnswer,
    CapstoneHarness,
    HarnessDSHClient,
    HarnessAttemptRunner,
    HarnessPiClient,
    HarnessRuntimeRegistry,
    HarnessRuntimeUnavailable,
    normalize_runtime_event,
)
from capstone_agent.thread_service import InMemoryThreadService
from capstone_agent.turn_router import DefaultTurnRouter, FakeDecisionRouter


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


class _ProtocolRuntime:
    def start(self) -> None:
        return None

    def prompt(
        self,
        question: str,
        *,
        on_event,
        correlation_id=None,
        on_heartbeat=None,
    ) -> str:
        del question, on_event, correlation_id, on_heartbeat
        return "answer"

    def stop(self) -> None:
        return None


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
    with pytest.raises(HarnessRuntimeUnavailable, match="DSH"):
        client.prompt("hello", on_event=lambda _event: None)


def test_runtime_registry_rejects_duplicate_names_and_resolves_registered_factory() -> None:
    registry = HarnessRuntimeRegistry()

    def factory(_claim):
        return _ProtocolRuntime()

    registry.register("pi", factory)

    assert registry.resolve("pi") is factory
    with pytest.raises(ValueError, match="duplicate runtime"):
        registry.register("pi", factory)


def test_pi_client_normalizes_runtime_mode_and_tool_provenance_at_harness_boundary() -> None:
    class _ProvenanceSession(_PiSession):
        def prompt_and_wait(self, question: str, **kwargs: object) -> str:
            del question
            callback = kwargs["on_semantic_event"]
            assert callable(callback)
            callback({
                "type": "tool_result",
                "toolCallId": "call-1",
                "toolName": "grid_powerflow_run",
                "capability_key": {
                    "binding_id": "grid",
                    "capability_id": "powerflow",
                },
                "projector_id": "pandapower.powerflow",
                "evidence_refs": ["evidence:sha256:" + "a" * 64],
            })
            return "answer"

    events: list[dict[str, object]] = []
    HarnessPiClient(
        _ProvenanceSession(), runtime_mode="pi_reference",
    ).prompt("hello", on_event=events.append)

    assert events == [{
        "event_type": "tool_completed",
        "runtime_mode": "pi_reference",
        "visibility": "public",
        "payload": {
            "tool_call_id": "call-1",
            "tool_name": "grid_powerflow_run",
            "binding_id": "grid",
            "capability_id": "powerflow",
            "projector_id": "pandapower.powerflow",
            "evidence_refs": ["evidence:sha256:" + "a" * 64],
        },
    }]


def test_capstone_harness_delegates_protocol_runtime_to_attempt_runner() -> None:
    service = _thread_service()
    service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_harness_facade",
        "idempotency_key": "idem_harness_facade", "thread_id": "thr_harness",
        "run_id": "run_harness", "kind": "send_ordinary", "expected_event_seq": 0,
        "payload": {"text": "hello"},
    })
    claim = service.claim_attempt("worker", lease_seconds=30)
    assert claim is not None

    result = CapstoneHarness.run_attempt(
        service, claim, _ProtocolRuntime(),
    )

    assert result.status == "completed"
    assert result.answer == "answer"


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
    result = HarnessAttemptRunner(service, HarnessPiClient(
        _PiSession(), admission=lambda _claim, answer, _results, _evidence, _events: AdmittedAttemptAnswer(
            answer, "limited", "limited",
        ),
    )).run(claim)

    assert result.status == "completed"
    assert result.answer == "answer"
    assert service.snapshot("thr_harness").current_attempt is None
    assert service.read_events("thr_harness", 0).events[-1].event_type == "attempt_completed"


def test_professional_attempt_persists_only_application_admitted_refs() -> None:
    service = _thread_service()
    service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_harness_evidence",
        "idempotency_key": "idem_harness_evidence", "thread_id": "thr_harness",
        "run_id": "run_harness", "kind": "send_professional", "expected_event_seq": 0,
        "payload": {"text": "analyze"},
    })

    class _EvidenceSession(_PiSession):
        def prompt_and_wait(self, question: str, **kwargs: object) -> str:
            callback = kwargs["on_semantic_event"]
            assert callable(callback)
            callback({
                "type": "tool_result", "toolCallId": "call-1",
                "toolName": "grid_powerflow_run", "capability": "analysis.run",
                "ok": True, "result_refs": ["result:sha256:" + "a" * 64],
                "evidence_refs": ["evidence:sha256:" + "b" * 64],
            })
            return "grounded answer"

    claim = service.claim_attempt("worker", lease_seconds=30)
    assert claim is not None
    result = HarnessAttemptRunner(service, HarnessPiClient(
        _EvidenceSession(), admission=lambda _claim, answer, _results, _evidence, _events: AdmittedAttemptAnswer(
            answer, "authority_backed", "lineage_verified",
            ("result:sha256:" + "a" * 64,), ("evidence:sha256:" + "b" * 64,),
        ),
    )).run(claim)

    assert result.status == "completed"
    assert result.result_refs == ("result:sha256:" + "a" * 64,)
    assert result.evidence_refs == ("evidence:sha256:" + "b" * 64,)
    terminal = service.read_events("thr_harness", 0).events[-1]
    assert terminal.payload["result_refs"] == list(result.result_refs)
    assert terminal.payload["evidence_refs"] == list(result.evidence_refs)


def test_professional_attempt_without_application_admission_fails_closed() -> None:
    service = _thread_service()
    service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_harness_no_evidence",
        "idempotency_key": "idem_harness_no_evidence", "thread_id": "thr_harness",
        "run_id": "run_harness", "kind": "send_professional", "expected_event_seq": 0,
        "payload": {"text": "analyze"},
    })
    claim = service.claim_attempt("worker", lease_seconds=30)
    assert claim is not None

    class _NoEvidenceSession(_PiSession):
        def prompt_and_wait(self, question: str, **kwargs: object) -> str:
            del question
            callback = kwargs["on_semantic_event"]
            assert callable(callback)
            callback({
                "type": "tool_execution_start",
                "toolCallId": "call-no-evidence",
                "toolName": "grid_powerflow_run",
            })
            return "ungrounded answer"

    result = HarnessAttemptRunner(
        service, HarnessPiClient(_NoEvidenceSession())
    ).run(claim)

    assert result.status == "failed"
    assert result.error_code == "capability_required"
    assert service.read_events("thr_harness", 0).events[-1].payload["error_code"] == (
        "capability_required"
    )


def test_application_admission_is_persisted_before_professional_completion() -> None:
    service = _thread_service()
    service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_harness_admit",
        "idempotency_key": "idem_harness_admit", "thread_id": "thr_harness",
        "run_id": "run_harness", "kind": "send_professional", "expected_event_seq": 0,
        "payload": {"text": "analyze"},
    })

    class _AdmittedSession(_PiSession):
        def prompt_and_wait(self, question: str, **kwargs: object) -> str:
            del question
            callback = kwargs["on_semantic_event"]
            assert callable(callback)
            callback({
                "type": "tool_result", "toolCallId": "call-admit",
                "toolName": "grid_powerflow_run", "ok": True,
                "evidence_refs": ["evidence:sha256:" + "c" * 64],
            })
            return "admitted answer"

        def admit_attempt(self, claim, answer, result_refs, evidence_refs, tool_events):
            assert claim.kind == "send_professional"
            assert answer == "admitted answer"
            assert result_refs == ()
            assert evidence_refs == ("evidence:sha256:" + "c" * 64,)
            assert tool_events
            return AdmittedAttemptAnswer(
                "validated answer", "authority_backed", "lineage_verified",
                evidence_refs=("evidence:sha256:" + "c" * 64,),
            )

    claim = service.claim_attempt("worker", lease_seconds=30)
    assert claim is not None
    session = _AdmittedSession()
    result = HarnessAttemptRunner(service, HarnessPiClient(
        session, admission=session.admit_attempt,
    )).run(claim)

    assert result.status == "completed"
    terminal = service.read_events("thr_harness", 0).events[-1]
    assert terminal.payload["admission"] == {
        "mode": "authority_backed", "assurance": "lineage_verified",
    }
    assert terminal.payload["answer"] == "validated answer"


def test_application_admission_persists_bounded_result_projection() -> None:
    service = _thread_service()
    service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_harness_projection",
        "idempotency_key": "idem_harness_projection", "thread_id": "thr_harness",
        "run_id": "run_harness", "kind": "send_professional", "expected_event_seq": 0,
        "payload": {"text": "analyze"},
    })
    result_ref = "result:sha256:" + "a" * 64
    evidence_ref = "evidence:sha256:" + "b" * 64
    projection = {
        "schema": "capstone-result-projection/1.0",
        "result_id": "powerflow_result_1", "result_ref": result_ref,
        "evidence_refs": [evidence_ref], "thread_id": "thr_harness",
        "run_id": "run_harness", "turn_id": "turn_harness_1",
        "attempt_id": "attempt_harness_1", "model_context_id": "ctx_ieee39",
        "model_id": "ieee39", "model_revision": "revision:sha256:" + "a" * 64,
        "source": {"capability_id": "analysis_powerflow_ac_run",
                    "domain_pack_id": "pandapower_static_analysis",
                    "implementation_family": "pandapower"},
        "status": "completed", "summary": [], "tables": [], "element_refs": [],
        "overlay": None,
    }

    class _ProjectionSession(_PiSession):
        def prompt_and_wait(self, question: str, **kwargs: object) -> str:
            del question
            callback = kwargs["on_semantic_event"]
            assert callable(callback)
            callback({
                "type": "tool_result", "toolCallId": "call-projection",
                "toolName": "grid_powerflow_run", "ok": True,
                "result_refs": [result_ref], "evidence_refs": [evidence_ref],
            })
            return "projected answer"

        def admit_attempt(self, claim, answer, result_refs, evidence_refs, tool_events):
            del tool_events
            assert answer == "projected answer"
            assert result_refs == (result_ref,)
            assert evidence_refs == (evidence_ref,)
            admitted_projection = dict(projection)
            admitted_projection["turn_id"] = claim.attempt.turn_id
            admitted_projection["attempt_id"] = claim.attempt.attempt_id
            return AdmittedAttemptAnswer(
                answer, "authority_backed", "lineage_verified",
                (result_ref,), (evidence_ref,), result_projections=(admitted_projection,),
            )

    claim = service.claim_attempt("worker", lease_seconds=30)
    assert claim is not None
    session = _ProjectionSession()
    result = HarnessAttemptRunner(
        service, HarnessPiClient(session, admission=session.admit_attempt),
    ).run(claim)

    assert result.status == "completed"
    terminal = service.read_events("thr_harness", 0).events[-1]
    assert terminal.payload["result_projections"][0]["result_id"] == projection["result_id"]


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
        service, HarnessPiClient(
            _HeartbeatSession(), admission=lambda _claim, answer, _results, _evidence, _events: AdmittedAttemptAnswer(
                answer, "limited", "limited",
            ),
        ), lease_seconds=30,
    ).run(claim)
    assert result.status == "completed"


def test_professional_route_rejects_limited_admission() -> None:
    service = _thread_service()
    service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_harness_limited",
        "idempotency_key": "idem_harness_limited", "thread_id": "thr_harness",
        "run_id": "run_harness", "kind": "send_professional", "expected_event_seq": 0,
        "payload": {"text": "hello"},
    })
    claim = service.claim_attempt("worker", lease_seconds=30)
    assert claim is not None
    result = HarnessAttemptRunner(
        service,
        HarnessPiClient(
            _PiSession(),
            admission=lambda _claim, answer, _results, _evidence, _events: AdmittedAttemptAnswer(
                answer, "limited", "limited",
            ),
        ),
        turn_router=DefaultTurnRouter(),
    ).run(claim)
    assert result.status == "failed"
    assert result.error_code == "capability_required"


def test_explicit_professional_route_cannot_be_downgraded_by_classifier() -> None:
    service = _thread_service()
    service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_harness_explicit",
        "idempotency_key": "idem_harness_explicit", "thread_id": "thr_harness",
        "run_id": "run_harness", "kind": "send_professional", "expected_event_seq": 0,
        "payload": {"text": "hello"},
    })
    claim = service.claim_attempt("worker", lease_seconds=30)
    assert claim is not None
    result = HarnessAttemptRunner(
        service,
        HarnessPiClient(
            _PiSession(),
            admission=lambda _claim, answer, _results, _evidence, _events: AdmittedAttemptAnswer(
                answer, "limited", "limited",
            ),
        ),
        turn_router=DefaultTurnRouter(decision_router=FakeDecisionRouter("ordinary")),
    ).run(claim)
    assert result.status == "failed"
    assert result.error_code == "capability_required"
