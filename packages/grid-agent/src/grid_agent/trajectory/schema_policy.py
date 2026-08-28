"""Grid-owned persisted schema identities injected into neutral contracts."""

import re

GRID_EVENT_PRODUCER = "grid-agent"
GRID_EVENT_SCHEMA_VERSION = "grid-run-event/1.0"
GRID_IMPORTED_EVENT_SCHEMA_VERSION = "grid-run-import-event/1.0"
GRID_IMPORTED_EVENT_PRODUCER = "legacy-v0.2-importer"
_GRID_EVENT_PRODUCER = re.compile(r"^grid-agent(?:\.[a-z0-9][a-z0-9-]*)*$")


def require_grid_event_producer(producer: str) -> str:
    if _GRID_EVENT_PRODUCER.fullmatch(producer) is None:
        raise ValueError("grid event producer must be grid-agent or a grid-agent.* component")
    return producer

__all__ = [
    "GRID_EVENT_PRODUCER",
    "GRID_EVENT_SCHEMA_VERSION",
    "GRID_IMPORTED_EVENT_SCHEMA_VERSION",
    "GRID_IMPORTED_EVENT_PRODUCER",
    "require_grid_event_producer",
]
