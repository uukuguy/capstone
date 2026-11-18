"""Goal state is versioned data, never inferred from a completed Attempt."""
from dataclasses import replace

import pytest
from datetime import datetime, timezone

from capstone_agent.goal_mode import parse_goal_mode
from capstone_agent.thread_protocol import ThreadProtocolError, ThreadSnapshot
from capstone_agent.thread_service import InMemoryThreadService, ThreadCreator


@pytest.fixture
def goal():
    return {'schema': 'capstone-work-goal/1', 'objective': 'Produce a reviewed report',
            'objective_revision': 1, 'generation': 1, 'state': 'ready', 'reason': None,
            'max_attempts': 4, 'attempts_admitted': 0,
            'deadline_at': '2099-01-01T00:00:00Z', 'last_settled_attempt_id': None}


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


def test_pause_resume_preserves_consumed_budget(goal):
    from capstone_agent.goal_mode import control_goal
    now = datetime(2026, 11, 16, tzinfo=timezone.utc)
    original = {**goal, 'state': 'running', 'attempts_admitted': 2}
    paused = control_goal(original, 'pause_goal', {}, now=now)
    assert paused['state'] == 'paused'
    resumed = control_goal(paused, 'resume_goal', {}, now=now)
    assert resumed['state'] == 'ready'
    assert resumed['attempts_admitted'] == 2
    assert original['state'] == 'running'


@pytest.mark.parametrize('patch', [{'attempts_admitted': 4},
    {'deadline_at': '2000-01-01T00:00:00Z'}, {'state': 'cancelled'}])
def test_resume_cannot_bypass_limits_or_terminal_state(goal, patch):
    from capstone_agent.goal_mode import control_goal
    with pytest.raises(ValueError):
        control_goal({**goal, 'state': 'paused', 'reason': 'user_pause', **patch},
                     'resume_goal', {}, now=datetime(2026, 11, 16, tzinfo=timezone.utc))


def test_revision_invalidates_prior_generation_without_resetting_budget(goal):
    from capstone_agent.goal_mode import control_goal
    revised = control_goal({**goal, 'attempts_admitted': 2}, 'revise_goal_objective',
        {'objective': 'Updated report'}, now=datetime(2026, 11, 16, tzinfo=timezone.utc))
    assert revised['generation'] == revised['objective_revision'] == 2
    assert revised['attempts_admitted'] == 2
    assert revised['state'] == 'paused'


def test_work_goal_controls_persist_without_admitting_execution(goal):
    from capstone_agent.thread_work import apply_work
    snapshot = saved_work()
    work = snapshot.works[0]
    command = {'kind': 'start_goal', 'run_id': None,
        'target': {'id': work['work_id'], 'expected_revision': work['revision']},
        'payload': {'objective': work['goal'], 'max_attempts': 4,
                    'deadline_at': '2099-01-01T00:00:00Z'}}
    updated, rejection, result = apply_work(snapshot, command)
    assert rejection is None
    assert updated.current_attempt is None
    assert result['goal_mode']['state'] == 'ready'
    assert ThreadSnapshot.from_document(updated.to_document()) == updated
    command.update(kind='pause_goal', payload={}, target={**command['target'],
        'expected_revision': result['revision']})
    paused, rejection, result = apply_work(updated, command)
    assert rejection is None
    assert result['goal_mode']['state'] == 'paused'
    assert snapshot.works[0].get('goal_mode') is None


def test_goal_commands_use_service_idempotency_and_revision_checks():
    snapshot = saved_work()
    store = InMemoryThreadService(snapshot)
    work = snapshot.works[0]
    start = {'schema': 'capstone-command/2', 'command_id': 'cmd_start_goal',
        'idempotency_key': 'key_start_goal', 'thread_id': snapshot.thread_id,
        'kind': 'start_goal', 'target': {'kind': 'work', 'id': work['work_id'],
        'expected_revision': work['revision']}, 'payload': {'objective': work['goal'],
        'max_attempts': 3, 'deadline_at': '2099-01-01T00:00:00Z'}}
    receipt = store.submit_command(start)
    assert receipt.status == 'accepted'
    assert store.submit_command(start) == receipt
    restored = store.snapshot(snapshot.thread_id)
    assert restored.works[0]['goal_mode']['max_attempts'] == 3
    pause = {**start, 'command_id': 'cmd_pause_goal', 'idempotency_key': 'key_pause_goal',
             'kind': 'pause_goal', 'payload': {}}
    assert store.submit_command(pause).rejection == 'revision_conflict'
    pause['target'] = {**pause['target'], 'expected_revision': restored.works[0]['revision']}
    # Rejected commands have durable receipts too; a corrected request needs a new identity.
    pause.update(command_id='cmd_pause_corrected', idempotency_key='key_pause_corrected')
    assert store.submit_command(pause).status == 'accepted'
    assert store.snapshot(snapshot.thread_id).works[0]['goal_mode']['state'] == 'paused'


