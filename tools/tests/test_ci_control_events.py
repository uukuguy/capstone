from tools.ci_scope import classify


def test_events_gate_is_limited_to_control_and_its_http_adapter():
    paths = ['packages/capstone-control/src/capstone_control/events.py',
             'packages/capstone-control/src/capstone_control/store.py',
             'packages/capstone-control/src/capstone_control/service.py',
             'packages/capstone-agent/src/capstone_agent/control_host.py',
             'tools/ci_scope.py', '.github/workflows/verify.yml']
    assert classify(paths) == 'control-events'
    assert classify(paths, target='main') == 'release'
    assert classify(paths + ['packages/capstone-agent/src/capstone_agent/thread_worker.py']) != 'control-events'
    assert classify(paths + ['packages/capstone-app/src/App.tsx']) != 'control-events'
