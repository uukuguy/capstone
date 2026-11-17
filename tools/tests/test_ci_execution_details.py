from tools.ci_scope import classify


def test_execution_details_gate_has_a_bounded_app_scope():
    paths = ['packages/capstone-app/src/ExecutionDetails.tsx',
             'packages/capstone-app/src/CapstoneAssistantThread.tsx',
             'packages/capstone-app/src/ThreadWorkAdapter.tsx']
    assert classify(paths) == 'execution-details'
    assert classify(paths, target='main') == 'release'
    assert classify(paths + ['packages/capstone-agent/src/capstone_agent/harness.py']) != 'execution-details'
    assert classify(paths + ['packages/capstone-app/src/Unrelated.tsx']) != 'execution-details'
