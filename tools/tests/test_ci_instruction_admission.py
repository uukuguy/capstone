from tools.ci_scope import classify


def test_instruction_gate_excludes_unrelated_domain_and_release_work():
    paths = ['packages/capstone-agent/src/capstone_agent/instruction_queue.py',
             'packages/capstone-app/src/InstructionStatus.tsx']
    assert classify(paths) == 'instruction-admission'
    assert classify(paths, target='main') == 'release'
    assert classify(paths + ['packages/pandapower-domain-pack/src/new.py']) != 'instruction-admission'
    assert classify(paths + ['packages/capstone-app/src/Unrelated.tsx']) != 'instruction-admission'
