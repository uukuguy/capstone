"""Fixed, bounded operator timings; never model input or public task events."""
import json
import math
import sys
from threading import Lock
import time

_PHASES = frozenset({'task_started', 'resources_configured', 'process_launch_requested',
    'process_spawned',
    'provider_request_started', 'provider_headers', 'first_bytes', 'first_thinking',
    'first_text', 'task_finished'})


class NativeTiming:
    def __init__(self, task_id, *, clock=time.monotonic):
        self.task_id, self.clock = task_id, clock
        self.started = clock()
        self.seen = set()
        self.closed = False
        self.lock = Lock()
        self.mark('task_started', at=self.started)

    def mark(self, phase, *, at=None, counts=None):
        if phase not in _PHASES:
            raise ValueError('Unknown native timing phase')
        with self.lock:
            return self._mark_locked(phase, at=at, counts=counts)

    def _mark_locked(self, phase, *, at=None, counts=None):
        if self.closed or phase in self.seen:
            return False
        self.seen.add(phase)
        elapsed = (self.clock() if at is None else at) - self.started
        if not math.isfinite(elapsed):
            return False
        record = {'task_id': self.task_id, 'scope': 'task_first_provider_exchange',
            'phase': phase, 'elapsed_ms': round(min(86400000, max(0, elapsed)*1000), 3)}
        allowed = {'request_bytes', 'tools_count', 'tools_schema_bytes',
                   'system_message_bytes', 'other_messages_bytes'}
        try:
            if callable(counts):
                counts = counts()
            if counts:
                record.update({key: min(value, 2**53-1) for key, value in counts.items()
                               if key in allowed and type(value) is int and value >= 0})
        except Exception:
            pass  # Optional counts cannot change task execution or suppress the phase.
        try:
            print(json.dumps({'event': 'native_timing', **record}), file=sys.stderr, flush=True)
        except Exception:
            pass  # Diagnostic sinks cannot change task execution.
        return True

    def close(self):
        with self.lock:
            try:
                self._mark_locked('task_finished')
            finally:
                self.closed = True
