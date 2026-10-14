import time

import pytest

from capstone_agent.thread_startup_timing import record_thread_startup


@pytest.mark.parametrize('failure', [OSError, ValueError])
def test_optional_startup_diagnostics_do_not_fail_a_completed_creation(monkeypatch, failure):
    class UnavailableOutput:
        def write(self, message):
            raise failure('diagnostic output unavailable')
    monkeypatch.setattr('capstone_agent.thread_startup_timing.sys.stderr', UnavailableOutput())
    assert record_thread_startup('thr_test', 'database_write', time.perf_counter()) >= 0
