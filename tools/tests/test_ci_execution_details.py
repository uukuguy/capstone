import json
from pathlib import Path

from tools.ci_scope import classify


def test_execution_details_gate_has_a_bounded_app_scope():
    paths = ['packages/capstone-app/src/ExecutionDetails.tsx',
             'packages/capstone-app/src/CapstoneAssistantThread.tsx',
             'packages/capstone-app/src/ThreadWorkAdapter.tsx']
    assert classify(paths) == 'execution-details'
    assert classify(paths, target='main') == 'release'
    assert classify(paths + ['packages/capstone-agent/src/capstone_agent/harness.py']) != 'execution-details'
    assert classify(paths + ['packages/capstone-app/src/Unrelated.tsx']) != 'execution-details'


def test_execution_details_gate_covers_the_enterprise_answer_transport():
    fixture = Path(__file__).resolve().parents[2] / 'configs/development/execution-details-gate.json'
    manifest = json.loads(fixture.read_text())
    paths = [*manifest['paths'], *manifest['answer_paths']]
    assert classify(paths) == 'execution-details'
    assert classify(paths + ['packages/grid-simulator/src/grid_simulator/registry.py']) != 'execution-details'


def test_execution_details_gate_covers_instruction_context_observations():
    fixture = Path(__file__).resolve().parents[2] / 'configs/development/execution-details-gate.json'
    manifest = json.loads(fixture.read_text())
    paths = [*manifest['context_paths'], 'packages/capstone-app/src/ThreadWorkAdapter.tsx']
    assert classify(paths) == 'context-observation'
    assert classify(paths + ['packages/grid-simulator/src/grid_simulator/registry.py']) != 'context-observation'
