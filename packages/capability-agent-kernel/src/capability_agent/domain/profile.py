from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from capability_agent.domain.authority import ArtifactAuthority
from capability_agent.domain.answer_admission import AnswerAdmissionPolicy
from capability_agent.domain.acceptance import DomainAcceptanceProfile
from capability_agent.domain.contracts import CapabilityContractSource
from capability_agent.domain.execution import CapabilityExecutor
from capability_agent.domain.guide import GuideProvider
from capability_agent.domain.manifest import DomainManifest
from capability_agent.domain.output import DomainOutputContract
from capability_agent.domain.policy import AnswerEvidencePolicy, DomainPolicyProvider
from capability_agent.domain.presentation import PresentationProvider
from capability_agent.domain.projection import DomainProjectorRegistry
from capability_agent.domain.provisioning import DomainRuntimeProvisioner
from capability_agent.domain.state import DomainStateAdapter


ExecutorFactory = Callable[[Path, Path, float], CapabilityExecutor]
AuthorityFactory = Callable[[Path], ArtifactAuthority]
AnswerAdmissionPolicyFactory = Callable[[ArtifactAuthority], AnswerAdmissionPolicy]
ToolDescriptionBuilder = Callable[[dict[str, object]], str]


@dataclass(frozen=True, slots=True)
class DomainRuntimeProfile:
    manifest: DomainManifest
    contract_source: CapabilityContractSource
    executor_factory: ExecutorFactory
    projector_registry: DomainProjectorRegistry
    authority_factory: AuthorityFactory
    answer_admission_policy_factory: AnswerAdmissionPolicyFactory | None = None
    tool_description_builder: ToolDescriptionBuilder | None = None
    provisioner: DomainRuntimeProvisioner | None = None
    state_adapter: DomainStateAdapter | None = None
    answer_policy: AnswerEvidencePolicy | None = None
    policy_provider: DomainPolicyProvider | None = None
    guide_provider: GuideProvider | None = None
    presentation_provider: PresentationProvider | None = None
    output_contract: DomainOutputContract | None = None
    acceptance_profile: DomainAcceptanceProfile | None = None

    def missing_application_components(self) -> tuple[str, ...]:
        names = (
            "provisioner",
            "state_adapter",
            "answer_policy",
            "answer_admission_policy_factory",
            "policy_provider",
            "guide_provider",
            "presentation_provider",
            "output_contract",
            "acceptance_profile",
        )
        return tuple(name for name in names if getattr(self, name) is None)

    def create_executor(
        self, executable: Path, workspace: Path, timeout_seconds: float
    ) -> CapabilityExecutor:
        return self.executor_factory(executable, workspace, timeout_seconds)

    def create_authority(self, workspace: Path) -> ArtifactAuthority:
        return self.authority_factory(workspace)

    def create_answer_admission_policy(
        self, authority: ArtifactAuthority
    ) -> AnswerAdmissionPolicy:
        factory = self.answer_admission_policy_factory
        if factory is None:
            raise RuntimeError("domain answer admission policy is unavailable")
        policy = factory(authority)
        if not callable(getattr(policy, "admit", None)):
            raise TypeError("domain answer admission policy is invalid")
        return policy
