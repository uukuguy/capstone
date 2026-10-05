from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from fastapi.testclient import TestClient

from capstone_agent.worker_wake import WorkerWakeClient, create_wake_app, wake_token


def test_worker_health_reports_fixed_runtime_identity() -> None:
    with TestClient(create_wake_app(threading.Event(), "operator-secret",
                                   runtime_mode="m11-provider-free",
                                   implementation_family="pypsa")) as client:
        assert client.get("/health").json() == {
            "status": "ready", "runtime_mode": "m11-provider-free",
            "implementation_family": "pypsa",
        }


def test_private_wake_requires_derived_token() -> None:
    wake = threading.Event()
    with TestClient(create_wake_app(wake, "operator-secret")) as client:
        assert client.get("/health").status_code == 200
        assert client.post("/wake").status_code == 401
        assert client.post("/wake", headers={
            "Authorization": "Bearer operator-secret",
        }).status_code == 401
        assert not wake.is_set()
        assert client.post("/wake", headers={
            "Authorization": f"Bearer {wake_token('operator-secret')}",
        }).status_code == 204
        assert wake.is_set()


def test_wake_client_retries_transient_cold_start_response() -> None:
    class Handler(BaseHTTPRequestHandler):
        calls = 0

        def do_POST(self) -> None:
            assert self.path == "/wake"
            assert self.headers["Authorization"] == f"Bearer {wake_token('operator-secret')}"
            Handler.calls += 1
            self.send_response(502 if Handler.calls < 3 else 204)
            self.end_headers()

        def log_message(self, *_args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = WorkerWakeClient(f"http://127.0.0.1:{server.server_port}",
                                  "operator-secret")
        assert client.wake(attempts=3, backoff_seconds=0)
        assert Handler.calls == 3
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()
