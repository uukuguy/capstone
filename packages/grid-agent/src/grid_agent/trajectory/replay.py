"""Compatibility replay models preserving the published grid import identity."""

from pydantic import Field

from capability_agent.trajectory.replay import (
    ImportedRunEvent as NeutralImportedRunEvent,
    ReplayEventLike,
    SourceCoordinate,
)


LEGACY_IMPORTED_EVENT_SCHEMA_VERSION = "grid-run-import-event/1.0"


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
