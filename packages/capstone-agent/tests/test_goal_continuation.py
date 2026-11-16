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
