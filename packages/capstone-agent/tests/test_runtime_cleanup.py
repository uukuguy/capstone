import pytest
from capstone_agent.runtime_cleanup import run_runtime_cleanup


def broken():
    raise OSError('private credential')


def test_cleanup_keeps_original_failure_and_records_secondary(caplog):
    with pytest.raises(ValueError, match='original'):
        try:
            raise ValueError('original')
        finally:
            run_runtime_cleanup(broken, operation='stop')
    assert 'exception_type=OSError' in caplog.text
    assert 'private credential' not in caplog.text


def test_cleanup_failure_without_original_remains_a_failure():
    with pytest.raises(OSError):
        run_runtime_cleanup(broken, operation='stop')
