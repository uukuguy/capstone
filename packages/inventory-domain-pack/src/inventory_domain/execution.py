from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path
from uuid import uuid4


_RUNTIME_ENVIRONMENT_NAMES = frozenset({
    "PATH", "LANG", "LC_ALL", "LC_CTYPE", "LC_MESSAGES", "LC_COLLATE",
    "LC_NUMERIC", "LC_TIME", "LC_MONETARY", "TZ",
    "TMPDIR", "TMP", "TEMP", "SYSTEMROOT", "SystemRoot", "WINDIR", "windir",
    "COMSPEC", "ComSpec", "PATHEXT",
    "PYTHONIOENCODING", "PYTHONUTF8", "PYTHONUNBUFFERED", "PYTHONDONTWRITEBYTECODE",
})


def sanitize_environment(
    environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    source = dict(os.environ if environment is None else environment)
    selected = {
        item.strip()
        for item in source.get("CAPABILITY_AGENT_SECRET_ENV_NAMES", "").split(",")
        if item.strip()
    }
    return {
        name: value
        for name, value in source.items()
        if name in _RUNTIME_ENVIRONMENT_NAMES and name not in selected
    }


class InventoryctlError(RuntimeError):
    pass


class InventoryCapabilityError(InventoryctlError):
    def __init__(self, error: dict[str, object]) -> None:
        super().__init__(str(error.get("message", "Inventory capability failed")))
        self.error = error


class InventoryctlExecutor:
    def __init__(
        self,
        *,
        executable: Path,
        workspace: Path,
        timeout_seconds: float = 60.0,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        self.executable = Path(executable)
        self.workspace = Path(workspace)
        self.timeout_seconds = timeout_seconds
        self._environment = dict(
            os.environ if environment is None else environment
        )
        self.last_diagnostics = ""

    def invoke(
        self, capability: str, arguments: dict[str, object]
    ) -> dict[str, object]:
        request_id = f"inventory-{uuid4().hex}"
        request = {
            "protocol": "inventory-capability",
            "protocol_version": "1.0",
            "request_id": request_id,
            "capability": capability,
            "arguments": arguments,
        }
        try:
            completed = subprocess.run(
                [
                    str(self.executable),
                    "request",
                    "--workspace",
                    str(self.workspace),
                ],
                input=json.dumps(request, separators=(",", ":")) + "\n",
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                shell=False,
                check=False,
                env=sanitize_environment(self._environment),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise InventoryctlError(
                "inventory service process could not complete"
            ) from exc
        self.last_diagnostics = completed.stderr
        lines = completed.stdout.splitlines()
        if len(lines) != 1:
            raise InventoryctlError(
                "inventory service returned an invalid stdout protocol"
            )
        try:
            response = json.loads(lines[0])
        except json.JSONDecodeError as exc:
            raise InventoryctlError(
                "inventory service returned non-JSON stdout"
            ) from exc
        if (
            not isinstance(response, dict)
            or response.get("protocol") != "inventory-capability"
            or response.get("protocol_version") != "1.0"
            or response.get("request_id") != request_id
        ):
            raise InventoryctlError(
                "inventory service response does not match its request"
            )
        if response.get("ok") is not True:
            error = response.get("error")
            if isinstance(error, dict):
                raise InventoryCapabilityError(error)
            raise InventoryctlError("inventory service operation failed")
        result = response.get("result")
        if not isinstance(result, dict):
            raise InventoryctlError("inventory service response has no result object")
        return result
