"""Pandapower-owned simulator provisioning.

The generic application only knows that a binding supplies an executor.  This
module owns the concrete ``gridctl`` lookup, the fixed request boundary, and
the run-local executable search path used by the first domain.
"""

from __future__ import annotations

import os
import json
import re
from hashlib import sha256
import shutil
import stat
from threading import Lock
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from capability_agent._safe_files import ensure_bound_directory
from capability_agent.application.profile import DomainBinding
from capability_agent.domain.execution import CapabilityExecutor
from capability_agent.domain.provisioning import CredentialLease

from pandapower_domain.execution import (
    DEFAULT_MAX_OUTPUT_BYTES,
    GridctlExecutor,
    prepare_runtime_environment,
)


GRIDCTL_ENVIRONMENT_NAME = "GRID_AGENT_GRIDCTL_EXECUTABLE"
GRIDCTL_NAME = "gridctl.exe" if os.name == "nt" else "gridctl"
DEFAULT_TIMEOUT_SECONDS = 60.0

# One immutable runtime catalog, shared across isolated binding workspaces.
# Replacement bounds memory without limiting contexts or rejecting any request.
_environment_lock = Lock()
_environment_key: tuple[object, ...] | None = None
_environment_document: str | None = None


class _RuntimeCatalogExecutor(GridctlExecutor):
    def __init__(self, *, runtime_identity: str, source_executable: Path, **kwargs) -> None:
        super().__init__(**kwargs)
        self._catalog_key = None
        if re.fullmatch(r'[0-9a-f]{64}', runtime_identity):
            self._catalog_key = (runtime_identity, str(source_executable.resolve()),
                sha256(source_executable.read_bytes()).hexdigest(),
                tuple(sorted(self._environment.items())), self.max_output_bytes)

    def invoke(self, capability: str, arguments: dict[str, object]) -> dict[str, object]:
        if capability != 'environment.describe' or arguments or self._catalog_key is None:
            return super().invoke(capability, arguments)
        global _environment_key, _environment_document
        with _environment_lock:
            if _environment_key == self._catalog_key and _environment_document is not None:
                self.last_diagnostics = ''
                return json.loads(_environment_document)
            result = super().invoke(capability, arguments)
            document = json.dumps(result, allow_nan=False)
            _environment_key, _environment_document = self._catalog_key, document
            return result


class PandapowerProvisioningError(RuntimeError):
    """The pandapower simulator endpoint cannot be prepared safely."""


@dataclass(slots=True)
class PreparedPandapowerEndpoint:
    """Run-scoped endpoint exposed to the generic composition layer."""

    executor: CapabilityExecutor
    metadata: Mapping[str, object]
    _closed: bool = False

    def close(self) -> None:
        self._closed = True

    @property
    def closed(self) -> bool:
        return self._closed


