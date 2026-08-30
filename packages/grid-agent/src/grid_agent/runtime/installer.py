"""Legacy managed-runtime installer seam backed by the generic installer."""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path

from capability_agent.runtime.installer import (
    PiRuntimeInstaller as _PiRuntimeInstaller,
    PiRuntimeInstallerError,
)
from grid_agent.runtime.lock import PiRuntimeLock


Runner = Callable[..., subprocess.CompletedProcess[str]]


class PiRuntimeInstaller(_PiRuntimeInstaller):
    def __init__(
        self,
        runtime_lock: PiRuntimeLock,
        pi_runtime_dir: Path,
        *,
        runner: Runner | None = None,
        timeout_seconds: int = 120,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(
            runtime_lock,
            pi_runtime_dir,
            runner=runner,
            timeout_seconds=timeout_seconds,
            environ=environ,
            command_env_name="GRID_AGENT_PI_COMMAND",
        )


__all__ = ["PiRuntimeInstaller", "PiRuntimeInstallerError"]
