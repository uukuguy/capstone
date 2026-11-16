"""Goal state is versioned data, never inferred from a completed Attempt."""
from dataclasses import replace

import pytest

from capstone_agent.goal_mode import parse_goal_mode
from capstone_agent.thread_protocol import ThreadProtocolError, ThreadSnapshot
from capstone_agent.thread_service import InMemoryThreadService, ThreadCreator


@pytest.fixture
def goal():
    return {'schema': 'capstone-work-goal/1', 'objective': 'Produce a reviewed report',
            'objective_revision': 1, 'generation': 1, 'state': 'ready', 'reason': None,
            'max_attempts': 4, 'attempts_admitted': 0,
            'deadline_at': '2026-11-17T12:00:00Z', 'last_settled_attempt_id': None}


@pytest.mark.parametrize('field', ['objective_revision', 'generation', 'max_attempts'])
@pytest.mark.parametrize('value', [True, False, 0, -1, 1.5, '2', None])
def test_strict_positive_integer(goal, field, value):
    with pytest.raises(ValueError):
        parse_goal_mode({**goal, field: value})


@pytest.mark.parametrize('value', [True, -1, 5, '0'])
def test_consumed_budget_is_bounded(goal, value):
    with pytest.raises(ValueError):
        parse_goal_mode({**goal, 'attempts_admitted': value})


@pytest.mark.parametrize('deadline', ['2026-11-17', '2026-11-17T12:00:00',
    '2026-11-17T12:00:00+08:00', 'invalid', None])
def test_deadline_requires_utc_instant(goal, deadline):
    with pytest.raises(ValueError):
        parse_goal_mode({**goal, 'deadline_at': deadline})


def test_expired_deadline_is_readable_for_recovery(goal):
    expired = {**goal, 'deadline_at': '2000-01-01T00:00:00Z'}
    assert parse_goal_mode(expired) == expired


@pytest.mark.parametrize('patch', [{'extra': 1}, {'schema': 'unknown'},
    {'state': 'success'}, {'objective': ' '}, {'reason': {}},
    {'state': 'paused'}, {'state': 'waiting'}, {'last_settled_attempt_id': ''}])
def test_invalid_state_rejected(goal, patch):
    with pytest.raises(ValueError):
        parse_goal_mode({**goal, **patch})


def test_parser_returns_owned_value(goal):
    parsed = parse_goal_mode(goal)
    parsed['objective'] = 'changed'
    assert goal['objective'] == 'Produce a reviewed report'


def saved_work():
    class Store:
        def create_thread(self, snapshot):
            return snapshot
    snapshot = ThreadCreator(Store(), None).create(model_free=True)
    service = InMemoryThreadService(snapshot)
    receipt = service.submit_command({'schema': 'capstone-command/2', 'command_id': 'cmd_goal',
        'idempotency_key': 'key_goal', 'thread_id': snapshot.thread_id, 'kind': 'work_message',
        'target': {'kind': 'work', 'id': 'new', 'expected_revision': 0},
        'payload': {'text': 'Produce a reviewed report'}})
    assert receipt.status == 'accepted'
    return service.snapshot(snapshot.thread_id)


def test_goal_snapshot_roundtrip_and_legacy_compatibility(goal):
    snapshot = saved_work()
    assert ThreadSnapshot.from_document(snapshot.to_document()) == snapshot
    assert 'goal_mode' not in snapshot.works[0]
    snapshot = replace(snapshot, works=({**snapshot.works[0], 'goal_mode': goal},))
    restored = ThreadSnapshot.from_document(snapshot.to_document())
    assert restored == snapshot
    assert restored.works[0]['goal_mode'] is not goal


@pytest.mark.parametrize('patch', [{'objective': 'different'}, {'objective_revision': 2},
                                {'generation': False}])
def test_goal_snapshot_rejects_inconsistent_identity(goal, patch):
    snapshot = saved_work()
    work = {**snapshot.works[0], 'goal_mode': {**goal, **patch}}
    document = replace(snapshot, works=(work,)).to_document()
    with pytest.raises(ThreadProtocolError):
        ThreadSnapshot.from_document(document)


@pytest.mark.parametrize('kind', ['revise_goal', 'work_message', 'start_work', 'send_message'])
def test_legacy_commands_cannot_bypass_goal_control(goal, kind):
    from capstone_agent.thread_work import apply_work
    snapshot = saved_work()
    work = {**snapshot.works[0], 'goal_mode': goal}
    snapshot = replace(snapshot, works=(work,))
    command = {'kind': kind, 'run_id': None,
        'target': {'id': work['work_id'], 'expected_revision': work['revision']},
        'payload': {} if kind == 'start_work' else {'text': 'Change the objective'}}
    updated, rejection, result = apply_work(snapshot, command)
    assert rejection == 'goal_control_required'
    assert updated == snapshot
    assert result is None
