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
            assert not any(event.event_type in {"network_layer_unavailable", "attempt_failed"} for event in events)
            diagram = next(event.payload["diagram"] for event in events if event.event_type == "network_diagram")
            assert diagram["model"]["id"] == model_id
            assert diagram["model"]["revision"] == model.model_revision
            assert diagram["buses"] and diagram["branches"]
            completed = events[-1]
            assert completed.event_type == "attempt_completed"
            assert completed.payload["admission"]["mode"] == "offline_information"
            assert all(event.model_context_id == context.id for event in events)
            assert service.snapshot("thr_topology").active_model_context == context
    finally:
        assembly.capability_context_owner.close()
