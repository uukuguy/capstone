"""Bound execution slots; the existing ledger still owns admission and leases."""
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from collections.abc import Callable
import logging
from threading import Event

_LOG = logging.getLogger(__name__)


def serve_attempt_slots(run: Callable[[], object | None], *, capacity: int,
                        stop: Event, wake: Event | None, poll_seconds: float,
                        sweep: Callable[[], object] | None = None,
                        reconcile: Callable[[], object] | None = None) -> None:
    scan = True
    with ThreadPoolExecutor(max_workers=capacity, thread_name_prefix='capstone-attempt') as pool:
        active: set[Future[object | None]] = set()
        while not stop.is_set():
            if wake is not None and wake.is_set():
                wake.clear()
                scan = True
            finished = {future for future in active if future.done()}
            active -= finished
            for future in finished:
                try:
                    if future.result() is not None:
                        scan = True
                except Exception:
                    # Do not expose exception text or stop unrelated attempts.
                    _LOG.warning('Thread execution slot failed; retrying after poll interval')
                    stop.wait(poll_seconds)
                    scan = True
            try:
                if reconcile is not None:
                    reconcile()
                if not active and sweep is not None:
                    sweep()
            except Exception:
                _LOG.warning('Thread worker maintenance failed; retrying after poll interval')
                stop.wait(poll_seconds)
                continue
            if stop.is_set():
                break
            if scan:
                # One submitted execution per free slot; never preclaim a queue.
                while len(active) < capacity and not stop.is_set():
                    active.add(pool.submit(run))
                scan = False
            if active:
                wait(active, timeout=poll_seconds, return_when=FIRST_COMPLETED)
            elif wake is not None:
                wake.wait(timeout=1)
            else:
                stop.wait(poll_seconds)
            if wake is None:
                scan = True
    # Executor context waits for attempt cleanup before factory shutdown.
