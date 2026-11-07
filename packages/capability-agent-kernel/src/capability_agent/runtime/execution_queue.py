"""Owner-scoped rolling execution leases. Effects are supplied by the owner."""
from contextlib import contextmanager, asynccontextmanager
import asyncio
from datetime import datetime, timezone
from threading import Condition
from time import monotonic
from uuid import uuid4
from concurrent.futures import CancelledError


class ExecutionReceiptError(RuntimeError):
    """Required owner telemetry could not be stored."""


class _ObservedReceipt(dict):
    def __init__(self, document, observer):
        super().__init__(document)
        self.observer = observer


class ExecutionQueue:
    def __init__(self, *, capacity: int = 8, provenance: str = 'owner_scheduler'):
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
            raise ValueError('execution capacity must be a positive integer')
        self.capacity = capacity
        self.provenance = provenance
        self.owner_id = 'execution-owner-' + uuid4().hex
        self._origin = monotonic()
        self._condition = Condition()
        self._active = {}
        self._pending = []

    def record(self, receipt, phase, *, provenance=None):
        receipt['events'].append({'phase': phase, 'at': datetime.now(timezone.utc).isoformat(),
            'elapsed_ms': (monotonic() - self._origin) * 1000, 'provenance': provenance or self.provenance})
        observer = getattr(receipt, 'observer', None)
        if observer is not None:
            try:
                observer(receipt)
            except Exception as error:
                raise ExecutionReceiptError('execution receipt persistence failed') from error

    def receipt(self, *, task_id, call_id, observer=None):
        receipt = _ObservedReceipt({'schema': 'capstone-tool-execution/1', 'owner_id': self.owner_id,
            'scope_id': self.owner_id, 'task_id': task_id, 'call_id': call_id,
            'policy_version': 'rolling/1', 'capacity': self.capacity, 'events': []}, observer)
        self.record(receipt, 'submitted')
        return receipt

    def _ready(self, ticket, resource, read_only):
        if len(self._active) >= self.capacity:
            return False
        if any(r == resource and not (read_only and ro) for r, ro in self._active.values()):
            return False
        for t, r, ro in self._pending:
            if t is ticket:
                return True
            if r == resource and not (read_only and ro):
                return False
        return False

    @asynccontextmanager
    async def acquire_async(self, receipt, *, resource, read_only=False):
        """Share leases across event loops without blocking them or starting threads."""
        ticket = object()
        acquired = False
        with self._condition:
            self.record(receipt, 'queued')
            self._pending.append((ticket, resource, read_only))
        try:
            while True:
                with self._condition:
                    if self._ready(ticket, resource, read_only):
                        self._pending = [p for p in self._pending if p[0] is not ticket]
                        self._active[ticket] = (resource, read_only)
                        acquired = True
                        self.record(receipt, 'acquired')
                        break
                await asyncio.sleep(.005)
            yield
        except asyncio.CancelledError:
            self.record(receipt, 'cancellation_requested')
            raise
        finally:
            with self._condition:
                self._pending = [p for p in self._pending if p[0] is not ticket]
                if acquired:
                    try:
                        self.record(receipt, 'released')
                    finally:
                        del self._active[ticket]
                self._condition.notify_all()

    @contextmanager
    def acquire(self, receipt, *, resource, read_only=False, cancel=None):
        ticket = object()
        with self._condition:
            self.record(receipt, 'queued')
            self._pending.append((ticket, resource, read_only))
            def ready():
                return self._ready(ticket, resource, read_only)
            try:
                while True:
                    if cancel is not None and cancel.is_set():
                        self.record(receipt, 'cancellation_requested')
                        raise CancelledError('execution cancelled before acquisition')
                    if ready():
                        break
                    self._condition.wait(timeout=.05 if cancel is not None else None)
            except BaseException:
                self._pending = [p for p in self._pending if p[0] is not ticket]
                self._condition.notify_all()
                raise
            self._pending = [p for p in self._pending if p[0] is not ticket]
            self._active[ticket] = (resource, read_only)
            try:
                self.record(receipt, 'acquired')
            except BaseException:
                del self._active[ticket]
                self._condition.notify_all()
                raise
        try:
            yield
        finally:
            with self._condition:
                try:
                    self.record(receipt, 'released')
                finally:
                    del self._active[ticket]
                    self._condition.notify_all()
