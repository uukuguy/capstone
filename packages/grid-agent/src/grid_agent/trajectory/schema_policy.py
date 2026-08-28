"""Grid-owned persisted schema identities injected into neutral contracts."""

import re

from pydantic import Field, model_validator

from capability_agent.trajectory.replay import (
    ImportedRunEvent as NeutralImportedRunEvent,
)

GRID_EVENT_PRODUCER = "grid-agent"
GRID_EVENT_SCHEMA_VERSION = "grid-run-event/1.0"
GRID_IMPORTED_EVENT_SCHEMA_VERSION = "grid-run-import-event/1.0"
GRID_IMPORTED_EVENT_PRODUCER = "legacy-v0.2-importer"
_GRID_EVENT_PRODUCER = re.compile(r"^grid-agent(?:\.[a-z0-9][a-z0-9-]*)*$")


def require_grid_event_producer(producer: str) -> str:
    if _GRID_EVENT_PRODUCER.fullmatch(producer) is None:
        raise ValueError("grid event producer must be grid-agent or a grid-agent.* component")
    return producer


class GridImportedRunEvent(NeutralImportedRunEvent):
    """Apply the grid import identity without depending on a compatibility shim."""

    schema_version: str = Field(
        default=GRID_IMPORTED_EVENT_SCHEMA_VERSION,
        min_length=1,
    )

    @model_validator(mode="after")
    def require_grid_import_identity(self) -> "GridImportedRunEvent":
        if self.schema_version != GRID_IMPORTED_EVENT_SCHEMA_VERSION:
            raise ValueError(
                "grid imported event schema must be "
                f"{GRID_IMPORTED_EVENT_SCHEMA_VERSION}"
            )
        if self.source.producer != GRID_IMPORTED_EVENT_PRODUCER:
            raise ValueError(
                "grid imported event producer must be "
                f"{GRID_IMPORTED_EVENT_PRODUCER}"
            )
        return self

__all__ = [
    "GRID_EVENT_PRODUCER",
    "GRID_EVENT_SCHEMA_VERSION",
    "GRID_IMPORTED_EVENT_SCHEMA_VERSION",
    "GRID_IMPORTED_EVENT_PRODUCER",
    "GridImportedRunEvent",
    "require_grid_event_producer",
]
