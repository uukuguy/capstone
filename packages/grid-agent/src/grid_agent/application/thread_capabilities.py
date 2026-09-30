"""Explicit migration registration for the existing pandapower application.

This module is an application composition hook only.  The compatibility CLI
does not call it implicitly; a future Capstone composition root may opt in.
"""

from __future__ import annotations

from capstone_agent.model_capability import CapstoneModelCapabilityCatalog, ModelCapabilityProfileInfo
from capstone_agent.model_capability_context import ModelCapabilityContextOwner, register_application_profile
from capstone_model_capability_spi import ModelCapabilityDescriptor

from .profile import build_pandapower_application_profile


PANDAPOWER_PROFILE_DESCRIPTOR = ModelCapabilityDescriptor(
    "pandapower-static-analysis", "1.0.1",
)
PANDAPOWER_PROFILE_INFO = ModelCapabilityProfileInfo(
    descriptor=PANDAPOWER_PROFILE_DESCRIPTOR,
    display_name="Pandapower Static Analysis",
    implementation_families=("pandapower",),
)


def register_pandapower_capability(
    catalog: CapstoneModelCapabilityCatalog,
    owner: ModelCapabilityContextOwner,
) -> None:
    """Register the current trusted profile for an explicit app assembly."""

    register_application_profile(
        owner,
        catalog,
        PANDAPOWER_PROFILE_INFO,
        build_pandapower_application_profile,
        trust_source="grid-agent-migration-assembly",
    )


__all__ = [
    "PANDAPOWER_PROFILE_DESCRIPTOR",
    "PANDAPOWER_PROFILE_INFO",
    "register_pandapower_capability",
]
