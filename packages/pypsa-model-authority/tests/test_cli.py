from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _invoke(tmp_path: Path, request: object) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment.pop("POLARS_MAX_THREADS", None)
    return subprocess.run(
        [sys.executable, "-m", "pypsa_model_authority.cli", "request",
         "--workspace", str(tmp_path / "authority"), "--run-id", "run-one"],
        input=json.dumps(request) + "\n", text=True, capture_output=True,
        timeout=30, check=False, env=environment,
    )


def test_cli_emits_one_protocol_object_for_real_open_and_invalid_request(tmp_path: Path) -> None:
    request = {
        "protocol": "pypsa-model-capability", "protocol_version": "1.0",
        "request_id": "req-1", "capability": "model.open",
        "arguments": {"catalog_id": "two-bus"},
    }
    opened = _invoke(tmp_path, request)
    assert opened.returncode == 0, opened.stderr
    lines = opened.stdout.splitlines()
    assert len(lines) == 1
    response = json.loads(lines[0])
    assert response["request_id"] == "req-1" and response["ok"] is True
    assert response["result"]["model_ref"].startswith("pypsa-model:sha256:")

    malformed = _invoke(tmp_path, {**request, "protocol_version": "0.9"})
    assert malformed.returncode == 0
    error_lines = malformed.stdout.splitlines()
    assert len(error_lines) == 1
    assert json.loads(error_lines[0])["error"]["code"] == "invalid_request"
