from __future__ import annotations

from pathlib import Path

from capability_agent.domain.manifest import DomainManifest
from capability_agent.domain.profile import DomainRuntimeProfile

from pandapower_domain.authority import PandapowerArtifactAuthority
from pandapower_domain.capabilities import (
    FilesystemCapabilityContractSource,
    build_pandapower_tool_description,
)
from pandapower_domain.execution import GridctlExecutor
from pandapower_domain.acceptance import PandapowerAcceptanceProfile
from pandapower_domain.answer_policy import (
    PandapowerAnswerEvidencePolicy,
    PandapowerPolicyProvider,
)
from pandapower_domain.answer_admission import PandapowerAnswerAdmissionPolicyFactory
from pandapower_domain.guide import PandapowerGuideProvider
from pandapower_domain.output import PandapowerOutputContract
from pandapower_domain.presentation import PandapowerPresentationProvider
from pandapower_domain.projection import (
    PandapowerProjectorLookupError,
    PandapowerProjectorRegistry,
)
from pandapower_domain.provisioning import PandapowerRuntimeProvisioner
from pandapower_domain.resources import PandapowerResourceSet
from pandapower_domain.state import PandapowerStateAdapter


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
        answer_admission_policy_factory=PandapowerAnswerAdmissionPolicyFactory(
            resources.guide_root
        ),
        tool_description_builder=build_pandapower_tool_description,
        provisioner=PandapowerRuntimeProvisioner(
            repository_root=_repository_root(),
        ),
        state_adapter=PandapowerStateAdapter(),
        answer_policy=PandapowerAnswerEvidencePolicy(),
        policy_provider=PandapowerPolicyProvider(resources.system_policy_path),
        guide_provider=PandapowerGuideProvider(resources.guide_root),
        presentation_provider=PandapowerPresentationProvider(),
        output_contract=PandapowerOutputContract(),
        acceptance_profile=PandapowerAcceptanceProfile(),
    )


def _repository_root() -> Path | None:
    candidate = Path(__file__).resolve().parents[4]
    return candidate if (candidate / "packages/grid-simulator").is_dir() else None
