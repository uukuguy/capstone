"""Stable, neutral contracts for domain runtime composition."""

from capability_agent.domain.authority import (
    ArtifactAuthority,
    VerifiedArtifact,
    VerifiedReferenceSet,
)
from capability_agent.domain.contracts import CapabilityContractSource
from capability_agent.domain.execution import CapabilityExecutor
from capability_agent.domain.manifest import DomainManifest, DomainManifestError
from capability_agent.domain.profile import DomainRuntimeProfile
from capability_agent.domain.projection import (
    DomainProjector,
    DomainProjectorRegistry,
    DomainStateDelta,
    VerifiedInvocation,
)

__all__ = [
    "ArtifactAuthority",
    "CapabilityContractSource",
    "CapabilityExecutor",
    "DomainManifest",
    "DomainManifestError",
    "DomainProjector",
    "DomainProjectorRegistry",
    "DomainRuntimeProfile",
    "DomainStateDelta",
    "VerifiedArtifact",
    "VerifiedInvocation",
    "VerifiedReferenceSet",
]
