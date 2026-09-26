"""Loopback HTTP and SSE adapter for neutral Capstone sessions."""

from __future__ import annotations

import asyncio
import hmac
import json
import threading
from contextlib import asynccontextmanager
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from capstone_agent.session import WorkerRegistry, WorkerSession


_LOOPBACK = frozenset({"localhost", "127.0.0.1", "::1"})


class _CreateSession(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    application_id: str = Field(min_length=1, max_length=100)
    mode: str = Field(pattern="^(provider|scripted-demo)$")
    case_id: str | None = Field(default=None, max_length=100)
    provider: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=200)


class _TurnInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    instruction: str = Field(min_length=1, max_length=32_000)


class _SessionManager:
    def __init__(self, registry: WorkerRegistry, max_sessions: int) -> None:
        self.registry = registry
        self.max_sessions = max_sessions
        self._sessions: dict[str, WorkerSession] = {}
        self._lock = threading.RLock()
        self._starting = 0

    def create(self, values: _CreateSession) -> WorkerSession:
        try:
            spec = self.registry.resolve(values.application_id)
        except ValueError:
            raise HTTPException(404, "application is not registered") from None
        try:
            session = WorkerSession(
                spec, mode=values.mode, case_id=values.case_id,
                provider=values.provider, model=values.model,
            )
        except ValueError:
            raise HTTPException(422, "application mode or case is invalid") from None
        with self._lock:
            if len(self._sessions) + self._starting >= self.max_sessions:
                raise HTTPException(429, "session capacity reached")
            self._starting += 1
        try:
            session.__enter__()
        except Exception:
            raise HTTPException(502, "application worker could not start") from None
        finally:
            with self._lock:
                self._starting -= 1
                if session.run_id is not None:
                    self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> WorkerSession:
        with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            raise HTTPException(404, "session not found")
        return session

    def shutdown(self) -> None:
        with self._lock:
            sessions = tuple(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            try:
                session.__exit__(None, None, None)
            except Exception:
                pass


def create_app(registry: WorkerRegistry, *, operator_token: str,
               max_sessions: int = 32) -> FastAPI:
    """Create a local authenticated service without importing Domain Packs."""

    if not isinstance(operator_token, str) or len(operator_token) < 8:
        raise ValueError("operator token is invalid")
    if max_sessions < 1:
        raise ValueError("session capacity is invalid")
    manager = _SessionManager(registry, max_sessions)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        manager.shutdown()

    app = FastAPI(title="capstone-agent", docs_url=None, redoc_url=None,
                  openapi_url=None, lifespan=lifespan)

    @app.middleware("http")
    async def local_access(request: Request, call_next):
        host = request.url.hostname
        if host not in _LOOPBACK:
            return JSONResponse({"error": "invalid_host"}, status_code=400)
        origin = request.headers.get("origin")
        if origin is not None:
            parsed = urlsplit(origin)
            if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != request.headers.get("host", "").lower():
                return JSONResponse({"error": "invalid_origin"}, status_code=403)
        authorization = request.headers.get("authorization", "")
        expected = "Bearer " + operator_token
        if not hmac.compare_digest(authorization, expected):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.post("/api/v1/sessions", status_code=201)
    def create_session(values: _CreateSession):
        session = manager.create(values)
        return {"session_id": session.session_id, "run_id": session.run_id,
                "application_id": values.application_id, "state": "ready"}

    @app.post("/api/v1/sessions/{session_id}/turns", status_code=202)
    def submit_turn(session_id: str, values: _TurnInput):
        session = manager.get(session_id)
        try:
            ordinal = session.submit(values.instruction)
        except ValueError:
            raise HTTPException(422, "instruction is invalid") from None
        except RuntimeError:
            raise HTTPException(409, "session cannot accept a turn") from None
        return {"session_id": session_id, "ordinal": ordinal, "state": "accepted"}

    @app.post("/api/v1/sessions/{session_id}/close", status_code=202)
    def close_session(session_id: str):
        session = manager.get(session_id)
        try:
            session.request_close()
        except RuntimeError:
            raise HTTPException(409, "session cannot close") from None
        return {"session_id": session_id, "state": "closing"}

    @app.get("/api/v1/sessions/{session_id}")
    def session_status(session_id: str):
        session = manager.get(session_id)
        events = session.events
        kinds = {event.kind for event in events}
        state = ("completed" if "completed" in kinds else
                 "failed" if session.failure_code is not None else
                 "closing" if session.closed else
                 "executing" if session.busy else "ready")
        return {"session_id": session_id, "run_id": session.run_id,
                "application_id": session.spec.application_id, "state": state,
                "error_code": session.failure_code,
                "accepted_turns": session.accepted,
                "completed_turns": sum(event.kind == "answer_committed" for event in events)}

    @app.get("/api/v1/sessions/{session_id}/turns/{ordinal}")
    def get_turn(session_id: str, ordinal: int):
        session = manager.get(session_id)
        for event in session.events:
            if event.kind == "answer_committed" and event.payload.get("ordinal") == ordinal:
                return event.payload
        raise HTTPException(404, "turn answer not found")

    @app.get("/api/v1/sessions/{session_id}/result")
    def get_result(session_id: str):
        session = manager.get(session_id)
        for event in session.events:
            if event.kind == "completed":
                return event.payload["result"]
        raise HTTPException(409, "session has no final result")

    @app.get("/api/v1/sessions/{session_id}/evidence")
    def get_evidence(session_id: str, ref: Annotated[str, Query(min_length=1, max_length=2048)]):
        session = manager.get(session_id)
        try:
            value = session.read_evidence(ref)
        except (RuntimeError, TimeoutError):
            raise HTTPException(502, "evidence worker is unavailable") from None
        if value is None:
            raise HTTPException(404, "evidence reference not found")
        return value

    @app.get("/api/v1/sessions/{session_id}/events")
    async def stream_events(session_id: str, after: Annotated[int, Query(ge=0)] = 0):
        session = manager.get(session_id)

        async def events():
            cursor = after
            while True:
                try:
                    event = await asyncio.to_thread(session.next_event, after=cursor, timeout=15.0)
                except RuntimeError:
                    return
                if event is None:
                    yield ": keepalive\n\n"
                    continue
                cursor = event.sequence
                data = json.dumps({"schema": "capstone-session-event/1.0",
                                   "session_id": session_id, "sequence": cursor,
                                   "event": event.kind, "payload": event.payload}, ensure_ascii=False)
                yield f"id: {cursor}\nevent: {event.kind}\ndata: {data}\n\n"
                if event.kind in {"completed", "failed"}:
                    return

        return StreamingResponse(events(), media_type="text/event-stream")

    return app
