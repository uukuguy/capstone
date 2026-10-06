"""Bound live Thread subscriptions and release capacity on every exit."""
from __future__ import annotations

from threading import Lock
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class ThreadStreamBudget:
    def __init__(self, app: ASGIApp, *, max_streams: int = 32, per_thread: int = 2):
        if not 1 <= per_thread <= max_streams <= 1024:
            raise ValueError('Thread stream limits are invalid')
        self.app, self.max_streams, self.per_thread = app, max_streams, per_thread
        self._counts: dict[str, int] = {}
        self._active = 0
        self._lock = Lock()

    @property
    def active_count(self) -> int:
        with self._lock:
            return self._active

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        parts = scope.get('path', '').split('/')
        if scope['type'] != 'http' or len(parts) != 7 or parts[1:4] != ['api', 'v1', 'threads'] or parts[5:] != ['events', 'stream']:
            await self.app(scope, receive, send)
            return
        thread_id = parts[4]
        with self._lock:
            admitted = self._active < self.max_streams and self._counts.get(thread_id, 0) < self.per_thread
            if admitted:
                self._active += 1
                self._counts[thread_id] = self._counts.get(thread_id, 0) + 1
        if not admitted:
            await JSONResponse({'detail': 'Conversation connections are busy. Retry shortly.'},
                               status_code=503, headers={'Retry-After': '2'})(scope, receive, send)
            return
        try:
            await self.app(scope, receive, send)
        finally:
            with self._lock:
                self._active -= 1
                remaining = self._counts[thread_id] - 1
                if remaining:
                    self._counts[thread_id] = remaining
                else:
                    del self._counts[thread_id]
