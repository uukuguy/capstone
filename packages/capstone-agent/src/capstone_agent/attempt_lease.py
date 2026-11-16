"""Keep an owned Attempt alive while its runtime or authority work blocks."""

from __future__ import annotations

import threading
import time

from .thread_service import AttemptClaim, ThreadExecutionService


class AttemptLeaseRenewal:
    """Renew independently of runtime events; never reclaim an expired lease."""

    def __init__(self, service: ThreadExecutionService, claim: AttemptClaim,
                 lease_seconds: int) -> None:
        if lease_seconds < 1:
            raise ValueError("attempt worker lease is invalid")
        self._service = service
        self._claim = claim
        self._seconds = lease_seconds
        self._stop = threading.Event()
        self._lost = threading.Event()
        self._state_lock = threading.Lock()
        self._deadline = 0.0
        self._thread = threading.Thread(
            target=self._renew, daemon=True,
            name=f"capstone-attempt-lease-{claim.attempt.attempt_id}",
        )

    def __enter__(self) -> AttemptLeaseRenewal:
        started = time.monotonic()
        if not self._service.renew_attempt(self._claim, self._seconds):
            raise RuntimeError("attempt lease is unavailable")
        self._deadline = started + self._seconds
        self.check()
        self._thread.start()
        return self

    def _renew(self) -> None:
        while not self._stop.wait(self._seconds / 3):
            try:
                self.check()
                started = time.monotonic()
                owned = self._service.renew_attempt(self._claim, self._seconds)
            except Exception:
                owned = False
            if not owned:
                self._lost.set()
                return
            with self._state_lock:
                # A late response must not revive authority already observed
                # expired while the ledger request was blocked.
                if self._lost.is_set() or time.monotonic() >= self._deadline:
                    self._lost.set()
                    return
                self._deadline = started + self._seconds

    def check(self) -> None:
        with self._state_lock:
            if time.monotonic() >= self._deadline:
                self._lost.set()
            if self._lost.is_set():
                raise RuntimeError("attempt lease is unavailable")

    def __exit__(self, *_args: object) -> None:
        self._stop.set()
        self._thread.join(timeout=self._seconds / 3)
