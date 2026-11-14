import pytest
from test_thread_postgres import postgres_thread_service, _snapshot
from test_product_series import ref
from capstone_agent.product_series_store import ProductSeriesStore


def test_durable_receipts_and_conflicts(postgres_thread_service):
    threads, thread = postgres_thread_service
    threads.create_thread(_snapshot(thread))
    store = ProductSeriesStore(threads)
    store.initialize()
    product = {**ref('original'), 'thread_id': thread}
    request = dict(series_id='series_one', expected_revision=0,
        operation='register', product=product, command_id='cmd_one', idempotency_key='idem_one')
    checked = []
    def validate(connection, value):
        checked.append(value)
    first = store.apply(thread, request, validate=validate)
    restored = ProductSeriesStore(threads)
    assert restored.apply(thread, request, validate=validate) == first
    assert len(checked) == 1
    assert restored.read(thread, 'series_one') == first
    with pytest.raises(ValueError, match='revision'):
        store.apply(thread, {**request, 'command_id': 'cmd_two', 'idempotency_key': 'idem_two'}, validate=validate)
    def unavailable(connection, value):
        raise ValueError('source unavailable')
    adopt = {**request, 'expected_revision': 1, 'operation': 'adopt',
        'command_id': 'cmd_three', 'idempotency_key': 'idem_three'}
    with pytest.raises(ValueError, match='unavailable'):
        store.apply(thread, adopt, validate=unavailable)
    assert store.read(thread, 'series_one') == first
    accepted = store.apply(thread, adopt, validate=validate)
    assert accepted['adopted_ref'] == product and accepted['revision'] == 2
    with pytest.raises(ValueError, match='idempotency'):
        store.apply(thread, {**adopt, 'operation': 'clear', 'product': None}, validate=validate)
