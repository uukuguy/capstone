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
from capstone_agent.kernel_pi_session import _build_kernel_admission
from capstone_agent.thread_worker import run_pending_attempt


def test_incomplete_catalog_stream_commits_the_complete_application_answer():
    service = _thread_service()
    service.set_catalog_context({"models": [
        {"model_id": "model-first", "display_name": "First", "implementation_family": "pypsa"},
        {"model_id": "model-second", "display_name": "Second", "implementation_family": "pypsa"},
    ]})
    service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_catalog_commit",
        "idempotency_key": "idem_catalog_commit", "thread_id": "thr_harness",
        "run_id": "run_harness", "kind": "send_auto", "expected_event_seq": 0,
        "payload": {"text": "有哪些 PyPSA 的电网模型？"},
    })

    class IncompleteCatalogSession(_PiSession):
        def prompt_and_wait(self, question: str, **kwargs: object) -> str:
            callback = kwargs["on_semantic_event"]
            assert callable(callback)
            callback({"type": "text_delta", "text": "有两个模型：model-first。"})
            return "有两个模型：model-first。"

    session = IncompleteCatalogSession()
    result = run_pending_attempt(
        service, lambda claim: HarnessPiClient(session, admission=_build_kernel_admission(())),
        worker_id="catalog-worker",
    )
    assert result is not None and result.status == "completed" and session.stopped
    events = service.read_events("thr_harness", 0).events
    terminal = events[-1]
    assert terminal.event_type == "attempt_completed"
    assert "model-first" in terminal.payload["answer"] and "model-second" in terminal.payload["answer"]
    assert terminal.payload["result_refs"] == terminal.payload["evidence_refs"] == []
    assert terminal.payload["admission"]["assurance"] == "deterministic_information"


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


def _network_projection() -> dict[str, object]:
    return {
        "schema": "capstone-network-view/2.0", "ordinal": 1,
        "diagram": {
            "schema": "capstone-network-diagram/1.0",
            "model": {
                "id": "ieee39", "revision": "revision:sha256:" + "a" * 64,
                "source": "gridctl",
            },
            "coordinate_system": "schematic",
            "buses": [
                {"id": "0", "label": "Bus 0", "x": 0.0, "y": 0.0, "vn_kv": 345.0},
                {"id": "1", "label": "Bus 1", "x": 1.0, "y": 0.0, "vn_kv": 345.0},
            ],
            "branches": [{"id": "line:1", "kind": "line", "label": "Line 1",
                          "from_bus": "0", "to_bus": "1"}],
        },
        "layer": {"focus_ids": [], "next_focus_ids": [], "overlay": None},
    }


class _NetworkProvider:
    def __init__(self, projection=None, error: Exception | None = None) -> None:
        self.projection = projection
        self.error = error

    def project(self, claim, result_refs, evidence_refs, tool_events):
        del claim, result_refs, evidence_refs, tool_events
        if self.error is not None:
            raise self.error
        return self.projection


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


def test_application_observer_gets_native_event_without_publishing_raw_details():
    observed = []
    public = []

    class Observer(_NetworkProvider):
        def observe_runtime_event(self, event):
            observed.append(event)

    class Session(_PiSession):
        def prompt_and_wait(self, question, **kwargs):
            kwargs["on_semantic_event"]({"type": "provider_internal", "private_rows": ["raw"]})
            return "answer"

    client = HarnessPiClient(Session(), network_projection_provider=Observer())
    assert client.prompt("hello", on_event=public.append) == "answer"
    assert observed[0]["private_rows"] == ["raw"]
    assert public[0]["payload"] == {"native_type": "provider_internal"}


