from capstone_agent.goal_continuation import continuation_command
from test_thread_postgres import postgres_thread_service


def test_continuation_command_is_stable_and_version_bound():
    work = {'work_id': 'work_one', 'revision': 4,
        'goal_mode': {'state': 'ready', 'generation': 2},
        'goal_continuation': {'generation': 2, 'predecessor_attempt_id': 'attempt_one',
                              'next_instruction': 'Review draft'}}
    first = continuation_command('thr_one', work)
    assert first == continuation_command('thr_one', work)
    assert first['kind'] == 'continue_goal'
    assert first['target']['expected_revision'] == 4
    assert first['payload'] == {'predecessor_attempt_id': 'attempt_one', 'generation': 2}
    work['goal_mode']['state'] = 'paused'
    assert continuation_command('thr_one', work) is None


def test_drain_submits_only_ready_idle_work():
    from types import SimpleNamespace
    from capstone_agent.goal_continuation import drain_goal_continuations
    work = {'work_id': 'work_one', 'revision': 4,
        'goal_mode': {'state': 'ready', 'generation': 2},
        'goal_continuation': {'generation': 2, 'predecessor_attempt_id': 'attempt_one',
                              'next_instruction': 'Review draft'}}
    commands = []
    class Service:
        def goal_continuation_candidates(self, limit):
            return ['thr_one']
        def snapshot(self, identity):
            return SimpleNamespace(current_attempt=None, works=[work])
        def submit_command(self, command):
            commands.append(command)
            return SimpleNamespace(status='accepted')
    assert drain_goal_continuations(Service()) == 1
    assert commands[0]['kind'] == 'continue_goal'


def _review_saved_step(store, claim, *, complete=False):
    from capstone_agent.session_goal_plan import drain_goal_step_reviews

    progress = {'schema': 'capstone-work-goal-proposal/1', 'disposition': 'continue',
        'summary': 'Draft saved', 'next_instruction': 'Review draft',
        'waiting_reason': None, 'product_refs': []}
    if complete:
        store.append_runtime_event(claim, event_type='native_artifact_published',
            payload={'artifact': {'artifact_id': 'report_product', 'file_name': 'report.md'}})
        progress.update(disposition='complete', next_instruction=None,
                        criteria=[{'index': 0, 'verdict': 'met', 'refs': ['report.md']}])
    store.finish_attempt(claim, phase='completed', payload={'answer': 'Reviewed' if complete else 'Draft'})
    assert drain_goal_step_reviews(store, reviewer=lambda *_: progress) == 1


def _admit_initial_plan(store):
    from capstone_agent.session_goal_plan import drain_initial_goal_plans

    assert drain_initial_goal_plans(store, planner=lambda _: {
        'schema': 'capstone-session-goal-plan/1', 'criteria': ['Reviewed report'],
        'steps': [{'instruction': 'Write draft', 'expected_result': 'Draft'},
                  {'instruction': 'Review draft', 'expected_result': 'Report'}]}) == 1


def test_service_runs_two_attempts_without_another_user_instruction():
    from capstone_agent.thread_service import InMemoryThreadService
    from capstone_agent.goal_continuation import drain_goal_continuations
    from test_thread_work_execution import professional_snapshot, save_work, command
    store = InMemoryThreadService(professional_snapshot())
    work = save_work(store, 'thr_work_exec')
    start = command(store, 'thr_work_exec', 'start_goal', 'start',
        work_id=work['work_id'], revision=work['revision'], payload={
        'objective': 'Inspect the model', 'max_attempts': 3, 'deadline_at': '2099-01-01T00:00:00Z'})
    assert store.submit_command(start).status == 'accepted'
    _admit_initial_plan(store)
    first = store.claim_attempt('worker', 30)
    _review_saved_step(store, first)
    state = store.snapshot('thr_work_exec').works[0]['task_state']
    assert state['revision_ref'] == first.attempt.attempt_id
    projected = store.snapshot('thr_work_exec').to_document()['works'][0]['task_state']['workflow']
    assert projected['kind'] == 'goal'
    assert projected['step_index'] == 1
    assert drain_goal_continuations(store) == 1
    assert drain_goal_continuations(store) == 0
    second = store.claim_attempt('worker', 30)
    assert second is not None and second.attempt.attempt_id != first.attempt.attempt_id
    assert second.task_context.task_state_ref == state['revision_ref']
    assert 'Review draft' in second.instruction
    _review_saved_step(store, second, complete=True)
    assert drain_goal_continuations(store) == 0
    goal = store.snapshot('thr_work_exec').works[0]['goal_mode']
    assert goal['state'] == 'completed'
    assert goal['attempts_admitted'] == 2


