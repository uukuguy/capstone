"""Real-authority Thread sequence through the hosted Pi event boundary.

The injectable session also supports an isolated browser validation bridge.
It replaces Provider decisions, while all facts and artifacts come from the
normal prepared registered authority.
"""

from __future__ import annotations

import json

from capstone_agent.kernel_pi_session import _build_kernel_admission
from capstone_agent.thread_commands import ThreadCommandFactory
from capstone_agent.thread_protocol import ModelContextSnapshot, ThreadSnapshot
from capstone_agent.thread_service import InMemoryThreadService
from capstone_agent.thread_worker import run_pending_attempt
from grid_agent import hosted


OPEN_RTS = "打开 case24_ieee_rts 电网模型"
FLOW_RTS = "对刚打开的模型运行交流潮流"
FLOW_RTS_REPEAT = "再次对当前模型运行交流潮流"
RANK_RTS = "沿用当前潮流结果列出负载率最高的三条线路"
OPEN_IEEE_ENDPOINT = "打开 ieee39 电网模型并查询线路 11 两端母线"
ENDPOINT_IEEE = "查询当前模型线路 11 两端母线"
CONTINGENCY_IEEE = "对当前模型线路 11 运行单一故障校核"


class ModelSequenceSession:
    """Finite Provider-free decisions over the selected prepared grid endpoint."""

    def __init__(self, claim, context, profiles):
        assert len(profiles) == 1
        assert context.model_context == claim.model_context
        self.claim = claim
        self.context = context
        self.profiles = profiles
        self.binding = profiles[0].model_binding
        assert self.binding.model_id == claim.model_context.model_id
        assert self.binding.model_revision == claim.model_context.model_revision
        self.runtime = profiles[0].prepared_application.bindings["grid"].runtime
        catalog = json.loads(self.runtime.tool_catalog_path.read_text())
        self.tools = {tool["capability"]: tool for tool in catalog["tools"]}
        assert self.tools["context.open"]["input_schema"]["properties"]["model_id"]["enum"] == [self.binding.model_id]
        assert self.tools["analysis.powerflow.ac.run"]["input_schema"]["properties"]["context_ref"]["enum"] == [self.binding.context_ref]
        self.calls = []
        self.native_events = []
        self._admission = _build_kernel_admission(profiles)
        self._started = False

    def start(self):
        self._started = True

    def stop(self):
        self._started = False

    def admit_attempt(self, claim, answer, result_refs, evidence_refs, tool_events):
        return self._admission(claim, answer, result_refs, evidence_refs, tool_events)

    def _invoke(self, capability, arguments, callback):
        tool = self.tools[capability]
        result = self.runtime.executor.invoke(capability, arguments)
        refs = result.get("evidence_refs", [])
        if isinstance(result.get("evidence_ref"), str):
            refs = [*refs, result["evidence_ref"]]
        self.runtime.authority.admit(capability, result, tuple(refs))
        event = {
            "type": "tool_execution_end",
            "toolCallId": f"call_{self.claim.attempt.attempt_id}_{len(self.calls)}",
            "toolName": tool["name"],
            "result": {
                "content": [{"type": "text", "text": json.dumps(result)}],
                "details": {
                    "event": "tool_result", "capability": capability, "ok": True,
                    "capability_key": {"binding_id": "grid", "capability_id": capability},
                    "projector_id": tool.get("projector_id"),
                    "result_kind": tool.get("result_kind"),
                    "result": result, "evidence_refs": list(refs),
                },
            },
        }
        # This is the native canonical Pi tool shape. Do not put extracted
        # identities or result references at the event's top level.
        self.native_events.append(event)
        callback(event)
        self.calls.append({"capability": capability, "arguments": arguments, "result": result})
        return result

    def prompt_and_wait(self, question, *, on_semantic_event, correlation_id, on_heartbeat):
        assert self._started
        assert question == self.claim.instruction
        assert correlation_id == self.claim.attempt.attempt_id
        on_heartbeat()
        invoke = lambda capability, arguments: self._invoke(capability, arguments, on_semantic_event)
        if question == RANK_RTS:
            assert self.claim.prior_results
            prior = self.claim.prior_results[0]
            ranked = invoke("result.branches.rank", {
                "result_ref": prior.result_ref, "metric": "loading_percent",
                "direction": "descending", "limit": 3, "element_kind": "line",
            })
            for reference in prior.evidence_refs:
                invoke("evidence.get", {"evidence_ref": reference})
            return f"Ranked {len(ranked['branches'])} lines from existing result {prior.result_ref}."
        if question in {OPEN_RTS, OPEN_IEEE_ENDPOINT}:
            opened = invoke("context.open", {"model_id": self.binding.model_id})
            assert opened["context_ref"] == self.binding.context_ref
            if question == OPEN_RTS:
                return f"Opened {opened['model']} at {opened['revision_ref']}."
        if question in {FLOW_RTS, FLOW_RTS_REPEAT}:
            arguments = {"context_ref": self.binding.context_ref}
            if question == FLOW_RTS_REPEAT:
                arguments["calculate_voltage_angles"] = False
            result = invoke("analysis.powerflow.ac.run", arguments)
            if question == FLOW_RTS:
                ranking = invoke("result.branches.rank", {
                    "result_ref": result["result_ref"], "metric": "loading_percent",
                    "direction": "descending", "limit": 3, "element_kind": "line",
                })
                assert ranking["result_ref"] == result["result_ref"]
                assert "evidence_ref" not in ranking and "evidence_refs" not in ranking
            on_heartbeat()
            return f"AC flow converged: {result['converged']}; active loss {result['total_active_loss']['value']} MW."
        if question in {OPEN_IEEE_ENDPOINT, ENDPOINT_IEEE, CONTINGENCY_IEEE}:
            endpoint = invoke("topology.branch.endpoints.get", {
                "context_ref": self.binding.context_ref, "kind": "line",
                "namespace": "pandapower_index", "identifier": "11",
            })
            if question == CONTINGENCY_IEEE:
                contingency = invoke("analysis.contingency.n_minus_one.run", {
                    "context_ref": self.binding.context_ref,
                    "branch_refs": [endpoint["branch"]["asset_ref"]],
                })
                return f"Contingency analysis status: {contingency['status']}."
            on_heartbeat()
            return f"Line {endpoint['branch']['index']} connects buses {endpoint['from_bus']['index']} and {endpoint['to_bus']['index']}."
        raise ValueError("model sequence instruction is not registered by this test session")


