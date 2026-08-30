"""Legacy locator seam backed by the domain-neutral runtime locator."""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path

from capability_agent.runtime import locator as _generic_locator
from capability_agent.runtime.locator import (
    PiRuntimeLocator as _PiRuntimeLocator,
    PiRuntimeLocatorError,
)
from grid_agent.application.paths import ProjectPaths
from grid_agent.runtime.lock import PiRuntimeLock


ENV_PI_COMMAND = "GRID_AGENT_PI_COMMAND"
Runner = Callable[..., subprocess.CompletedProcess[str]]


# Keep the historical monkeypatch seam working while all implementation stays
# in the generic module (the two names refer to the same module object).
shutil = _generic_locator.shutil


class PiRuntimeLocator(_PiRuntimeLocator):
    def __init__(
        self,
        pi_runtime_dir: Path,
        environ: Mapping[str, str] | None = None,
        *,
        runtime_lock: PiRuntimeLock | None = None,
        runner: Runner | None = None,
    ) -> None:
        super().__init__(
            pi_runtime_dir,
            environ,
            runtime_lock=runtime_lock or PiRuntimeLock.load(),
            runner=runner,
            command_env_name=ENV_PI_COMMAND,
        )

    @classmethod
    def from_cwd(cls) -> "PiRuntimeLocator":
        paths = ProjectPaths.from_root(Path.cwd())
        return cls(paths.pi_runtime_dir, os.environ)


__all__ = ["ENV_PI_COMMAND", "PiRuntimeLocator", "PiRuntimeLocatorError"]