def test_normalizer_preserves_nested_authority_refs_and_model_identity() -> None:
    result_ref = "result:sha256:" + "a" * 64
    context_ref = "context:sha256:" + "b" * 64
    revision_ref = "revision:sha256:" + "c" * 64
    event = normalize_runtime_event({
        "type": "tool_execution_end", "toolName": "grid_analysis_powerflow_ac",
        "result": {"details": {
            "ok": True, "capability": "analysis.powerflow.ac.run",
            "result": {"result_ref": result_ref, "context_ref": context_ref,
                       "revision_ref": revision_ref, "model": "case24_ieee_rts",
                       "raw_network": {"secret": "must-not-cross"}},
        }},
    }, runtime_mode="capstone")
    payload = event["payload"]
    assert payload["result_refs"] == [result_ref]
    assert payload["context_ref"] == context_ref
    assert payload["model_revision"] == revision_ref
    assert payload["model_id"] == "case24_ieee_rts"
    assert "must-not-cross" not in str(payload)


def test_canonical_rpc_result_keeps_authority_references_and_identity() -> None:
    from capability_agent.runtime.rpc import _canonical_tool_result_event

    result_ref = "result:sha256:" + "a" * 64
    context_ref = "context:sha256:" + "b" * 64
    revision_ref = "revision:sha256:" + "c" * 64
    canonical = _canonical_tool_result_event({
        "type": "tool_execution_end", "toolCallId": "call_1",
        "result": {"details": {
            "ok": True, "capability": "analysis.powerflow.ac.run",
            "result": {"result_ref": result_ref, "context_ref": context_ref,
                       "revision_ref": revision_ref, "model": "case24_ieee_rts"},
            "evidence_refs": ["evidence:sha256:" + "d" * 64],
        }},
    })
    assert canonical is not None
    payload = normalize_runtime_event(canonical, runtime_mode="capstone")["payload"]
    assert payload["result_refs"] == [result_ref]
    assert payload["context_ref"] == context_ref
    assert payload["model_revision"] == revision_ref
    assert payload["model_id"] == "case24_ieee_rts"
    assert payload["evidence_refs"] == ["evidence:sha256:" + "d" * 64]


def test_canonical_authority_business_details_do_not_hide_pypsa_identity() -> None:
    from capability_agent.runtime.rpc import _canonical_tool_result_event

    model_ref = "model:sha256:" + "b" * 64
    result_ref = "result:sha256:" + "a" * 64
    canonical = _canonical_tool_result_event({
        "type": "tool_execution_end", "result": {"details": {
            "ok": True, "capability": "model.inspect",
            "result": {"model_ref": model_ref, "result_ref": result_ref,
                       "details": {"component": "Bus", "secret": "must-not-cross"}},
        }},
    })
    assert canonical is not None
    payload = normalize_runtime_event(canonical, runtime_mode="capstone")["payload"]
    assert payload["model_ref"] == model_ref
    assert payload["result_refs"] == [result_ref]
    assert "must-not-cross" not in str(payload)


@pytest.mark.parametrize("identity", [
    {"model_id": "ieee39", "model": "case24_ieee_rts"},
    {"revision_ref": "revision:sha256:" + "a" * 64,
     "model_revision": "revision:sha256:" + "b" * 64},
    {"model_id": "x" * 513}, {"context_ref": ""},
    {"revision_ref": None}, {"model_ref": {"id": "foreign"}},
])
def test_successful_tool_cannot_hide_invalid_or_conflicting_identity(identity) -> None:
    with pytest.raises(ValueError, match="identity"):
        normalize_runtime_event({
            "type": "tool_result", "ok": True, "capability": "context.open",
            "result": identity,
        }, runtime_mode="capstone")


def test_successful_tool_rejects_conflict_between_native_metadata_and_result() -> None:
    with pytest.raises(ValueError, match="identity"):
        normalize_runtime_event({
            "type": "tool_execution_end", "model_id": "ieee39",
            "result": {"details": {"ok": True, "capability": "context.open",
                                   "result": {"model_id": "case24_ieee_rts"}}},
        }, runtime_mode="capstone")


