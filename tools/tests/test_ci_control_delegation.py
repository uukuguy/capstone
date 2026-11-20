from tools.ci_scope import classify


def test_control_delegation_gate_is_bounded_to_implementation_and_consumers():
    paths = ['packages/capstone-control/src/capstone_control/service.py',
             'packages/capstone-agent/src/capstone_agent/agent_delegation.py',
             'packages/capstone-agent/pyproject.toml', 'packages/pypsa-agent/uv.lock',
             'Dockerfile', 'pyrightconfig.json', 'packages/capstone-app/src/ControlGoalPanel.tsx']
    assert classify(paths) == 'control-delegation'
    assert classify(paths, target='main') == 'release'
    assert classify(paths + ['packages/grid-simulator/src/grid_simulator/engine.py']) != 'control-delegation'


def test_organizer_recovery_runs_control_delegation_gate():
    paths = [
        'packages/capstone-control/src/capstone_control/mission_reviews.py',
        'packages/capstone-control/src/capstone_control/service.py',
        'packages/capstone-control/tests/test_mission_reviews.py',
        'packages/capstone-agent/src/capstone_agent/mission_continuation.py',
        'packages/capstone-agent/src/capstone_agent/thread_worker.py',
        'packages/capstone-agent/tests/test_mission_continuation.py',
        'packages/capstone-agent/tests/test_thread_worker.py',
    ]
    assert classify(paths) == 'control-delegation'
    assert classify(paths + ['packages/grid-simulator/src/grid_simulator/engine.py']) != 'control-delegation'
