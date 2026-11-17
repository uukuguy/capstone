from copy import deepcopy

import pytest

from capstone_control.service import ControlService, Conflict
from test_contracts import request
from test_service import command, service, NOW


def test_events_are_durable_unique_and_bounded_to_a_snapshot():
    s = service()
    g = s.create('a', request())
    dispatch = command(g, 'delegate_next', 'dispatch')
    g = s.command('a', dispatch)['goal']
    s.command('a', dispatch)
    s.create('a', request())
    first = s.read_events('a', g['goal_id'], limit=1)
    assert first['through_sequence'] == 2
    assert first['has_more']
    assert first['history_complete']
    assert first['events'][0]['kind'] == 'goal.created'
    d = g['tasks'][0]['delegation']['delegation_id']
    binding = {'thread_id': 'thread-1', 'work_id': 'work-1'}
    s.bind('a', g['goal_id'], d, binding)
    s.bind('a', g['goal_id'], d, binding)
    second = s.read_events('a', g['goal_id'], after=first['next_sequence'], through=2)
    assert [e['kind'] for e in second['events']] == ['command.delegate_next']
    assert not second['has_more']
    restarted = ControlService(s.store, now=lambda: NOW)
    events = restarted.read_events('a', g['goal_id'])['events']
    assert [e['sequence'] for e in events] == [1, 2, 3]
    assert len({e['event_id'] for e in events}) == 3
    assert events[-1]['task_changes'][0]['after']['binding'] == binding
    assert '_event_sequence' not in s.read('a', g['goal_id'])
    with pytest.raises(KeyError):
        s.read_events('b', g['goal_id'])


def test_stale_observation_and_conflicts_do_not_append():
    s = service()
    g = s.create('a', request())
    g = s.command('a', command(g, 'delegate_next', 'dispatch'))['goal']
    d = g['tasks'][0]['delegation']['delegation_id']
    s.bind('a', g['goal_id'], d, {'thread_id': 'thread-1', 'work_id': 'work-1'})
    obs = {'sequence': 4, 'state': 'running', 'summary': '', 'delivery': None}
    s.observe('a', g['goal_id'], d, obs)
    before = s.read_events('a', g['goal_id'])
    s.observe('a', g['goal_id'], d, obs)
    s.observe('a', g['goal_id'], d, {**obs, 'sequence': 3})
    with pytest.raises(Conflict):
        s.observe('a', g['goal_id'], d, {**obs, 'state': 'waiting'})
    assert s.read_events('a', g['goal_id']) == before
    assert before['events'][-1]['observation_sequence'] == 4


def test_legacy_history_is_not_fabricated():
    s = service()
    g = s.create('a', request())
    legacy = deepcopy(s.store._values[('a', g['goal_id'])])
    legacy.pop('_event_sequence')
    legacy.pop('_event_revision')
    legacy.pop('_event_history_complete')
    s.store._values[('a', g['goal_id'])] = legacy
    s.store._events.clear()
    empty = s.read_events('a', g['goal_id'])
    assert empty['events'] == [] and not empty['history_complete']
    s.command('a', command(g, 'pause', 'pause'))
    page = s.read_events('a', g['goal_id'])
    assert not page['history_complete']
    assert page['first_recorded_goal_revision'] == 2
    assert len(page['events']) == 1


@pytest.mark.parametrize('kwargs', [dict(limit=0), dict(limit=101), dict(after=-1),
    dict(after=True), dict(through=2), dict(after=2), dict(through=-1)])
def test_invalid_page_boundaries(kwargs):
    s = service()
    g = s.create('a', request())
    with pytest.raises(ValueError):
        s.read_events('a', g['goal_id'], **kwargs)


def test_event_failure_rolls_back_state_and_operation(monkeypatch):
    import capstone_control.store as stores
    s = service()
    g = s.create('a', request())
    events = s.read_events('a', g['goal_id'])
    def fail(*args):
        raise OSError('event storage failed')
    with monkeypatch.context() as patch:
        patch.setattr(stores, 'build_event', fail)
        with pytest.raises(OSError):
            s.command('a', command(g, 'pause', 'pause'))
    assert s.read('a', g['goal_id']) == g
    assert s.read_events('a', g['goal_id']) == events
    assert s.command('a', command(g, 'pause', 'pause'))['goal']['state'] == 'paused'


def test_revise_keeps_old_binding_and_new_task_versions():
    s = service()
    g = s.create('a', request())
    g = s.command('a', command(g, 'delegate_next', 'dispatch'))['goal']
    d = g['tasks'][0]['delegation']['delegation_id']
    binding = {'thread_id': 'thread-old', 'work_id': 'work-old'}
    g = s.bind('a', g['goal_id'], d, binding)
    payload = {k: request()[k] for k in ('objective', 'acceptance_criteria', 'tasks')}
    g = s.command('a', command(g, 'revise', 'revise', **payload))['goal']
    assert g['state'] == 'revising'
    event = s.read_events('a', g['goal_id'])['events'][-1]
    assert event['task_changes'][0]['after']['state'] == 'revoke_requested'
    s.observe('a', g['goal_id'], d, dict(sequence=1, state='cancelled', summary='', delivery=None))
    event = s.read_events('a', g['goal_id'])['events'][-1]
    change = next(c for c in event['task_changes'] if c['before']['binding'])
    assert change['before']['binding'] == binding
    assert change['before']['objective_revision'] == 1
    assert change['after']['objective_revision'] == 2
    assert change['after']['binding'] is None
    assert change['after']['task_revision'] == 2


def test_old_writer_gap_is_reported_without_changing_pinned_coverage():
    s = service()
    g = s.create('a', request())
    # An old writer preserves unknown fields but cannot append events.
    def old_write(value):
        value['revision'] += 1
        value['state'] = 'paused'
        return value, None
    s.store.transact('a', g['goal_id'], old_write)
    g = s.read('a', g['goal_id'])
    s.command('a', command(g, 'resume', 'resume'))
    page = s.read_events('a', g['goal_id'])
    assert not page['history_complete']
    assert page['events'][-1]['missing_goal_revisions'] == {'from': 2, 'through': 2}
    assert s.read_events('a', g['goal_id'], through=1)['history_complete']
