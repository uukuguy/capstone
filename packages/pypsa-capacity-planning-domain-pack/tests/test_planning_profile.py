"""One granted two-binding run reaches real HiGHS and target-owned evidence."""

from __future__ import annotations

from types import SimpleNamespace

import pytest


def test_prepared_planning_binding_requires_receipt_and_admits_expansion(tmp_path) -> None:
    from capability_agent.application.composition import prepare_application
    from capability_agent.application.context_store import ApplicationContextStore
    from capability_agent.application.manifest import ApplicationManifest
    from capability_agent.application.output import JsonOutputRenderer
    from capability_agent.application.profile import (
        ApplicationProfile, CredentialScope, DataSharingPolicy, DomainBinding,
        ReferenceGrant,
    )
    from capability_agent.application.reference_handoff import ReferenceHandoffService
    from capability_agent.application.registry import DomainRegistry
    from capability_agent.application.reporting import GenericReportShell
    from capability_agent.application.workspace import ApplicationWorkspace
    from capability_agent.domain.projection import VerifiedInvocation
    from pypsa_network_modeling.profile import build_pypsa_network_modeling_profile
    from pypsa_capacity_planning.profile import build_pypsa_capacity_planning_profile

    model = build_pypsa_network_modeling_profile()
    planning = build_pypsa_capacity_planning_profile(source_binding_id="model")
    assert planning.missing_application_components() == ()
    registry = DomainRegistry()
    registry.register(model.manifest.domain_id, model.manifest.version, lambda: model)
    registry.register(planning.manifest.domain_id, planning.manifest.version, lambda: planning)
    workspace = ApplicationWorkspace.create(
        tmp_path / "runs", run_id="plan-app", binding_ids=("model", "planning")
    )
    profile = ApplicationProfile(
        manifest=ApplicationManifest(
            "pypsa-plan-conformance", "1.0", "PyPSA planning conformance",
            "application-context/1.0", "application-result/1.0", "artifact/1.0", "agent_",
        ),
        domains=(
            DomainBinding("model", "pypsa_model_", model, CredentialScope(), DataSharingPolicy()),
            DomainBinding("planning", "pypsa_plan_", planning, CredentialScope(), DataSharingPolicy()),
        ),
        output_renderer=JsonOutputRenderer(),
        application_policy=SimpleNamespace(load=lambda: "Use registered PyPSA capabilities."),
        report_shell=GenericReportShell(),
        acceptance_profile=SimpleNamespace(cases=lambda: ()),
        reference_grants=(ReferenceGrant("model", "planning", "model", "planning", "planning"),),
    )

    class EmptyCredentials:
        def issue(self, *, binding_id, scope):
            return SimpleNamespace(scope_id=scope.scope_id, credentials={})

    prepared = prepare_application(
        profile, registry=registry, workspace=workspace.root, credentials=EmptyCredentials(),
    )
    store = ApplicationContextStore.initialize(workspace)
    source = prepared.bindings["model"]
    target = prepared.bindings["planning"]
    opened = source.endpoint.executor.invoke("model.open", {"catalog_id": "capacity-two-bus"})
    service = ReferenceHandoffService(profile, workspace, store, prepared.bindings)

    with pytest.raises(Exception, match="transport failed"):
        target.endpoint.executor.invoke("planning.capacity_expand", {
            "reference": opened["model_ref"],
            "handoff_ref": "handoff:sha256:" + "0" * 64,
        })
    result, receipt = service.invoke_target(
        source_binding_id="model", target_binding_id="planning",
        reference=opened["model_ref"], reference_kind="model",
        purpose="planning", capability="planning.capacity_expand", arguments={},
    )
    assert receipt.target_binding_id == "planning"
    assert result["objective"] == pytest.approx(4800.0)
    assert target.runtime.authority.admit(
        "planning.capacity_expand", result, tuple(result["evidence_refs"])
    ).results[0].reference == result["result_ref"]
    with pytest.raises(Exception):
        source.runtime.authority.verify_result(result["result_ref"])
    delta = planning.projector_registry.require("pypsa-planning-result-v1").project(
        VerifiedInvocation(
            capability="planning.capacity_expand", projector_id="pypsa-planning-result-v1",
            result_kind="pypsa-planning.result", result=result, arguments={},
            turn_id="turn-1", result_paths={}, active_revision_ref=None,
        )
    )
    state = planning.state_adapter.merge(binding_id="planning", state={}, delta=delta)
    view = planning.state_adapter.build_context(binding_id="planning", state=state)
    assert planning.output_contract.build(
        binding_id="planning", context=view, committed_answers=(),
    ) == {"result_refs": [result["result_ref"]]}
    assert "Admitted results: 1" in planning.presentation_provider.render_report(view)
