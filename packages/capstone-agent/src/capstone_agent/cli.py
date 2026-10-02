"""Headless, interactive, and local-service entry points for Capstone."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import time
from pathlib import Path
from typing import Any, TextIO

from capstone_agent.registry import build_registry
from capstone_agent.progress import summarize_answer
from capstone_agent.server import create_app
from capstone_agent.case_service import CaseExecutionService
from capstone_agent.session import WorkerRegistry, WorkerSession
from capstone_agent.thread_application import ThreadApplicationAssembly
from capstone_agent.thread_service import ThreadCreator, ThreadModelCatalog
from capstone_agent.thread_worker import RuntimeFactory, serve_thread_attempts


REQUEST_SCHEMA = "capstone-client-request/1.0"
RESULT_SCHEMA = "capstone-client-result/1.0"
_REQUEST_FIELDS = frozenset({
    "schema", "application_id", "mode", "case_id", "instructions", "provider", "model",
})


def _request(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
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


def _run(request_path: Path, registry: WorkerRegistry, output: TextIO, errors: TextIO) -> None:
    values = _request(request_path)
    application_id = values["application_id"]
    spec = registry.resolve(application_id)
    started_at = time.monotonic()
    with WorkerSession(
        spec, mode=values.get("mode", "provider"),
        case_id=values.get("case_id"), provider=values.get("provider"),
        model=values.get("model"),
        on_event=lambda event: _print_progress(event, errors, started_at),
    ) as session:
        print(f"Capstone run {session.run_id} started", file=errors, flush=True)
        for ordinal, instruction in enumerate(values["instructions"], start=1):
            print(f"开始第 {ordinal} 步：{instruction}", file=errors, flush=True)
            answer = session.submit_and_wait(instruction)
            print(
                f"Turn {ordinal}: {summarize_answer(answer.payload['answer_output'], has_references=bool(answer.payload.get('result_refs') or answer.payload.get('evidence_refs')))}",
                file=errors,
                flush=True,
            )
        completed = session.close()
        report_path = completed.payload.get("report_path")
        result = completed.payload["result"]
        if isinstance(result, str):
            result = json.loads(result)
        if output.isatty():
            print(f"运行完成：{session.run_id}（已完成 {len(values['instructions'])} 题）",
                  file=output, flush=True)
        else:
            print(json.dumps({
                "schema": RESULT_SCHEMA, "application_id": application_id,
                "run_id": session.run_id, "status": "completed", "result": result,
            }, ensure_ascii=False), file=output, flush=True)
        if isinstance(report_path, str) and report_path:
            print(f"报告文件：{report_path}", file=errors, flush=True)


def _chat(
    application_id: str, mode: str, case_id: str | None,
    provider: str | None, model: str | None, registry: WorkerRegistry,
    source: TextIO, output: TextIO, errors: TextIO,
) -> None:
    started_at = time.monotonic()
    with WorkerSession(
        registry.resolve(application_id), mode=mode, case_id=case_id,
        provider=provider, model=model,
        on_event=lambda event: _print_progress(event, errors, started_at),
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
            result_count = len(answer.payload.get("result_refs", []))
            evidence_count = len(answer.payload.get("evidence_refs", []))
            if result_count or evidence_count:
                print(f"引用：结果 {result_count} 项、证据 {evidence_count} 项；详见报告",
                      file=output, flush=True)
        completed = session.close()
        report_path = completed.payload.get("report_path")
        print(f"Capstone run {session.run_id} completed.", file=errors, flush=True)
        if isinstance(report_path, str) and report_path:
            print(f"报告文件：{report_path}", file=errors, flush=True)


def _print_progress(event: object, errors: TextIO, started_at: float) -> None:
    if getattr(event, "kind", None) != "progress":
        return
    payload = getattr(event, "payload", {})
    message = payload.get("message") if isinstance(payload, dict) else None
    if isinstance(message, str) and message:
        print(f"[{time.monotonic() - started_at:6.1f}s] {message}", file=errors, flush=True)


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


def _read_operator_token(path: Path) -> str:
    """Read an operator token from ignored local auth state without exposing it."""

    if path.is_symlink() or path.stat().st_mode & 0o077:
        raise ValueError("operator token file permissions are unsafe")
    token = path.read_text(encoding="utf-8").strip()
    if not token:
        raise ValueError("operator token file is empty")
    return token


def main(
    argv: list[str] | None = None, *, registry: WorkerRegistry | None = None,
    input_stream: TextIO | None = None, output_stream: TextIO | None = None,
    error_stream: TextIO | None = None,
    thread_catalog: ThreadModelCatalog | None = None,
    thread_runtime_factory: RuntimeFactory | None = None,
    thread_application: ThreadApplicationAssembly | None = None,
    thread_case_service: CaseExecutionService | None = None,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    headless = commands.add_parser("run", help="Execute an ordered JSON request")
    headless.add_argument("--request", type=Path, required=True)
    chat = commands.add_parser("chat", help="Submit turns in one interactive run")
    chat.add_argument("--application", required=True)
    chat.add_argument("--mode", choices=("provider", "scripted-demo"), default="provider")
    chat.add_argument("--case")
    chat.add_argument("--provider")
    chat.add_argument("--model")
    tui = commands.add_parser("tui", help="Open the Textual Thread workspace")
    tui.add_argument("--api-origin", default=os.environ.get("CAPSTONE_API_ORIGIN", "http://127.0.0.1:8767"))
    tui.add_argument("--operator-token-file", type=Path)
    tui.add_argument("--model-id")
    serve = commands.add_parser("serve", help="Start the local HTTP/SSE service")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8766)
    commands.add_parser("serve-hosted", help="Start the portable PostgreSQL-backed API")
    commands.add_parser("work-hosted", help="Run registered sessions from the command ledger")
    args = parser.parse_args(argv)
    selected_registry = registry or build_registry()
    source = input_stream or sys.stdin
    output = output_stream or sys.stdout
    errors = error_stream or sys.stderr
    try:
        if thread_application is not None:
            if thread_catalog is not None or thread_runtime_factory is not None:
                raise ValueError(
                    "thread_application cannot be combined with individual Thread bindings",
                )
            thread_catalog = thread_application.catalog
            thread_runtime_factory = thread_application.runtime_factory
            if thread_case_service is None:
                candidate = getattr(thread_application, "case_service", None)
                if isinstance(candidate, CaseExecutionService):
                    thread_case_service = candidate
        if args.command == "run":
            _run(args.request, selected_registry, output, errors)
        elif args.command == "chat":
            _chat(args.application, args.mode, args.case, args.provider, args.model,
                  selected_registry, source, output, errors)
        elif args.command == "tui":
            from capstone_agent.thread_http import HttpThreadSession
            from capstone_agent.thread_tui import run_tui_session

            root = Path(__file__).resolve().parents[4]
            token_path = args.operator_token_file or root / ".capstone-agent" / "auth" / "server.token"
            with HttpThreadSession(args.api_origin, _read_operator_token(token_path)) as session:
                snapshot = session.create(args.model_id)
                catalog = session.catalog()
                model_options = tuple(
                    (entry.model_id, entry.display_name)
                    for entry in catalog.models
                )
                active_model_id = snapshot.active_model_context.model_id
                if not any(model_id == active_model_id for model_id, _ in model_options):
                    model_options = (*model_options, (active_model_id, active_model_id))
                run_tui_session(
                    session,
                    model_options=model_options,
                )
        elif args.command == "serve":
            if args.host not in {"127.0.0.1", "localhost", "::1"}:
                raise ValueError("server must bind to loopback")
            import uvicorn

            root = Path(__file__).resolve().parents[4]
            token = _operator_token(root)
            print(f"Capstone local token: {root / '.capstone-agent/auth/server.token'}",
                  file=errors, flush=True)
            uvicorn.run(create_app(selected_registry, operator_token=token),
                        host=args.host, port=args.port, log_config=None, access_log=False)
        else:
            from capstone_agent.host_api import create_host_app
            from capstone_agent.host_worker import serve_forever
            from capstone_agent.hosting import build_artifacts, load_host_settings
            from capstone_agent.ledger import Ledger
            from capstone_agent.thread_service import PostgresThreadService
            from capstone_agent.worker_wake import WorkerWakeClient, create_wake_app

            settings = load_host_settings(os.environ)
            ledger = Ledger(settings.database_url)
            ledger.initialize()
            artifacts = build_artifacts(settings, ledger)
            thread_service = PostgresThreadService(settings.database_url)
            thread_service.initialize()
            if args.command == "serve-hosted":
                import uvicorn

                wake_worker = None
                if settings.worker_wake_url:
                    wake_worker = WorkerWakeClient(
                        settings.worker_wake_url, settings.operator_token,
                    ).wake

                app = create_host_app(
                    ledger, selected_registry, operator_token=settings.operator_token,
                    allowed_hosts=set(settings.allowed_hosts),
                    allowed_origins=set(settings.allowed_origins),
                    public_demo=settings.public_demo,
                    public_provider=settings.public_provider,
                    public_model=settings.public_model,
                    artifacts=artifacts,
                    wake_worker=wake_worker,
                    thread_service=thread_service,
                    thread_creator=(
                        thread_application.thread_creator(thread_service)
                        if thread_application is not None
                        else (
                            ThreadCreator(thread_service, thread_catalog)
                            if thread_catalog is not None else None
                        )
                    ),
                )
                uvicorn.run(app, host=settings.bind_host, port=settings.port,
                            log_config=None, access_log=False)
            else:
                thread_stop = None
                thread_scheduler = None
                if thread_runtime_factory is not None:
                    import threading

                    thread_stop = threading.Event()
                    thread_scheduler = threading.Thread(
                        target=serve_thread_attempts,
                        args=(thread_service, thread_runtime_factory),
                        kwargs={
                            "stop_event": thread_stop,
                            "case_service": thread_case_service,
                            "turn_router": (
                                thread_application.turn_router_for_worker()
                                if thread_application is not None else None
                            ),
                        },
                        name="capstone-thread-worker", daemon=True,
                    )
                    thread_scheduler.start()
                if settings.worker_wake_url:
                    import threading
                    import uvicorn

                    wake_event = threading.Event()
                    stop_event = threading.Event()
                    scheduler = threading.Thread(
                        target=serve_forever,
                        args=(ledger, selected_registry, artifacts),
                        kwargs={"idle_seconds": settings.session_idle_seconds,
                                "max_sessions": settings.worker_max_sessions,
                                "stop_event": stop_event, "wake_event": wake_event},
                        name="capstone-worker-scheduler", daemon=True,
                    )
                    scheduler.start()
                    try:
                        uvicorn.run(
                            create_wake_app(wake_event, settings.operator_token),
                            host=settings.bind_host, port=settings.port,
                            log_config=None, access_log=False,
                        )
                    finally:
                        stop_event.set()
                        wake_event.set()
                        scheduler.join(timeout=3)
                        if thread_stop is not None:
                            thread_stop.set()
                            if thread_scheduler is not None:
                                thread_scheduler.join(timeout=3)
                else:
                    try:
                        serve_forever(ledger, selected_registry, artifacts,
                                      idle_seconds=settings.session_idle_seconds,
                                      max_sessions=settings.worker_max_sessions)
                    finally:
                        if thread_stop is not None:
                            thread_stop.set()
                            if thread_scheduler is not None:
                                thread_scheduler.join(timeout=3)
    except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
        print(f"capstone-agent error: {type(exc).__name__}", file=errors, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
