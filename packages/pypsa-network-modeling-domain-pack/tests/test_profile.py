from __future__ import annotations

from types import SimpleNamespace

import pytest


def test_complete_pack_prepares_and_admits_real_model_results(tmp_path) -> None:
    from capability_agent.application.manifest import ApplicationManifest
    from capability_agent.application.output import JsonOutputRenderer
    from capability_agent.application.profile import (
        ApplicationProfile, CredentialScope, DataSharingPolicy, DomainBinding,
    )
    from capability_agent.application.registry import DomainRegistry
    from capability_agent.application.composition import prepare_application
    from capability_agent.application.reporting import GenericReportShell
    from capability_agent.application.workspace import ApplicationWorkspace
    from pypsa_network_modeling.profile import build_pypsa_network_modeling_profile

    domain = build_pypsa_network_modeling_profile()
    assert domain.missing_application_components() == ()
    registry = DomainRegistry()
    registry.register(domain.manifest.domain_id, domain.manifest.version, lambda: domain)
    workspace = ApplicationWorkspace.create(
        tmp_path / "runs", run_id="model-run", binding_ids=("pypsa-model",)
    )
    profile = ApplicationProfile(
        manifest=ApplicationManifest(
            "pypsa-model-conformance", "1.0", "PyPSA model conformance",
            "application-context/1.0", "application-result/1.0", "artifact/1.0", "agent_",
        ),
        domains=(DomainBinding(
            "pypsa-model", "pypsa_model_", domain, CredentialScope(),
            DataSharingPolicy(),
        ),),
        output_renderer=JsonOutputRenderer(),
        application_policy=SimpleNamespace(load=lambda: "Use registered PyPSA model capabilities."),
        report_shell=GenericReportShell(),
        acceptance_profile=SimpleNamespace(cases=lambda: ()),
    )

    class EmptyCredentials:
        def issue(self, *, binding_id, scope):
            assert binding_id == "pypsa-model" and scope.credential_names == ()
            return SimpleNamespace(scope_id=scope.scope_id, credentials={})

    prepared = prepare_application(
        profile, registry=registry, workspace=workspace.root,
        credentials=EmptyCredentials(),
    )
    binding = prepared.bindings["pypsa-model"]
    assert {item["id"] for item in binding.runtime.capability_documents} == {
            "model.open", "model.derive", "model.derive_series", "model.inspect", "model.validate",
            "model.topology",
    }
    opened = binding.endpoint.executor.invoke("model.open", {"catalog_id": "two-bus"})
    assert opened["model_ref"].startswith("pypsa-model:sha256:")
    assert binding.runtime.authority.admit(
        "model.open", opened, tuple(opened["evidence_refs"])
    ).results[0].reference == opened["result_ref"]
    derived = binding.endpoint.executor.invoke("model.derive", {
        "model_ref": opened["model_ref"], "load_id": "demand", "p_set_mw": 55.0,
    })
    inspected = binding.endpoint.executor.invoke(
        "model.inspect", {"model_ref": derived["model_ref"]}
    )
    assert inspected["load_p_set_mw"] == {"demand": 55.0}
    assert binding.runtime.authority.verify_result(inspected["result_ref"]).reference == inspected["result_ref"]

    other = domain.create_authority(tmp_path / "other-run" / "domains" / "pypsa-model")
    with pytest.raises(Exception, match="current run|unavailable"):
        other.verify_result(opened["result_ref"])
