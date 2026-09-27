"""Private, best-effort wake signal for a sleeping hosted worker."""

from __future__ import annotations

import hashlib
import hmac
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import FastAPI, Header, HTTPException


def wake_token(operator_token: str) -> str:
    return hmac.new(operator_token.encode(), b"capstone-worker-wake-v1",
                    hashlib.sha256).hexdigest()


def create_wake_app(wake_event: threading.Event, operator_token: str) -> FastAPI:
    app = FastAPI(title="capstone-worker-wake", docs_url=None, redoc_url=None,
                  openapi_url=None)
    expected = "Bearer " + wake_token(operator_token)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ready"}

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
