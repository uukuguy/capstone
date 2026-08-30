"""Install and verify the managed Pi runtime from its lock contract."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from capability_agent.runtime.lock import (
    PiCommand,
    PiRuntimeIdentity,
    PiRuntimeLock,
    PiRuntimePatch,
)
from capability_agent.runtime.locator import (
    ENV_PI_COMMAND,
    PiRuntimeLocator,
    PiRuntimeLocatorError,
)


Runner = Callable[..., subprocess.CompletedProcess[str]]


class PiRuntimeInstallerError(RuntimeError):
    """Raised when managed runtime installation cannot be completed."""


class PiRuntimeInstaller:
    def __init__(
        self,
        runtime_lock: PiRuntimeLock,
        pi_runtime_dir: Path,
        *,
        runner: Runner | None = None,
        timeout_seconds: int = 120,
        environ: Mapping[str, str] | None = None,
        command_env_name: str = ENV_PI_COMMAND,
    ) -> None:
        self.runtime_lock = runtime_lock
        self.pi_runtime_dir = Path(pi_runtime_dir)
        self.runner = runner or subprocess.run
        self.timeout_seconds = timeout_seconds
        self.environ = dict(os.environ if environ is None else environ)
        self.command_env_name = command_env_name

    @property
    def source_dir(self) -> Path:
        return self.pi_runtime_dir / "source"

    @property
    def active_marker(self) -> Path:
        return self.pi_runtime_dir / "active"

    def install(self) -> PiCommand:
        source = self._prepare_source_dir()
        self._clear_active_marker()
        self._verify_patch_bytes()
        if not (source / ".git").exists():
            self._run(["git", "init"])
        self._run(["git", "remote", "remove", "origin"], check=False)
        self._run(["git", "remote", "add", "origin", self.runtime_lock.repository])
        self._run(["git", "fetch", "--depth", "1", "origin", self.runtime_lock.commit])
        self._run(["git", "checkout", "--detach", self.runtime_lock.commit])
        self._run(["git", "reset", "--hard", self.runtime_lock.commit])
        self._run(["git", "clean", "-fdx"])
        for patch in self.runtime_lock.patches:
            self._apply_patch(patch)
        self._run(["npm", "ci"], timeout=max(self.timeout_seconds, 300))
        self._hydrate_pinned_dependency()
        self._run_pi_build()
        cli = source / self.runtime_lock.executable
        if not cli.is_file():
            raise PiRuntimeInstallerError("managed runtime build did not produce its executable")
        version = self._probe_version(cli)
        if version != self.runtime_lock.package_version:
            raise PiRuntimeInstallerError(
                "managed runtime version does not match the lock: "
                f"expected {self.runtime_lock.package_version}, got {version}"
            )
        self.active_marker.parent.mkdir(parents=True, exist_ok=True)
        self.active_marker.write_text(
            f"{source}\n"
            f"commit={self.runtime_lock.commit}\n"
            f"lock_sha256={self.runtime_lock.sha256}\n"
            f"patches_sha256={self.runtime_lock.patches_sha256}\n",
            encoding="utf-8",
        )
        identity = PiRuntimeIdentity(
            path=cli,
            source="managed",
            commit=self.runtime_lock.commit,
            package_version=self.runtime_lock.package_version,
            lock_sha256=self.runtime_lock.sha256,
            pi_ai_version=self.runtime_lock.pi_ai_version,
            patches_sha256=self.runtime_lock.patches_sha256,
            version=version,
        )
        return PiCommand(argv=("node", str(cli)), identity=identity)

    def ensure(self) -> PiCommand:
        locator = PiRuntimeLocator(
            self.pi_runtime_dir,
            self.environ,
            runtime_lock=self.runtime_lock,
            command_env_name=self.command_env_name,
        )
        try:
            return locator.resolve(require_managed=True)
        except PiRuntimeLocatorError:
            self.install()
            return locator.resolve(require_managed=True)

    def _prepare_source_dir(self) -> Path:
        runtime_root = self._prepare_runtime_root()
        source = self.source_dir
        if source.is_symlink():
            raise PiRuntimeInstallerError("managed runtime source must not be a symlink")
        try:
            source.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise PiRuntimeInstallerError("managed runtime source could not be created") from exc
        if source.is_symlink() or not source.is_dir():
            raise PiRuntimeInstallerError("managed runtime source is not a safe directory")
        try:
            source.resolve().relative_to(runtime_root)
        except ValueError as exc:
            raise PiRuntimeInstallerError("managed runtime source escapes its root") from exc
        return source

    def _prepare_runtime_root(self) -> Path:
        root = self.pi_runtime_dir
        if root.is_symlink():
            raise PiRuntimeInstallerError("managed runtime root must not be a symlink")
        try:
            root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise PiRuntimeInstallerError("managed runtime root could not be created") from exc
        if root.is_symlink() or not root.is_dir():
            raise PiRuntimeInstallerError("managed runtime root is not a safe directory")
        return root.resolve()

    def _clear_active_marker(self) -> None:
        try:
            self.active_marker.unlink()
        except FileNotFoundError:
            return
        except OSError as exc:
            raise PiRuntimeInstallerError("managed runtime active marker could not be removed") from exc

    def _apply_patch(self, patch: PiRuntimePatch) -> None:
        self._verify_patch_bytes(patch)
        self._run(["git", "apply", "--check", str(patch.path)])
        self._run(["git", "apply", str(patch.path)])

    def _verify_patch_bytes(self, patch: PiRuntimePatch | None = None) -> None:
        for item in ((patch,) if patch is not None else self.runtime_lock.patches):
            try:
                actual = hashlib.sha256(item.path.read_bytes()).hexdigest()
            except OSError as exc:
                raise PiRuntimeInstallerError("managed runtime patch cannot be read") from exc
            if actual != item.sha256:
                raise PiRuntimeInstallerError("managed runtime patch digest mismatch")

    def _probe_version(self, cli: Path) -> str:
        result = self._run(["node", str(cli), "--version"], timeout=15)
        for line in result.stdout.splitlines():
            if line.strip():
                return line.strip().removeprefix("v")
        raise PiRuntimeInstallerError("runtime version probe returned no version")

    def _run_pi_build(self) -> None:
        for workspace in (
            "@earendil-works/pi-tui",
            "@earendil-works/pi-agent-core",
            "@earendil-works/pi-coding-agent",
        ):
            self._run(["npm", "run", "build", "--workspace", workspace], timeout=max(self.timeout_seconds, 300))

    def _hydrate_pinned_dependency(self) -> None:
        with tempfile.TemporaryDirectory(prefix="capability-agent-pi-ai-") as temporary:
            result = self._run(
                [
                    "npm",
                    "pack",
                    "--json",
                    "--pack-destination",
                    temporary,
                    f"@earendil-works/pi-ai@{self.runtime_lock.pi_ai_version}",
                ],
                timeout=max(self.timeout_seconds, 300),
            )
            try:
                package = json.loads(result.stdout)[0]
                filename = package["filename"]
                integrity = package["integrity"]
            except (IndexError, KeyError, TypeError, json.JSONDecodeError) as exc:
                raise PiRuntimeInstallerError("pinned dependency metadata is invalid") from exc
            if integrity != self.runtime_lock.pi_ai_npm_integrity:
                raise PiRuntimeInstallerError("pinned dependency integrity mismatch")
            archive = Path(temporary, filename)
            if archive.parent != Path(temporary) or not archive.is_file():
                raise PiRuntimeInstallerError("pinned dependency archive is unavailable")
            self._run(["tar", "-xzf", str(archive), "-C", temporary])
            source_dist = Path(temporary, "package", "dist")
            target_dist = self.source_dir / "packages" / "ai" / "dist"
            if not source_dist.is_dir() or target_dist.is_symlink():
                raise PiRuntimeInstallerError("pinned dependency archive is unsafe")
            shutil.rmtree(target_dist, ignore_errors=True)
            shutil.copytree(source_dist, target_dist)

    def _run(
        self,
        argv: Sequence[str],
        *,
        timeout: int | None = None,
        check: bool = True,
        env: Mapping[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command = list(argv)
        try:
            result = self.runner(
                command,
                cwd=self.source_dir,
                timeout=timeout or self.timeout_seconds,
                shell=False,
                capture_output=True,
                text=True,
                env=dict(env) if env is not None else None,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise PiRuntimeInstallerError("managed runtime command failed to start") from exc
        if check and result.returncode != 0:
            detail = _sanitize_command_detail(result.stderr or result.stdout or "")
            message = f"managed runtime command failed: {' '.join(command)}"
            if detail:
                message = f"{message}: {detail}"
            raise PiRuntimeInstallerError(message)
        return result


_COMMAND_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_-]?key|token|password|secret|credential|authorization)\s*[:=]\s*([^\s,;]+)"
)
_COMMAND_BEARER = re.compile(r"(?i)\b(bearer\s+)([^\s,;]+)")


def _sanitize_command_detail(value: object) -> str:
    if not isinstance(value, str):
        return "provider reported an invalid diagnostic"
    detail = _COMMAND_SECRET_ASSIGNMENT.sub(r"\1=[REDACTED]", value)
    detail = _COMMAND_BEARER.sub(r"\1[REDACTED]", detail)
    return detail.strip()[:500]


__all__ = ["PiRuntimeInstaller", "PiRuntimeInstallerError"]
