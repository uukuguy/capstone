from __future__ import annotations

from capability_agent.domain.manifest import DomainManifest
from capability_agent.domain.profile import DomainRuntimeProfile

from pandapower_domain.authority import PandapowerArtifactAuthority
from pandapower_domain.capabilities import (
    FilesystemCapabilityContractSource,
    build_pandapower_tool_description,
)
from pandapower_domain.execution import GridctlExecutor
from pandapower_domain.projection import (
    PandapowerProjectorLookupError,
    PandapowerProjectorRegistry,
)
from pandapower_domain.resources import PandapowerResourceSet


__all__ = [
    "PandapowerProjectorLookupError",
    "PandapowerProjectorRegistry",
    "build_pandapower_profile",
]


def build_pandapower_profile() -> DomainRuntimeProfile:
    """Build the installed-resource pandapower runtime profile."""

    resources = PandapowerResourceSet.load()
    manifest = DomainManifest(
        domain_id="pandapower-static-analysis",
        version="1.0.1",
        display_name="Pandapower Static Analysis",
        protocol="grid-capability",
        protocol_version="1.0",
        executable_name="gridctl",
        tool_name_prefix="grid_",
        authority_id="gridctl",
        capability_contract_root=resources.capability_contract_root,
        system_policy_path=resources.system_policy_path,
        guide_root=resources.guide_root,
    )
    return DomainRuntimeProfile(
        manifest=manifest,
        contract_source=FilesystemCapabilityContractSource(resources),
        executor_factory=lambda executable, workspace, timeout: GridctlExecutor(
            executable=executable,
            workspace=workspace,
            timeout_seconds=timeout,
        ),
        projector_registry=PandapowerProjectorRegistry(),
        authority_factory=PandapowerArtifactAuthority,
        tool_description_builder=build_pandapower_tool_description,
    )
