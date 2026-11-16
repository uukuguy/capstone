from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest

from capstone_control.service import ControlService, Conflict, InvalidTransition
from capstone_control.store import MemoryStore
from test_contracts import request


NOW = datetime(2026, 11, 17, tzinfo=timezone.utc)


def service():
    return ControlService(MemoryStore(), now=lambda: NOW)


def command(goal, kind, operation_id, **payload):
    return {'schema': 'capstone-control-command/1', 'operation_id': operation_id,
            'goal_id': goal['goal_id'], 'expected_revision': goal['revision'],
            'kind': kind, 'payload': payload}


def test_create_replay_content_conflict_and_workspace_isolation():
    s = service()
    original = s.create('a', request())
    assert s.create('a', request()) == original
    changed = request()
    changed['objective'] = 'Different objective'
    with pytest.raises(Conflict):
        s.create('a', changed)
    assert s.create('b', request())['goal_id'] != original['goal_id']
    with pytest.raises(KeyError):
        s.read('b', original['goal_id'])


def test_concurrent_dispatch_has_one_durable_intent_and_replay_is_exact():
    s = service()
    goal = s.create('a', request())
    cmd = command(goal, 'delegate_next', 'dispatch-1')
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: s.command('a', cmd), range(8)))
    assert all(r == results[0] for r in results)
    current = s.read('a', goal['goal_id'])
    assert current['delegations_admitted'] == 1
    assert current['tasks'][0]['state'] == 'dispatching'
    assert current['tasks'][1]['state'] == 'pending'
    assert len(s.pending('a')) == 1
    with pytest.raises(Conflict):
        s.command('a', command(goal, 'delegate_next', 'dispatch-2'))


def test_pause_and_cancel_prevent_dispatch_without_deleting_history():
    s = service()
    goal = s.create('a', request())
    paused = s.command('a', command(goal, 'pause', 'pause-1'))['goal']
    with pytest.raises(InvalidTransition):
        s.command('a', command(paused, 'delegate_next', 'bad-dispatch'))
    cancelled = s.command('a', command(paused, 'cancel', 'cancel-1'))['goal']
    assert cancelled['state'] == 'cancelled'
    assert cancelled['tasks'][0]['objective'] == goal['tasks'][0]['objective']
    with pytest.raises(InvalidTransition):
        s.command('a', command(cancelled, 'resume', 'bad-resume'))


def test_budget_exhaustion_pauses_without_extra_intent():
    s = service()
    body = request()
    body['max_delegations'] = 1
    goal = s.create('a', body)
    first = s.command('a', command(goal, 'delegate_next', 'dispatch-1'))['goal']
    binding = first['tasks'][0]['delegation']
    # Host delivery and verification are separate from model completion.
    delivered = s.deliver('a', goal['goal_id'], binding['delegation_id'],
                          {'thread_id': 'thread-1', 'work_id': 'work-1'},
                          {'answer_ref': 'answer-1', 'products': [], 'status': 'completed'})
    assert delivered['tasks'][0]['state'] == 'delivered'
    verified = s.command('a', command(delivered, 'verify_task', 'verify-1',
                                     task_id='draft', delivery_revision=1,
                                     checks=[{'name': 'saved answer', 'passed': True}]))['goal']
    stopped = s.command('a', command(verified, 'delegate_next', 'dispatch-2'))['goal']
    assert stopped['state'] == 'paused'
    assert stopped['reason'] == 'delegation_budget_exhausted'
    assert stopped['delegations_admitted'] == 1


def test_delivery_identity_and_late_cancel_do_not_complete_goal():
    s = service()
    goal = s.create('a', request())
    dispatched = s.command('a', command(goal, 'delegate_next', 'dispatch-1'))['goal']
    cancelled = s.command('a', command(dispatched, 'cancel', 'cancel-1'))['goal']
    d = cancelled['tasks'][0]['delegation']
    with pytest.raises(InvalidTransition):
        s.deliver('a', goal['goal_id'], d['delegation_id'],
                  {'thread_id': 'thread-1', 'work_id': 'work-1'},
                  {'answer_ref': 'answer-1', 'products': [], 'status': 'completed'})
    assert s.read('a', goal['goal_id'])['state'] == 'cancelling'


def test_user_acceptance_requires_all_verified_tasks_and_exact_products():
    s = service()
    goal = s.create('a', request())
    with pytest.raises(InvalidTransition):
        s.command('a', command(goal, 'accept', 'accept-1', products=[]))
