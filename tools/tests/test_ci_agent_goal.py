from tools.ci_scope import classify


def test_agent_goal_gate_is_focused():
    paths = ['packages/capstone-agent/src/capstone_agent/goal_mode.py',
             'packages/capstone-agent/tests/test_goal_mode.py']
    assert classify(paths) == 'agent-goal'
    assert classify(paths, target='main') == 'release'
    assert classify(paths + ['packages/grid-simulator/src/grid_simulator/engine.py']) != 'agent-goal'



def test_session_goal_plan_uses_the_focused_gate():
    assert classify([
        'packages/capstone-agent/src/capstone_agent/session_goal_plan.py',
        'packages/capstone-agent/tests/test_session_goal_plan.py',
        'packages/capstone-agent/tests/test_harness.py',
        'packages/capstone-app/src/CapstoneAssistantThread.tsx',
    ]) == 'agent-goal'
