"""Legacy Pi lock imports backed by the capability-agent runtime.

The grid application still exposes the historical module path to its callers,
but the lock parser and immutable identity models live in the domain-neutral
kernel.  Keeping this module as an adapter prevents the application from
forking runtime verification logic.
"""

from __future__ import annotations

from pathlib import Path

from capability_agent.runtime.lock import (
    EXPECTED_SCHEMA_VERSION,
    PiCommand,
    PiOAuthHelper,
    PiRuntimeIdentity,
    PiRuntimeLock as _PiRuntimeLock,
    PiRuntimeLockError,
    PiRuntimePatch,
)
from grid_agent.application.paths import ProjectPaths


class PiRuntimeLock(_PiRuntimeLock):
    """Compatibility lock whose implicit path follows the grid project root."""

    @classmethod
    def load(cls, path: Path | None = None) -> "PiRuntimeLock":
        return super().load(path or default_lock_path())


def default_lock_path() -> Path:
    return ProjectPaths.from_root(Path(__file__).resolve().parents[5]).runtime_lock


__all__ = [
    "EXPECTED_SCHEMA_VERSION",
    "PiCommand",
    "PiOAuthHelper",
    "PiRuntimeIdentity",
    "PiRuntimeLock",
    "PiRuntimeLockError",
    "PiRuntimePatch",
    "default_lock_path",
]
