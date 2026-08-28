"""Public API for the domain-neutral capability-agent kernel."""

from capability_agent.application import PreparedDomainRuntime, prepare_domain_runtime
from capability_agent.domain import (
    ArtifactAuthority,
    CapabilityContractSource,
    CapabilityExecutor,
    DomainManifest,
    DomainManifestError,
    DomainProjector,
    DomainProjectorRegistry,
    DomainRuntimeProfile,
    DomainStateDelta,
    VerifiedArtifact,
    VerifiedInvocation,
    VerifiedReferenceSet,
)
from capability_agent.tools import GuideIndex, ToolCatalog, describe_tool_document

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
    "GuideIndex",
    "PreparedDomainRuntime",
    "ToolCatalog",
    "describe_tool_document",
    "VerifiedArtifact",
    "VerifiedInvocation",
    "VerifiedReferenceSet",
    "prepare_domain_runtime",
]
