"""One granted two-binding run reaches real HiGHS and target-owned evidence."""

from __future__ import annotations

from types import SimpleNamespace

import pytest


def test_prepared_operations_binding_requires_receipt_and_admits_dispatch(tmp_path) -> None:
    from capability_agent.application.composition import prepare_application
    from capability_agent.application.context_store import ApplicationContextStore
    from capability_agent.application.manifest import ApplicationManifest
    from capability_agent.application.output import JsonOutputRenderer
    from capability_agent.application.profile import (
        ApplicationProfile,
        CredentialScope,
        DataSharingPolicy,
        DomainBinding,
        ReferenceGrant,
    )
    from capability_agent.application.reference_handoff import ReferenceHandoffService
    from capability_agent.application.registry import DomainRegistry
    from capability_agent.application.reporting import GenericReportShell
    from capability_agent.application.workspace import ApplicationWorkspace
    from capability_agent.domain.projection import VerifiedInvocation
    from pypsa_network_modeling.profile import build_pypsa_network_modeling_profile

    from pypsa_power_operations.profile import build_pypsa_power_operations_profile

    model = build_pypsa_network_modeling_profile()
    operations = build_pypsa_power_operations_profile(source_binding_id="model")
    assert operations.missing_application_components() == ()
    registry = DomainRegistry()
    registry.register(model.manifest.domain_id, model.manifest.version, lambda: model)
    registry.register(operations.manifest.domain_id, operations.manifest.version, lambda: operations)
    workspace = ApplicationWorkspace.create(
        tmp_path / "runs", run_id="ops-app", binding_ids=("model", "operations")
    )
    profile = ApplicationProfile(
        manifest=ApplicationManifest(
            "pypsa-ops-conformance", "1.0", "PyPSA operations conformance",
            "application-context/1.0", "application-result/1.0", "artifact/1.0", "agent_",
        ),
        domains=(
            DomainBinding("model", "pypsa_model_", model, CredentialScope(), DataSharingPolicy()),
            DomainBinding("operations", "pypsa_ops_", operations, CredentialScope(), DataSharingPolicy()),
        ),
        output_renderer=JsonOutputRenderer(),
        application_policy=SimpleNamespace(load=lambda: "Use registered PyPSA capabilities."),
        report_shell=GenericReportShell(),
        acceptance_profile=SimpleNamespace(cases=lambda: ()),
        reference_grants=(ReferenceGrant("model", "operations", "model", "operations", "operations"),),
    )

    class EmptyCredentials:
        def issue(self, *, binding_id, scope):
            return SimpleNamespace(scope_id=scope.scope_id, credentials={})

    prepared = prepare_application(
        profile, registry=registry, workspace=workspace.root, credentials=EmptyCredentials(),
    )
    store = ApplicationContextStore.initialize(workspace)
    source = prepared.bindings["model"]
    target = prepared.bindings["operations"]
    opened = source.endpoint.executor.invoke("model.open", {"catalog_id": "two-bus"})
    service = ReferenceHandoffService(profile, workspace, store, prepared.bindings)

    with pytest.raises(Exception, match="transport failed"):
        target.endpoint.executor.invoke("operations.dispatch", {
            "reference": opened["model_ref"],
            "handoff_ref": "handoff:sha256:" + "0" * 64,
        })
    result, receipt = service.invoke_target(
        source_binding_id="model", target_binding_id="operations",
        reference=opened["model_ref"], reference_kind="model",
        purpose="operations", capability="operations.dispatch", arguments={},
    )
    assert receipt.target_binding_id == "operations"
    assert result["objective"] == pytest.approx(800.0)
    assert target.runtime.authority.admit(
        "operations.dispatch", result, tuple(result["evidence_refs"])
    ).results[0].reference == result["result_ref"]
    projection = operations.projector_registry.result_projector.project_admitted(
        authority=target.runtime.authority,
        invoke=target.endpoint.executor.invoke,
        context_ref=opened["model_ref"],
        model_revision="revision:sha256:" + "a" * 64,
        model_context_id="ctx-ops",
        model_id="two-bus",
        thread_id="thread-ops", run_id="ops-app", turn_id="turn-1",
        attempt_id="attempt-1", result_refs=(result["result_ref"],),
        result_evidence={result["result_ref"]: tuple(result["evidence_refs"])},
    )
    assert projection[0]["status"] == "completed"
    assert any(item["table_id"] == "generator_dispatch" for item in projection[0]["tables"])
    with pytest.raises(Exception):
        source.runtime.authority.verify_result(result["result_ref"])
    delta = operations.projector_registry.require("pypsa-operations-result-v1").project(
        VerifiedInvocation(
            capability="operations.dispatch", projector_id="pypsa-operations-result-v1",
            result_kind="pypsa-operations.result", result=result, arguments={},
            turn_id="turn-1", result_paths={}, active_revision_ref=None,
        )
    )
    state = operations.state_adapter.merge(binding_id="operations", state={}, delta=delta)
    view = operations.state_adapter.build_context(binding_id="operations", state=state)
    assert operations.output_contract.build(
        binding_id="operations", context=view, committed_answers=(),
    ) == {"result_refs": [result["result_ref"]]}
    assert "Admitted results: 1" in operations.presentation_provider.render_report(view)

    ac, _ = service.invoke_target(
        source_binding_id="model", target_binding_id="operations",
        reference=opened["model_ref"], reference_kind="model",
        purpose="operations", capability="operations.ac_validate",
        arguments={"dispatch_result_ref": result["result_ref"]},
    )
    assert ac["converged"] is True
    assert target.runtime.authority.verify_result(ac["result_ref"]).document["details"]["dispatch_result_ref"] == result["result_ref"]

    for catalog_id, capability, arguments in (
        ("unit-commitment", "operations.commitment", {}),
        ("security-triangle", "operations.security_dispatch", {"outage_set_id": "triangle-l3"}),
    ):
        revision = source.endpoint.executor.invoke("model.open", {"catalog_id": catalog_id})
        solved, _ = service.invoke_target(
            source_binding_id="model", target_binding_id="operations",
            reference=revision["model_ref"], reference_kind="model",
            purpose="operations", capability=capability, arguments=arguments,
        )
        assert target.runtime.authority.admit(
            capability, solved, tuple(solved["evidence_refs"])
        ).results[0].document["capability"] == capability
