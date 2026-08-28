"""Compatibility recorder preserving the published grid event identity."""

from typing import Any

from capability_agent.trajectory.recorder import (
    RecorderIntegrityError,
    RunEventRecorder as NeutralRunEventRecorder,
)

from grid_agent.trajectory.events import (
    LEGACY_EVENT_PRODUCER,
    LEGACY_EVENT_SCHEMA_VERSION,
    build_event,
)
from grid_agent.trajectory.schema_policy import require_grid_event_producer


class RunEventRecorder(NeutralRunEventRecorder):
    """Inject the legacy grid producer and schema into the neutral recorder."""

    def __init__(
        self,
        *args: Any,
        producer: str = LEGACY_EVENT_PRODUCER,
        schema_version: str = LEGACY_EVENT_SCHEMA_VERSION,
        **kwargs: Any,
    ) -> None:
        if schema_version != LEGACY_EVENT_SCHEMA_VERSION:
            raise ValueError(
                f"grid event schema must be {LEGACY_EVENT_SCHEMA_VERSION}"
            )
        require_grid_event_producer(producer)
        super().__init__(
            *args,
            producer=producer,
            schema_version=schema_version,
            event_builder=build_event,
            **kwargs,
        )

__all__ = ["RecorderIntegrityError", "RunEventRecorder"]
