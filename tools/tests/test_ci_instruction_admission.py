from tools.ci_scope import classify


def test_instruction_gate_excludes_unrelated_domain_and_release_work():
    paths = ['packages/capstone-agent/src/capstone_agent/instruction_queue.py',
             'packages/capstone-app/src/InstructionStatus.tsx']
    assert classify(paths) == 'instruction-admission'
    assert classify(paths, target='main') == 'release'
    assert classify(paths + ['packages/pandapower-domain-pack/src/new.py']) != 'instruction-admission'
    assert classify(paths + ['packages/capstone-app/src/Unrelated.tsx']) != 'instruction-admission'


def test_instruction_recovery_uses_the_focused_gate():
    agent = 'packages/capstone-agent/'
    paths = [agent + 'src/capstone_agent/thread_service.py',
             agent + 'src/capstone_agent/thread_work.py',
             agent + 'tests/test_enterprise_normal_chat.py',
             'configs/development/instruction-admission-gate.json',
             'tools/test_instruction_admission.sh', 'tools/ci_scope.py',
             'tools/tests/test_ci_instruction_admission.py']
    assert classify(paths) == 'instruction-admission'
    assert classify(paths, target='main') == 'release'
    assert classify(paths + ['packages/grid-simulator/src/new.py']) != 'instruction-admission'
