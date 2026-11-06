"""Bounded text coalescing for diagnostic progress, never for final answers."""
from collections.abc import Callable
from time import monotonic
from math import isfinite


def thinking_delta_buffer(emit: Callable[[str], None], *, preview: bool, clock=monotonic):
    """Use display cadence only when a separate durable writer is enabled."""
    return TextDeltaBuffer(emit, clock=clock,
                           interval_seconds=.075 if preview else 1.0,
                           max_chars=256 if preview else 4096)


class IdleFlushCallback:
    """Keep the native callback callable and expose its display idle deadline."""
    def __init__(self, emit, flush_due):
        self.emit, self.flush_due = emit, flush_due

    def __call__(self, event):
        self.emit(event)

    def on_idle(self):
        self.flush_due()


class TextDeltaBuffer:
    def __init__(self, emit: Callable[[str], None], *, clock=monotonic,
                 interval_seconds: float = 1.0, max_chars: int = 4096):
        if not isfinite(interval_seconds) or interval_seconds <= 0:
            raise ValueError('Text flush interval must be positive and finite')
        if type(max_chars) is not int or not 1 <= max_chars <= 4096:
            raise ValueError('Text event size must be between 1 and 4096 characters')
        self.emit = emit
        self.clock = clock
        self.interval = interval_seconds
        self.max_chars = max_chars
        self.pending = ''
        self.last_sent: float | None = None
        self.failed = False

    def push(self, text: str) -> None:
        while text:
            take = self.max_chars - len(self.pending)
            self.pending += text[:take]
            text = text[take:]
            if (len(self.pending) == self.max_chars or self.last_sent is None
                    or self.clock() - self.last_sent >= self.interval):
                self.flush()

    def flush(self) -> None:
        if self.pending and not self.failed:
            try:
                self.emit(self.pending)
            except BaseException:
                self.failed = True
                raise
            self.pending = ''
            self.last_sent = self.clock()

    def flush_due(self) -> None:
        if self.pending and (self.last_sent is None or self.clock() - self.last_sent >= self.interval):
            self.flush()
