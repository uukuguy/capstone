"""Two installed Domain Pack wheels exchange one application-granted model revision."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from capability_agent.application.composition import prepare_application
from capability_agent.application.context_store import ApplicationContextStore
from capability_agent.application.manifest import ApplicationManifest
from capability_agent.application.output import JsonOutputRenderer
from capability_agent.application.profile import (
    ApplicationProfile, CredentialScope, DataSharingPolicy, DomainBinding, ReferenceGrant,
)
from capability_agent.application.reference_handoff import ReferenceHandoffService
from capability_agent.application.registry import DomainRegistry
from capability_agent.application.reporting import GenericReportShell
from capability_agent.application.workspace import ApplicationWorkspace
from pypsa_network_modeling.profile import build_pypsa_network_modeling_profile
from pypsa_power_operations.profile import build_pypsa_power_operations_profile


class EmptyCredentials:
    def issue(self, *, binding_id, scope):
        return SimpleNamespace(scope_id=scope.scope_id, credentials={})


def main() -> None:
    model = build_pypsa_network_modeling_profile()
    operations = build_pypsa_power_operations_profile(source_binding_id="model")
    registry = DomainRegistry()
    registry.register(model.manifest.domain_id, model.manifest.version, lambda: model)
    registry.register(operations.manifest.domain_id, operations.manifest.version, lambda: operations)
    with TemporaryDirectory() as temporary:
        workspace = ApplicationWorkspace.create(
            Path(temporary).resolve() / "runs", run_id="installed-operations",
            binding_ids=("model", "operations"),
        )
        profile = ApplicationProfile(
            manifest=ApplicationManifest(
                "pypsa-operations-smoke", "1.0", "Installed PyPSA operations",
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
        prepared = prepare_application(
            profile, registry=registry, workspace=workspace.root, credentials=EmptyCredentials(),
        )
        store = ApplicationContextStore.initialize(workspace)
        service = ReferenceHandoffService(profile, workspace, store, prepared.bindings)
        target = prepared.bindings["operations"]
        for catalog_id, capability, objective in (
            ("two-bus", "operations.dispatch", 800.0),
            ("rolling-storage", "operations.rolling_dispatch", 1000.0),
            ("congested-two-bus", "operations.congested_opf", 800.0),
        ):
            opened = prepared.bindings["model"].endpoint.executor.invoke(
                "model.open", {"catalog_id": catalog_id},
            )
            result, receipt = service.invoke_target(
                source_binding_id="model", target_binding_id="operations",
                reference=opened["model_ref"], reference_kind="model", purpose="operations",
                capability=capability, arguments={},
            )
            assert result["objective"] == objective
            assert target.runtime.authority.admit(
                capability, result, tuple(result["evidence_refs"])
            ).results[0].document["source_binding_id"] == "model"
            assert service.verify_receipt(receipt) == receipt
        assert ApplicationContextStore.replay(workspace.context_events_path) == store.snapshot
        for binding in prepared.bindings.values():
            binding.endpoint.close()
    print("installed-pypsa-operations: ok")


if __name__ == "__main__":
    main()
