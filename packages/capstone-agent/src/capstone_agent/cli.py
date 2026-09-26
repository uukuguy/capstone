"""Headless, interactive, and local-service entry points for Capstone."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from pathlib import Path
from typing import Any, TextIO

from capstone_agent.registry import build_registry
from capstone_agent.server import create_app
from capstone_agent.session import WorkerRegistry, WorkerSession


REQUEST_SCHEMA = "capstone-client-request/1.0"
RESULT_SCHEMA = "capstone-client-result/1.0"
_REQUEST_FIELDS = frozenset({
    "schema", "application_id", "mode", "case_id", "instructions", "provider", "model",
})


def _request(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    return _validate_request(document)


def _validate_request(document: object) -> dict[str, Any]:
    if not isinstance(document, dict) or document.get("schema") != REQUEST_SCHEMA or set(document) - _REQUEST_FIELDS:
        raise ValueError("client request schema is invalid")
    application_id = document.get("application_id")
    instructions = document.get("instructions")
    if not isinstance(application_id, str) or not application_id:
        raise ValueError("application ID is invalid")
    if not isinstance(instructions, list) or not instructions or any(
        not isinstance(value, str) or not value.strip() or "\n" in value or "\r" in value
        for value in instructions
    ):
        raise ValueError("instructions must be an ordered list of single-line text")
    return document


def _instruction_request(
    path: Path, application_id: str | None,
    provider: str | None, model: str | None,
) -> dict[str, Any]:
    instructions = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return _validate_request({
        "schema": REQUEST_SCHEMA,
        "application_id": application_id,
        "mode": "provider",
        "instructions": instructions,
        "provider": provider,
        "model": model,
    })


def _run(values: dict[str, Any], registry: WorkerRegistry, output: TextIO, errors: TextIO) -> None:
    application_id = values["application_id"]
    spec = registry.resolve(application_id)
    with WorkerSession(
        spec, mode=values.get("mode", "provider"),
        case_id=values.get("case_id"), provider=values.get("provider"),
        model=values.get("model"),
        on_event=lambda event: _print_progress(event, errors),
    ) as session:
        print(f"Capstone run {session.run_id} started", file=errors, flush=True)
        for ordinal, instruction in enumerate(values["instructions"], start=1):
            answer = session.submit_and_wait(instruction)
            print(f"Turn {ordinal}: {answer.payload['answer_output']}", file=errors, flush=True)
        completed = session.close()
        result = completed.payload["result"]
        if isinstance(result, str):
            result = json.loads(result)
        print(json.dumps({
            "schema": RESULT_SCHEMA, "application_id": application_id,
            "run_id": session.run_id, "status": "completed", "result": result,
        }, ensure_ascii=False), file=output, flush=True)


def _chat(
    application_id: str, mode: str, case_id: str | None,
    provider: str | None, model: str | None, registry: WorkerRegistry,
    source: TextIO, output: TextIO, errors: TextIO,
) -> None:
    with WorkerSession(
        registry.resolve(application_id), mode=mode, case_id=case_id,
        provider=provider, model=model,
        on_event=lambda event: _print_progress(event, errors),
    ) as session:
        print(f"Capstone session {session.run_id} ready; /exit ends this run.",
              file=errors, flush=True)
        while True:
            print("capstone> ", end="", file=errors, flush=True)
            instruction = source.readline()
            if not instruction or instruction.strip() == "/exit":
                break
            if not instruction.strip():
                continue
            answer = session.submit_and_wait(instruction.rstrip("\r\n"))
            print(answer.payload["answer_output"], file=output, flush=True)
            refs = [*answer.payload.get("result_refs", []),
                    *answer.payload.get("evidence_refs", [])]
            if refs:
                print("Evidence: " + ", ".join(refs), file=output, flush=True)
        session.close()
        print(f"Capstone run {session.run_id} completed.", file=errors, flush=True)


def _print_progress(event: object, errors: TextIO) -> None:
    if getattr(event, "kind", None) != "progress":
        return
    payload = getattr(event, "payload", {})
    message = payload.get("message") if isinstance(payload, dict) else None
    if isinstance(message, str) and message:
        print(message, file=errors, flush=True)


def _operator_token(root: Path) -> str:
    directory = root / ".capstone-agent" / "auth"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / "server.token"
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if path.is_symlink() or path.stat().st_mode & 0o077:
            raise ValueError("operator token file permissions are unsafe") from None
        return path.read_text(encoding="utf-8").strip()
    token = secrets.token_urlsafe(32)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(token + "\n")
    return token


def main(
    argv: list[str] | None = None, *, registry: WorkerRegistry | None = None,
    input_stream: TextIO | None = None, output_stream: TextIO | None = None,
    error_stream: TextIO | None = None,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    headless = commands.add_parser("run", help="Execute ordered instructions or a JSON request")
    headless_source = headless.add_mutually_exclusive_group(required=True)
    headless_source.add_argument("--request", type=Path)
    headless_source.add_argument("--instructions", type=Path)
    headless.add_argument("--application")
    headless.add_argument("--provider")
    headless.add_argument("--model")
    chat = commands.add_parser("chat", help="Submit turns in one interactive run")
    chat.add_argument("--application", required=True)
    chat.add_argument("--mode", choices=("provider", "scripted-demo"), default="provider")
    chat.add_argument("--case")
    chat.add_argument("--provider")
    chat.add_argument("--model")
    serve = commands.add_parser("serve", help="Start the local HTTP/SSE service")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8766)
    args = parser.parse_args(argv)
    selected_registry = registry or build_registry()
    source = input_stream or sys.stdin
    output = output_stream or sys.stdout
    errors = error_stream or sys.stderr
    try:
        if args.command == "run":
            if args.request is not None:
                if any(value is not None for value in (args.application, args.provider, args.model)):
                    raise ValueError("request file cannot be combined with application options")
                values = _request(args.request)
            else:
                values = _instruction_request(
                    args.instructions, args.application, args.provider, args.model,
                )
            _run(values, selected_registry, output, errors)
        elif args.command == "chat":
            _chat(args.application, args.mode, args.case, args.provider, args.model,
                  selected_registry, source, output, errors)
        else:
            if args.host not in {"127.0.0.1", "localhost", "::1"}:
                raise ValueError("server must bind to loopback")
            import uvicorn

            root = Path(__file__).resolve().parents[4]
            token = _operator_token(root)
            print(f"Capstone local token: {root / '.capstone-agent/auth/server.token'}",
                  file=errors, flush=True)
            uvicorn.run(create_app(selected_registry, operator_token=token),
                        host=args.host, port=args.port, log_config=None, access_log=False)
    except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
        print(f"capstone-agent error: {type(exc).__name__}", file=errors, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
