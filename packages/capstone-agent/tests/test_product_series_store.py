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
    other = {**request, 'series_id': 'series_other', 'command_id': 'cmd_other', 'idempotency_key': 'idem_other'}
    first = store.apply(thread, request, validate=validate, actor='operator:test')
    restored = ProductSeriesStore(threads)
    assert restored.apply(thread, request, validate=validate, actor='operator:test') == first
    assert len(checked) == 1
    assert restored.read(thread, 'series_one') == first
    with pytest.raises(ValueError, match='another series'):
        store.apply(thread, other, validate=validate, actor='operator:test')
    with pytest.raises(ValueError, match='revision'):
        store.apply(thread, {**request, 'command_id': 'cmd_two', 'idempotency_key': 'idem_two'}, validate=validate, actor='operator:test')
    def unavailable(connection, value):
        raise ValueError('source unavailable')
    adopt = {**request, 'expected_revision': 1, 'operation': 'adopt',
        'command_id': 'cmd_three', 'idempotency_key': 'idem_three'}
    with pytest.raises(ValueError, match='unavailable'):
        store.apply(thread, adopt, validate=unavailable, actor='operator:test')
    assert store.read(thread, 'series_one') == first
    accepted = store.apply(thread, adopt, validate=validate, actor='operator:test')
    assert accepted['adopted_ref'] == product and accepted['revision'] == 2
    history = restored.history(thread, 'series_one', limit=1)
    assert len(history['events']) == 1 and history['next_revision'] == 1
    event = history['events'][0]
    assert event['operation'] == 'adopt' and event['revision'] == 2
    assert event['previous_revision'] == 1 and event['created_at']
    assert event['product'] == product
    with pytest.raises(ValueError, match='idempotency'):
        store.apply(thread, {**adopt, 'operation': 'clear', 'product': None}, validate=validate, actor='operator:test')


def test_member_pages_do_not_expand_persistent_state(postgres_thread_service):
    threads, thread=postgres_thread_service
    threads.create_thread(_snapshot(thread))
    store=ProductSeriesStore(threads)
    store.initialize()
    for revision in range(25):
        product={**ref(str(revision)), 'thread_id':thread}
        store.apply(thread,dict(series_id='series_many',expected_revision=revision,operation='register',
            product=product,command_id=f'cmd_{revision}',idempotency_key=f'idem_{revision}'),
            validate=lambda connection,value:None,actor='operator:test')
    assert len(store.read(thread,'series_many')['members'])==20
    first=store.members(thread,'series_many',limit=20)
    second=store.members(thread,'series_many',limit=20,after=first['next_cursor'])
    assert len(second['members'])==5 and second['next_cursor'] is None
    with threads._connect() as c:
        assert c.execute('SELECT state FROM capstone_product_series WHERE thread_id=%s',(thread,)).fetchone()['state']['members']==[]
