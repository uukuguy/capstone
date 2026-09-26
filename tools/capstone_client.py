#!/usr/bin/env python3
"""Local unified client for explicitly registered Capstone applications.

The client routes one ordered instruction request to a trusted application
worker. Its process boundary keeps the pandapower and PyPSA environments apart.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any


REQUEST_SCHEMA = "capstone-client-request/1.0"
RESULT_SCHEMA = "capstone-client-result/1.0"
PANDAPOWER_APPLICATION = "pandapower-static-analysis"
PYPSA_APPLICATION = "pypsa-business-cases"
APPLICATIONS = (PANDAPOWER_APPLICATION, PYPSA_APPLICATION)
PANDAPOWER_DEMOS = frozenset({"pandapower-scripted-task", "pandapower-scripted-test"})
_SCRIPTED_ENV_NAMES = frozenset({
    "PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE",
    "UV_CACHE_DIR", "CAPSTONE_PYPSA_MODEL_LIBRARY_DIR",
})


def _emit_progress(event: str, application_id: str, **details: object) -> None:
    try:
        print(json.dumps({
            "schema": "capstone-client-progress/1.0", "event": event,
            "application_id": application_id, **details,
        }, ensure_ascii=False), file=sys.stderr, flush=True)
    except OSError:
        pass


def run_request(
    request: Mapping[str, object], *, repo_root: Path,
    runner: Callable[..., Any] = subprocess.run,
    environment: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Run one registered application without exposing a command selector."""

    application_id, mode, instructions, case_id, provider, model = _validate_request(request)
    root = Path(repo_root).resolve()
    source_environment = dict(os.environ if environment is None else environment)
    worker_environment = (
        source_environment if mode == "provider"
        else {name: value for name, value in source_environment.items() if name in _SCRIPTED_ENV_NAMES}
    )
    _emit_progress("started", application_id, total_instructions=len(instructions),
                   message=f"已开始运行 {application_id}，共 {len(instructions)} 条指令")
    with tempfile.TemporaryDirectory(prefix="capstone-instructions-") as directory:
        instruction_path = Path(directory) / "instructions.txt"
        instruction_path.write_text("\n".join(instructions) + "\n", encoding="utf-8")
        command = _command(application_id, mode, instruction_path, case_id, provider, model)
        completed = runner(
            command, cwd=root, env=worker_environment, text=True,
            stdout=subprocess.PIPE, stderr=sys.stderr, timeout=900,
        )
    if completed.returncode != 0:
        _emit_progress("failed", application_id, message="应用运行失败")
        raise RuntimeError("registered application worker failed")
    try:
        payload = json.loads(completed.stdout)
    except (TypeError, ValueError):
        raise RuntimeError("registered application worker returned invalid JSON") from None
    if not isinstance(payload, dict):
        raise RuntimeError("registered application worker returned an invalid result")
    if application_id == PANDAPOWER_APPLICATION:
        if payload.get("schema") != "capability-agent-output/1.0":
            raise RuntimeError("pandapower application returned the wrong output contract")
        core = payload.get("core")
        if not isinstance(core, dict) or core.get("application_id") != application_id:
            raise RuntimeError("pandapower application identity is invalid")
        answer_refs = core.get("answer_refs")
        if not isinstance(answer_refs, list) or len(answer_refs) != len(instructions):
            raise RuntimeError("pandapower application result does not match its request")
        run_id, status = core.get("run_id"), core.get("status")
    else:
        if payload.get("schema") != "capstone-pypsa-case-presentation/1.0":
            raise RuntimeError("PyPSA application returned the wrong output contract")
        turns = payload.get("turns")
        if payload.get("case_id") != case_id or not isinstance(turns, list) or len(turns) != len(instructions):
            raise RuntimeError("PyPSA application result does not match its request")
        run_id, status = payload.get("run_id"), payload.get("status")
    if not isinstance(run_id, str) or not run_id or status != "completed":
        raise RuntimeError("registered application run did not complete")
    _emit_progress("completed", application_id, run_id=run_id, message="运行完成")
    return {
        "schema": RESULT_SCHEMA, "application_id": application_id,
        "run_id": run_id, "status": status, "result": payload,
    }


def _validate_request(
    request: Mapping[str, object],
) -> tuple[str, str, tuple[str, ...], str | None, str | None, str | None]:
    if not isinstance(request, Mapping) or request.get("schema") != REQUEST_SCHEMA:
        raise ValueError("client request schema is invalid")
    if set(request) - {"schema", "application_id", "mode", "case_id", "instructions", "provider", "model"}:
        raise ValueError("client request has unknown fields")
    application_id = request.get("application_id")
    if application_id not in APPLICATIONS:
        raise ValueError("application is not registered")
    mode = request.get("mode", (
        "provider" if application_id == PANDAPOWER_APPLICATION else "scripted-demo"
    ))
    if mode not in {"provider", "scripted-demo"}:
        raise ValueError("application mode is invalid")
    values = request.get("instructions")
    if not isinstance(values, list) or not values or any(
        not isinstance(value, str) or not value.strip() or "\n" in value or "\r" in value
        for value in values
    ):
        raise ValueError("instructions must be a nonempty ordered list of single-line text")
    instructions = tuple(values)
    case_id, provider, model = (request.get(name) for name in ("case_id", "provider", "model"))
    if application_id == PANDAPOWER_APPLICATION:
        if mode == "provider" and case_id is not None:
            raise ValueError("pandapower Provider application does not use a case ID")
        if mode == "scripted-demo" and (
            case_id not in PANDAPOWER_DEMOS or provider is not None or model is not None
        ):
            raise ValueError("pandapower scripted demo requires a registered case and no Provider options")
    else:
        if (mode != "scripted-demo" or not isinstance(case_id, str) or not case_id
                or provider is not None or model is not None):
            raise ValueError("PyPSA case route requires a case ID and no Provider options")
    for value in (provider, model):
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError("Provider and model options must be nonempty text")
    return application_id, mode, instructions, case_id, provider, model


def _command(
    application_id: str, mode: str, instruction_path: Path,
    case_id: str | None, provider: str | None, model: str | None,
) -> list[str]:
    if application_id == PANDAPOWER_APPLICATION and mode == "provider":
        command = [
            "uv", "run", "--project", "packages/grid-agent", "grid-agent",
            "analysis-generic", "--application", application_id,
            "--instructions", str(instruction_path),
        ]
        if provider is not None:
            command.extend(("--provider", provider))
        if model is not None:
            command.extend(("--model", model))
        return command
    if application_id == PANDAPOWER_APPLICATION:
        assert case_id is not None
        return [
            "uv", "run", "--project", "packages/grid-agent", "python",
            "tools/pandapower_scripted_demo.py", "--case", case_id,
            "--instructions", str(instruction_path),
        ]
    assert case_id is not None
    return [
        "uv", "run", "--project", "packages/pypsa-power-operations-domain-pack",
        "python", "validation/pypsa_cases.py", "run", case_id,
        "--instructions", str(instruction_path),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        request = json.loads(args.request.read_text(encoding="utf-8"))
        result = run_request(request, repo_root=args.repo_root)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"Capstone client error: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
