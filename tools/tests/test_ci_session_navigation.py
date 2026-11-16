from tools.ci_scope import classify


def test_navigation_gate_covers_shared_catalog_consumers_without_solver_scope():
    paths = ['packages/capstone-app/src/SessionNavigation.tsx',
             'packages/capstone-app/src/sessionCatalog.ts',
             'packages/capstone-app/src/SessionNavigation.test.tsx',
             'configs/development/session-navigation-gate.json',
             'tools/test_session_navigation.sh',
             'tools/tests/test_ci_session_navigation.py']
    assert classify(paths) == 'session-navigation'
    assert classify(paths, target='main') == 'release'
    assert classify(paths + ['packages/capstone-agent/src/capstone_agent/thread_service.py']) != 'session-navigation'
    assert classify(paths + ['packages/capstone-app/src/OtherPanel.tsx']) != 'session-navigation'
