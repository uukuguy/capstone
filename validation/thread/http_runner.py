"""Provider-free HTTP acceptance adapter for the public Thread protocol."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx

from capstone_agent.thread_commands import ThreadCommandFactory
from capstone_agent.thread_protocol import CommandReceipt, EventPage, ThreadProtocolError, ThreadSnapshot

from .catalog import ThreadCatalog


MAX_JSON_BYTES = 2 * 1024 * 1024 + 128 * 1024


class ThreadHttpError(RuntimeError):
    def __init__(self, status_code: int, message: str, body: object = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class ThreadResyncRequired(ThreadHttpError):
    def __init__(self, snapshot: ThreadSnapshot) -> None:
        super().__init__(409, "Thread event cursor requires a snapshot resync")
        self.snapshot = snapshot


def _origin(value: str) -> str:
    parsed = urlsplit(value.rstrip("/"))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        raise ValueError("api_origin is invalid")
    return value.rstrip("/")


def _decode(response: httpx.Response) -> Any:
    if len(response.content) > MAX_JSON_BYTES:
        raise ThreadHttpError(response.status_code, "Thread response exceeds the bounded JSON limit")
    try:
        body = response.json()
    except (json.JSONDecodeError, ValueError) as error:
        raise ThreadHttpError(response.status_code, "Thread response is not JSON") from error
    if not response.is_success:
        raise ThreadHttpError(response.status_code, f"Thread request failed ({response.status_code})", body)
    return body


@dataclass
class HttpThreadSession:
    api_origin: str
    operator_token: str
    client: httpx.Client | None = None
    thread_id: str | None = None
    run_id: str | None = None

    def __post_init__(self) -> None:
        self.api_origin = _origin(self.api_origin)
        if not isinstance(self.operator_token, str) or not self.operator_token:
            raise ValueError("operator_token is required")
        self._owned_client = self.client is None
        if self.client is None:
            self.client = httpx.Client(timeout=10.0)

    def close(self) -> None:
        if self._owned_client and self.client is not None:
            self.client.close()

    def __enter__(self) -> HttpThreadSession:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _request(self, method: str, path: str, *, json_body: object = None, **kwargs: Any) -> Any:
        assert self.client is not None
        headers = {"Authorization": f"Bearer {self.operator_token}"}
        if json_body is not None:
            headers["Content-Type"] = "application/json"
        extra_headers = kwargs.pop("headers", None)
        if extra_headers:
            headers.update(extra_headers)
        response = self.client.request(method, f"{self.api_origin}{path}", headers=headers, json=json_body, **kwargs)
        return _decode(response)

    def create(self, model_id: str | None = None) -> ThreadSnapshot:
        body = {} if model_id is None else {"model_id": model_id}
        snapshot = ThreadSnapshot.from_document(self._request("POST", "/api/v1/threads", json_body=body))
        self.thread_id, self.run_id = snapshot.thread_id, snapshot.run.run_id
        return snapshot

    def _require_identity(self) -> tuple[str, str | None]:
        if self.thread_id is None:
            raise RuntimeError("create() must be called before using the Thread session")
        return self.thread_id, self.run_id

    def snapshot(self) -> ThreadSnapshot:
        thread_id, _ = self._require_identity()
        snapshot = ThreadSnapshot.from_document(self._request("GET", f"/api/v1/threads/{thread_id}"))
        if snapshot.thread_id != thread_id:
            raise RuntimeError("snapshot identity does not match session")
        self.run_id = snapshot.run.run_id
        return snapshot

    def catalog(self) -> ThreadCatalog:
        thread_id, _ = self._require_identity()
        return ThreadCatalog.from_document(self._request("GET", f"/api/v1/threads/{thread_id}/catalog"))

    def events(self, *, after: int = 0) -> EventPage:
        thread_id, _ = self._require_identity()
        try:
            document = self._request("GET", f"/api/v1/threads/{thread_id}/events?after={after}")
        except ThreadHttpError as error:
            if error.status_code == 409 and isinstance(error.body, dict) and error.body.get("error") == "resync_required":
                try:
                    snapshot = ThreadSnapshot.from_document(error.body["snapshot"])
                except (KeyError, ThreadProtocolError) as parse_error:
                    raise ThreadHttpError(409, "resync response is malformed", error.body) from parse_error
                if snapshot.thread_id != thread_id:
                    raise ThreadHttpError(409, "resync snapshot identity does not match session", error.body)
                self.run_id = snapshot.run.run_id
                raise ThreadResyncRequired(snapshot) from error
            raise
        return EventPage.from_document(document, expected_after_seq=after)

    def command(
        self, kind: str, payload: dict[str, Any], *, expected_event_seq: int | None = None,
        command_id: str | None = None, idempotency_key: str | None = None,
    ) -> CommandReceipt:
        thread_id, run_id = self._require_identity()
        if expected_event_seq is None:
            expected_event_seq = self.snapshot().last_event_seq
        command_id = command_id or f"cmd_{uuid.uuid4().hex[:20]}"
        idempotency_key = idempotency_key or f"idem_{uuid.uuid4().hex[:20]}"
        factory = ThreadCommandFactory(thread_id, run_id)
        command = factory._command(kind, dict(payload), expected_event_seq=expected_event_seq, command_id=command_id, idempotency_key=idempotency_key)
        document = self._request(
            "POST", f"/api/v1/threads/{thread_id}/commands", json_body=command,
            headers={"Idempotency-Key": idempotency_key},
        )
        receipt = CommandReceipt.from_document(document)
        if receipt.command_id != command_id or receipt.idempotency_key != idempotency_key or receipt.thread_id != thread_id or receipt.run_id != run_id:
            raise RuntimeError("receipt identity does not match command")
        return receipt


def wait_for_terminal(session: HttpThreadSession, *, timeout_seconds: float = 30.0) -> ThreadSnapshot:
    deadline = time.monotonic() + timeout_seconds
    cursor = session.snapshot().last_event_seq
    while time.monotonic() < deadline:
        snapshot = session.snapshot()
        if snapshot.current_attempt is None:
            return snapshot
        page = session.events(after=cursor)
        cursor = page.next_event_seq
        time.sleep(0.05)
    raise TimeoutError("Thread attempt did not reach a terminal snapshot before timeout")


__all__ = ["HttpThreadSession", "ThreadHttpError", "ThreadResyncRequired", "wait_for_terminal"]
