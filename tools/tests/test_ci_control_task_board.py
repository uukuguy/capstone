from tools.ci_scope import classify


def test_control_task_board_gate_is_limited_to_app_and_direct_consumers():
    paths = ['packages/capstone-app/src/ControlTaskBoard.tsx',
             'packages/capstone-app/src/ControlGoalPanel.tsx',
             'packages/capstone-app/src/ControlTaskBoard.test.tsx',
             'tools/test_control_task_board.sh',
             'tools/tests/test_ci_control_task_board.py',
             'tools/ci_scope.py', '.github/workflows/verify.yml']
    assert classify(paths) == 'control-task-board'
    assert classify(paths, target='main') == 'release'
    assert classify(paths + ['packages/capstone-agent/src/capstone_agent/control_host.py']) != 'control-task-board'
    assert classify(paths + ['packages/capstone-app/src/OtherPanel.tsx']) != 'control-task-board'
