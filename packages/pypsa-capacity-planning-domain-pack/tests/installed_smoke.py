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
from pypsa_capacity_planning.profile import build_pypsa_capacity_planning_profile


class EmptyCredentials:
    def issue(self, *, binding_id, scope):
        return SimpleNamespace(scope_id=scope.scope_id, credentials={})


def main() -> None:
    model = build_pypsa_network_modeling_profile()
    planning = build_pypsa_capacity_planning_profile(source_binding_id="model")
    registry = DomainRegistry()
    registry.register(model.manifest.domain_id, model.manifest.version, lambda: model)
    registry.register(planning.manifest.domain_id, planning.manifest.version, lambda: planning)
    with TemporaryDirectory() as temporary:
        workspace = ApplicationWorkspace.create(
            Path(temporary).resolve() / "runs", run_id="installed-planning",
            binding_ids=("model", "planning"),
        )
        profile = ApplicationProfile(
            manifest=ApplicationManifest(
                "pypsa-planning-smoke", "1.0", "Installed PyPSA planning",
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
        prepared = prepare_application(
            profile, registry=registry, workspace=workspace.root, credentials=EmptyCredentials(),
        )
        store = ApplicationContextStore.initialize(workspace)
        service = ReferenceHandoffService(profile, workspace, store, prepared.bindings)
        target = prepared.bindings["planning"]
        for catalog_id, capability, expected in (
            ("capacity-two-bus", "planning.capacity_expand", 4800.0),
            ("capacity-commitment", "planning.capacity_commitment", 4450.0),
            ("capacity-pathway", "planning.multi_period", 20.0),
            ("capacity-scenarios", "planning.stochastic", 20.0),
            ("capacity-two-bus", "planning.near_optimal_capacity", 42.4),
        ):
            opened = prepared.bindings["model"].endpoint.executor.invoke(
                "model.open", {"catalog_id": catalog_id},
            )
            result, receipt = service.invoke_target(
                source_binding_id="model", target_binding_id="planning",
                reference=opened["model_ref"], reference_kind="model", purpose="planning",
                capability=capability, arguments={},
            )
            observed = (
                result["generator_capacity_mw"].get("early", result["generator_capacity_mw"].get("build"))
                if capability in {"planning.multi_period", "planning.stochastic"}
                else result["objective"]
            )
            assert abs(observed - expected) < 1e-6
            assert target.runtime.authority.admit(
                capability, result, tuple(result["evidence_refs"])
            ).results[0].document["source_binding_id"] == "model"
            assert service.verify_receipt(receipt) == receipt
        assert ApplicationContextStore.replay(workspace.context_events_path) == store.snapshot
        for binding in prepared.bindings.values():
            binding.endpoint.close()
    print("installed-pypsa-planning: ok")


if __name__ == "__main__":
    main()
