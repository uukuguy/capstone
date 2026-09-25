"""One granted two-binding run reaches real HiGHS and target-owned evidence."""

from __future__ import annotations

from types import SimpleNamespace

import pytest


def test_prepared_sector_binding_requires_receipt_and_admits_balance(tmp_path) -> None:
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
    from pypsa_sector_coupling.profile import build_pypsa_sector_coupling_profile

    model = build_pypsa_network_modeling_profile()
    sector = build_pypsa_sector_coupling_profile(source_binding_id="model")
    assert sector.missing_application_components() == ()
    registry = DomainRegistry()
    registry.register(model.manifest.domain_id, model.manifest.version, lambda: model)
    registry.register(sector.manifest.domain_id, sector.manifest.version, lambda: sector)
    workspace = ApplicationWorkspace.create(
        tmp_path / "runs", run_id="sector-app", binding_ids=("model", "sector")
    )
    profile = ApplicationProfile(
        manifest=ApplicationManifest(
            "pypsa-sector-conformance", "1.0", "PyPSA sector conformance",
            "application-context/1.0", "application-result/1.0", "artifact/1.0", "agent_",
        ),
        domains=(
            DomainBinding("model", "pypsa_model_", model, CredentialScope(), DataSharingPolicy()),
                DomainBinding("sector", "pypsa_sector_", sector, CredentialScope(), DataSharingPolicy()),
        ),
        output_renderer=JsonOutputRenderer(),
        application_policy=SimpleNamespace(load=lambda: "Use registered PyPSA capabilities."),
        report_shell=GenericReportShell(),
        acceptance_profile=SimpleNamespace(cases=lambda: ()),
        reference_grants=(ReferenceGrant("model", "sector", "model", "sector", "sector"),),
    )

    class EmptyCredentials:
        def issue(self, *, binding_id, scope):
            return SimpleNamespace(scope_id=scope.scope_id, credentials={})

    prepared = prepare_application(
        profile, registry=registry, workspace=workspace.root, credentials=EmptyCredentials(),
    )
    store = ApplicationContextStore.initialize(workspace)
    source = prepared.bindings["model"]
    target = prepared.bindings["sector"]
    opened = source.endpoint.executor.invoke("model.open", {"catalog_id": "electricity-hydrogen"})
    service = ReferenceHandoffService(profile, workspace, store, prepared.bindings)

    with pytest.raises(Exception, match="transport failed"):
        target.endpoint.executor.invoke("sector.hydrogen_balance", {
            "reference": opened["model_ref"],
            "handoff_ref": "handoff:sha256:" + "0" * 64,
        })
    result, receipt = service.invoke_target(
        source_binding_id="model", target_binding_id="sector",
        reference=opened["model_ref"], reference_kind="model",
        purpose="sector", capability="sector.hydrogen_balance", arguments={},
    )
    assert receipt.target_binding_id == "sector"
    assert result["objective"] == pytest.approx(1000.0)
    assert target.runtime.authority.admit(
        "sector.hydrogen_balance", result, tuple(result["evidence_refs"])
    ).results[0].reference == result["result_ref"]
    with pytest.raises(Exception):
        source.runtime.authority.verify_result(result["result_ref"])
    delta = sector.projector_registry.require("pypsa-sector-result-v1").project(
        VerifiedInvocation(
            capability="sector.hydrogen_balance", projector_id="pypsa-sector-result-v1",
            result_kind="pypsa-sector.result", result=result, arguments={},
            turn_id="turn-1", result_paths={}, active_revision_ref=None,
        )
    )
    state = sector.state_adapter.merge(binding_id="sector", state={}, delta=delta)
    view = sector.state_adapter.build_context(binding_id="sector", state=state)
    assert sector.output_contract.build(
        binding_id="sector", context=view, committed_answers=(),
    ) == {"result_refs": [result["result_ref"]]}
    assert "Admitted results: 1" in sector.presentation_provider.render_report(view)
