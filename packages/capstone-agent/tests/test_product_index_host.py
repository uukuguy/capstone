import threading

import pytest

from capstone_agent.product_index_host import configured_product_indexes, serve_product_indexes


def test_disabled_index_host_needs_no_database():
    assert configured_product_indexes({}, None, None) is None


def test_invalid_configuration_fails_before_database_access():
    for value in ('null', '{}', '{"x":1,"x":2}', '[]'):
        with pytest.raises(ValueError):
            configured_product_indexes({'CAPSTONE_PRODUCT_INDEX_BUDGETS_JSON': value}, None, None)


def test_scheduler_retries_failure_without_logging_private_error(caplog):
    stop = threading.Event()
    class Service:
        calls = 0
        def run_once(self, worker):
            self.calls += 1
            if self.calls == 1:
                raise OSError('secret object key')
            stop.set()
            return 'idle'
    service = Service()
    serve_product_indexes(service, stop_event=stop, poll_seconds=0.001)
    assert service.calls == 2
    assert 'secret' not in caplog.text


def test_stopped_scheduler_claims_no_job():
    stop = threading.Event(); stop.set()
    serve_product_indexes(None, stop_event=stop)
