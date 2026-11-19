"""Keep an owned Attempt alive while its runtime or authority work blocks."""

from __future__ import annotations

import logging
import threading

from .thread_service import AttemptClaim, ThreadExecutionService


class AttemptLeaseRenewal:
    """Refresh contact while the ledger still recognizes the claim owner."""

    def __init__(self, service: ThreadExecutionService, claim: AttemptClaim,
                 lease_seconds: int) -> None:
        if lease_seconds < 1:
            raise ValueError("attempt heartbeat window is invalid")
        self._service = service
        self._claim = claim
        self._seconds = lease_seconds
        self._stop = threading.Event()
        self._lost = threading.Event()
        self._heartbeat_error = False
        self._thread = threading.Thread(
            target=self._renew, daemon=True,
            name=f"capstone-attempt-heartbeat-{claim.attempt.attempt_id}",
        )

    def __enter__(self) -> AttemptLeaseRenewal:
        self._refresh()
        self.check()
        self._thread.start()
        return self

    def _refresh(self) -> None:
        try:
            owned = self._service.renew_attempt(self._claim, self._seconds)
        except Exception as error:
            # A missing response does not prove ownership changed. Every durable
            # write still checks the token and execution phase under a lock.
            if not self._heartbeat_error:
                from .native_failure_origin import native_failure_origin
                logging.getLogger(__name__).warning(
                    "Attempt heartbeat unavailable; attempt_id=%s exception_type=%s origin=%s",
                    self._claim.attempt.attempt_id, type(error).__name__, native_failure_origin(error))
            self._heartbeat_error = True
            return
        self._heartbeat_error = False
        if not owned:
            self._lost.set()

    def _renew(self) -> None:
        while not self._lost.is_set() and not self._stop.wait(self._seconds / 3):
            self._refresh()

    def check(self) -> None:
        if self._lost.is_set():
            raise RuntimeError("attempt owner is unavailable")

    def __exit__(self, *_args: object) -> None:
        self._stop.set()
        self._thread.join(timeout=self._seconds / 3)
