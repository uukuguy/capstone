"""Trusted two-binding PyPSA application profile."""

from __future__ import annotations

from capability_agent.application.manifest import ApplicationManifest
from capability_agent.application.output import JsonOutputRenderer
from capability_agent.application.profile import (
    ApplicationProfile, CredentialScope, DataSharingPolicy, DomainBinding, ReferenceGrant,
)
from pypsa_agent.reporting import PyPSAApplicationReportShell
from pypsa_network_modeling.profile import build_pypsa_network_modeling_profile
from pypsa_power_operations.profile import build_pypsa_power_operations_profile


class _ApplicationPolicy:
    def load(self) -> str:
        return "Use only registered PyPSA capabilities and current-run evidence."


class _AcceptanceProfile:
    def cases(self) -> tuple[()]:
        return ()


def build_profile() -> ApplicationProfile:
    """Bind the model library and operations authority without cross-pack imports."""

    model = build_pypsa_network_modeling_profile()
    operations = build_pypsa_power_operations_profile(source_binding_id="source")
    return ApplicationProfile(
        manifest=ApplicationManifest(
            "pypsa-business-cases", "1.0", "PyPSA business cases",
            "application-context/1.0", "application-result/1.0", "artifact/1.0", "agent_",
        ),
        domains=(
            DomainBinding("source", "pypsa_model_", model, CredentialScope(), DataSharingPolicy()),
            DomainBinding("operations", "pypsa_ops_", operations, CredentialScope(), DataSharingPolicy()),
        ),
        output_renderer=JsonOutputRenderer(),
        application_policy=_ApplicationPolicy(),
        report_shell=PyPSAApplicationReportShell(),
        acceptance_profile=_AcceptanceProfile(),
        reference_grants=(ReferenceGrant(
            "source", "operations", "model", "operations", "operations"
        ),),
    )
