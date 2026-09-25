"""Complete application composition contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from capability_agent.application.errors import ApplicationConfigurationError
from capability_agent.application.manifest import ApplicationManifest
from capability_agent.application.output import OutputRenderer
from capability_agent.domain.profile import DomainRuntimeProfile


@dataclass(frozen=True, slots=True)
class CredentialScope:
    """An isolated set of named credentials granted to one binding."""

    scope_id: str = "isolated"
    credential_names: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DataSharingPolicy:
    """Cross-binding data-sharing policy; sharing is denied by default."""

    mode: str = "deny"


class ApplicationPolicy(Protocol):
    """Provide the deterministic application policy fragment."""

    def load(self) -> str: ...


class ReportShell(Protocol):
    """Render a generic report shell around validated application sections."""

    def render(
        self, *, core: Mapping[str, object], domains: Mapping[str, object]
    ) -> str: ...


class AcceptanceProfile(Protocol):
    """Declare application-level acceptance cases."""

    def cases(self) -> tuple[object, ...]: ...


@dataclass(frozen=True, slots=True)
class DomainBinding:
    binding_id: str
    tool_namespace: str
    profile: DomainRuntimeProfile
    credential_scope: CredentialScope
    sharing_policy: DataSharingPolicy


@dataclass(frozen=True, slots=True)
class ApplicationProfile:
    manifest: ApplicationManifest
    domains: tuple[DomainBinding, ...]
    output_renderer: OutputRenderer
    application_policy: ApplicationPolicy
    report_shell: ReportShell
    acceptance_profile: AcceptanceProfile

    def __post_init__(self) -> None:
        binding_ids = tuple(binding.binding_id for binding in self.domains)
        duplicate_binding_ids = _duplicates(binding_ids)
        if duplicate_binding_ids:
            raise ApplicationConfigurationError(
                "duplicate binding namespace: " + ", ".join(duplicate_binding_ids)
            )

        tool_namespaces = tuple(binding.tool_namespace for binding in self.domains)
        duplicate_tool_namespaces = _duplicates(tool_namespaces)
        if duplicate_tool_namespaces:
            raise ApplicationConfigurationError(
                "duplicate tool namespace: " + ", ".join(duplicate_tool_namespaces)
            )

        if len(self.domains) < 1:
            raise ApplicationConfigurationError(
                "application profile requires at least one domain binding"
            )

        for binding in self.domains:
            missing = binding.profile.missing_application_components()
            if missing:
                raise ApplicationConfigurationError(
                    f"domain binding {binding.binding_id!r} has missing application "
                    f"components: {', '.join(missing)}"
                )


def _duplicates(values: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return tuple(duplicates)


__all__ = [
    "AcceptanceProfile",
    "ApplicationPolicy",
    "ApplicationProfile",
    "CredentialScope",
    "DataSharingPolicy",
    "DomainBinding",
    "OutputRenderer",
    "ReportShell",
]
