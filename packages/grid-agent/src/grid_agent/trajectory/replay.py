"""Compatibility replay models preserving the published grid import identity."""

from pydantic import Field

from capability_agent.trajectory.replay import (
    ImportedRunEvent as NeutralImportedRunEvent,
    ReplayEventLike,
    SourceCoordinate,
)
from grid_agent.trajectory.schema_policy import GRID_IMPORTED_EVENT_SCHEMA_VERSION


LEGACY_IMPORTED_EVENT_SCHEMA_VERSION = GRID_IMPORTED_EVENT_SCHEMA_VERSION


class ImportedRunEvent(NeutralImportedRunEvent):
    """A legacy grid import layered over the neutral kernel replay model."""

    schema_version: str = Field(
        default=LEGACY_IMPORTED_EVENT_SCHEMA_VERSION,
        min_length=1,
    )

__all__ = [
    "LEGACY_IMPORTED_EVENT_SCHEMA_VERSION",
    "ImportedRunEvent",
    "ReplayEventLike",
    "SourceCoordinate",
]
