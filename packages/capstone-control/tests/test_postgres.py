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
