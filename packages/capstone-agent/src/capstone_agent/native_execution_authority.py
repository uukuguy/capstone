"""Executor-local authority; observation never extends permission to execute.

This is private control state, separate from task products and ledger tokens.
The caller must validate its host attempt before sending a renewal.
"""
from __future__ import annotations

from hmac import compare_digest
import math
from threading import Lock
import time


class ExecutionAuthority:
    def __init__(self, generation: str, capability: str, duration_seconds: float,
                 *, clock=time.monotonic):
        if (not isinstance(generation, str) or not generation
                or not isinstance(capability, str) or not capability
                or not capability.isascii()
                or type(duration_seconds) not in {int, float}
                or not math.isfinite(duration_seconds) or duration_seconds <= 0):
            raise ValueError('invalid execution authority')
        self._generation = generation
        self._capability = capability
        self._duration = duration_seconds
        self._clock = clock
        self._deadline = clock() + duration_seconds
        self._sequence = 0
        self._revoked = False
        self._lock = Lock()

    def _active(self, now):
        if now >= self._deadline:
            self._revoked = True
        return not self._revoked

    def active(self) -> bool:
        with self._lock:
            return self._active(self._clock())

    def renew(self, generation: str, capability: str, sequence: int) -> None:
        with self._lock:
            now = self._clock()
            if (not self._active(now) or generation != self._generation
                    or not isinstance(capability, str) or not capability.isascii()
                    or not compare_digest(capability, self._capability)):
                raise PermissionError('execution authority rejected')
            if type(sequence) is not int or sequence < 1:
                raise ValueError('invalid renewal sequence')
            if sequence == self._sequence:
                return  # Lost response: acknowledge without extending the grant.
            if sequence != self._sequence + 1:
                raise ValueError('invalid renewal sequence')
            self._sequence = sequence
            self._deadline = now + self._duration

    def revoke(self) -> None:
        with self._lock:
            self._revoked = True
