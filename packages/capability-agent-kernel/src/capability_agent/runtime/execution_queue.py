"""Owner-scoped rolling execution leases. Effects are supplied by the owner."""
from contextlib import contextmanager
from datetime import datetime, timezone
from threading import Condition
from time import monotonic
from uuid import uuid4
from concurrent.futures import CancelledError


class ExecutionQueue:
    def __init__(self, *, capacity: int = 8):
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
            raise ValueError('execution capacity must be a positive integer')
        self.capacity = capacity
        self.owner_id = 'execution-owner-' + uuid4().hex
        self._origin = monotonic()
        self._condition = Condition()
        self._active = {}
        self._pending = []

    def record(self, receipt, phase, *, provenance='owner_scheduler'):
        receipt['events'].append({'phase': phase, 'at': datetime.now(timezone.utc).isoformat(),
            'elapsed_ms': (monotonic() - self._origin) * 1000, 'provenance': provenance})

    def receipt(self, *, task_id, call_id):
        receipt = {'schema': 'capstone-tool-execution/1', 'owner_id': self.owner_id,
            'scope_id': self.owner_id, 'task_id': task_id, 'call_id': call_id,
            'policy_version': 'rolling/1', 'capacity': self.capacity, 'events': []}
        self.record(receipt, 'submitted')
        return receipt

    @contextmanager
    def acquire(self, receipt, *, resource, read_only=False, cancel=None):
        ticket = object()
        with self._condition:
            self.record(receipt, 'queued')
            self._pending.append((ticket, resource, read_only))
            def ready():
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
            self.record(receipt, 'acquired')
        try:
            yield
        finally:
            with self._condition:
                self.record(receipt, 'released')
                del self._active[ticket]
                self._condition.notify_all()
