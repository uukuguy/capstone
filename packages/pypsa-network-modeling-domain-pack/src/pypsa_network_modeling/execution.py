"""Fixed process transport for the registered PyPSA model authority."""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path
from uuid import uuid4


_ENV_NAMES = frozenset({
    "PATH", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "TMPDIR", "TMP", "TEMP",
    "SYSTEMROOT", "SystemRoot", "WINDIR", "windir", "PATHEXT",
    "PYTHONIOENCODING", "PYTHONUTF8", "PYTHONUNBUFFERED", "PYTHONDONTWRITEBYTECODE",
})


def sanitize_environment(source: Mapping[str, str] | None = None) -> dict[str, str]:
    provided = dict(os.environ if source is None else source)
    selected = {
        name.strip() for name in provided.get("CAPABILITY_AGENT_SECRET_ENV_NAMES", "").split(",")
        if name.strip()
    }
    clean = {
        name: value for name, value in provided.items()
        if name in _ENV_NAMES and name not in selected
    }
    clean["POLARS_MAX_THREADS"] = "4"
    return clean


class ModelctlError(RuntimeError):
    pass


class ModelctlCapabilityError(ModelctlError):
    def __init__(self, error: Mapping[str, object]) -> None:
        super().__init__(str(error.get("message", "PyPSA model capability failed")))
        self.code = str(error.get("code", "capability_failed"))


class ModelctlExecutor:
    def __init__(
        self, *, executable: Path, workspace: Path, timeout_seconds: float = 60.0,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        self.executable = Path(executable)
        self.workspace = Path(workspace)
        self.run_id = self.workspace.parent.parent.name
        self.timeout_seconds = timeout_seconds
        self.environment = sanitize_environment(environment)
        self.last_diagnostics = ""

    def invoke(self, capability: str, arguments: dict[str, object]) -> dict[str, object]:
        request_id = f"pypsa-model-{uuid4().hex}"
        request = {
            "protocol": "pypsa-model-capability", "protocol_version": "1.0",
            "request_id": request_id, "capability": capability,
            "arguments": arguments,
        }
        try:
            completed = subprocess.run(
                [str(self.executable), "request", "--workspace", str(self.workspace),
                 "--run-id", self.run_id],
                input=json.dumps(request, ensure_ascii=False, separators=(",", ":")) + "\n",
                text=True, capture_output=True, timeout=self.timeout_seconds,
                shell=False, check=False, env=self.environment,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ModelctlError("PyPSA model authority process could not complete") from exc
        self.last_diagnostics = completed.stderr
        lines = completed.stdout.splitlines()
        if len(lines) != 1:
            raise ModelctlError("PyPSA model authority returned an invalid stdout protocol")
        try:
            response = json.loads(lines[0])
        except json.JSONDecodeError as exc:
            raise ModelctlError("PyPSA model authority returned non-JSON stdout") from exc
        if (
            not isinstance(response, dict)
            or response.get("protocol") != "pypsa-model-capability"
            or response.get("protocol_version") != "1.0"
            or response.get("request_id") != request_id
        ):
            raise ModelctlError("PyPSA model authority response does not match its request")
        if response.get("ok") is not True:
            error = response.get("error")
            if completed.returncode == 0 and isinstance(error, dict):
                raise ModelctlCapabilityError(error)
            raise ModelctlError("PyPSA model authority operation failed")
        if completed.returncode != 0 or not isinstance(response.get("result"), dict):
            raise ModelctlError("PyPSA model authority returned an invalid success")
        return response["result"]
