"""Real registered authorities must admit the Thread's model before dispatch."""
import json

import pytest

from capability_agent.application.workspace import ApplicationWorkspace
from capstone_agent.application import EmptyCredentialBroker, domain_registry
from capability_agent.application.composition import prepare_application
from capstone_agent.kernel_capability_preparation import AuthorityModelBinding, PreparedKernelApplicationProfile
from capstone_agent.kernel_reference_handoff import PreparedKernelReferenceHandoffs
from pypsa_agent.profile import build_profile
from pypsa_agent.thread_binding import verify_bound_model_reference


def test_thread_handoff_enables_registered_dispatch_and_rejects_foreign_reference(tmp_path):
    profile = build_profile()
    workspace = ApplicationWorkspace.create(tmp_path, binding_ids=("source", "operations"))
    prepared = prepare_application(profile, registry=domain_registry(profile),
        workspace=workspace.root, credentials=EmptyCredentialBroker())
    try:
        opened = prepared.bindings["source"].endpoint.executor.invoke("model.open", {"catalog_id": "two-bus"})
        reference = opened["model_ref"]
        bound = PreparedKernelApplicationProfile(profile, prepared, workspace,
            AuthorityModelBinding("source", "two-bus", "revision:sha256:" + "a" * 64, "pypsa", reference,
                model_reference_verifier=lambda ref: verify_bound_model_reference(
                    prepared.bindings["source"].runtime.authority, ref, model_id="two-bus", base_ref=reference)))
        handoffs = PreparedKernelReferenceHandoffs((bound,))
        index = json.loads(handoffs.path.read_text())
        receipt = index["handoffs"][0]
        assert receipt["reference"] == reference
        assert receipt["target_binding_id"] == "operations"
        result = prepared.bindings["operations"].endpoint.executor.invoke("operations.dispatch", {
            "reference": reference, "handoff_ref": receipt["handoff_ref"]})
        assert result["result_ref"] and result["evidence_refs"]
        derived = prepared.bindings["source"].endpoint.executor.invoke("model.derive", {
            "model_ref": reference, "load_id": "demand", "p_set_mw": 55.0})
        handoffs.observe({"type": "tool_result", "ok": True,
            "capability_key": {"binding_id": "source"}, "result": derived})
        resumed = PreparedKernelReferenceHandoffs((bound,))
        index = json.loads(resumed.path.read_text())
        descendant = next(row for row in index["handoffs"] if row["reference"] == derived["model_ref"])
        assert len(index["handoffs"]) == 2
        result = prepared.bindings["operations"].endpoint.executor.invoke("operations.dispatch", {
            "reference": derived["model_ref"], "handoff_ref": descendant["handoff_ref"]})
        assert result["result_ref"] and result["evidence_refs"]
        with pytest.raises(ValueError, match="bound"):
            handoffs.observe({"type": "tool_result", "ok": True,
                "capability_key": {"binding_id": "source"},
                "result": {"model_ref": "pypsa-model:sha256:" + "b" * 64}})
        assert json.loads(handoffs.path.read_text()) == index
    finally:
        for binding in prepared.bindings.values():
            binding.endpoint.close()
