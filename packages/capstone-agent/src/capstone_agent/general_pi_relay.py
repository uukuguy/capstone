"""Task-bound Provider relay permits and whole-exchange cancellation."""
import asyncio
from dataclasses import dataclass, field
import math
import json
import logging
import secrets
import socket
from threading import Event, RLock, Thread
import time

import httpx
from .bounded_http_loop import write_http

_LOG = logging.getLogger(__name__)


def model_transport_timeout(policy=None):
    """Network silence budget; progressing streams retain the task deadline."""
    if policy is None:
        from pathlib import Path
        candidates = [Path('/opt/general/config/model-transport.json')]
        candidates.extend(root / 'configs/runtime/general-pi/model-transport.json'
                          for root in Path(__file__).resolve().parents)
        path = next((path for path in candidates if path.is_file()), None)
        if path is None:
            raise ValueError('Model transport policy is not installed')
        policy = json.loads(path.read_text())
    fields = {'connect_seconds', 'read_idle_seconds', 'write_seconds', 'pool_seconds'}
    if (not isinstance(policy, dict) or set(policy) != fields | {'schema'}
            or policy['schema'] != 'capstone-model-transport/1'
            or any(type(policy[key]) not in (int, float) or not math.isfinite(policy[key])
                   or not 0 < policy[key] <= 3600 for key in fields)):
        raise ValueError('Invalid model transport policy')
    return httpx.Timeout(connect=policy['connect_seconds'], read=policy['read_idle_seconds'],
                         write=policy['write_seconds'], pool=policy['pool_seconds'])

from .application_capacity import limits, current_capacity, CapacityExceeded


class StreamDiagnostics:
    """Read protocol endings, never retain model text or tool arguments."""
    def __init__(self):
        self.pending = b''
        self.dropping = False
        self.done = False
        self.finish_reason = None

    def feed(self, chunk):
        data = self.pending + chunk
        self.pending = b''
        lines = data.split(b'\n')
        for line in lines[:-1]:
            if self.dropping:
                self.dropping = False
                continue
            if len(line) > 131072 or not line.startswith(b'data:'):
                continue
            value = line[5:].strip()
            if value == b'[DONE]':
                self.done = True
                continue
            try:
                document = json.loads(value)
            except (ValueError, UnicodeError):
                continue
            if not isinstance(document, dict):
                continue
            for choice in document.get('choices', []) if isinstance(document.get('choices'), list) else []:
                reason = choice.get('finish_reason') if isinstance(choice, dict) else None
                if isinstance(reason, str) and reason in {'stop', 'tool_calls', 'function_call', 'length', 'network_error', 'content_filter'}:
                    self.finish_reason = reason
        tail = lines[-1]
        if len(tail) > 131072:
            self.dropping = True
        elif not self.dropping:
            self.pending = tail

    def summary(self):
        return {'stream_done': self.done, 'finish_reason': self.finish_reason}

    def failure_code(self):
        if self.finish_reason == 'network_error':
            return 'stream_network_error'
        if self.finish_reason == 'content_filter':
            return 'stream_content_filtered'
        if not self.done and self.finish_reason is None:
            return 'stream_incomplete'
        return None


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
    def __init__(self, *, max_requests=None, per_task=None):
        max_requests = limits.provider_relay_requests if max_requests is None else max_requests
        per_task = limits.provider_relay_task_requests if per_task is None else per_task
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
            for dimension, actual, maximum in (
                ('provider_relay_requests', len(self.active) + 1, self.max_requests),
                ('provider_relay_task_requests', sum(item.task_id == task_id for item in self.active) + 1, self.per_task),
            ):
                if actual > maximum:
                    raise CapacityExceeded(dimension, actual, maximum, 'provider_relay', mode=current_capacity().mode)
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
    started, total, status = time.monotonic(), 0, None
    stream, diagnostics, failure = False, StreamDiagnostics(), None
    try:
        async with httpx.AsyncClient(timeout=model_transport_timeout(), trust_env=False) as client, client.stream(
            'POST', upstream.rstrip('/') + '/chat/completions', content=body,
            headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key}) as response:
            status = response.status_code
            stream = response.headers.get('Content-Type', '').split(';')[0].strip() == 'text/event-stream'
            if lease.cancelled.is_set():
                raise asyncio.CancelledError()
            def headers():
                handler.send_response(response.status_code)
                handler.send_header('Content-Type', response.headers.get('Content-Type', 'application/json'))
                handler.send_header('Connection', 'close')
                handler.end_headers()
                handler.close_connection = True
            await write_http(headers)
            async for chunk in response.aiter_bytes():
                if lease.cancelled.is_set() or time.monotonic() >= lease.deadline:
                    raise asyncio.CancelledError()
                total += len(chunk)
                if stream and limits.provider_stream_bytes and total > limits.provider_stream_bytes:
                    failure = 'response_limit'
                    raise ValueError('Provider stream exceeds configured capacity')
                if stream:
                    diagnostics.feed(chunk)
                # SSE repeats protocol/usage metadata for each token. This is
                # a bounded-memory relay, not an accumulated document. A total
                # wire-byte cap truncates valid long responses mid-tool-call.
                # Task deadlines/revocation still close the whole exchange.
                if not stream and total > limits.provider_response_bytes:
                    failure = 'response_size_limit'
                    raise ValueError('Provider response exceeds bounds')
                def write(data=chunk):
                    handler.wfile.write(data)
                    handler.wfile.flush()
                await write_http(write)
    except BaseException as error:
        failure = failure or ('cancelled' if lease.cancelled.is_set() else type(error).__name__)
        raise
    finally:
        if stream and failure is None:
            failure = diagnostics.failure_code()
        if failure or (status is not None and status >= 400) or (stream and (
                not diagnostics.done or diagnostics.finish_reason in {'network_error', 'content_filter'})):
            # Only bounded protocol metadata crosses the operator log boundary.
            # No URL, credentials, prompts, output text or exception text.
            _LOG.warning('Provider relay failure: %s', json.dumps({
                'task_id': lease.task_id, 'status': status, 'response_bytes': total,
                'duration_seconds': round(time.monotonic() - started, 3),
                'failure': failure, **diagnostics.summary()}))