@pytest.mark.parametrize('command_kind', ['start_goal', 'resume_goal'])
def test_goal_controls_never_mutate_frozen_active_attempt(goal, command_kind):
    from capstone_agent.thread_work import apply_work
    from capstone_agent.thread_protocol import AttemptSnapshot
    snapshot = saved_work()
    work = {**snapshot.works[0], 'goal_mode': goal}
    snapshot = replace(snapshot, works=(work,),
        current_attempt=AttemptSnapshot('turn_active', 'attempt_active', 'accepted', None, 'capstone'))
    command = {'kind': command_kind, 'run_id': None,
        'target': {'id': work['work_id'], 'expected_revision': work['revision']}, 'payload': {}}
    unchanged, rejection, _ = apply_work(snapshot, command)
    assert unchanged == snapshot
    assert rejection == 'attempt_in_progress'


@pytest.mark.parametrize('kind', ['pause_goal', 'cancel_goal', 'revise_goal_objective'])
def test_active_goal_control_is_deferred_to_terminal_boundary(goal, kind):
    from capstone_agent.thread_work import apply_work, transition_work
    from capstone_agent.thread_protocol import AttemptSnapshot
    from capstone_agent.enterprise_context import TaskContext
    snapshot = saved_work()
    work = {**snapshot.works[0], 'goal_mode': {**goal, 'state': 'running'},
            'latest_attempt_id': 'attempt_active'}
    snapshot = replace(snapshot, works=(work,), current_attempt=AttemptSnapshot(
        'turn_active', 'attempt_active', 'running', None, 'capstone'))
    payload = {'objective': 'New objective'} if kind == 'revise_goal_objective' else {}
    updated, rejection, changed = apply_work(snapshot, {'kind': kind, 'run_id': None,
        'target': {'id': work['work_id'], 'expected_revision': work['revision']}, 'payload': payload})
    assert rejection is None
    assert changed['cancel_requested'] is True
    assert changed['task_context'] == work['task_context']
    assert changed['goal'] == work['goal']
    settled, result = transition_work(updated, TaskContext.from_document(work['task_context']),
                                      'attempt_active', 'cancelled')
    assert 'pending_goal_control' not in result
    assert result['goal_mode']['state'] == ('cancelled' if kind == 'cancel_goal' else 'paused')
    if kind == 'revise_goal_objective':
        assert result['goal'] == 'New objective'
    assert ThreadSnapshot.from_document(settled.to_document()) == settled


def test_service_pause_requests_worker_cancel_and_settles_goal(goal):
    from test_thread_work_execution import professional_snapshot, save_work, command
    store = InMemoryThreadService(professional_snapshot())
    work = save_work(store, 'thr_work_exec')
    start = command(store, 'thr_work_exec', 'start_work', 'execute',
                    work_id=work['work_id'], revision=work['revision'])
    assert store.submit_command(start).status == 'accepted'
    claim = store.claim_attempt('worker', 30)
    assert claim is not None
    # Seed goal state to exercise the running boundary independently of start admission.
    work = dict(store._snapshot.works[0])
    work['goal_mode'] = {**goal, 'objective': work['goal'], 'state': 'running'}
    store._snapshot = replace(store._snapshot, works=(work,))
    pause = command(store, 'thr_work_exec', 'pause_goal', 'pause_running',
                    work_id=work['work_id'], revision=work['revision'])
    assert store.submit_command(pause).status == 'accepted'
    assert store.cancel_requested(claim)
    store.finish_attempt(claim, phase='cancelled', payload={})
    restored = store.snapshot('thr_work_exec')
    assert restored.works[0]['goal_mode']['state'] == 'paused'
    assert restored.current_attempt is None


def test_attempt_boundary_does_not_complete_goal_without_receipt(goal):
    from capstone_agent.thread_work import transition_work
    from capstone_agent.enterprise_context import TaskContext
    snapshot = saved_work()
    work = {**snapshot.works[0], 'goal_mode': {**goal, 'state': 'running', 'attempts_admitted': 1}}
    snapshot = replace(snapshot, works=(work,))
    updated, result = transition_work(snapshot, TaskContext.from_document(work['task_context']),
                                      'attempt_one', 'completed')
    assert result['status'] == 'completed'
    assert result['goal_mode']['state'] == 'paused'
    assert result['goal_mode']['reason'] == 'goal_receipt_missing'
    assert result['goal_mode']['last_settled_attempt_id'] == 'attempt_one'


def test_goal_attempt_admission_consumes_budget_once(goal):
    from capstone_agent.thread_work import create_attempt
    snapshot = saved_work()
    work = {**snapshot.works[0], 'goal_mode': goal}
    snapshot = replace(snapshot, works=(work,))
    updated, attempt, _, _ = create_attempt(snapshot, work)
    assert work['goal_mode']['attempts_admitted'] == 1
    assert work['goal_mode']['state'] == 'running'
    with pytest.raises(ThreadProtocolError):
        create_attempt(updated, work)


