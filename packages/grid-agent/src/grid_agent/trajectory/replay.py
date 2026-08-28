"""Compatibility replay models preserving the published grid import identity."""

from capability_agent.trajectory.replay import (
    ReplayEventLike,
    SourceCoordinate,
)
from grid_agent.trajectory.schema_policy import (
    GRID_IMPORTED_EVENT_SCHEMA_VERSION,
    GridImportedRunEvent,
)


LEGACY_IMPORTED_EVENT_SCHEMA_VERSION = GRID_IMPORTED_EVENT_SCHEMA_VERSION


ImportedRunEvent = GridImportedRunEvent

__all__ = [
    "LEGACY_IMPORTED_EVENT_SCHEMA_VERSION",
    "ImportedRunEvent",
    "ReplayEventLike",
    "SourceCoordinate",
]
