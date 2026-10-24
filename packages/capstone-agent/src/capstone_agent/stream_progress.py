"""Bounded text coalescing for diagnostic progress, never for final answers."""
from collections.abc import Callable
from time import monotonic
from math import isfinite


class TextDeltaBuffer:
    def __init__(self, emit: Callable[[str], None], *, clock=monotonic,
                 interval_seconds: float = .05, max_chars: int = 1024):
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

    def push(self, text: str) -> None:
        while text:
            take = self.max_chars - len(self.pending)
            self.pending += text[:take]
            text = text[take:]
            if (len(self.pending) == self.max_chars or self.last_sent is None
                    or self.clock() - self.last_sent >= self.interval):
                self.flush()

    def flush(self) -> None:
        if self.pending:
            text, self.pending = self.pending, ''
            self.emit(text)
            self.last_sent = self.clock()
