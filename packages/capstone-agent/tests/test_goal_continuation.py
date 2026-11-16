from capstone_agent.goal_continuation import continuation_command


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
    first = store.claim_attempt('worker', 30)
    progress = {'schema': 'capstone-work-goal-proposal/1', 'disposition': 'continue',
        'summary': 'Draft saved', 'next_instruction': 'Review draft',
        'waiting_reason': None, 'product_refs': []}
    store.finish_attempt(first, phase='completed', payload={'answer': 'Draft', 'goal_proposal': progress})
    assert drain_goal_continuations(store) == 1
    assert drain_goal_continuations(store) == 0
    second = store.claim_attempt('worker', 30)
    assert second is not None and second.attempt.attempt_id != first.attempt.attempt_id
    assert 'Review draft' in second.instruction
    store.finish_attempt(second, phase='completed', payload={'answer': 'Reviewed report',
        'goal_proposal': {**progress, 'disposition': 'complete', 'next_instruction': None}})
    assert drain_goal_continuations(store) == 0
    goal = store.snapshot('thr_work_exec').works[0]['goal_mode']
    assert goal['state'] == 'completed'
    assert goal['attempts_admitted'] == 2
