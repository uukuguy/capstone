"""Trusted application profiles owned by the grid-agent composition root.

The Kernel owns the application contracts and runner.  This module is the
small, explicit composition root that selects the first complete Domain Pack;
it is deliberately not a discovery mechanism.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from capability_agent.application.manifest import ApplicationManifest
from capability_agent.application.profile import (
    ApplicationProfile,
    CredentialScope,
    DataSharingPolicy,
    DomainBinding,
)
from capability_agent.application.reporting import GenericReportShell
from capability_agent.application.output import JsonOutputRenderer
from pandapower_domain import build_pandapower_profile


@dataclass(frozen=True, slots=True)
class ReadOnlyApplicationPolicy:
    """Application invariants layered above the Kernel's safety policy."""

    policy: str = (
        "deny: arbitrary-subprocess, generic-file-access, generic-tools, "
        "cross-domain-sharing"
    )

    def load(self) -> str:
        return self.policy


@dataclass(frozen=True, slots=True)
class PandapowerApplicationAcceptanceProfile:
    """Expose Domain Pack acceptance declarations at application level."""

    domain_profile: object

    def cases(self) -> tuple[object, ...]:
        values: list[object] = []
        for name in ("offline_cases", "scripted_cases", "provider_cases"):
            method = getattr(self.domain_profile, name, None)
            if callable(method):
                cases = method()
                if isinstance(cases, Iterable):
                    values.extend(cases)
        return tuple(values)

    def offline_cases(self) -> tuple[object, ...]:
        return _acceptance_cases(self.domain_profile, "offline_cases")

    def scripted_cases(self) -> tuple[object, ...]:
        return _acceptance_cases(self.domain_profile, "scripted_cases")

    def provider_cases(self) -> tuple[object, ...]:
        return _acceptance_cases(self.domain_profile, "provider_cases")


def build_pandapower_application_profile() -> ApplicationProfile:
    """Build the explicitly supported pandapower application profile.

    The profile is newly assembled for each call.  Domain resources and their
    safety policies remain owned by ``pandapower_domain``; this module only
    binds that complete profile into an application-local ``grid`` instance.
    """

    domain_profile = build_pandapower_profile()
    acceptance = PandapowerApplicationAcceptanceProfile(
        domain_profile=domain_profile.acceptance_profile,
    )
    return ApplicationProfile(
        manifest=ApplicationManifest(
            application_id="pandapower-static-analysis",
            version="1.0.1",
            display_name="Pandapower Static Analysis",
            context_schema="application-context/1.0",
            result_schema="capability-agent-output/1.0",
            artifact_schema="capability-agent-run/1.0",
            core_tool_namespace="agent_",
        ),
        domains=(
            DomainBinding(
                binding_id="grid",
                tool_namespace="grid_",
                profile=domain_profile,
                credential_scope=CredentialScope(
                    scope_id="pandapower-empty",
                    credential_names=(),
                ),
                sharing_policy=DataSharingPolicy(mode="deny"),
            ),
        ),
        output_renderer=JsonOutputRenderer(),
        application_policy=ReadOnlyApplicationPolicy(),
        report_shell=GenericReportShell(),
        acceptance_profile=acceptance,
    )


def _acceptance_cases(profile: object, name: str) -> tuple[object, ...]:
    method = getattr(profile, name, None)
    if not callable(method):
        return ()
    values = method()
    if isinstance(values, tuple):
        return values
    if isinstance(values, list):
        return tuple(values)
    return ()


__all__ = [
    "PandapowerApplicationAcceptanceProfile",
    "ReadOnlyApplicationPolicy",
    "build_pandapower_application_profile",
]
