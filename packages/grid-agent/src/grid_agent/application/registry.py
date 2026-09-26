"""Pandapower application registration and stable compatibility imports."""

from __future__ import annotations

from capstone_agent.application_registry import (
    ApplicationProfileFactory,
    ApplicationRegistry,
)

from grid_agent.application.profile import build_pandapower_application_profile


def build_trusted_application_registry() -> ApplicationRegistry:
    registry = ApplicationRegistry()
    registry.register(
        "pandapower-static-analysis", "1.0.1",
        build_pandapower_application_profile,
    )
    return registry


build_application_registry = build_trusted_application_registry
trusted_application_registry = build_trusted_application_registry


__all__ = [
    "ApplicationProfileFactory",
    "ApplicationRegistry",
    "build_application_registry",
    "build_trusted_application_registry",
    "trusted_application_registry",
]
