"""Compatibility replay models preserving the published grid import identity."""

from pydantic import Field, model_validator

from capability_agent.trajectory.replay import (
    ImportedRunEvent as NeutralImportedRunEvent,
    ReplayEventLike,
    SourceCoordinate,
)
from grid_agent.trajectory.schema_policy import (
    GRID_IMPORTED_EVENT_PRODUCER,
    GRID_IMPORTED_EVENT_SCHEMA_VERSION,
)


LEGACY_IMPORTED_EVENT_SCHEMA_VERSION = GRID_IMPORTED_EVENT_SCHEMA_VERSION


class ImportedRunEvent(NeutralImportedRunEvent):
    """A legacy grid import layered over the neutral kernel replay model."""

    schema_version: str = Field(
        default=LEGACY_IMPORTED_EVENT_SCHEMA_VERSION,
        min_length=1,
    )

    @model_validator(mode="after")
    def require_grid_import_identity(self) -> "ImportedRunEvent":
        if self.schema_version != LEGACY_IMPORTED_EVENT_SCHEMA_VERSION:
            raise ValueError(
                "grid imported event schema must be "
                f"{LEGACY_IMPORTED_EVENT_SCHEMA_VERSION}"
            )
        if self.source.producer != GRID_IMPORTED_EVENT_PRODUCER:
            raise ValueError(
                "grid imported event producer must be "
                f"{GRID_IMPORTED_EVENT_PRODUCER}"
            )
        return self

__all__ = [
    "LEGACY_IMPORTED_EVENT_SCHEMA_VERSION",
    "ImportedRunEvent",
    "ReplayEventLike",
    "SourceCoordinate",
]
