"""Execution lifecycle changes have a bounded, opt-in development gate."""
from pathlib import Path
import subprocess

import pytest

from tools.ci_scope import classify

ROOT = Path(__file__).resolve().parents[2]
ANCHOR = 'packages/capability-agent-kernel/src/capability_agent/runtime/execution_queue.py'


def test_lifecycle_anchor_selects_only_its_registered_consumers():
    paths = [ANCHOR, 'packages/grid-agent/src/grid_agent/domain_tools.py',
             'packages/pandapower-domain-pack/src/pandapower_domain/execution.py',
             'packages/capstone-app/src/ProcessCallTrace.tsx',
             'packages/capstone-agent/src/capstone_agent/resources/general-sdk.mjs',
             'tools/tests/test_ci_execution_lifecycle.py']
    assert classify(paths) == 'execution-lifecycle'
    assert classify(paths, target='main') == 'release'
    assert classify(paths, release=True) == 'release'
    assert classify(paths[1:]) != 'execution-lifecycle'


def test_shared_sdk_leaf_dispatch_uses_the_same_focused_gate():
    source = 'packages/capstone-agent/src/capstone_agent/resources/'
    paths = [ANCHOR, *[source + name for name in (
        'tool-call-scheduler.mjs', 'general-sdk.mjs', 'tool-composition.mjs',
        'delegation-tool.mjs', 'llm-call-tools.mjs')],
        'packages/capstone-agent/tests/application-tool-dispatch.test.mjs']
    assert classify(paths) == 'execution-lifecycle'
    assert classify(paths, target='main') == 'release'
    assert classify(paths, release=True) == 'release'
    for extra in ('delegation-scheduler.mjs', 'research-tools.mjs', 'unknown-runtime.mjs'):
        assert classify([*paths, source + extra]) != 'execution-lifecycle'


def test_lifecycle_route_includes_only_named_application_relay_capacity_files():
    paths = [ANCHOR, 'configs/runtime/application-capacity.json',
             'packages/capstone-agent/src/capstone_agent/resources/application-capacity.json',
             'packages/capstone-agent/tests/test_application_capacity.py']
    assert classify(paths) == 'execution-lifecycle'
    assert classify(paths, target='main') == 'release'
    for extra in ('configs/runtime/model-budget.json', 'configs/runtime/provider-capacity.json',
                  'packages/capstone-agent/src/capstone_agent/resources/model-budget.json'):
        assert classify([*paths, extra]) != 'execution-lifecycle'


def test_lifecycle_closeout_admits_only_its_named_owning_control_documents():
    paths = [ANCHOR,
             'docs/superpowers/specs/2026-10-07-capstone-core-evolution-discussion.md',
             'docs/superpowers/plans/2026-10-16-enterprise-unified-execution.md']
    assert classify(paths) == 'execution-lifecycle'
    assert classify([*paths, 'docs/superpowers/specs/unrelated-research.md']) != 'execution-lifecycle'


@pytest.mark.parametrize('extra', [
    'packages/grid-simulator/src/grid_simulator/solver.py',
    'packages/capstone-agent/pyproject.toml', 'packages/grid-agent/uv.lock',
    'packages/capstone-app/src/App.tsx', 'packages/capstone-app/src/new.ts',
    'packages/capstone-agent/src/capstone_agent/thread_worker.py',
    'packages/capstone-agent/tests/test_unregistered.py', 'docs/unregistered.md',
    'deploy/unknown.Dockerfile', '../escape.py',
])
def test_lifecycle_route_rejects_uncovered_paths(extra):
    assert classify([ANCHOR, extra]) != 'execution-lifecycle'


