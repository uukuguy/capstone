"""Explicit migration registration for the existing PyPSA application."""

from __future__ import annotations

from capstone_agent.model_capability import CapstoneModelCapabilityCatalog, ModelCapabilityProfileInfo
from capstone_agent.model_capability_context import ModelCapabilityContextOwner, register_application_profile
from capstone_model_capability_spi import ModelCapabilityDescriptor

from .profile import build_profile


PYPSA_PROFILE_DESCRIPTOR = ModelCapabilityDescriptor("pypsa-business-cases", "1.0.0")
PYPSA_PROFILE_INFO = ModelCapabilityProfileInfo(
    descriptor=PYPSA_PROFILE_DESCRIPTOR,
    display_name="PyPSA Business Cases",
    implementation_families=("pypsa",),
)


def register_pypsa_capability(
    catalog: CapstoneModelCapabilityCatalog,
    owner: ModelCapabilityContextOwner,
) -> None:
    """Register the current trusted two-binding profile for app assembly."""

    register_application_profile(
        owner,
        catalog,
        PYPSA_PROFILE_INFO,
        build_profile,
        trust_source="pypsa-agent-migration-assembly",
    )


__all__ = [
    "PYPSA_PROFILE_DESCRIPTOR",
    "PYPSA_PROFILE_INFO",
    "register_pypsa_capability",
]
