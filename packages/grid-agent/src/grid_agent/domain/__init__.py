"""Stable, neutral contracts for domain runtime composition."""

from grid_agent.domain.authority import (
    ArtifactAuthority,
    VerifiedArtifact,
    VerifiedReferenceSet,
)
from grid_agent.domain.contracts import CapabilityContractSource
from grid_agent.domain.execution import CapabilityExecutor
from grid_agent.domain.manifest import DomainManifest, DomainManifestError
from grid_agent.domain.profile import DomainRuntimeProfile
from grid_agent.domain.projection import (
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
