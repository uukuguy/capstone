import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from capstone_control.service import ControlService
from capstone_control.store import PostgresStore
from test_contracts import request
from test_service import NOW, command


@pytest.fixture
def stored():
    dsn = os.environ.get('CAPSTONE_TEST_DATABASE_URL')
    if not dsn:
        pytest.skip('disposable PostgreSQL database required')
    store = PostgresStore(dsn)
    store.initialize()
    workspace = 'test_' + uuid4().hex
    try:
        yield store, workspace
    finally:
        with store.connect() as connection:
            connection.execute('DELETE FROM capstone_control_goals WHERE workspace=%s', (workspace,))


def test_restart_and_concurrent_dispatch_are_durable(stored):
    store, workspace = stored
    service = ControlService(store, now=lambda: NOW)
    goal = service.create(workspace, request())
    dispatch = command(goal, 'delegate_next', 'dispatch-1')

    def submit(_):
        restarted = ControlService(PostgresStore(store.dsn), now=lambda: NOW)
        return restarted.command(workspace, dispatch)

    with ThreadPoolExecutor(max_workers=8) as pool:
        receipts = list(pool.map(submit, range(8)))
    assert all(r == receipts[0] for r in receipts)
    restarted = ControlService(PostgresStore(store.dsn), now=lambda: NOW)
    assert restarted.create(workspace, request()) == goal
    assert restarted.read(workspace, goal['goal_id'])['delegations_admitted'] == 1
    assert len(restarted.pending(workspace)) == 1
    assert restarted.pending('other_workspace') == []
    page = restarted.read_events(workspace, goal['goal_id'], limit=1)
    assert page['through_sequence'] == 2
    assert page['has_more']
    assert page['history_complete']
    second = restarted.read_events(workspace, goal['goal_id'], after=page['next_sequence'], through=2)
    assert [e['kind'] for e in second['events']] == ['command.delegate_next']
    assert not second['has_more']
    with pytest.raises(KeyError):
        restarted.read_events('other_workspace', goal['goal_id'])


def test_failed_transition_rolls_back_without_operation_receipt(stored):
    from capstone_control.service import InvalidTransition
    store, workspace = stored
    service = ControlService(store, now=lambda: NOW)
    goal = service.create(workspace, request())
    with pytest.raises(InvalidTransition):
        service.command(workspace, command(goal, 'accept', 'too-early', products=[]))
    assert service.read(workspace, goal['goal_id']) == goal
    # The rejected operation has not consumed its key or modified the revision.
    paused = service.command(workspace, command(goal, 'pause', 'too-early'))['goal']
    assert paused['state'] == 'paused'
    assert [e['kind'] for e in service.read_events(workspace, goal['goal_id'])['events']] == [
        'goal.created', 'command.pause']


def test_event_insert_failure_rolls_back_aggregate_and_receipt(stored):
    from psycopg import errors
    from psycopg.types.json import Jsonb
    store, workspace = stored
    service = ControlService(store, now=lambda: NOW)
    goal = service.create(workspace, request())
    # A conflicting stored row forces the event INSERT to fail in the real transaction.
    with store.connect() as connection:
        connection.execute('''INSERT INTO capstone_control_events
            (workspace, goal_id, sequence, document) VALUES (%s,%s,2,%s)''',
            (workspace, goal['goal_id'], Jsonb({'sentinel': True})))
    cmd = command(goal, 'pause', 'pause-after-failure')
    with pytest.raises(errors.UniqueViolation):
        service.command(workspace, cmd)
    assert service.read(workspace, goal['goal_id']) == goal
    with store.connect() as connection:
        connection.execute('DELETE FROM capstone_control_events WHERE workspace=%s AND sequence=2', (workspace,))
    assert service.command(workspace, cmd)['goal']['state'] == 'paused'
    assert service.read_events(workspace, goal['goal_id'])['through_sequence'] == 2
