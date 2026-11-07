from capstone_agent.thread_gateway import prepare_admission, historical_binding
from test_thread_postgres import postgres_thread_service


def publication(connection='one', instance='instance-one', revision='new'):
    return {'available': True, 'connection_id': connection, 'identity': {'instance_id': instance},
            'catalog': {'revision': revision}}


def test_lock_and_refresh_same_instance_without_rewriting_prior_binding():
    original = {'capability': {'data_gateway': publication(revision='old')}}
    bound, state, error = prepare_admission(original, None, publication())
    assert error is None and state['locked']
    assert bound['capability']['data_gateway']['catalog']['revision'] == 'new'
    assert original['capability']['data_gateway']['catalog']['revision'] == 'old'
    assert prepare_admission(bound, state, publication(revision='next'))[2] is None


def test_locked_thread_rejects_replaced_instance_and_another_connection():
    saved = {'connection_id': 'one', 'instance_id': 'instance-one', 'locked': True}
    for value in (publication(instance='replacement'), publication(connection='two')):
        assert prepare_admission(None, saved, value)[2] == 'gateway_instance_changed'


def test_locked_thread_with_no_gateway_does_not_gain_default_gateway():
    saved = historical_binding({})
    assert prepare_admission(None, saved, publication())[2] == 'gateway_instance_changed'


def test_public_display_address_stays_in_ledger_not_native_execution_context():
    from capstone_agent.pi_delegation import _json_document
    value = publication()
    value['identity']['display_address'] = 'registered.example:18001'
    bound, state, error = prepare_admission({'capability': {}}, None, value)
    assert error is None
    assert state['identity']['endpoint'] == 'registered.example:18001'
    _json_document(bound['capability'])
    assert set(bound['capability']['data_gateway']['session_binding']) == {'connection_id','instance_id','locked'}


def empty_service():
    from capstone_agent.thread_service import InMemoryThreadService, ThreadCreator
    class Store:
        def create_thread(self, snapshot):
            return snapshot
    snapshot = ThreadCreator(Store(), None).create(model_free=True)
    return InMemoryThreadService(snapshot), snapshot.thread_id


def message(thread_id, name='one', expected=0):
    return {'schema': 'capstone-command/2', 'command_id': 'cmd_'+name, 'idempotency_key': 'key_'+name,
            'thread_id': thread_id, 'kind': 'work_message',
            'target': {'kind': 'work', 'id': 'new', 'expected_revision': expected}, 'payload': {'text': 'Inspect materials'}}


def test_selection_can_change_after_first_accepted_instruction():
    import pytest
    from capstone_agent.thread_gateway import publication_binding
    from capstone_agent.thread_protocol import ThreadProtocolError
    service, thread = empty_service()
    service.select_thread_gateway(thread, publication_binding(publication()))
    assert not service.read_thread_gateway(thread)['locked']
    assert service.submit_gateway_command(message(thread), publication()).status == 'accepted'
    assert service.read_thread_gateway(thread)['locked']
    service.select_thread_gateway(thread, publication_binding(publication('two', 'instance-two')))
    assert service.read_thread_gateway(thread)['connection_id'] == 'two'
    assert service.submit_gateway_command(message(thread), publication('two', 'instance-two')).status == 'accepted'  # idempotent receipt
    assert service.read_thread_gateway(thread)['locked'] is False


def test_rejected_instruction_and_selection_race_do_not_lock_an_empty_session():
    from capstone_agent.thread_gateway import publication_binding
    service, thread = empty_service()
    service.select_thread_gateway(thread, publication_binding(publication('two', 'instance-two')))
    assert service.submit_gateway_command(message(thread), publication()).rejection == 'gateway_instance_changed'
    assert not service.read_thread_gateway(thread)['locked']
    service.select_thread_gateway(thread, publication_binding(publication()))
    assert service.submit_gateway_command(message(thread, 'bad', expected=99), publication()).status == 'rejected'
    assert not service.read_thread_gateway(thread)['locked']


def test_postgres_selection_survives_restart_and_can_switch(postgres_thread_service):
    import pytest
    from dataclasses import replace
    from capstone_agent.thread_service import PostgresThreadService
    from capstone_agent.thread_protocol import ThreadProtocolError
    from capstone_agent.thread_gateway import publication_binding
    service, thread = postgres_thread_service
    empty, generated = empty_service()
    service.create_thread(replace(empty.snapshot(generated), thread_id=thread))
    service.select_thread_gateway(thread, publication_binding(publication()))
    assert service.submit_gateway_command(message(thread), publication()).status == 'accepted'
    with service._connect() as connection:
        frozen_before = connection.execute('SELECT submission_snapshot FROM capstone_thread_attempts WHERE thread_id=%s', (thread,)).fetchall()
    restarted = PostgresThreadService(service.dsn)
    assert restarted.read_thread_gateway(thread)['instance_id'] == 'instance-one'
    assert restarted.read_thread_gateway(thread)['locked']
    restarted.select_thread_gateway(thread, publication_binding(publication('two', 'instance-two')))
    assert restarted.read_thread_gateway(thread)['connection_id'] == 'two'
    with service._connect() as connection:
        assert connection.execute('SELECT submission_snapshot FROM capstone_thread_attempts WHERE thread_id=%s', (thread,)).fetchall() == frozen_before


def test_postgres_switch_and_first_instruction_are_serialized(postgres_thread_service):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from dataclasses import replace
    from capstone_agent.thread_gateway import publication_binding
    from capstone_agent.thread_protocol import ThreadProtocolError
    service, thread = postgres_thread_service
    empty, generated = empty_service()
    service.create_thread(replace(empty.snapshot(generated), thread_id=thread))
    service.select_thread_gateway(thread, publication_binding(publication()))
    barrier = threading.Barrier(2)
    def submit():
        barrier.wait()
        return service.submit_gateway_command(message(thread), publication())
    def select():
        barrier.wait()
        try:
            service.select_thread_gateway(thread, publication_binding(publication('two', 'instance-two')))
            return True
        except ThreadProtocolError:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        sent, switched = pool.submit(submit), pool.submit(select)
        receipt, changed = sent.result(), switched.result()
    saved = service.read_thread_gateway(thread)
    assert changed is True
    assert receipt.status in {'accepted', 'rejected'}
    assert saved['instance_id'] == ('instance-two' if changed else 'instance-one')
    assert saved['locked'] is not changed


def test_changing_gateway_preserves_already_accepted_task_snapshot():
    from copy import deepcopy
    from capstone_agent.thread_gateway import publication_binding
    service, thread = empty_service()
    service.select_thread_gateway(thread, publication_binding(publication()))
    assert service.submit_gateway_command(message(thread), publication()).status == 'accepted'
    before = deepcopy(service._attempts)
    service.select_thread_gateway(thread, publication_binding(publication('two', 'instance-two')))
    assert service.read_thread_gateway(thread)['connection_id'] == 'two'
    assert service.read_thread_gateway(thread)['locked'] is False
    assert service._attempts == before
