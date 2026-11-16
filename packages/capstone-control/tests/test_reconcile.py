from copy import deepcopy

import pytest

from capstone_control.reconcile import reconcile
from capstone_control.service import Conflict, ControlService
from capstone_control.store import MemoryStore
from test_contracts import request
from test_service import NOW, command


class Agent:
    def __init__(self):
        self.executions = {}
        self.observations = {}
        self.revoked = []

    def delegate(self, workspace, delegation):
        key = delegation['operation_id']
        self.executions.setdefault(key, {'thread_id': 'thread_' + key,
                                         'work_id': 'work_' + key})
        return deepcopy(self.executions[key])

    def observe(self, workspace, delegation):
        return self.observations.get(delegation['delegation_id'],
            {'sequence': 0, 'state': 'running', 'summary': '', 'delivery': None})

    def control(self, workspace, delegation, kind, operation_id):
        self.revoked.append((delegation['delegation_id'], kind, operation_id))
        return {'sequence': 1, 'state': 'cancelled' if kind == 'cancel' else 'paused',
                'summary': '', 'delivery': None}


def setup(mode='single'):
    s = ControlService(MemoryStore(), now=lambda: NOW)
    body = request()
    body['tasks'][0]['mode'] = mode
    g = s.create('a', body)
    g = s.command('a', command(g, 'delegate_next', 'dispatch'))['goal']
    return s, g, Agent()


def test_replay_after_agent_admitted_before_control_binding_does_not_duplicate():
    s, g, agent = setup()
    original_bind = s.bind
    def lost_ack(*args, **kwargs):
        raise OSError('crash after Agent admission')
    s.bind = lost_ack
    assert reconcile(s, agent)['errors'] == 1
    s.bind = original_bind
    assert reconcile(s, agent)['errors'] == 0
    assert reconcile(s, agent)['errors'] == 0
    assert len(agent.executions) == 1
    current = s.read('a', g['goal_id'])
    assert current['tasks'][0]['state'] == 'running'
    assert current['tasks'][0]['delegation']['binding'] == next(iter(agent.executions.values()))


def test_cancel_before_binding_still_revokes_exact_admitted_execution():
    s, g, agent = setup()
    original = s.bind
    def race(workspace, goal_id, delegation_id, binding):
        current = s.read(workspace, goal_id)
        s.command(workspace, command(current, 'cancel', 'cancel'))
        return original(workspace, goal_id, delegation_id, binding)
    s.bind = race
    reconcile(s, agent)
    s.bind = original
    reconcile(s, agent)
    current = s.read('a', g['goal_id'])
    assert current['state'] == 'cancelled'
    assert len(agent.executions) == 1
    assert agent.revoked[0][1] == 'cancel'


def test_cancel_before_any_agent_admission_never_starts_execution():
    s, g, agent = setup()
    s.command('a', command(g, 'cancel', 'cancel-before-admission'))
    reconcile(s, agent)
    assert agent.executions == {}
    assert s.read('a', g['goal_id'])['state'] == 'cancelled'


def test_progress_is_monotone_and_delivery_does_not_imply_acceptance():
    s, g, agent = setup()
    reconcile(s, agent)
    d = s.read('a', g['goal_id'])['tasks'][0]['delegation']
    observation = {'sequence': 3, 'state': 'running', 'summary': 'Saved draft', 'delivery': None}
    agent.observations[d['delegation_id']] = observation
    reconcile(s, agent)
    assert s.read('a', g['goal_id'])['tasks'][0]['observation'] == observation
    # A stale poll cannot erase newer progress.
    agent.observations[d['delegation_id']] = {**observation, 'sequence': 2}
    reconcile(s, agent)
    assert s.read('a', g['goal_id'])['tasks'][0]['observation']['sequence'] == 3
    agent.observations[d['delegation_id']] = {'sequence': 4, 'state': 'completed',
        'summary': 'Saved', 'delivery': {'answer_ref': 'answer-1', 'products': [], 'status': 'completed'}}
    reconcile(s, agent)
    current = s.read('a', g['goal_id'])
    assert current['tasks'][0]['state'] == 'delivered'
    assert current['acceptance'] is None


def test_binding_and_same_sequence_content_changes_are_rejected():
    s, g, agent = setup()
    reconcile(s, agent)
    d = s.read('a', g['goal_id'])['tasks'][0]['delegation']
    with pytest.raises(Conflict):
        s.bind('a', g['goal_id'], d['delegation_id'], {'thread_id': 'forged', 'work_id': 'forged'})
    s.observe('a', g['goal_id'], d['delegation_id'],
              {'sequence': 2, 'state': 'running', 'summary': 'first', 'delivery': None})
    with pytest.raises(Conflict):
        s.observe('a', g['goal_id'], d['delegation_id'],
                  {'sequence': 2, 'state': 'running', 'summary': 'changed', 'delivery': None})


def test_deadline_before_binding_revokes_intent_without_new_admission():
    s, g, agent = setup()
    s.now = lambda: NOW.replace(year=2100)
    reconcile(s, agent)
    current = s.read('a', g['goal_id'])
    assert agent.executions == {}
    assert current['state'] == 'paused'
    assert current['reason'] == 'deadline_exhausted'


def test_deadline_after_lost_binding_ack_revokes_original_operation():
    s, g, agent = setup()
    d = s.delegation_request('a', g['goal_id'], g['tasks'][0]['delegation']['delegation_id'])
    agent.delegate('a', d)  # Agent admitted; Control process lost the response.
    s.now = lambda: NOW.replace(year=2100)
    reconcile(s, agent)
    assert len(agent.executions) == 1
    assert agent.revoked[0][0] == d['delegation_id']
    assert s.read('a', g['goal_id'])['state'] == 'paused'


@pytest.mark.parametrize('mode', ['single', 'goal'])
def test_deadline_revokes_bound_execution_before_admitting_late_delivery(mode):
    s, g, agent = setup(mode)
    reconcile(s, agent)
    bound = s.read('a', g['goal_id'])
    d = bound['tasks'][0]['delegation']
    # Deadline belongs to Control even when single-shot Agent execution has no
    # inner /goal deadline. A late completion is a stop ack, never a delivery.
    agent.observations[d['delegation_id']] = {'sequence': 1, 'state': 'completed',
        'summary': 'late result', 'delivery': {'answer_ref': 'late', 'products': [], 'status': 'completed'}}
    s.now = lambda: NOW.replace(year=2100)
    reconcile(s, agent)
    current = s.read('a', g['goal_id'])
    assert current['state'] == 'paused'
    assert current['reason'] == 'deadline_exhausted'
    assert current['tasks'][0]['delivery'] is None
    assert current['tasks'][0]['state'] == 'cancelled'
    assert agent.revoked[0][:2] == (d['delegation_id'], 'cancel')
    assert len(agent.executions) == current['delegations_admitted'] == 1