def test_revise_discards_old_continuation(goal):
    from capstone_agent.thread_work import apply_work
    snapshot = saved_work()
    work = {**snapshot.works[0], 'goal_mode': goal, 'goal_continuation': {
        'generation': 1, 'predecessor_attempt_id': 'attempt_old', 'next_instruction': 'Old step'}}
    snapshot = replace(snapshot, works=(work,))
    updated, rejection, result = apply_work(snapshot, {'kind': 'revise_goal_objective',
        'run_id': None, 'target': {'id': work['work_id'], 'expected_revision': work['revision']},
        'payload': {'objective': 'New report'}})
    assert rejection is None
    assert 'goal_continuation' not in result
    assert ThreadSnapshot.from_document(updated.to_document()) == updated


def test_terminal_goal_proposal_is_saved_with_work_state(goal):
    from capstone_agent.goal_receipts import apply_terminal_goal_proposal
    from capstone_agent.enterprise_context import TaskContext
    snapshot = saved_work()
    work = {**snapshot.works[0], 'goal_mode': {**goal, 'state': 'running', 'attempts_admitted': 1}}
    snapshot = replace(snapshot, works=(work,))
    progress = {'schema': 'capstone-work-goal-proposal/1', 'disposition': 'continue',
        'summary': 'Draft ready', 'next_instruction': 'Review draft',
        'waiting_reason': None, 'product_refs': []}
    updated = apply_terminal_goal_proposal(snapshot, TaskContext.from_document(work['task_context']),
        'attempt_one', progress, saved_product_refs=(), delivery_saved=True)
    assert updated.works[0]['goal_mode']['state'] == 'ready'
    assert updated.works[0]['goal_continuation']['next_instruction'] == 'Review draft'
    assert updated.works[0]['goal_continuation']['predecessor_attempt_id'] == 'attempt_one'
    assert ThreadSnapshot.from_document(updated.to_document()) == updated


@pytest.mark.parametrize('with_product', [False, True])
def test_service_terminal_commits_continuation_with_attempt(goal, with_product):
    from test_thread_work_execution import professional_snapshot, save_work, command
    store = InMemoryThreadService(professional_snapshot())
    work = save_work(store, 'thr_work_exec')
    assert store.submit_command(command(store, 'thr_work_exec', 'start_work', 'run_goal',
        work_id=work['work_id'], revision=work['revision'])).status == 'accepted'
    claim = store.claim_attempt('worker', 30)
    work = dict(store._snapshot.works[0])
    work['goal_mode'] = {**goal, 'objective': work['goal'], 'state': 'running', 'attempts_admitted': 1}
    store._snapshot = replace(store._snapshot, works=(work,))
    progress = {'schema': 'capstone-work-goal-proposal/1', 'disposition': 'continue',
        'summary': 'Draft ready', 'next_instruction': 'Review draft',
        'waiting_reason': None, 'product_refs': []}
    if with_product:
        store.append_runtime_event(claim, event_type='native_artifact_published', payload={
            'artifact': {'artifact_id': 'artifact_draft', 'file_name': 'draft.md'}}, visibility='public')
        progress['product_refs'] = ['draft.md']
    restored = store.finish_attempt(claim, phase='completed',
        payload={'answer': 'Draft ready', 'goal_proposal': progress})
    assert restored.current_attempt is None
    assert restored.works[0]['goal_mode']['state'] == 'ready'
    assert restored.works[0]['goal_continuation']['predecessor_attempt_id'] == claim.attempt.attempt_id
    assert restored.works[0]['goal_continuation']['product_refs'] == progress['product_refs']


def test_start_goal_admits_first_attempt_through_existing_service():
    from test_thread_work_execution import professional_snapshot, save_work, command
    store = InMemoryThreadService(professional_snapshot())
    work = save_work(store, 'thr_work_exec')
    receipt = store.submit_command(command(store, 'thr_work_exec', 'start_goal', 'goal_start',
        work_id=work['work_id'], revision=work['revision'], payload={
        'objective': work['goal'], 'max_attempts': 3, 'deadline_at': '2099-01-01T00:00:00Z'}))
    assert receipt.status == 'accepted'
    claim = store.claim_attempt('worker', 30)
    assert claim is not None
    assert store.snapshot('thr_work_exec').works[0]['goal_mode']['attempts_admitted'] == 1


def test_goal_start_prepares_standard_input_submission(monkeypatch):
    import capstone_agent.thread_service as module
    from test_thread_work_execution import professional_snapshot, save_work
    store = InMemoryThreadService(professional_snapshot())
    work = save_work(store, 'thr_work_exec')
    observed = []
    def admission(snapshot, parsed, provider):
        observed.append(parsed)
        return {'input': {'kind': 'text', 'text': parsed['payload']['text']}}, None
    monkeypatch.setattr(module, 'admission_submission', admission)
    snapshot, submission, rejection = module._work_send_input(store.snapshot('thr_work_exec'), {
        'kind': 'start_goal', 'target': {'id': work['work_id']},
        'payload': {'objective': 'Review report'}}, None, None)
    assert rejection is None
    assert submission['input'] == {'kind': 'text', 'text': 'Review report'}
    assert observed


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
