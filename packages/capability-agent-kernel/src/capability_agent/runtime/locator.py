"""Locate only explicitly selected or verified managed Pi runtimes."""

from __future__ import annotations

import os
import stat
import shutil
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from pathlib import Path

from capability_agent.runtime.lock import (
    PiCommand,
    PiOAuthHelper,
    PiRuntimeIdentity,
    PiRuntimeLock,
)


ENV_PI_COMMAND = "CAPABILITY_AGENT_PI_COMMAND"
Runner = Callable[..., subprocess.CompletedProcess[str]]


class PiRuntimeLocatorError(RuntimeError):
    """Raised when no trusted runtime can be located."""


class PiRuntimeLocator:
    def __init__(
        self,
        pi_runtime_dir: Path,
        environ: Mapping[str, str] | None = None,
        *,
        runtime_lock: PiRuntimeLock | None = None,
        runner: Runner | None = None,
        command_env_name: str = ENV_PI_COMMAND,
    ) -> None:
        self.pi_runtime_dir = Path(pi_runtime_dir)
        self.environ = dict(environ or {})
        self.runtime_lock = runtime_lock or PiRuntimeLock.load()
        self.runner = runner or subprocess.run
        self.command_env_name = command_env_name

    @property
    def source_dir(self) -> Path:
        return self.pi_runtime_dir / "source"

    @property
    def active_marker(self) -> Path:
        return self.pi_runtime_dir / "active"

    def resolve(self, *, require_managed: bool = False) -> PiCommand:
        if require_managed:
            self._reject_managed_symlinks(self.source_dir, "managed runtime source")
            cli = self.source_dir / self.runtime_lock.executable
            self._require_valid_active_marker()
            self._reject_managed_symlinks(cli, "managed runtime executable")
            if not cli.is_file():
                raise PiRuntimeLocatorError("managed runtime executable is missing")
            identity = self._identity(path=cli, source="managed", commit=self.runtime_lock.commit)
            return PiCommand(argv=("node", str(cli)), identity=identity)

        explicit = self.environ.get(self.command_env_name)
        if explicit:
            path = Path(explicit)
            identity = self._identity(path=path, source="explicit_override", commit=None)
            return PiCommand(argv=(str(path),), identity=identity)

        cli = self.source_dir / self.runtime_lock.executable
        self._reject_managed_symlinks(self.source_dir, "managed runtime source")
        self._reject_managed_symlinks(cli, "managed runtime executable")
        if cli.is_file() and self._has_valid_active_marker():
            identity = self._identity(path=cli, source="managed", commit=self.runtime_lock.commit)
            return PiCommand(argv=("node", str(cli)), identity=identity)

        path_command = shutil.which("pi", path=self.environ.get("PATH", ""))
        if path_command:
            path = Path(path_command)
            identity = self._identity(path=path, source="path", commit=None)
            return PiCommand(argv=(str(path),), identity=identity)
        raise PiRuntimeLocatorError(
            "no Pi runtime is available; set the runtime command, add pi to PATH, or install the managed runtime"
        )

    def resolve_oauth_helper(self) -> PiOAuthHelper:
        explicit = self.environ.get(self.command_env_name)
        if explicit:
            command_path = Path(explicit)
            helper = self._explicit_helper_path(command_path)
            if not helper.is_file():
                raise PiRuntimeLocatorError(
                    "pinned OAuth helper pi-ai is unavailable next to the explicit runtime"
                )
            identity = self._identity(path=helper, source="explicit_override", commit=None)
            return PiOAuthHelper(argv=("node", str(helper)), identity=identity)

        helper = self.source_dir / self.runtime_lock.oauth_helper
        self._require_valid_active_marker()
        self._reject_managed_symlinks(helper, "managed OAuth helper")
        if not helper.is_file():
            raise PiRuntimeLocatorError("managed OAuth helper is missing")
        identity = self._identity(path=helper, source="managed", commit=self.runtime_lock.commit)
        return PiOAuthHelper(argv=("node", str(helper)), identity=identity)

    def probe(self) -> PiCommand:
        command = self.resolve()
        result = self._run([*command.argv, "--version"])
        version = _parse_version(result.stdout)
        if version != self.runtime_lock.package_version:
            raise PiRuntimeLocatorError("runtime version does not match the lock")
        return PiCommand(argv=command.argv, identity=replace(command.identity, version=version))

    def _identity(self, *, path: Path, source: str, commit: str | None) -> PiRuntimeIdentity:
        return PiRuntimeIdentity(
            path=path,
            source=source,
            commit=commit,
            package_version=self.runtime_lock.package_version,
            lock_sha256=self.runtime_lock.sha256,
            pi_ai_version=self.runtime_lock.pi_ai_version,
            patches_sha256=self.runtime_lock.patches_sha256,
        )

    def _has_valid_active_marker(self) -> bool:
        try:
            self.active_marker.lstat()
        except FileNotFoundError:
            return False
        except OSError as exc:
            raise PiRuntimeLocatorError(
                "managed runtime active marker cannot be inspected"
            ) from exc
        self._require_valid_active_marker()
        return True

    def _require_valid_active_marker(self) -> None:
        marker = self.active_marker
        self._reject_managed_symlinks(marker, "managed runtime active marker")
        self._reject_managed_symlinks(self.source_dir, "managed runtime source")
        if not marker.is_file():
            raise PiRuntimeLocatorError("managed runtime active marker is missing or invalid")
        try:
            lines = marker.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise PiRuntimeLocatorError("managed runtime active marker cannot be read") from exc
        if len(lines) != 4:
            raise PiRuntimeLocatorError("managed runtime active marker is malformed")
        if not Path(lines[0]).is_absolute() or Path(lines[0]).resolve() != self.source_dir.resolve():
            raise PiRuntimeLocatorError("managed runtime active marker source is invalid")
        values: dict[str, str] = {}
        for line in lines[1:]:
            key, separator, value = line.partition("=")
            if not separator or not key or key in values:
                raise PiRuntimeLocatorError("managed runtime active marker is malformed")
            values[key] = value
        expected = {
            "commit": self.runtime_lock.commit,
            "lock_sha256": self.runtime_lock.sha256,
            "patches_sha256": self.runtime_lock.patches_sha256,
        }
        if values != expected:
            raise PiRuntimeLocatorError("managed runtime active marker identity does not match the lock")

    def _reject_managed_symlinks(self, path: Path, label: str) -> None:
        current = Path(path)
        while True:
            try:
                metadata = current.lstat()
            except FileNotFoundError:
                parent = current.parent
                if parent == current:
                    return
                current = parent
                continue
            except OSError as exc:
                raise PiRuntimeLocatorError(f"{label} cannot be inspected") from exc
            if stat.S_ISLNK(metadata.st_mode):
                raise PiRuntimeLocatorError(f"{label} must not contain symlinks")
            if current != path and not stat.S_ISDIR(metadata.st_mode):
                raise PiRuntimeLocatorError(f"{label} parent is not a directory")
            parent = current.parent
            if parent == current:
                return
            current = parent

    def _run(self, argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        self.pi_runtime_dir.mkdir(parents=True, exist_ok=True)
        try:
            result = self.runner(
                list(argv),
                cwd=self.pi_runtime_dir,
                timeout=15,
                shell=False,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise PiRuntimeLocatorError("runtime command failed to start") from exc
        if result.returncode != 0:
            raise PiRuntimeLocatorError("runtime version command failed")
        return result

    @staticmethod
    def _explicit_helper_path(command_path: Path) -> Path:
        for parent in command_path.parents:
            if parent.name == "node_modules":
                return parent / "@earendil-works/pi-ai/dist/cli.js"
        return command_path.parent / "node_modules/@earendil-works/pi-ai/dist/cli.js"


def _parse_version(stdout: str) -> str:
    if not isinstance(stdout, str):
        raise PiRuntimeLocatorError("runtime version probe returned invalid output")
    for line in stdout.splitlines():
        value = line.strip()
        if value:
            return value.removeprefix("v")
    raise PiRuntimeLocatorError("runtime version probe returned no version")


__all__ = ["ENV_PI_COMMAND", "PiRuntimeLocator", "PiRuntimeLocatorError"]
