"""Trusted, run-local provisioning of the installed inventoryctl authority."""
from __future__ import annotations

import math
import os
import shutil
import stat
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from capability_agent.application.profile import DomainBinding
from capability_agent.domain.provisioning import CredentialLease
from inventory_domain.execution import InventoryctlExecutor, sanitize_environment

INVENTORYCTL_NAME = "inventoryctl.exe" if os.name == "nt" else "inventoryctl"


@dataclass(slots=True)
class PreparedInventoryEndpoint:
    executor: InventoryctlExecutor
    metadata: Mapping[str, object]
    closed: bool = False

    def close(self) -> None:
        self.closed = True


class InventoryRuntimeProvisioner:
    def __init__(
        self, *, executable: Path | None = None,
        environment: Mapping[str, str] | None = None, timeout_seconds: float = 60.0,
    ) -> None:
        if isinstance(timeout_seconds, bool) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("inventory timeout must be positive and finite")
        self._executable = Path(executable) if executable is not None else None
        self._environment = dict(os.environ if environment is None else environment)
        self._timeout_seconds = float(timeout_seconds)

    def prepare(
        self, *, binding: DomainBinding, workspace: Path, credentials: CredentialLease,
    ) -> PreparedInventoryEndpoint:
        try:
            scope_id = credentials.scope_id
            values = credentials.credentials
            expected = binding.credential_scope.scope_id
        except AttributeError as exc:
            raise ValueError("inventory credential lease is invalid") from exc
        if not isinstance(scope_id, str) or not scope_id or scope_id != expected or not isinstance(values, Mapping) or values:
            raise ValueError("inventory credential lease is invalid")
        if not isinstance(binding.binding_id, str) or not binding.binding_id.strip():
            raise ValueError("inventory binding is invalid")
        source = self._resolve_executable()
        root = Path(os.path.abspath(workspace))
        if root.is_symlink():
            raise ValueError("inventory binding workspace must not be a symlink")
        try:
            root.mkdir(parents=True, exist_ok=True, mode=0o700)
            root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                root = root.resolve(strict=True)
                try:
                    os.mkdir("bin", mode=0o700, dir_fd=root_fd)
                except FileExistsError:
                    pass
                bin_fd = os.open("bin", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd)
                try:
                    _copy_new_executable(source, bin_fd)
                finally:
                    os.close(bin_fd)
            finally:
                os.close(root_fd)
        except OSError as exc:
            raise ValueError("inventory binding workspace or executable target is unsafe") from exc
        bin_path = root / "bin"
        environment = sanitize_environment(self._environment)
        executor = InventoryctlExecutor(
            executable=bin_path / INVENTORYCTL_NAME, workspace=root,
            timeout_seconds=self._timeout_seconds, environment=environment,
        )
        return PreparedInventoryEndpoint(executor, {
            "binding_id": binding.binding_id,
            "executable": INVENTORYCTL_NAME,
            "executable_args": ("request", "--workspace", str(root)),
            "search_path": (str(bin_path),),
            "timeout_seconds": self._timeout_seconds,
            "environment": environment,
        })

    def _resolve_executable(self) -> Path:
        if self._executable is not None:
            return _trusted_executable(self._executable)
        candidate = Path(sys.executable).parent / INVENTORYCTL_NAME
        if candidate.exists() or candidate.is_symlink():
            return _trusted_executable(candidate)
        found = shutil.which(INVENTORYCTL_NAME, path=self._environment.get("PATH", ""))
        if found is None:
            raise ValueError("installed inventoryctl executable is unavailable")
        return _trusted_executable(Path(found))


def _trusted_executable(path: Path) -> Path:
    try:
        info = path.lstat()
    except OSError as exc:
        raise ValueError("inventoryctl executable is invalid") from exc
    if not stat.S_ISREG(info.st_mode) or not os.access(path, os.X_OK):
        raise ValueError("inventoryctl executable is invalid")
    return path.resolve(strict=True)


def _copy_new_executable(source: Path, bin_fd: int) -> None:
    """Exclusive creation prevents overwrite, including target symlink races."""
    source_fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(source_fd)
        if not stat.S_ISREG(info.st_mode) or not info.st_mode & 0o111:
            raise ValueError("inventoryctl executable is invalid")
        target_fd = os.open(
            INVENTORYCTL_NAME, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o700, dir_fd=bin_fd,
        )
        try:
            while chunk := os.read(source_fd, 64 * 1024):
                pending = memoryview(chunk)
                while pending:
                    count = os.write(target_fd, pending)
                    if count <= 0:
                        raise OSError("inventory executable copy made no progress")
                    pending = pending[count:]
            os.fchmod(target_fd, 0o700)
        finally:
            os.close(target_fd)
    finally:
        os.close(source_fd)
