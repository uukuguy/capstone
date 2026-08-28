"""Compatibility exports for the installed pandapower Domain Pack."""

from __future__ import annotations

from pathlib import Path

from capability_agent.domain.profile import DomainRuntimeProfile
from pandapower_domain import build_pandapower_profile as _build_pandapower_profile
from pandapower_domain.authority import PandapowerArtifactAuthority
from pandapower_domain.projection import (
    PandapowerProjectorLookupError,
    PandapowerProjectorRegistry,
)


def build_pandapower_profile(
    repository_root: Path | None = None,
) -> DomainRuntimeProfile:
    """Return the installed-resource profile; ``repository_root`` is ignored."""

    del repository_root
    return _build_pandapower_profile()


__all__ = [
    "PandapowerArtifactAuthority",
    "PandapowerProjectorLookupError",
    "PandapowerProjectorRegistry",
    "build_pandapower_profile",
]
