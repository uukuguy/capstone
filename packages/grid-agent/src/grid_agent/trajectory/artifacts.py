"""Compatibility exports for the neutral trajectory artifact registry."""

from capability_agent.trajectory import artifacts as _artifacts
from capability_agent.trajectory.artifacts import (
    ArtifactIntegrityError,
    ArtifactLayout,
    ArtifactPathPolicy,
    ArtifactPointer,
    ImmutableArtifactRegistry,
    NeutralArtifactPathPolicy,
)

os = _artifacts.os
__all__ = [
    "ArtifactIntegrityError",
    "ArtifactLayout",
    "ArtifactPathPolicy",
    "ArtifactPointer",
    "ImmutableArtifactRegistry",
    "NeutralArtifactPathPolicy",
]
