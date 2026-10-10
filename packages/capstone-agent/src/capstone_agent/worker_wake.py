"""Private, best-effort wake signal for a sleeping hosted worker."""

from __future__ import annotations

import hashlib
import hmac
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import FastAPI, Header, HTTPException


def wake_token(operator_token: str) -> str:
    return hmac.new(operator_token.encode(), b"capstone-worker-wake-v1",
                    hashlib.sha256).hexdigest()


def _configured_clients(legacy_origin: str | None, family_origins: str,
                        operator_token: str) -> list[tuple[str, WorkerWakeClient]]:
    origins = {legacy_origin: 'worker'} if legacy_origin else {}
    for entry in family_origins.split(','):
        if not entry.strip():
            continue
        family, separator, origin = entry.partition('=')
        if not separator or not family or not origin:
            raise ValueError('CAPSTONE_FAMILY_HEALTH_URLS is invalid')
        origins[origin] = 'worker:' + family
    clients = []
    for origin, component in origins.items():
        parsed = urlsplit(origin)
        if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password or parsed.path not in {'', '/'} or parsed.query or parsed.fragment:
            raise ValueError('worker origin configuration is invalid')
        clients.append((component, WorkerWakeClient(origin, operator_token)))
    return clients


def _wake_safely(client: WorkerWakeClient, *, attempts: int = 3) -> bool:
    try:
        return client.wake(attempts=attempts)
    except (OSError, TimeoutError):
        return False


def configured_worker_preparation(legacy_origin: str | None, family_origins: str, operator_token: str):
    """Stream actual startup checks; never publish private origins or tokens."""
    clients = _configured_clients(legacy_origin, family_origins, operator_token)
    def prepare():
        if not clients:
            return
        for component, _ in clients:
            yield {'component': component, 'status': 'preparing'}
        with ThreadPoolExecutor(max_workers=len(clients)) as pool:
            pending = {pool.submit(_wake_safely, client, attempts=12): component
                       for component, client in clients}
            for future in as_completed(pending):
                yield {'component': pending[future], 'status': 'ready' if future.result() else 'failed'}
    return prepare


def configured_worker_wake(legacy_origin: str | None, family_origins: str, operator_token: str) -> Callable[[], bool] | None:
    """Wake every worker selected by protected host configuration."""
    clients = _configured_clients(legacy_origin, family_origins, operator_token)
    if not clients:
        return None
    def wake_all() -> bool:
        results = []
        for _, client in clients:
            results.append(_wake_safely(client))
        return all(results)
    return wake_all


def create_wake_app(
    wake_event: threading.Event, operator_token: str,
    *, health_check: Callable[[], bool] | None = None,
    runtime_mode: str = "normal", implementation_family: str | None = None,
    resource_status: Callable[[], dict[str, int]] | None = None,
    additional_wake_events: tuple[threading.Event, ...] = (),
    input_catalog: Callable[[str], dict] | None = None,
    thread_family: Callable[[str], str] | None = None,
) -> FastAPI:
    if runtime_mode not in {"normal", "m11-provider-free"} or implementation_family not in {None, "pandapower", "pypsa"}:
        raise ValueError("worker runtime identity is invalid")
    app = FastAPI(title="capstone-worker-wake", docs_url=None, redoc_url=None,
                  openapi_url=None)
    expected = "Bearer " + wake_token(operator_token)

    @app.get("/health")
    def health() -> dict[str, object]:
        if health_check is not None and not health_check():
            raise HTTPException(503, "worker scheduler unavailable")
        document: dict[str, object] = {"status": "ready", "runtime_mode": runtime_mode}
        if implementation_family is not None:
            document["implementation_family"] = implementation_family
        if resource_status is not None:
            document['thread_contexts'] = resource_status()
        return document

    @app.post("/wake", status_code=204)
    def wake(authorization: str = Header(default="")) -> None:
        if not hmac.compare_digest(authorization, expected):
            raise HTTPException(401, "unauthorized")
        if health_check is not None and not health_check():
            raise HTTPException(503, "worker scheduler unavailable")
        wake_event.set()
        for event in additional_wake_events:
            event.set()

    @app.get('/threads/{thread_id}/input-resources')
    def resources(thread_id: str, authorization: str = Header(default='')):
        if not hmac.compare_digest(authorization, expected):
            raise HTTPException(401, 'unauthorized')
        if input_catalog is None:
            raise HTTPException(503, 'resource catalog unavailable')
        from .thread_service import ThreadNotFound
        try:
            if thread_family is not None and thread_family(thread_id) != implementation_family:
                raise HTTPException(409, 'thread family does not match worker')
            document = input_catalog(thread_id)
            if document.get('implementation_family') != implementation_family:
                raise HTTPException(409, 'thread family does not match worker')
            return document
        except ThreadNotFound:
            raise HTTPException(404, 'thread not found') from None

    return app


class WorkerWakeClient:
    def __init__(self, base_url: str, operator_token: str):
        self.url = base_url.rstrip("/") + "/wake"
        self.authorization = "Bearer " + wake_token(operator_token)

    def wake(self, *, attempts: int = 3, backoff_seconds: float = 0.5) -> bool:
        if attempts < 1 or backoff_seconds < 0:
            raise ValueError("wake retry settings are invalid")
        for attempt in range(attempts):
            request = Request(self.url, data=b"", method="POST",
                              headers={"Authorization": self.authorization})
            try:
                with urlopen(request, timeout=3) as response:
                    if response.status == 204:
                        return True
                    if response.status not in {502, 503, 504}:
                        return False
            except HTTPError as exc:
                if exc.code not in {502, 503, 504}:
                    return False
            except (URLError, TimeoutError, OSError):
                pass
            if attempt + 1 < attempts:
                time.sleep(backoff_seconds * (attempt + 1))
        return False
