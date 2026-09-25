"""Trusted, run-local preparation of the installed pypsamodelctl entry point."""

from __future__ import annotations

import os
import shutil
import stat
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from capability_agent.application.profile import DomainBinding
from capability_agent.domain.provisioning import CredentialLease

from pypsa_network_modeling.execution import ModelctlExecutor, sanitize_environment


_EXECUTABLE = "pypsamodelctl.exe" if os.name == "nt" else "pypsamodelctl"


@dataclass(slots=True)
class PreparedModelEndpoint:
    executor: ModelctlExecutor
    metadata: Mapping[str, object]
    closed: bool = False

    def close(self) -> None:
        self.closed = True


class ModelRuntimeProvisioner:
    def __init__(self, *, executable: Path | None = None) -> None:
        self.executable = executable

    def prepare(
        self, *, binding: DomainBinding, workspace: Path, credentials: CredentialLease
    ) -> PreparedModelEndpoint:
        if credentials.scope_id != binding.credential_scope.scope_id or credentials.credentials:
            raise ValueError("PyPSA modeling requires an empty, matching credential lease")
        source = self._executable()
        root = Path(workspace)
        if root.is_symlink():
            raise ValueError("PyPSA binding workspace is unsafe")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        bin_dir = root / "bin"
        bin_dir.mkdir(mode=0o700)
        target = bin_dir / _EXECUTABLE
        source_fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            mode = os.fstat(source_fd).st_mode
            if not stat.S_ISREG(mode) or not mode & 0o111:
                raise ValueError("installed pypsamodelctl is invalid")
            target_fd = os.open(
                target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o700,
            )
            try:
                while chunk := os.read(source_fd, 64 * 1024):
                    pending = memoryview(chunk)
                    while pending:
                        count = os.write(target_fd, pending)
                        if count <= 0:
                            raise OSError("pypsamodelctl copy made no progress")
                        pending = pending[count:]
                os.fchmod(target_fd, 0o700)
            finally:
                os.close(target_fd)
        finally:
            os.close(source_fd)
        environment = sanitize_environment()
        executor = ModelctlExecutor(
            executable=target, workspace=root, environment=environment,
        )
        return PreparedModelEndpoint(executor, {
            "binding_id": binding.binding_id,
            "executable": _EXECUTABLE,
            "executable_args": (
                "request", "--workspace", str(root), "--run-id", executor.run_id,
            ),
            "search_path": (str(bin_dir),),
            "timeout_seconds": executor.timeout_seconds,
            "environment": environment,
        })

    def _executable(self) -> Path:
        candidate = self.executable or Path(sys.executable).parent / _EXECUTABLE
        if not candidate.exists() and self.executable is None:
            found = shutil.which(_EXECUTABLE)
            if found is None:
                raise ValueError("installed pypsamodelctl is unavailable")
            candidate = Path(found)
        if candidate.is_symlink() or not candidate.is_file() or not os.access(candidate, os.X_OK):
            raise ValueError("installed pypsamodelctl is invalid")
        return candidate
