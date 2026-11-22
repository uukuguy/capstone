from tools.ci_scope import classify


def test_mission_gate_covers_only_organization_and_direct_consumers():
    paths = ['packages/capstone-control/src/capstone_control/mission.py',
             'packages/capstone-agent/src/capstone_agent/native_mission.py',
             'packages/capstone-agent/tests/test_delegation_resources.py',
             'docs/superpowers/plans/2026-11-23-execution-continuity-remediation.md',
             'packages/capstone-app/src/missions.ts']
    assert classify(paths) == 'mission-conversation'
    assert classify(paths, target='main') == 'release'
    assert classify(paths + ['packages/grid-simulator/src/new.py']) != 'mission-conversation'
    assert classify(paths + ['packages/capstone-app/src/Unrelated.tsx']) != 'mission-conversation'


def test_mission_entry_changes_use_the_mission_conversation_gate():
    paths = [
        'packages/capstone-agent/src/capstone_agent/native_mission.py',
        'packages/capstone-agent/src/capstone_agent/general_pi_server.py',
        'packages/capstone-agent/tests/test_native_mission.py',
        'packages/capstone-agent/tests/test_general_pi_server.py',
        'configs/development/mission-conversation-gate.json',
        'tools/tests/test_ci_mission_conversation.py',
        'tools/ci_scope.py',
    ]
    assert classify(paths) == 'mission-conversation'
    assert classify(paths + ['packages/grid-simulator/src/new.py']) != 'mission-conversation'
