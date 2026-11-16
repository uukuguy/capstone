from tools.ci_scope import classify


def test_pin_scope_is_focused_and_does_not_hide_unrelated_changes():
    paths = ['packages/capstone-agent/src/capstone_agent/session_pins.py',
             'packages/capstone-agent/tests/test_session_pins.py',
             'packages/capstone-app/src/sessionNavigationState.ts',
             'docs/status/VERSION-CONTROL.md']
    assert classify(paths) == 'session-pins'
    assert classify(paths, target='main') == 'release'
    assert classify(paths + ['packages/grid-simulator/src/grid_simulator/engine.py']) != 'session-pins'
