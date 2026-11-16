from tools.ci_scope import classify


def test_control_delegation_gate_is_bounded_to_implementation_and_consumers():
    paths = ['packages/capstone-control/src/capstone_control/service.py',
             'packages/capstone-agent/src/capstone_agent/agent_delegation.py',
             'packages/capstone-agent/pyproject.toml', 'packages/pypsa-agent/uv.lock',
             'Dockerfile', 'packages/capstone-app/src/ControlGoalPanel.tsx']
    assert classify(paths) == 'control-delegation'
    assert classify(paths, target='main') == 'release'
    assert classify(paths + ['packages/grid-simulator/src/grid_simulator/engine.py']) != 'control-delegation'