def build_model_sequence_session(claim, context, profiles):
    return ModelSequenceSession(claim, context, profiles)


def test_hosted_thread_model_switch_flow_endpoint_and_snapshot_share_authority_identity(monkeypatch, tmp_path):
    sessions = []

    def build(claim, context, profiles):
        session = build_model_sequence_session(claim, context, profiles)
        sessions.append(session)
        return session

    monkeypatch.setenv("CAPSTONE_RUNS_ROOT", str(tmp_path))
    monkeypatch.setattr(hosted, "select_validation_builder", lambda *_args: build)
    assembly = hosted.build_registered_pandapower_thread_application()
    initial = assembly.catalog.resolve("ieee39")
    selection = assembly.capability_catalog.resolve(initial)
    initial_context = ModelContextSnapshot(
        "ctx_sequence_initial", initial.model_id, initial.model_revision,
        initial.implementation_family, "sel_0", selection.enabled_profiles,
    )
    service = InMemoryThreadService.from_document({
        "schema": "capstone-thread-snapshot/1", "thread_id": "thr_sequence",
        "run": {"run_id": "run_sequence", "state": "open"},
        "active_model_context": initial_context.to_document(),
        "active_grid_page_id": "page_ieee39", "current_attempt": None,
        "last_event_seq": 0, "base_event_seq": 0,
    }, model_catalog=assembly.catalog, capability_catalog=assembly.capability_catalog)
    commands = ThreadCommandFactory("thr_sequence", "run_sequence")
    command_number = 0

    def submit(command_builder, value):
        nonlocal command_number
        command_number += 1
        receipt = service.submit_command(command_builder(
            value, expected_event_seq=service.snapshot("thr_sequence").last_event_seq,
            command_id=f"cmd_sequence_{command_number}", idempotency_key=f"idem_sequence_{command_number}",
        ))
        assert receipt.status == "accepted", receipt

    def run(question):
        previous_cursor = service.snapshot("thr_sequence").last_event_seq
        submit(commands.send_professional, question)
        outcome = run_pending_attempt(
            service, assembly.runtime_factory, worker_id="worker_sequence", lease_seconds=120,
            turn_router=assembly.turn_router_for_worker(), implementation_family="pandapower",
        )
        assert outcome is not None and outcome.status == "completed", outcome
        events = service.read_events("thr_sequence", previous_cursor).events
        assert not any(event.event_type == "network_layer_unavailable" for event in events)
        diagram = next(event.payload["diagram"] for event in events if event.event_type == "network_diagram")
        layer = next(event.payload["layer"] for event in events if event.event_type == "network_layer")
        snapshot = service.snapshot("thr_sequence")
        assert diagram["model"]["id"] == snapshot.active_model_context.model_id
        assert diagram["model"]["revision"] == snapshot.active_model_context.model_revision
        assert all(event.model_context_id == snapshot.active_model_context.id
                   for event in events if event.event_type in {"tool_completed", "network_diagram", "network_layer", "attempt_completed"})
        completed = next(event for event in events if event.event_type == "attempt_completed")
        assert tuple(completed.payload["result_refs"]) == outcome.result_refs
        assert tuple(completed.payload["evidence_refs"]) == outcome.evidence_refs
        return outcome, diagram, layer, snapshot, events

    try:
        submit(commands.switch_model, "case24_ieee_rts")
        pending = service.snapshot("thr_sequence")
        assert pending.active_model_context == initial_context
        assert pending.pending_model_switch.model_id == "case24_ieee_rts"

        opened, diagram, layer, rts_snapshot, _events = run(OPEN_RTS)
        rts_context = rts_snapshot.active_model_context
        assert rts_context.id != initial_context.id
        assert rts_context.model_id == "case24_ieee_rts"
        assert rts_context.model_revision == assembly.catalog.resolve("case24_ieee_rts").model_revision
        assert rts_snapshot.pending_model_switch is None
        assert len(diagram["buses"]) == 24
        assert not opened.result_refs and not opened.evidence_refs
        assert layer["focus_ids"] == []

        flow, flow_diagram, _layer, flow_snapshot, events = run(FLOW_RTS)
        assert flow_snapshot.active_model_context == rts_context
        assert flow_diagram["model"] == diagram["model"]
        assert flow.result_refs and flow.evidence_refs
        assert sessions[0].profiles[0] is sessions[1].profiles[0]
        flow_call = sessions[1].calls[0]
        assert flow_call["capability"] == "analysis.powerflow.ac.run"
        assert flow_call["arguments"]["context_ref"] == sessions[0].binding.context_ref
        assert flow_call["result"]["converged"] is True
        assert flow_call["result"]["revision_ref"] == rts_context.model_revision
        rank_call = sessions[1].calls[1]
        assert rank_call["capability"] == "result.branches.rank"
        assert rank_call["result"]["result_ref"] == flow_call["result"]["result_ref"]
        projected = flow_snapshot.result_projections[-1]
        assert projected.model_context_id == rts_context.id
        assert projected.model_id == "case24_ieee_rts"
        assert projected.result_ref == flow.result_refs[0]
        assert projected.status == "completed" and projected.overlay is not None
        normalized_tool = next(event.payload for event in events if event.event_type == "tool_completed")
        assert normalized_tool["result_refs"] == list(flow.result_refs)
        assert normalized_tool["binding_id"] == "grid"
        assert normalized_tool["context_ref"] == sessions[0].binding.context_ref
        assert normalized_tool["model_revision"] == rts_context.model_revision
        assert "result" not in normalized_tool

        ranked, _, rank_layer, ranked_snapshot, rank_events = run(RANK_RTS)
        assert ranked.result_refs == flow.result_refs
        assert ranked.evidence_refs == flow.evidence_refs
        assert [call["capability"] for call in sessions[-1].calls] == ["result.branches.rank", "evidence.get"]
        ranking_source = sessions[-1].calls[0]["result"]
        expected_ids = [f"line:{row['pandapower_index']}" for row in ranking_source["branches"]]
        assert rank_layer["focus_ids"] == expected_ids
        assert [item["id"] for item in rank_layer["overlay"]["values"]] == expected_ids
        assert rank_layer["overlay"]["source_ref"] == flow.result_refs[0]
        assert ranked_snapshot.active_model_context == rts_context
        assert len(ranked_snapshot.result_projections) == 2

        second_flow, _, _, repeated_snapshot, _ = run(FLOW_RTS_REPEAT)
        assert repeated_snapshot.active_model_context == rts_context
        assert second_flow.result_refs != flow.result_refs
        assert len(repeated_snapshot.result_projections) == 3
        assert repeated_snapshot.result_projections[0] == projected
        assert all(item.model_context_id == rts_context.id for item in repeated_snapshot.result_projections)

        submit(commands.switch_model, "ieee39")
        assert service.snapshot("thr_sequence").active_model_context == rts_context
        endpoint, ieee_diagram, ieee_layer, ieee_snapshot, _ = run(OPEN_IEEE_ENDPOINT)
        ieee_context = ieee_snapshot.active_model_context
        assert ieee_context.id != rts_context.id
        assert ieee_context.model_id == "ieee39"
        assert ieee_context.model_revision == initial_context.model_revision
        assert len(ieee_diagram["buses"]) == 39
        assert ieee_layer["focus_ids"] == ["line:11"]
        assert endpoint.evidence_refs and not endpoint.result_refs
        endpoint_source = sessions[-1].calls[-1]["result"]
        branch = next(branch for branch in ieee_diagram["branches"] if branch["id"] == "line:11")
        assert branch["from_bus"] == str(endpoint_source["from_bus"]["index"])
        assert branch["to_bus"] == str(endpoint_source["to_bus"]["index"])
        assert endpoint_source["revision_ref"] == ieee_context.model_revision
        assert ieee_snapshot.result_projections == repeated_snapshot.result_projections

        refreshed_document = json.loads(json.dumps(ieee_snapshot.to_document()))
        assert ThreadSnapshot.from_document(refreshed_document) == ieee_snapshot
        service = InMemoryThreadService.from_document(
            refreshed_document, model_catalog=assembly.catalog,
            capability_catalog=assembly.capability_catalog,
        )
        refreshed, refreshed_diagram, refreshed_layer, refreshed_snapshot, _ = run(ENDPOINT_IEEE)
        assert refreshed_snapshot.active_model_context == ieee_context
        assert refreshed_diagram == ieee_diagram
        assert refreshed_layer["focus_ids"] == ["line:11"]
        assert refreshed.evidence_refs == endpoint.evidence_refs
        assert refreshed_snapshot.result_projections == repeated_snapshot.result_projections

        contingency, _, _, contingency_snapshot, _ = run(CONTINGENCY_IEEE)
        contingency_source = sessions[-1].calls[-1]["result"]
        assert contingency.result_refs == (contingency_source["result_ref"],)
        root = sessions[-1].runtime.authority.verify_result(contingency.result_refs[0]).document
        assert root["evidence_refs"] == contingency_source["evidence_refs"]
        assert root["scenarios"]
        for evidence_ref in root["evidence_refs"]:
            evidence = sessions[-1].runtime.authority.verify_evidence(evidence_ref).document
            if evidence.get("result_ref") is not None:
                assert evidence["result_ref"] != contingency.result_refs[0]
                assert any(scenario.get("scenario_result_ref") == evidence["result_ref"]
                           for scenario in root["scenarios"])
        projected_contingency = contingency_snapshot.result_projections[-1]
        assert projected_contingency.result_ref == contingency.result_refs[0]
        assert set(projected_contingency.evidence_refs) == set(root["evidence_refs"])
        assert endpoint.evidence_refs[0] not in projected_contingency.evidence_refs
    finally:
        assembly.capability_context_owner.close()
