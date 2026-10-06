"""Private, best-effort wake signal for a sleeping hosted worker."""

from __future__ import annotations

import hashlib
import hmac
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from collections.abc import Callable

from fastapi import FastAPI, Header, HTTPException


def wake_token(operator_token: str) -> str:
    return hmac.new(operator_token.encode(), b"capstone-worker-wake-v1",
                    hashlib.sha256).hexdigest()


def create_wake_app(
    wake_event: threading.Event, operator_token: str,
    *, health_check: Callable[[], bool] | None = None,
    runtime_mode: str = "normal", implementation_family: str | None = None,
    resource_status: Callable[[], dict[str, int]] | None = None,
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
        wake_event.set()

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
