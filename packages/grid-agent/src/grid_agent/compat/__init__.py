"""Explicit versioned compatibility adapters for the historical CLI."""

from grid_agent.compat.v1_0_1 import (
    LEGACY_COMMANDS,
    LEGACY_CORE_TOOL_ALIASES,
    V1_0_1CompatibilityAdapter,
    build_grid_v1_0_1_compatibility_adapter,
)

__all__ = [
    "LEGACY_COMMANDS",
    "LEGACY_CORE_TOOL_ALIASES",
    "V1_0_1CompatibilityAdapter",
    "build_grid_v1_0_1_compatibility_adapter",
]
