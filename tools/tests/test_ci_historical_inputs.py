from tools.ci_scope import classify


def test_historical_input_receipts_have_a_focused_gate():
    paths = ['packages/capstone-agent/src/capstone_agent/historical_input_receipts.py',
             'packages/capstone-agent/src/capstone_agent/thread_service.py',
             'packages/capstone-app/src/taskProgress.ts']
    assert classify(paths) == 'historical-inputs'
    assert classify(paths, target='main') == 'release'
    assert classify(paths + ['packages/grid-simulator/src/grid_simulator/engine.py']) != 'historical-inputs'
    assert classify(paths[1:]) != 'historical-inputs'
