import psycopg
import pytest


def test_cold_database_connection_retries_before_any_transaction(monkeypatch):
    from capstone_agent.database_connect import connect_database
    calls, waits = [], []
    ready = object()
    def connect(dsn, **kwargs):
        calls.append(kwargs)
        if len(calls) < 3:
            raise psycopg.OperationalError('connection refused')
        return ready
    monkeypatch.setattr('capstone_agent.database_connect.psycopg.connect', connect)
    assert connect_database('postgresql://fixture', sleep=waits.append) is ready
    assert len(calls) == 3 and len(waits) == 2
    assert all(call['connect_timeout'] == 3 for call in calls)


def test_database_connection_retries_are_bounded(monkeypatch):
    from capstone_agent.database_connect import connect_database
    calls = []
    def connect(*_args, **_kwargs):
        calls.append(1)
        raise psycopg.OperationalError('unavailable')
    monkeypatch.setattr('capstone_agent.database_connect.psycopg.connect', connect)
    with pytest.raises(psycopg.OperationalError):
        connect_database('postgresql://fixture', sleep=lambda _: None)
    assert len(calls) == 5
