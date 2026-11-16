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
