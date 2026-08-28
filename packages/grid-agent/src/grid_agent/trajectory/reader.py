"""Grid compatibility reader with fail-closed persisted identity policy."""

from pathlib import Path

from capability_agent.trajectory.reader import (
    ReplayFailure,
    ReplayFailureCode,
    ReplayPrefix,
    RunEventReader as NeutralRunEventReader,
    recompute_event_hash,
)
from grid_agent.trajectory.events import RunEvent


class RunEventReader(NeutralRunEventReader):
    """Read only grid-native events while the kernel remains schema-neutral."""

    def __init__(self, events_path: Path) -> None:
        super().__init__(events_path, event_model=RunEvent)

__all__ = [
    "ReplayFailureCode",
    "ReplayFailure",
    "ReplayPrefix",
    "RunEventReader",
    "recompute_event_hash",
]
