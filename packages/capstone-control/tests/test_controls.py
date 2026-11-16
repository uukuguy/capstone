import pytest

from capstone_control.service import InvalidTransition
from capstone_control.reconcile import reconcile
from test_contracts import request
from test_service import command, service
from test_reconcile import Agent


def test_revision_revokes_old_generation_before_new_tasks_dispatch():
    s, agent = service(), Agent()
    goal = s.create('a', request())
    goal = s.command('a', command(goal, 'delegate_next', 'start'))['goal']
    reconcile(s, agent)
    goal = s.read('a', goal['goal_id'])
    old = goal['tasks'][0]['delegation']['delegation_id']
    payload = request()
    goal = s.command('a', command(goal, 'revise', 'revise',
        objective='A revised goal', acceptance_criteria=['New accepted report'], tasks=payload['tasks']))['goal']
    assert goal['state'] == 'revising'
    assert goal['objective_revision'] == 2
    with pytest.raises(InvalidTransition):
        s.command('a', command(goal, 'delegate_next', 'too-early'))
    reconcile(s, agent)
    goal = s.read('a', goal['goal_id'])
    assert goal['state'] == 'ready'
    assert goal['tasks'][0]['state'] == 'pending'
    assert goal['history'][0]['objective_revision'] == 1
    goal = s.command('a', command(goal, 'delegate_next', 'new-start'))['goal']
    assert goal['tasks'][0]['delegation']['delegation_id'] != old
    assert goal['delegations_admitted'] == 2
    with pytest.raises(InvalidTransition):
        s.deliver('a', goal['goal_id'], old, {'thread_id': 'old', 'work_id': 'old'},
                  {'answer_ref': 'old-answer', 'products': [], 'status': 'completed'})


def test_resume_paused_goal_mode_reuses_binding_without_resetting_budget():
    s, agent = service(), Agent()
    body = request()
    body['tasks'][0].update(mode='goal', max_attempts=3)
    goal = s.create('a', body)
    goal = s.command('a', command(goal, 'delegate_next', 'start'))['goal']
    reconcile(s, agent)
    goal = s.read('a', goal['goal_id'])
    binding = goal['tasks'][0]['delegation']['binding']
    goal = s.command('a', command(goal, 'pause', 'pause'))['goal']
    reconcile(s, agent)
    goal = s.read('a', goal['goal_id'])
    assert goal['state'] == 'paused'
    goal = s.command('a', command(goal, 'resume', 'resume'))['goal']
    assert goal['tasks'][0]['state'] == 'resume_requested'
    assert goal['tasks'][0]['delegation']['binding'] == binding
    assert goal['delegations_admitted'] == 1


def test_single_execution_resume_consumes_new_delegation_after_stop():
    s, agent = service(), Agent()
    goal = s.create('a', request())
    goal = s.command('a', command(goal, 'delegate_next', 'start'))['goal']
    reconcile(s, agent)
    goal = s.read('a', goal['goal_id'])
    old = goal['tasks'][0]['delegation']['delegation_id']
    s.command('a', command(goal, 'pause', 'pause'))
    reconcile(s, agent)
    goal = s.read('a', goal['goal_id'])
    goal = s.command('a', command(goal, 'resume', 'resume'))['goal']
    assert goal['tasks'][0]['state'] == 'pending'
    goal = s.command('a', command(goal, 'delegate_next', 'restart'))['goal']
    assert goal['delegations_admitted'] == 2
    assert goal['tasks'][0]['delegation']['delegation_id'] != old
    assert goal['tasks'][0]['delegation_history'][0]['delegation_id'] == old
