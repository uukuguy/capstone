"""Topology-only Thread answers use current authority observations, not AC evidence."""

import pytest

from capstone_agent.thread_commands import ThreadCommandFactory
from capstone_agent.thread_protocol import ModelContextSnapshot
from capstone_agent.thread_service import InMemoryThreadService
from capstone_agent.thread_worker import run_pending_attempt
from grid_agent import hosted

from test_thread_model_sequence import ModelSequenceSession


OPEN_TOPOLOGY = "打开当前电网模型并显示电网拓扑。"


class TopologyObservationSession(ModelSequenceSession):
    """Finite decisions with the same capability set as the reported failure."""

    def prompt_and_wait(self, question, *, on_semantic_event, correlation_id, on_heartbeat):
        assert self._started and question == self.claim.instruction
        assert correlation_id == self.claim.attempt.attempt_id
        on_heartbeat()
        invoke = lambda capability, arguments: self._invoke(capability, arguments, on_semantic_event)
        context = invoke("context.get", {"context_ref": self.binding.context_ref})
        components = invoke("topology.components.get", {"context_ref": self.binding.context_ref})
        invoke("model.dataset.list", {"context_ref": self.binding.context_ref})
        return f"Model {context['model']}: {components['component_count']} connected components."


def build_topology_session(claim, context, profiles):
    return TopologyObservationSession(claim, context, profiles)


def recognize_topology_task(claim, *, on_heartbeat, requirement_schemas):
    from capstone_agent.task_understanding import recognize_decision
    assert claim.instruction == OPEN_TOPOLOGY
    selected = [item for item in requirement_schemas if item["schema"] == "capstone-professional-task/1"]
    assert len(selected) == 1
    on_heartbeat()
    return recognize_decision(claim.task_request, {"schema": "capstone-task-understanding/2", "goals": [{
        "id": "topology", "purpose": OPEN_TOPOLOGY, "subject": "selected model topology", "scope": "full",
        "scenario": "baseline", "change": None, "conclusion": "description", "measure": None,
        "obligations": ["Report registered current-model topology observations without AC calculations"],
        "missing_requirements": [], "execution": "professional", "dependencies": [],
        "domain_request": {"binding_id": selected[0]["binding_id"], "schema": selected[0]["schema"],
            "payload": {"purpose": OPEN_TOPOLOGY}}}], "answer_policy": {"language": "en", "scale": "standard"}},
        recognizer="controlled-topology-observation")


setattr(build_topology_session, "recognize_task", recognize_topology_task)


@pytest.mark.parametrize("model_id", ["four_loads_with_branches_out", "case24_ieee_rts", "ieee39", "GBnetwork", "case9241pegase"])
def test_topology_only_answer_completes_and_projects_the_selected_model(monkeypatch, tmp_path, model_id):
    monkeypatch.setenv("CAPSTONE_RUNS_ROOT", str(tmp_path))
    monkeypatch.setattr(hosted, "select_validation_builder", lambda *_args: build_topology_session)
    assembly = hosted.build_registered_pandapower_thread_application()
    model = assembly.catalog.resolve(model_id)
    selection = assembly.capability_catalog.resolve(model)
    context = ModelContextSnapshot(
        "ctx_topology", model.model_id, model.model_revision,
        model.implementation_family, "sel_0", selection.enabled_profiles,
    )
    service = InMemoryThreadService.from_document({
        "schema": "capstone-thread-snapshot/1", "thread_id": "thr_topology",
        "run": {"run_id": "run_topology", "state": "open"},
        "active_model_context": context.to_document(), "active_grid_page_id": "page_topology",
        "current_attempt": None, "last_event_seq": 0, "base_event_seq": 0,
    }, model_catalog=assembly.catalog, capability_catalog=assembly.capability_catalog)
    commands = ThreadCommandFactory("thr_topology", "run_topology")
    try:
        for number in range(2):
            before = service.snapshot("thr_topology").last_event_seq
            receipt = service.submit_command(commands.send_professional(
                OPEN_TOPOLOGY, expected_event_seq=before,
                command_id=f"cmd_topology_{number}", idempotency_key=f"idem_topology_{number}",
            ))
            assert receipt.status == "accepted"
            outcome = run_pending_attempt(
                service, assembly.runtime_factory, worker_id="worker_topology",
                lease_seconds=120, turn_router=assembly.turn_router_for_worker(),
                implementation_family="pandapower",
            )
            assert outcome is not None and outcome.status == "completed", outcome
            assert not outcome.result_refs and not outcome.evidence_refs
            events = service.read_events("thr_topology", before).events
            understanding = next(event.payload["understanding"] for event in events if event.event_type == "task_understanding_created")
            assert understanding["goals"][0]["domain_request"]["schema"] == "capstone-professional-task/1"
            resolution = next(event.payload["goals"] for event in events if event.event_type == "task_requirements_resolved")
            assert resolution[0]["status"] == "uncertified" and resolution[0]["execution_required"] is True
            assert not any(event.event_type in {"network_layer_unavailable", "attempt_failed"} for event in events)
            diagram = next(event.payload["diagram"] for event in events if event.event_type == "network_diagram")
            assert diagram["model"]["id"] == model_id
            assert diagram["model"]["revision"] == model.model_revision
            assert diagram["buses"] and diagram["branches"]
            completed = events[-1]
            assert completed.event_type == "attempt_completed"
            assert completed.payload["admission"]["mode"] == "offline_information"
            assert "task_goal_coverage_unverified" in completed.payload["admission"]["diagnostic_codes"]
            assert all(event.model_context_id == context.id for event in events)
            assert service.snapshot("thr_topology").active_model_context == context
    finally:
        assembly.capability_context_owner.close()
