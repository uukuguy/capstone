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
from pypsa_sector_coupling.profile import build_pypsa_sector_coupling_profile


class EmptyCredentials:
    def issue(self, *, binding_id, scope):
        return SimpleNamespace(scope_id=scope.scope_id, credentials={})


def main() -> None:
    model = build_pypsa_network_modeling_profile()
    sector = build_pypsa_sector_coupling_profile(source_binding_id="model")
    registry = DomainRegistry()
    registry.register(model.manifest.domain_id, model.manifest.version, lambda: model)
    registry.register(sector.manifest.domain_id, sector.manifest.version, lambda: sector)
    with TemporaryDirectory() as temporary:
        workspace = ApplicationWorkspace.create(
            Path(temporary).resolve() / "runs", run_id="installed-sector",
            binding_ids=("model", "sector"),
        )
        profile = ApplicationProfile(
            manifest=ApplicationManifest(
                "pypsa-sector-smoke", "1.0", "Installed PyPSA sector",
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
        prepared = prepare_application(
            profile, registry=registry, workspace=workspace.root, credentials=EmptyCredentials(),
        )
        store = ApplicationContextStore.initialize(workspace)
        service = ReferenceHandoffService(profile, workspace, store, prepared.bindings)
        target = prepared.bindings["sector"]
        for catalog_id, capability, objective in (
            ("electricity-hydrogen", "sector.hydrogen_balance", 1000.0),
            ("electricity-heat-pump", "sector.heat_balance", 200.0),
            ("hydrogen-storage", "sector.hydrogen_storage", 1000.0),
            ("heat-pump-storage", "sector.heat_storage", 200.0),
            ("chp-hydrogen-heat", "sector.multiport_balance", 1000.0),
        ):
            opened = prepared.bindings["model"].endpoint.executor.invoke(
                "model.open", {"catalog_id": catalog_id},
            )
            result, receipt = service.invoke_target(
                source_binding_id="model", target_binding_id="sector",
                reference=opened["model_ref"], reference_kind="model", purpose="sector",
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
    print("installed-pypsa-sector: ok")


if __name__ == "__main__":
    main()
