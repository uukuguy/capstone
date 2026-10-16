from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from capability_agent.domain.authority import ArtifactAuthority
from capability_agent.domain.answer_admission import AnswerAdmissionPolicy
from capability_agent.domain.acceptance import DomainAcceptanceProfile
from capability_agent.domain.contracts import CapabilityContractSource
from capability_agent.domain.execution import CapabilityExecutor
from capability_agent.domain.guide import GuideProvider
from capability_agent.domain.manifest import DomainManifest, PackManifest
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
    execution_kind: Literal["authority"] = field(default="authority", init=False)
    manifest: DomainManifest
    contract_source: CapabilityContractSource
    executor_factory: ExecutorFactory
    projector_registry: DomainProjectorRegistry
    authority_factory: AuthorityFactory
    answer_admission_policy_factory: AnswerAdmissionPolicyFactory | None = None
    answer_admission_policy_version: str | None = None
    answer_admission_capabilities: frozenset[str] | None = None
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
            "contract_source", "executor_factory", "projector_registry", "authority_factory",
            "provisioner",
            "state_adapter",
            "answer_policy",
            "answer_admission_policy_factory",
            "answer_admission_policy_version",
            "answer_admission_capabilities",
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

    def validate_answer_admission_declaration(self) -> None:
        if self.answer_admission_policy_version != "answer-admission/1.0":
            raise ValueError("domain answer admission policy version is invalid")
        capabilities = self.answer_admission_capabilities
        required = frozenset({"authority_backed", "limited"})
        allowed = required | {"offline_information"}
        if capabilities is None or not required.issubset(capabilities) or not capabilities.issubset(allowed):
            raise ValueError("domain answer admission capabilities are invalid")


@dataclass(frozen=True, slots=True)
class NativeExecutionConfig:
    """Select a host-owned resource profile and native result contract, not an endpoint."""

    resource_profile_id: str
    result_contract: str
    required_resources: tuple[str, ...] = ()
    kind: Literal["native"] = field(default="native", init=False)

    def __post_init__(self) -> None:
        if any(not isinstance(value, str) or not value.strip()
               for value in (self.resource_profile_id, self.result_contract)):
            raise ValueError("native resource profile and result contract are required")
        if (not isinstance(self.required_resources, tuple)
                or any(not isinstance(value, str) or not value.strip() for value in self.required_resources)
                or len(set(self.required_resources)) != len(self.required_resources)):
            raise ValueError("native resource requirements are invalid")


@dataclass(frozen=True, slots=True)
class NativeDomainRuntimeProfile:
    manifest: PackManifest
    execution: NativeExecutionConfig
    policy_provider: DomainPolicyProvider
    guide_provider: GuideProvider
    execution_kind: Literal["native"] = field(default="native", init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.manifest, PackManifest) or not isinstance(self.execution, NativeExecutionConfig):
            raise ValueError("native pack declaration is invalid")

    def missing_application_components(self) -> tuple[str, ...]:
        return tuple(name for name in ("policy_provider", "guide_provider") if getattr(self, name) is None)


DomainPackProfile = DomainRuntimeProfile | NativeDomainRuntimeProfile


def require_authority_profile(profile: DomainPackProfile) -> DomainRuntimeProfile:
    """Narrow a registered profile at an authority-only application boundary."""
    if isinstance(profile, NativeDomainRuntimeProfile):
        raise ValueError("this application entry point requires an authority profile")
    return profile
