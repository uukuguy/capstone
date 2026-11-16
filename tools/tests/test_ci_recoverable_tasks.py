from tools.ci_scope import classify


def test_recoverable_tasks_scope_covers_execution_and_direct_consumers():
    paths = [
        'deploy/general-pi.Dockerfile',
        'packages/capstone-agent/src/capstone_agent/native_execution_authority.py',
        'packages/capstone-agent/src/capstone_agent/general_pi_executor.py',
        'packages/capstone-agent/tests/test_native_owned_execution.py',
        'docs/status/CURRENT-STATE.md',
    ]
    assert classify(paths) == 'recoverable-tasks'
    assert classify(paths, target='main') == 'release'
    assert classify(paths, release=True) == 'release'
    assert classify(paths[:-2]) != 'recoverable-tasks'
    assert classify(paths + ['packages/grid-simulator/src/grid_simulator/engine.py']) != 'recoverable-tasks'
