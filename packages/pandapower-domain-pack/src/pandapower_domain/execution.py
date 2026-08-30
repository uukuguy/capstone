from __future__ import annotations

import json
import os
import re
import subprocess
from collections.abc import Mapping
from pathlib import Path
from uuid import uuid4


_CANONICAL_SECRET_NAMES = frozenset(
    {
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "DEEPSEEK_API_KEY",
        "MINIMAX_API_KEY",
        "GRID_AGENT_SECRET_ENV_NAMES",
    }
)
# Match complete credential tokens, not arbitrary substrings: this catches
# ``SERVICE_APIKEY`` and ``API_KEY_PATH`` while retaining ``SECRETARY`` and
# ``TOKENIZER_MODE``.  The explicit ``KEY`` forms cover both common spellings
# without treating every environment variable containing the word ``KEY`` as
# sensitive.
_CREDENTIAL_NAME_PATTERN = re.compile(
    r"(?<![A-Z0-9])"
    r"(?:API_KEY|APIKEY|TOKEN|SECRETKEY|SECRET|PASSPHRASE|"
    r"AUTHORIZATION|CREDENTIAL|PASSWORD|PRIVATE_KEY)"
    r"(?![A-Z0-9])",
    re.IGNORECASE,
)


def sanitize_environment(
    environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Remove credential-shaped names before starting the simulator process."""

    source = dict(os.environ if environment is None else environment)
    selected_names = {
        name.strip()
        for name in source.get("GRID_AGENT_SECRET_ENV_NAMES", "").split(",")
        if name.strip()
    }
    blocked = _CANONICAL_SECRET_NAMES | selected_names
    return {
        name: value
        for name, value in source.items()
        if name not in blocked and not _CREDENTIAL_NAME_PATTERN.search(name)
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
        self._environment = dict(
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
                env=sanitize_environment(self._environment),
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
