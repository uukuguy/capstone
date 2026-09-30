"""Lease-aware worker entry points for durable Thread Attempts.

The HTTP process only admits commands.  This module owns the small polling
boundary that claims accepted Attempts, constructs an injected Harness
runtime, and lets :class:`HarnessAttemptRunner` persist the terminal result.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from .harness import HarnessAttemptResult, HarnessAttemptRunner, HarnessRuntime
from .thread_service import AttemptClaim, ThreadExecutionService


RuntimeFactory = Callable[[AttemptClaim], HarnessRuntime]


def run_pending_attempt(
    service: ThreadExecutionService,
    runtime_factory: RuntimeFactory,
    *,
    worker_id: str,
    lease_seconds: int = 30,
) -> HarnessAttemptResult | None:
    """Run at most one accepted Attempt and return ``None`` when idle."""

    service.interrupt_expired_attempts()
    claim = service.claim_attempt(worker_id, lease_seconds)
    if claim is None:
        return None
    try:
        runtime = runtime_factory(claim)
    except Exception:
        service.finish_attempt(
            claim, phase="failed", payload={"error_code": "runtime_unavailable"},
        )
        return HarnessAttemptResult("failed", None, "runtime_unavailable")
    return HarnessAttemptRunner(service, runtime, lease_seconds=lease_seconds).run(claim)


def serve_thread_attempts(
    service: ThreadExecutionService,
    runtime_factory: RuntimeFactory,
    *,
    worker_id: str = "capstone-thread-worker",
    lease_seconds: int = 30,
    poll_seconds: float = 0.25,
    stop_event: threading.Event | None = None,
) -> None:
    """Poll accepted Attempts until ``stop_event`` is set.

    Runtime construction is injected so this worker remains neutral about Pi,
    DSH, Domain Packs, and registered Authorities.
    """

    if not worker_id or lease_seconds < 1 or poll_seconds <= 0:
        raise ValueError("thread worker configuration is invalid")
    stop = stop_event or threading.Event()
    while not stop.is_set():
        result = run_pending_attempt(
            service, runtime_factory, worker_id=worker_id,
            lease_seconds=lease_seconds,
        )
        if result is None:
            stop.wait(poll_seconds)


__all__ = ["RuntimeFactory", "run_pending_attempt", "serve_thread_attempts"]
