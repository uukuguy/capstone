from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path
from uuid import uuid4


# Keep this allowlist deliberately small.  These names are runtime inputs for
# executable lookup, locale/time handling, temporary files, Python stream
# encoding/buffering, or Windows process startup; provider, domain, and
# business variables are never ambient inputs to the simulator.
_RUNTIME_ENVIRONMENT_NAMES = frozenset(
    {
        "COMSPEC",
        "__CF_USER_TEXT_ENCODING",
        "LANG",
        "LANGUAGE",
        "PATH",
        "PATHEXT",
        "PYTHONHASHSEED",
        "PYTHONIOENCODING",
        "PYTHONUNBUFFERED",
        "PYTHONUTF8",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "TMPDIR",
        "TZ",
        "WINDIR",
    }
)
# These are the POSIX locale categories consumed by the C/Python runtime.  Do
# not use an ``LC_`` prefix wildcard: an unknown variable must not become an
# ambient channel just because it resembles a locale setting.
_LOCALE_ENVIRONMENT_NAMES = frozenset(
    {
        "LC_ALL",
        "LC_COLLATE",
        "LC_CTYPE",
        "LC_MESSAGES",
        "LC_MONETARY",
        "LC_NUMERIC",
        "LC_TIME",
    }
)


def _is_runtime_environment_name(name: str) -> bool:
    """Return whether an environment name is needed by the simulator runtime."""

    normalized = name.upper()
    return normalized in _RUNTIME_ENVIRONMENT_NAMES or normalized in _LOCALE_ENVIRONMENT_NAMES


def sanitize_environment(
    environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Allow only portable runtime inputs before starting the simulator process."""

    source = dict(os.environ if environment is None else environment)
    return {
        name: value
        for name, value in source.items()
        if _is_runtime_environment_name(name)
    }


class GridctlClientError(RuntimeError):
    """The simulator transport could not produce a valid response."""


class SimulatorOperationError(GridctlClientError):
    """The simulator reported an untyped operation failure."""


class SimulatorCapabilityError(GridctlClientError):
    """The simulator returned a typed capability error envelope."""

    def __init__(self, error: dict[str, object]) -> None:
        super().__init__(str(error.get("message", "Grid capability failed")))
        self.error = error


class GridctlExecutor:
    """Invoke the fixed gridctl capability protocol."""

    def __init__(
        self,
        *,
        executable: Path,
        workspace: Path,
        timeout_seconds: float = 60,
        environ: Mapping[str, str] | None = None,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        if environ is not None and environment is not None:
            raise TypeError("provide only one of environ or environment")
        base_environment = environment if environment is not None else environ
        self.executable = Path(executable)
        self.workspace = Path(workspace)
        self.timeout_seconds = timeout_seconds
        self._environment = sanitize_environment(
            os.environ if base_environment is None else base_environment
        )
        self.last_diagnostics = ""

    def invoke(self, capability: str, arguments: dict[str, object]) -> dict[str, object]:
        request_id = f"sim-{uuid4().hex}"
        request = {
            "protocol": "grid-capability",
            "protocol_version": "1.0",
            "request_id": request_id,
            "capability": capability,
            "arguments": arguments,
        }
        try:
            completed = subprocess.run(
                [str(self.executable), "request", "--workspace", str(self.workspace)],
                input=json.dumps(request, separators=(",", ":")) + "\n",
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                shell=False,
                check=False,
                env=self._environment,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise GridctlClientError(
                "Grid simulator process could not complete"
            ) from exc
        self.last_diagnostics = completed.stderr
        lines = completed.stdout.splitlines()
        if len(lines) != 1:
            raise GridctlClientError("Grid simulator returned an invalid stdout protocol")
        try:
            response = json.loads(lines[0])
        except json.JSONDecodeError as exc:
            raise GridctlClientError("Grid simulator returned non-JSON stdout") from exc
        if not isinstance(response, dict):
            raise GridctlClientError("Grid simulator response does not match its request")
        if (
            response.get("protocol") != "grid-capability"
            or response.get("protocol_version") != "1.0"
            or response.get("request_id") != request_id
        ):
            raise GridctlClientError("Grid simulator response does not match its request")
        if response.get("ok") is not True:
            error = response.get("error") or {}
            if isinstance(error, dict):
                raise SimulatorCapabilityError(error)
            raise SimulatorOperationError("Grid simulator operation failed")
        result = response.get("result")
        if not isinstance(result, dict):
            raise GridctlClientError("Grid simulator response has no result object")
        return result

    def call(self, capability: str, arguments: dict[str, object]) -> dict[str, object]:
        return self.invoke(capability, arguments)
