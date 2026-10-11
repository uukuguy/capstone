import pytest


def test_reused_recognition_process_resets_history_and_discards_failures():
    from capstone_agent.recognition_process import RecognitionProcess
    clients = []
    class Client:
        def __init__(self): self.resets = self.stops = 0; clients.append(self)
        def new_session(self, **_): self.resets += 1
        def stop(self): self.stops += 1
    process = RecognitionProcess()
    make = lambda root: Client()
    with process.lease(make, on_heartbeat=lambda: None, timeout_seconds=10) as (first, reused):
        assert not reused
    with process.lease(make, on_heartbeat=lambda: None, timeout_seconds=10) as (second, reused):
        assert second is first and reused and second.resets == 1
    with pytest.raises(ValueError):
        with process.lease(make, on_heartbeat=lambda: None, timeout_seconds=10): raise ValueError('invalid task')
    assert first.stops == 1
    with process.lease(make, on_heartbeat=lambda: None, timeout_seconds=10) as (third, reused):
        assert third is not first and not reused
    process.close()
    assert third.stops == 1


def test_idle_recognition_process_is_released_without_a_new_request(monkeypatch):
    from capstone_agent import recognition_process
    now = [1000.0]
    monkeypatch.setattr(recognition_process.time, 'monotonic', lambda: now[0])
    stops = []
    class Client:
        def stop(self): stops.append(1)
    process = recognition_process.RecognitionProcess()
    with process.lease(lambda root: Client(), on_heartbeat=lambda: None, timeout_seconds=10): pass
    now[0] += 181
    assert process.sweep_idle() == 1 and stops == [1]
    assert process.sweep_idle() == 0


@pytest.mark.parametrize('failure', ['reset', 'cancel', 'rotate'])
def test_reset_cancel_and_rotation_do_not_retain_a_dirty_process(failure):
    from capstone_agent.recognition_process import RecognitionProcess
    stops = []
    class Client:
        def new_session(self, **_):
            if failure == 'reset': raise ValueError('reset failed')
        def stop(self): stops.append(self)
    process = RecognitionProcess()
    with process.lease(lambda root: Client(), on_heartbeat=lambda: None, timeout_seconds=10) as (first, _): pass
    if failure == 'rotate':
        process._uses = 32
        with process.lease(lambda root: Client(), on_heartbeat=lambda: None, timeout_seconds=10) as (second, reused):
            assert second is not first and not reused
    else:
        with pytest.raises(ValueError):
            with process.lease(lambda root: Client(), on_heartbeat=lambda: None, timeout_seconds=10):
                raise ValueError('cancelled')
    assert first in stops
    process.close()
