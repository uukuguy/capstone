from __future__ import annotations

import json
import subprocess
import sys


def _invoke(workspace, request):
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "inventory_reference.cli",
            "request",
            "--workspace",
            str(workspace),
        ],
        input=json.dumps(request) + "\n",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_cli_writes_one_correlated_success_object_to_stdout(tmp_path) -> None:
    completed = _invoke(
        tmp_path,
        {
            "protocol": "inventory-capability",
            "protocol_version": "1.0",
            "request_id": "request-1",
            "capability": "environment.describe",
            "arguments": {},
        },
    )

    assert completed.returncode == 0
    assert len(completed.stdout.splitlines()) == 1
    response = json.loads(completed.stdout)
    assert response["protocol"] == "inventory-capability"
    assert response["protocol_version"] == "1.0"
    assert response["request_id"] == "request-1"
    assert response["ok"] is True
    assert response["result"]["executable_capabilities"] == [
        {"id": "catalog.open"},
        {"id": "asset.list"},
        {"id": "asset.get"},
        {"id": "stock.summary"},
    ]
    assert completed.stderr == ""


def test_cli_returns_typed_failure_without_traceback_or_extra_stdout(tmp_path) -> None:
    completed = _invoke(
        tmp_path,
        {
            "protocol": "inventory-capability",
            "protocol_version": "1.0",
            "request_id": "request-2",
            "capability": "asset.create",
            "arguments": {},
        },
    )

    assert completed.returncode == 0
    assert len(completed.stdout.splitlines()) == 1
    response = json.loads(completed.stdout)
    assert response["ok"] is False
    assert response["error"]["code"] == "capability_not_published"
    assert "Traceback" not in completed.stdout
    assert completed.stderr == ""


def test_cli_rejects_invalid_protocol_with_a_correlated_error(tmp_path) -> None:
    completed = _invoke(
        tmp_path,
        {
            "protocol": "grid-capability",
            "protocol_version": "1.0",
            "request_id": "request-3",
            "capability": "environment.describe",
            "arguments": {},
        },
    )

    assert completed.returncode == 0
    response = json.loads(completed.stdout)
    assert response["request_id"] == "request-3"
    assert response["ok"] is False
    assert response["error"]["code"] == "invalid_request"
