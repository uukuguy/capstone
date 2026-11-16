"""An idle restarted worker must expire old attempts without a browser wake."""
from threading import Event
from types import SimpleNamespace

import pytest

from capstone_agent import thread_worker


@pytest.mark.parametrize('capacity', [1, 2])
def test_idle_worker_reaps_expired_attempt_without_rescanning_admission(monkeypatch, capacity):
    clock = [0.0]
    stop = Event()
    expired = Event()
    scans, reaps = [], []
    def reap():
        reaps.append(clock[0])
        if clock[0] >= 2:
            expired.set()
        return 0
    service = SimpleNamespace(interrupt_expired_attempts=reap, has_pending_attempts=lambda _:False)
    def run(*_, **__):
        scans.append(clock[0])
        reap()
        return None
    class Wake:
        def is_set(self):return False
        def clear(self):pass
        def wait(self, timeout):
            clock[0] += timeout
            if clock[0] >= 4:
                stop.set()
            return False
    monkeypatch.setattr(thread_worker, 'time', SimpleNamespace(monotonic=lambda: clock[0]))
    monkeypatch.setattr(thread_worker, 'run_pending_attempt', run)
    thread_worker.serve_thread_attempts(service, lambda _:None, lease_seconds=3,
        wake_event=Wake(), stop_event=stop, poll_seconds=.001, max_concurrent_attempts=capacity)
    assert expired.is_set(), 'expired attempt stayed running until a new command or snapshot read'
    assert 1 <= len(scans) <= capacity, 'lease maintenance must not rescan admissions'
    assert 2 <= len(reaps) <= 6