def test_postgres_restart_and_concurrent_continuation(postgres_thread_service):
    from concurrent.futures import ThreadPoolExecutor
    from capstone_agent.thread_service import PostgresThreadService
    from capstone_agent.goal_continuation import drain_goal_continuations
    from test_thread_work_execution import professional_snapshot, save_work, command
    store, thread_id = postgres_thread_service
    store.create_thread(professional_snapshot(thread_id))
    work = save_work(store, thread_id)
    assert store.submit_command(command(store, thread_id, 'start_goal', 'start',
        work_id=work['work_id'], revision=work['revision'], payload={
        'objective': 'Inspect model', 'max_attempts': 3,
        'deadline_at': '2099-01-01T00:00:00Z'})).status == 'accepted'
    _admit_initial_plan(store)
    first = store.claim_attempt('worker', 30)
    _review_saved_step(store, first)
    restarted = PostgresThreadService(store.dsn)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(drain_goal_continuations, [store, restarted]))
    second = restarted.claim_attempt('worker_two', 30)
    assert second is not None
    assert restarted.claim_attempt('worker_three', 30) is None
    assert 'Review draft' in second.instruction
    _review_saved_step(restarted, second, complete=True)
    restored = PostgresThreadService(store.dsn).snapshot(thread_id)
    assert restored.works[0]['goal_mode']['state'] == 'completed'
    assert restored.works[0]['goal_mode']['attempts_admitted'] == 2

    from capstone_agent.task_handoff import freeze_task_handoff
    work = restored.works[0]
    source = {'thread_id': thread_id, 'work_id': work['work_id'], 'work_revision': work['revision'],
              'revision_ref': second.attempt.attempt_id}
    with store._connect() as connection:
        handoff = freeze_task_handoff(connection, {'thread_id': 'thr_distinct', 'workspace_name': 'enterprise'}, source)
    assert handoff['state']['workflow']['objective'] == 'Inspect model'
    assert handoff['state']['workflow']['plan']['steps'][0]['instruction'] == 'Write draft'


def test_recovered_goal_handoff_reply_preserves_saved_plan():
    from dataclasses import replace
    from capstone_agent.thread_service import InMemoryThreadService, _recover_workflow_delivery
    from capstone_agent.thread_work import settle_early_task_state
    from test_thread_work_execution import professional_snapshot, save_work, command

    store = InMemoryThreadService(professional_snapshot())
    thread_id = 'thr_work_exec'
    initial = save_work(store, thread_id)
    assert store.submit_command(command(store, thread_id, 'start_goal', 'start',
        work_id=initial['work_id'], revision=initial['revision'], payload={
            'objective': 'Inspect model', 'max_attempts': 3,
            'deadline_at': '2099-01-01T00:00:00Z'})).status == 'accepted'
    _admit_initial_plan(store)
    first = store.claim_attempt('worker', 30)
    _review_saved_step(store, first)
    ready = store.snapshot(thread_id)
    work = ready.works[0]
    assert store.submit_command(command(store, thread_id, 'pause_goal', 'pause',
        work_id=work['work_id'], revision=work['revision'])).status == 'accepted'
    paused = store.snapshot(thread_id).works[0]
    assert store.submit_command(command(store, thread_id, 'send_message', 'followup',
        work_id=paused['work_id'], revision=paused['revision'], payload={'text': 'Continue a separate task'})).status == 'accepted'
    claim = store.claim_attempt('worker', 30)
    attempt = replace(claim.attempt, phase='interrupted')
    source = {'thread_id': 'thr_other', 'work_id': 'work_other', 'work_revision': 3, 'revision_ref': 'attempt_other'}
    submission = {'_task_handoff': {**source, 'state': {}}}
    interrupted, payload = settle_early_task_state(
        replace(store.snapshot(thread_id), current_attempt=None), claim.task_context, attempt, submission)
    original = {'attempt_id': attempt.attempt_id, 'turn_id': attempt.turn_id,
                'task_context_snapshot': claim.task_context.to_document(), 'submission_snapshot': submission,
                'interrupted_work': payload['work']}
    restored, _ = _recover_workflow_delivery(interrupted, original, {'answer': 'Saved result'}, ())
    assert restored.works[0]['task_state']['execution']['phase'] == 'completed'
    assert restored.works[0]['task_state']['handoff'] == source
    assert restored.works[0]['goal_mode'] == paused['goal_mode']
    assert restored.works[0]['goal_plan'] == paused['goal_plan']
    assert 'goal_step_review' not in restored.works[0]
    advanced = replace(interrupted, works=({**interrupted.works[0], 'revision': payload['work']['revision'] + 1},))
    assert _recover_workflow_delivery(advanced, original, {'answer':'Saved result'}, ()) == (advanced, {})