def test_current_development_diff_uses_route_after_exact_deployment_validation():
    from tools.ci_scope import execution_lifecycle_deployment_diff
    base = next((ref for ref in ('origin/dev', 'dev') if subprocess.run(
        ['git', 'rev-parse', '--verify', ref], cwd=ROOT, capture_output=True).returncode == 0), None)
    if base is None:
        pytest.skip('Development base is unavailable in this checkout')
    paths = subprocess.check_output(['git', 'diff', '--name-only', f'{base}...HEAD'], cwd=ROOT, text=True).splitlines()
    if ANCHOR not in paths:
        pytest.skip('This checkout has no lifecycle development diff')
    assert execution_lifecycle_deployment_diff(paths, base, 'HEAD')
    assert classify(paths, execution_lifecycle_deployment=True) == 'execution-lifecycle'
    if {'compose.yaml', 'deploy/general-pi.Dockerfile'} & set(paths):
        assert classify(paths) != 'execution-lifecycle'


def test_deployment_allowance_rejects_changes_outside_the_exact_binding(monkeypatch):
    from tools.ci_scope import execution_lifecycle_deployment_document, execution_lifecycle_deployment_diff
    old = 'services:\n  worker:\n      CAPSTONE_THREAD_FAMILY: pandapower\n    command: [worker]\n'
    new = old.replace('    command:', '      CAPSTONE_DOMAIN_EXECUTION_RECEIPTS_ROOT: /app/runs/domain-control\n    command:')
    assert execution_lifecycle_deployment_document('compose.yaml', old, new)
    assert not execution_lifecycle_deployment_document('compose.yaml', old, new + 'unrelated: true\n')
    assert not execution_lifecycle_deployment_document('compose.yaml', old, new.replace('/app/runs/domain-control', '/public'))
    assert not execution_lifecycle_deployment_document('unknown', old, new)
    monkeypatch.setattr('tools.ci_scope.subprocess.check_output', lambda command, **kw: old if command[-1].startswith('base:') else new)
    assert execution_lifecycle_deployment_diff(['compose.yaml'], 'base', 'head')
    new += 'unrelated: true\n'
    assert not execution_lifecycle_deployment_diff(['compose.yaml'], 'base', 'head')


def test_workflow_has_scoped_setup_and_only_focused_consumers():
    workflow = (ROOT / '.github/workflows/verify.yml').read_text()
    assert 'execution-lifecycle|' in workflow
    setup = workflow.split('- name: Set up gateway binding dependencies',1)[1].split('- name:',1)[0]
    assert "gate == 'execution-lifecycle'" in setup
    standard = workflow.split('- name: Set up standard dependencies',1)[1].split('- name:',1)[0]
    assert "gate != 'execution-lifecycle'" in standard
    block = workflow.split('- name: Verify tool execution lifecycle',1)[1].split('- name:',1)[0]
    assert 'timeout-minutes: 5' in block
    for target in ('test_execution_queue.py', 'test_domain_execution_lifecycle.py',
                   'pandapower-domain-pack/tests/test_execution.py', 'test_tool_execution_receipt.py',
                   'test_data_gateway_*.py', 'test_general_pi_server.py', 'test_delegated_runtime.py',
                   'test_graph_host_observation.py', 'test_execution_lifecycle_packaging.py',
                   'check-package-boundaries', 'toolExecutionReceipt.test.ts',
                   'ProcessCallTrace.test.tsx', 'executionGraph.test.ts',
                   'CapstoneAssistantThread.test.tsx', 'ExecutionGraphProcess.test.tsx',
                   'tool-composition.test.mjs', 'tool-discovery.test.mjs',
                   'application-tool-dispatch.test.mjs',
                   'test_application_capacity.py', 'test_relay_backpressure.py', 'test_general_pi_relay.py',
                   'graph', 'npm --prefix packages/capstone-app run check'):
        assert target in block
    for forbidden in ('check-release','check-pr','test-kernel','test-capstone-app',
                      'test-capstone-agent','tests/*.test.mjs','tests/fixtures/*.test.mjs'):
        assert forbidden not in block
    for line in block.splitlines():
        if ' pytest ' in line or 'node --test ' in line:
            for token in line.split():
                if token.startswith(('packages/', 'tools/')):
                    assert list(ROOT.glob(token)), token
