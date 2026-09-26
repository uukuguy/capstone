"""Source-defined PyPSA application registration."""

from __future__ import annotations

from capstone_agent.application_registry import ApplicationRegistry
from pypsa_agent.profile import build_profile


def build_trusted_application_registry() -> ApplicationRegistry:
    registry = ApplicationRegistry()
    registry.register("pypsa-business-cases", "1.0", build_profile)
    return registry
