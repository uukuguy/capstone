"""Task-bound Provider relay permits and whole-exchange cancellation."""
import asyncio
from dataclasses import dataclass, field
import math
import secrets
import socket
from threading import Event, RLock, Thread
import time

import httpx
from .bounded_http_loop import write_http


@dataclass(eq=False)
class RelayLease:
    task_id: str
    grant: str
    deadline: float
    downstream: socket.socket
    cancelled: Event = field(default_factory=Event)
    released: Event = field(default_factory=Event)
    loop: asyncio.AbstractEventLoop | None = None
    task: asyncio.Task | None = None

    def abort(self):
        self.cancelled.set()
        try:
            self.downstream.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        if self.loop is not None and self.task is not None:
            try:
                self.loop.call_soon_threadsafe(self.task.cancel)
            except RuntimeError:
                pass


class ProviderRelay:
    def __init__(self, *, max_requests=16, per_task=2):
        if max_requests < 1 or per_task < 1:
            raise ValueError('Provider relay limits are invalid')
        self.max_requests, self.per_task = max_requests, per_task
        self.grants: dict[str, str] = {}
        self.deadlines: dict[str, float] = {}
        self.active: set[RelayLease] = set()
        self.lock = RLock()

    def register(self, task_id, grant, deadline):
        if not grant or not math.isfinite(deadline) or deadline <= time.monotonic():
            raise ValueError('Provider relay grant is invalid')
        with self.lock:
            self.grants[task_id], self.deadlines[task_id] = grant, deadline

    def acquire(self, task_id, grant, downstream):
        with self.lock:
            accepted = self.grants.get(task_id)
            deadline = self.deadlines.get(task_id, 0)
            if not accepted or not secrets.compare_digest(accepted, grant) or deadline <= time.monotonic():
                raise PermissionError('Provider relay grant is unavailable')
            if (len(self.active) >= self.max_requests
                    or sum(item.task_id == task_id for item in self.active) >= self.per_task):
                raise RuntimeError('Provider relay capacity reached')
            lease = RelayLease(task_id, grant, deadline, downstream)
            self.active.add(lease)
        def watch():
            while not lease.released.wait(0.02):
                with self.lock:
                    valid = self.grants.get(task_id) == grant and time.monotonic() < deadline
                if not valid:
                    lease.abort()
                    break
        Thread(target=watch, daemon=True).start()
        return lease

    def release(self, lease):
        lease.released.set()
        with self.lock:
            self.active.discard(lease)

    def revoke(self, task_id):
        with self.lock:
            self.grants.pop(task_id, None)
            self.deadlines.pop(task_id, None)
            leases = [item for item in self.active if item.task_id == task_id]
        for lease in leases:
            lease.abort()


async def forward_provider(handler, lease: RelayLease, upstream: str, body: bytes, key: str):
    """Cancellation closes the httpx stream even while headers are incomplete."""
    lease.loop, lease.task = asyncio.get_running_loop(), asyncio.current_task()
    if lease.cancelled.is_set():
        raise asyncio.CancelledError()
    async with httpx.AsyncClient(timeout=None, trust_env=False) as client:
        async with client.stream('POST', upstream.rstrip('/') + '/chat/completions', content=body,
            headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key}) as response:
            if lease.cancelled.is_set():
                raise asyncio.CancelledError()
            def headers():
                handler.send_response(response.status_code)
                handler.send_header('Content-Type', response.headers.get('Content-Type', 'application/json'))
                handler.send_header('Connection', 'close')
                handler.end_headers()
                handler.close_connection = True
            await write_http(headers)
            total = 0
            async for chunk in response.aiter_bytes():
                if lease.cancelled.is_set() or time.monotonic() >= lease.deadline:
                    raise asyncio.CancelledError()
                total += len(chunk)
                if total > 4 * 1024 * 1024:
                    raise ValueError('Provider response exceeds bounds')
                def write(data=chunk):
                    handler.wfile.write(data)
                    handler.wfile.flush()
                await write_http(write)
