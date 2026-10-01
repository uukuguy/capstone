"""Bounded HTTP client for the public Capstone Thread contract."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx

from .thread_commands import ThreadCommandFactory
from .thread_catalog import ThreadCatalogProjection
from .thread_protocol import CommandReceipt, EventPage, ThreadProtocolError, ThreadSnapshot


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


def _decode(status_code: int, is_success: bool, content: bytes) -> Any:
    if len(content) > MAX_JSON_BYTES:
        raise ThreadHttpError(status_code, "Thread response exceeds the bounded JSON limit")
    try:
        body = json.loads(content)
    except (json.JSONDecodeError, ValueError) as error:
        raise ThreadHttpError(status_code, "Thread response is not JSON") from error
    if not is_success:
        raise ThreadHttpError(status_code, f"Thread request failed ({status_code})", body)
    return body


@dataclass
class HttpThreadSession:
    """Synchronous typed HTTP session suitable for TUI worker polling."""

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
        if json_body is not None:
            try:
                request_size = len(json.dumps(json_body, ensure_ascii=False, allow_nan=False).encode())
            except (TypeError, ValueError) as error:
                raise ThreadHttpError(400, "Thread request JSON is invalid") from error
            if request_size > MAX_JSON_BYTES:
                raise ThreadHttpError(413, "Thread request exceeds the bounded JSON limit")
        with self.client.stream(method, f"{self.api_origin}{path}", headers=headers, json=json_body, **kwargs) as response:
            content = bytearray()
            for chunk in response.iter_bytes():
                content.extend(chunk)
                if len(content) > MAX_JSON_BYTES:
                    raise ThreadHttpError(response.status_code, "Thread response exceeds the bounded JSON limit")
            return _decode(response.status_code, response.is_success, bytes(content))

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
        if self.run_id is not None and snapshot.run.run_id != self.run_id:
            raise RuntimeError("snapshot run identity does not match session")
        self.run_id = snapshot.run.run_id
        return snapshot

    def catalog(self) -> ThreadCatalogProjection:
        thread_id, _ = self._require_identity()
        return ThreadCatalogProjection.from_document(self._request("GET", f"/api/v1/threads/{thread_id}/catalog"))

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
                if self.run_id is not None and snapshot.run.run_id != self.run_id:
                    raise ThreadHttpError(409, "resync snapshot run identity does not match session", error.body)
                self.run_id = snapshot.run.run_id
                raise ThreadResyncRequired(snapshot) from error
            raise
        page = EventPage.from_document(document, expected_after_seq=after)
        if page.thread_id != thread_id:
            raise RuntimeError("event page thread identity does not match session")
        if self.run_id is not None and any(event.run_id != self.run_id for event in page.events):
            raise RuntimeError("event page run identity does not match session")
        return page

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
        document = self._request("POST", f"/api/v1/threads/{thread_id}/commands", json_body=command, headers={"Idempotency-Key": idempotency_key})
        receipt = CommandReceipt.from_document(document)
        if receipt.command_id != command_id or receipt.idempotency_key != idempotency_key or receipt.thread_id != thread_id or receipt.run_id != run_id:
            raise RuntimeError("receipt identity does not match command")
        return receipt


__all__ = ["HttpThreadSession", "ThreadHttpError", "ThreadResyncRequired"]
