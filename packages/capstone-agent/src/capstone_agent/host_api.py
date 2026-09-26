"""Authenticated, stateless HTTP and SSE adapter over the durable ledger."""

from __future__ import annotations

import asyncio
import hmac
import json
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated
from collections.abc import Callable

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from capstone_agent.artifacts import ArtifactService
from capstone_agent.catalog import build_catalog
from capstone_agent.case_diagrams import CaseDiagramCache, load_case_diagram
from capstone_agent.ledger import Conflict, Ledger, SessionRecord
from capstone_agent.server import _CreateSession, _TurnInput
from capstone_agent.session import WorkerRegistry, WorkerSession, WorkerSpec


def _status(record: SessionRecord) -> dict[str, object]:
    return {
        "session_id": record.session_id, "run_id": record.run_id,
        "application_id": record.application_id, "state": record.state,
        "error_code": record.error_code,
        "accepted_turns": record.accepted_turns,
        "completed_turns": record.completed_turns,
    }


def create_host_app(
    ledger: Ledger, registry: WorkerRegistry, *, operator_token: str,
    allowed_hosts: set[str], allowed_origins: set[str],
    repo_root: Path | None = None,
    artifacts: ArtifactService | None = None,
    preview_loader: Callable[[WorkerSpec, str], dict[str, object]] | None = None,
) -> FastAPI:
    if len(operator_token) < 8 or not allowed_hosts or not allowed_origins:
        raise ValueError("host access configuration is invalid")
    catalog = build_catalog(registry, repo_root or Path(__file__).resolve().parents[4])
    diagram_cases = {
        (application["application_id"], case["case_id"]): registry.resolve(application["application_id"])
        for application in catalog["applications"] for case in application["cases"]
        if preview_loader is not None or registry.resolve(application["application_id"]).preview_command
    }
    diagrams = CaseDiagramCache(diagram_cases, preview_loader or load_case_diagram)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        diagrams.prewarm()
        try:
            yield
        finally:
            diagrams.close()

    app = FastAPI(title="capstone-agent", docs_url=None, redoc_url=None,
                  openapi_url=None, lifespan=lifespan)

    @app.middleware("http")
    async def access(request: Request, call_next):
        if request.url.path != "/health/ready" and request.url.hostname not in allowed_hosts:
            return JSONResponse({"error": "invalid_host"}, status_code=400)
        origin = request.headers.get("origin")
        if origin is not None and origin not in allowed_origins:
            return JSONResponse({"error": "invalid_origin"}, status_code=403)
        if request.method == "OPTIONS" and origin is not None:
            response = Response(status_code=204)
        elif request.url.path == "/health/ready":
            response = await call_next(request)
        else:
            expected = "Bearer " + operator_token
            if not hmac.compare_digest(request.headers.get("authorization", ""), expected):
                response = JSONResponse({"error": "unauthorized"}, status_code=401)
            else:
                response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        if origin is not None:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = (
                "Authorization, Content-Type, Idempotency-Key"
            )
        return response

    def get_session(session_id: str) -> SessionRecord:
        record = ledger.get_session(session_id)
        if record is None:
            raise HTTPException(404, "session not found")
        return record

    @app.get("/health/ready")
    def health_ready():
        try:
            if ledger.ping():
                return {"status": "ready"}
        except Exception:
            pass
        raise HTTPException(503, "database unavailable")

    @app.get("/api/v1/catalog")
    def get_catalog():
        return catalog

    @app.get("/api/v1/cases/{application_id}/{case_id}/diagram")
    def get_case_diagram(application_id: str, case_id: str):
        try:
            return diagrams.get(application_id, case_id)
        except KeyError:
            raise HTTPException(404, "case diagram is not registered") from None
        except Exception:
            raise HTTPException(503, "case diagram is unavailable") from None

    @app.post("/api/v1/sessions", status_code=201)
    def create_session(values: _CreateSession):
        try:
            spec = registry.resolve(values.application_id)
        except ValueError:
            raise HTTPException(404, "application is not registered") from None
        try:
            WorkerSession(spec, mode=values.mode, case_id=values.case_id,
                          provider=values.provider, model=values.model)
        except ValueError:
            raise HTTPException(422, "application mode or case is invalid") from None
        record = ledger.create_session(values.application_id, values.mode, values.case_id,
                                       values.provider, values.model)
        return {"session_id": record.session_id, "run_id": None,
                "application_id": record.application_id, "state": "pending"}

    @app.post("/api/v1/sessions/{session_id}/turns", status_code=202)
    def submit_turn(session_id: str, values: _TurnInput,
                    idempotency_key: Annotated[str | None, Header(max_length=200)] = None):
        try:
            command = ledger.accept_turn(session_id, values.instruction,
                                         idempotency_key or secrets.token_urlsafe(24))
        except KeyError:
            raise HTTPException(404, "session not found") from None
        except Conflict:
            raise HTTPException(409, "session cannot accept a turn") from None
        return {"session_id": session_id, "ordinal": command.ordinal, "state": "accepted"}

    @app.post("/api/v1/sessions/{session_id}/close", status_code=202)
    def close_session(session_id: str,
                      idempotency_key: Annotated[str | None, Header(max_length=200)] = None):
        try:
            ledger.accept_close(session_id, idempotency_key or secrets.token_urlsafe(24))
        except KeyError:
            raise HTTPException(404, "session not found") from None
        except Conflict:
            raise HTTPException(409, "session cannot close") from None
        return {"session_id": session_id, "state": "closing"}

    @app.get("/api/v1/sessions/{session_id}")
    def session_status(session_id: str):
        return _status(get_session(session_id))

    @app.get("/api/v1/sessions/{session_id}/turns/{ordinal}")
    def get_turn(session_id: str, ordinal: int):
        get_session(session_id)
        for event in ledger.events_after(session_id, 0):
            if event.kind == "answer_committed" and event.payload.get("ordinal") == ordinal:
                return event.payload
        raise HTTPException(404, "turn answer not found")

    @app.get("/api/v1/sessions/{session_id}/result")
    def get_result(session_id: str):
        get_session(session_id)
        for event in ledger.events_after(session_id, 0):
            if event.kind == "completed":
                return event.payload["result"]
        raise HTTPException(409, "session has no final result")

    @app.get("/api/v1/sessions/{session_id}/network")
    def get_network(session_id: str, ordinal: Annotated[int, Query(ge=1, le=3)]):
        record = get_session(session_id)
        if record.completed_turns < ordinal:
            raise HTTPException(404, "network view not found")
        from capstone_agent.network_diagram import (
            normalize_network_diagram, normalize_network_layer,
        )

        diagrams: dict[str, dict[str, object]] = {}
        admitted: dict[int, tuple[str, ...]] = {}
        for event in ledger.events_after(session_id, 0):
            if event.kind == "answer_committed":
                step = event.payload.get("ordinal")
                refs = event.payload.get("result_refs")
                if type(step) is int and isinstance(refs, list):
                    admitted[step] = tuple(ref for ref in refs if isinstance(ref, str))
            if event.kind == "network_diagram":
                try:
                    diagram = normalize_network_diagram(event.payload.get("diagram"))
                except ValueError:
                    continue
                diagrams[diagram["ref"]] = diagram
            if event.kind == "network_layer" and event.payload.get("ordinal") == ordinal:
                raw = event.payload.get("layer")
                if not isinstance(raw, dict):
                    continue
                diagram = diagrams.get(raw.get("diagram_ref"))
                if diagram is None:
                    continue
                try:
                    layer = normalize_network_layer(
                        raw, diagram, ordinal, admitted_refs=admitted.get(ordinal, ()),
                    )
                except ValueError:
                    continue
                return {"schema": "capstone-network-view/2.0", "ordinal": ordinal,
                        "diagram": diagram, "layer": layer}
            if event.kind == "network_view" and event.payload.get("ordinal") == ordinal:
                return event.payload["view"]
        raise HTTPException(404, "network view not found")

    @app.get("/api/v1/sessions/{session_id}/report")
    def get_report(session_id: str):
        get_session(session_id)
        if artifacts is None:
            raise HTTPException(404, "report not found")
        try:
            report = artifacts.read_report(session_id)
        except (OSError, ValueError, KeyError):
            raise HTTPException(502, "report is unavailable") from None
        if report is None:
            raise HTTPException(404, "report not found")
        return Response(report, media_type="text/markdown; charset=utf-8")

    @app.get("/api/v1/sessions/{session_id}/evidence")
    def get_evidence(session_id: str,
                     ref: Annotated[str, Query(min_length=1, max_length=2048)]):
        get_session(session_id)
        if artifacts is None:
            raise HTTPException(404, "evidence reference not found")
        try:
            value = artifacts.read_evidence(session_id, ref)
        except (OSError, ValueError, KeyError):
            raise HTTPException(502, "evidence is unavailable") from None
        if value is None:
            raise HTTPException(404, "evidence reference not found")
        return value

    @app.get("/api/v1/sessions/{session_id}/events")
    async def stream_events(session_id: str, after: Annotated[int, Query(ge=0)] = 0):
        get_session(session_id)

        async def events():
            cursor = after
            last_heartbeat = asyncio.get_running_loop().time()
            while True:
                rows = await asyncio.to_thread(ledger.events_after, session_id, cursor)
                for event in rows:
                    cursor = event.sequence
                    data = json.dumps({
                        "schema": "capstone-session-event/1.0",
                        "session_id": session_id, "sequence": cursor,
                        "event": event.kind, "payload": event.payload,
                    }, ensure_ascii=False)
                    yield f"id: {cursor}\nevent: {event.kind}\ndata: {data}\n\n"
                    if event.kind in {"completed", "failed"}:
                        return
                current = await asyncio.to_thread(ledger.get_session, session_id)
                if current is None or current.state in {"completed", "failed", "interrupted"}:
                    return
                now = asyncio.get_running_loop().time()
                if now - last_heartbeat >= 15:
                    yield ": keepalive\n\n"
                    last_heartbeat = now
                await asyncio.sleep(0.25)

        return StreamingResponse(events(), media_type="text/event-stream")

    return app