def test_failed_tool_cannot_introduce_nested_result_refs() -> None:
    event = normalize_runtime_event({
        "type": "tool_execution_end", "result": {"details": {
            "ok": False, "result": {"result_ref": "result:sha256:" + "a" * 64},
        }},
    }, runtime_mode="capstone")
    assert "result_refs" not in event["payload"]


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


def test_harness_attempt_runner_persists_network_events_before_terminal_answer() -> None:
    service = _thread_service()
    service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_harness_network",
        "idempotency_key": "idem_harness_network", "thread_id": "thr_harness",
        "run_id": "run_harness", "kind": "send_ordinary", "expected_event_seq": 0,
        "payload": {"text": "hello"},
    })
    claim = service.claim_attempt("worker", lease_seconds=30)
    assert claim is not None
    result = HarnessAttemptRunner(service, HarnessPiClient(
        _PiSession(),
        admission=lambda _claim, answer, _results, _evidence, _events: AdmittedAttemptAnswer(
            answer, "limited", "limited",
        ),
        network_projection_provider=_NetworkProvider(_network_projection()),
    )).run(claim)

    assert result.status == "completed"
    event_types = [event.event_type for event in service.read_events("thr_harness", 0).events]
    assert event_types[-3:] == ["network_diagram", "network_layer", "attempt_completed"]


def test_network_provider_failure_keeps_attempt_completed_and_emits_unavailable() -> None:
    service = _thread_service()
    service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_harness_network_failure",
        "idempotency_key": "idem_harness_network_failure", "thread_id": "thr_harness",
        "run_id": "run_harness", "kind": "send_ordinary", "expected_event_seq": 0,
        "payload": {"text": "hello"},
    })
    claim = service.claim_attempt("worker", lease_seconds=30)
    assert claim is not None
    result = HarnessAttemptRunner(service, HarnessPiClient(
        _PiSession(),
        admission=lambda _claim, answer, _results, _evidence, _events: AdmittedAttemptAnswer(
            answer, "limited", "limited",
        ),
        network_projection_provider=_NetworkProvider(error=RuntimeError("authority unavailable")),
    )).run(claim)

    assert result.status == "completed"
    events = service.read_events("thr_harness", 0).events
    assert events[-2].event_type == "network_layer_unavailable"
    assert events[-2].payload == {"ordinal": 1, "code": "projection_source_unavailable"}
    assert events[-1].event_type == "attempt_completed"


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


def test_professional_model_observation_admission_is_accepted_without_evidence() -> None:
    service = _thread_service()
    service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_harness_observation",
        "idempotency_key": "idem_harness_observation", "thread_id": "thr_harness",
        "run_id": "run_harness", "kind": "send_auto", "expected_event_seq": 0,
        "payload": {"text": "IEEE-39 有哪些母线和线路?"},
    })

    class _ObservationSession(_PiSession):
        def prompt_and_wait(self, question: str, **kwargs: object) -> str:
            del question
            callback = kwargs["on_semantic_event"]
            assert callable(callback)
            for capability in ("context.open", "model.dataset.query"):
                callback({
                    "type": "tool_result", "toolCallId": capability,
                    "toolName": "grid_" + capability.replace(".", "_"),
                    "capability": capability, "ok": True,
                })
            return "IEEE-39 包含 39 条母线和 46 条线路。"

        def admit_attempt(self, claim, answer, result_refs, evidence_refs, tool_events):
            del claim, result_refs, evidence_refs, tool_events
            return AdmittedAttemptAnswer(
                answer, "offline_information", "deterministic_information",
                diagnostic_codes=("current_model_observation_verified",),
            )

    claim = service.claim_attempt("worker", lease_seconds=30)
    assert claim is not None
    session = _ObservationSession()
    result = HarnessAttemptRunner(
        service, HarnessPiClient(session, admission=session.admit_attempt),
    ).run(claim)

    assert result.status == "completed"
    assert result.error_code is None


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