class PandapowerRuntimeProvisioner:
    """Resolve ``gridctl`` and expose it only inside one binding workspace.

    The first domain has no domain credentials.  The executable is copied into
    the binding-owned ``bin`` directory so the model runtime receives a stable,
    run-local search path rather than the operator's ambient PATH entry.
    """

    def __init__(
        self,
        *,
        executable: Path | None = None,
        repository_root: Path | None = None,
        environ: Mapping[str, str] | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_output_bytes <= 0:
            raise ValueError("max_output_bytes must be positive")
        self.executable = Path(executable) if executable is not None else None
        self.repository_root = (
            Path(repository_root).resolve() if repository_root is not None else None
        )
        self.environ = dict(os.environ if environ is None else environ)
        self.timeout_seconds = float(timeout_seconds)
        self.max_output_bytes = int(max_output_bytes)

    def with_prepared_backend(self, environment: Mapping[str, str]) -> PandapowerRuntimeProvisioner:
        """Clone trusted backend selection; never modify a prepared endpoint."""
        names = {'CAPSTONE_POWERMCP_MANAGED_ROOT', 'CAPSTONE_POWERMCP_INSTALL_ID',
                 'CAPSTONE_POWERMCP_DESCRIPTOR_SHA256'}
        if set(environment) != names or any(not isinstance(value, str) or not value for value in environment.values()):
            raise ValueError('prepared backend environment is invalid')
        return type(self)(executable=self.executable, repository_root=self.repository_root,
            environ={**self.environ, **environment}, timeout_seconds=self.timeout_seconds,
            max_output_bytes=self.max_output_bytes)

    def prepare(
        self,
        *,
        binding: DomainBinding,
        workspace: Path,
        credentials: CredentialLease,
    ) -> PreparedPandapowerEndpoint:
        self._require_empty_credentials(binding, credentials)
        binding_root = _prepare_workspace(workspace)
        executable = self._resolve_executable()
        bin_path = binding_root / "bin"
        _ensure_directory(bin_path, label="pandapower binding bin directory")
        target = bin_path / GRIDCTL_NAME
        self._install_binding_executable(executable, target)

        safe_environment = prepare_runtime_environment(self.environ)
        metadata = {
            "binding_id": binding.binding_id,
            # The descriptor exposes only the validated basename.  The
            # absolute target remains private to the executor below.
            "executable": GRIDCTL_NAME,
            "executable_args": (
                "request",
                "--workspace",
                str(binding_root),
            ),
            "search_path": (str(bin_path),),
            "timeout_seconds": self.timeout_seconds,
            "max_output_bytes": self.max_output_bytes,
            "environment": dict(safe_environment),
        }
        executor = _RuntimeCatalogExecutor(
            runtime_identity=self.environ.get('CAPSTONE_RUNTIME_ARTIFACT_SHA256', ''),
            source_executable=executable,
            executable=target,
            workspace=binding_root,
            timeout_seconds=self.timeout_seconds,
            max_output_bytes=self.max_output_bytes,
            environment=safe_environment,
        )
        return PreparedPandapowerEndpoint(executor=executor, metadata=metadata)

    def _require_empty_credentials(
        self, binding: DomainBinding, credentials: CredentialLease
    ) -> None:
        try:
            values = dict(credentials.credentials)
            scope_id = credentials.scope_id
            expected_scope_id = binding.credential_scope.scope_id
        except Exception as exc:
            raise PandapowerProvisioningError(
                "pandapower credential lease is invalid"
            ) from exc
        if scope_id != expected_scope_id:
            raise PandapowerProvisioningError(
                "pandapower credential lease scope does not match binding"
            )
        if values:
            raise PandapowerProvisioningError(
                "pandapower runtime does not accept domain credentials"
            )

    def _resolve_executable(self) -> Path:
        candidate: Path | None = self.executable
        if candidate is None:
            explicit = self.environ.get(GRIDCTL_ENVIRONMENT_NAME)
            if explicit:
                candidate = Path(explicit)
            elif self.repository_root is not None:
                candidate = self._managed_path(self.repository_root)
            else:
                installed = shutil.which(GRIDCTL_NAME, path=self.environ.get("PATH", ""))
                if installed:
                    candidate = Path(installed)
        if candidate is None:
            raise PandapowerProvisioningError(
                "pandapower simulator executable is unavailable"
            )
        try:
            resolved = candidate.resolve(strict=True)
        except OSError as exc:
            raise PandapowerProvisioningError(
                "pandapower simulator executable is unavailable"
            ) from exc
        if not resolved.is_file() or not os.access(resolved, os.X_OK):
            raise PandapowerProvisioningError(
                "pandapower simulator executable is unavailable"
            )
        return resolved

    @staticmethod
    def _managed_path(repository_root: Path) -> Path:
        folder = "Scripts" if os.name == "nt" else "bin"
        return repository_root / "packages/grid-simulator/.venv" / folder / GRIDCTL_NAME

    @staticmethod
    def _install_binding_executable(source: Path, target: Path) -> None:
        try:
            if target.exists() or target.is_symlink():
                target.unlink()
            shutil.copy2(source, target)
            target.chmod(target.stat().st_mode | 0o111)
        except OSError as exc:
            raise PandapowerProvisioningError(
                "pandapower simulator executable could not be installed"
            ) from exc


__all__ = [
    "DEFAULT_MAX_OUTPUT_BYTES",
    "DEFAULT_TIMEOUT_SECONDS",
    "GRIDCTL_ENVIRONMENT_NAME",
    "GRIDCTL_NAME",
    "PandapowerProvisioningError",
    "PandapowerRuntimeProvisioner",
    "PreparedPandapowerEndpoint",
]


def _prepare_workspace(workspace: Path) -> Path:
    try:
        return ensure_bound_directory(workspace)
    except (OSError, TypeError, ValueError) as exc:
        raise PandapowerProvisioningError(
            "pandapower binding workspace could not be prepared safely"
        ) from exc


def _ensure_directory(path: Path, *, label: str) -> None:
    try:
        if path.exists() or path.is_symlink():
            metadata = path.lstat()
            if stat.S_ISLNK(metadata.st_mode):
                raise PandapowerProvisioningError(f"{label} must not be a symlink")
            if not stat.S_ISDIR(metadata.st_mode):
                raise PandapowerProvisioningError(f"{label} is not a directory")
            return
        path.mkdir(mode=0o700)
        metadata = path.lstat()
    except PandapowerProvisioningError:
        raise
    except OSError as exc:
        raise PandapowerProvisioningError(f"{label} could not be prepared") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise PandapowerProvisioningError(f"{label} is not a private directory")
