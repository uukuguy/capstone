from threading import Event, Lock, Thread

import pytest

from capstone_agent.thread_worker import serve_thread_attempts


def test_two_slots_overlap_and_third_waits_for_runtime_cleanup(monkeypatch):
    stop, wake = Event(), Event()
    entered = [Event() for _ in range(3)]
    release = [Event() for _ in range(3)]
    lock = Lock()
    claimed = []
    closed = []

    class Factory:
        def close(self):
            assert all(release[i].is_set() for i in claimed)
            closed.append(True)

    def run(*args, **kwargs):
        with lock:
            if len(claimed) == 3:
                return None
            index = len(claimed)
            claimed.append(index)
        entered[index].set()
        assert release[index].wait(3)
        return object()

    monkeypatch.setattr('capstone_agent.thread_worker.run_pending_attempt', run)
    worker = Thread(target=serve_thread_attempts, kwargs=dict(
        service=object(), runtime_factory=Factory(), max_concurrent_attempts=2,
        wake_event=wake, stop_event=stop, poll_seconds=0.01))
    worker.start()
    try:
        assert entered[0].wait(1)
        assert entered[1].wait(1)
        assert not entered[2].is_set()
        release[0].set()
        assert entered[2].wait(1)
        stop.set()
        assert worker.is_alive()
        assert not closed
    finally:
        stop.set()
        for event in release:
            event.set()
        worker.join(3)
    assert not worker.is_alive()
    assert closed == [True]


@pytest.mark.parametrize('capacity', [0, -1, True, 1.5])
def test_worker_capacity_requires_a_positive_integer(capacity):
    with pytest.raises(ValueError, match='capacity'):
        serve_thread_attempts(object(), object(), max_concurrent_attempts=capacity)


def test_waiting_cancel_is_terminal_without_a_worker_claim():
    from test_thread_worker import _service, _submit
    service = _service()
    _submit(service)
    assert service.has_pending_attempts('pandapower')
    assert not service.has_pending_attempts('native')
    snapshot = service.snapshot('thr_worker')
    attempt = snapshot.current_attempt
    receipt = service.submit_command({
        'schema': 'capstone-command/1', 'command_id': 'cancel_waiting',
        'idempotency_key': 'cancel_waiting', 'thread_id': snapshot.thread_id,
        'run_id': snapshot.run.run_id, 'kind': 'cancel_live_attempt',
        'expected_event_seq': snapshot.last_event_seq, 'payload': {'attempt_id': attempt.attempt_id}})
    assert receipt.status == 'accepted'
    assert service.snapshot(snapshot.thread_id).current_attempt is None
    assert service.claim_attempt('free-slot', 30) is None
    assert not service.has_pending_attempts()
    assert [event.event_type for event in service.read_events(snapshot.thread_id, 0).events] == [
        'command_accepted', 'command_accepted', 'attempt_cancel_requested', 'attempt_cancelled']


def test_native_worker_capacity_defaults_to_one_and_validates_configuration():
    from capstone_agent.native_hosted_worker import native_worker_capacity
    assert native_worker_capacity({}) == 1
    assert native_worker_capacity({'CAPSTONE_NATIVE_MAX_CONCURRENT_ATTEMPTS': '2'}) == 2
    for value in ('0', '-1', '1.5', 'true', '', ' 2'):
        with pytest.raises(ValueError, match='CAPSTONE_NATIVE_MAX_CONCURRENT_ATTEMPTS'):
            native_worker_capacity({'CAPSTONE_NATIVE_MAX_CONCURRENT_ATTEMPTS': value})


@pytest.mark.parametrize('capacity', [1, 2])
def test_known_pending_attempt_is_retried_without_a_second_wake(monkeypatch, capacity):
    import capstone_agent.thread_worker as module
    from test_thread_worker import _service, _submit, _Runtime
    service = _service()
    _submit(service)
    stop, wake, skipped, released, executed = Event(), Event(), Event(), Event(), Event()
    original = module.run_pending_attempt
    def run(*args, **kwargs):
        if not released.is_set():
            skipped.set()
            return None
        return original(*args, **kwargs)
    class Runtime(_Runtime):
        def prompt(self, question, **kwargs):
            executed.set()
            return 'done'
    monkeypatch.setattr(module, 'run_pending_attempt', run)
    worker = Thread(target=module.serve_thread_attempts, kwargs=dict(
        service=service, runtime_factory=lambda _: Runtime(),
        max_concurrent_attempts=capacity, wake_event=wake, stop_event=stop, poll_seconds=.01))
    worker.start()
    try:
        assert skipped.wait(1)
        released.set()
        assert executed.wait(2)
    finally:
        stop.set()
        wake.set()
        worker.join(3)
    assert not worker.is_alive()


def test_concurrent_worker_recovers_from_slot_error_and_does_not_scan_idle_ledger(monkeypatch):
    from time import sleep
    stop, wake, completed, idle = Event(), Event(), Event(), Event()
    calls = []
    lock = Lock()
    def run(*args, **kwargs):
        with lock:
            calls.append(True)
            count = len(calls)
        if count == 1:
            raise RuntimeError('private internal failure')
        completed.set()
        return None
    class Factory:
        def sweep_idle(self):
            if completed.is_set():
                idle.set()
    monkeypatch.setattr('capstone_agent.thread_worker.run_pending_attempt', run)
    worker = Thread(target=serve_thread_attempts, kwargs=dict(
        service=object(), runtime_factory=Factory(), max_concurrent_attempts=2,
        wake_event=wake, stop_event=stop, poll_seconds=0.01))
    worker.start()
    try:
        assert idle.wait(3)
        count = len(calls)
        sleep(0.05)
        assert len(calls) == count
        completed.clear()
        wake.set()
        assert completed.wait(3)
    finally:
        stop.set()
        wake.set()
        worker.join(3)
    assert not worker.is_alive()
