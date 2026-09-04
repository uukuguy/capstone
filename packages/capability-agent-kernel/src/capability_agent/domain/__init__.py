"""Stable, neutral contracts for domain runtime composition."""

from capability_agent.domain.authority import (
    ArtifactAuthority,
    VerifiedArtifact,
    VerifiedReferenceSet,
)
from capability_agent.domain.answer_admission import (
    AnswerAdmissionDecision,
    AnswerAdmissionInput,
    AnswerAdmissionPolicy,
    read_answer_admission_metadata,
)
from capability_agent.domain.acceptance import DomainAcceptanceProfile
from capability_agent.domain.contracts import CapabilityContractSource
from capability_agent.domain.execution import CapabilityExecutor
from capability_agent.domain.guide import GuideProvider
from capability_agent.domain.manifest import DomainManifest, DomainManifestError
from capability_agent.domain.output import CommittedAnswer, DomainOutputContract
from capability_agent.domain.policy import AnswerEvidencePolicy, DomainPolicyProvider
from capability_agent.domain.presentation import PresentationProvider
from capability_agent.domain.profile import DomainRuntimeProfile
from capability_agent.domain.projection import (
    DomainProjector,
    DomainProjectorRegistry,
    DomainStateDelta,
    VerifiedInvocation,
)
from capability_agent.domain.provisioning import (
    CredentialLease,
    DomainRuntimeProvisioner,
    PreparedDomainEndpoint,
)
from capability_agent.domain.state import DomainContextView, DomainStateAdapter

__all__ = [
    "AnswerEvidencePolicy",
    "AnswerAdmissionDecision",
    "AnswerAdmissionInput",
    "AnswerAdmissionPolicy",
    "read_answer_admission_metadata",
    "ArtifactAuthority",
    "CapabilityContractSource",
    "CapabilityExecutor",
    "CommittedAnswer",
    "CredentialLease",
    "DomainAcceptanceProfile",
    "DomainContextView",
    "DomainManifest",
    "DomainManifestError",
    "DomainOutputContract",
    "DomainPolicyProvider",
    "DomainProjector",
    "DomainProjectorRegistry",
    "DomainRuntimeProfile",
    "DomainRuntimeProvisioner",
    "DomainStateAdapter",
    "DomainStateDelta",
    "GuideProvider",
    "PreparedDomainEndpoint",
    "PresentationProvider",
    "VerifiedArtifact",
    "VerifiedInvocation",
    "VerifiedReferenceSet",
]
