"""Final development routing follows ownership; unknown boundaries stay broad."""
import pytest
from pathlib import Path
from tools.ci_scope import classify

ROOT = Path(__file__).resolve().parents[2]
WORKBENCH = [
    'packages/capstone-agent/src/capstone_agent/pi_delegation.py',
    'packages/capstone-agent/src/capstone_agent/new_service.py',
    'packages/capstone-agent/src/capstone_agent/resources/general-sdk.mjs',
    'packages/capstone-app/src/ThreadWorkspace.tsx',
    'packages/capability-agent-kernel/src/capability_agent/runtime/step_events.py',
    'packages/enterprise-research-domain-pack/src/enterprise_research/__init__.py',
    'packages/pi-capability-tools/test/research-tools.test.mjs',
    'configs/runtime/workbench-llm-profiles.json', 'compose.yaml',
    'deploy/general-pi.Dockerfile', 'deploy/launch_host_runtime.py',
    'tools/native_report.py', 'tools/tests/test_native_presentation.py',
    'docs/RUNBOOK.md', '.superpowers/sdd/task-2-report.md',
]


def test_workbench_union_uses_owned_suites_instead_of_solver_regression():
    assert classify(WORKBENCH) == 'workbench'
    assert classify(WORKBENCH, target='main') == 'release'
    assert classify(WORKBENCH, release=True) == 'release'


@pytest.mark.parametrize('path', [
    'packages/capstone-app/src/styles.css',
    'packages/capstone-app/src/NewView.tsx',
    'packages/capstone-app/package-lock.json',
    'packages/capstone-app/vite.config.ts',
])
def test_frontend_only_does_not_run_backend_suites(path):
    assert classify([path, 'docs/RUNBOOK.md']) == 'app'
    assert classify([path], target='main') == 'release'


@pytest.mark.parametrize('path', [
    'packages/grid-simulator/src/grid_simulator/solver.py',
    'packages/capability-agent-kernel/src/capability_agent/domain/authority.py',
    'packages/capability-agent-kernel/src/capability_agent/runtime/environment.py',
    'packages/capstone-agent/src/capstone_agent/kernel_pi_session.py',
    'packages/capstone-agent/pyproject.toml',
    'packages/grid-agent/uv.lock', 'Makefile', 'unknown.file',
    'packages/capstone-app/src/../../../unknown.py',
    '.superpowers/sdd/executable.py',
])
def test_unknown_or_authority_changes_keep_full_product_gate(path):
    assert classify([*WORKBENCH, path]) == 'product'


def test_workbench_workflow_covers_owned_consumers_without_full_solvers():
    text = (ROOT / '.github/workflows/verify.yml').read_text()
    block = text.split('- name: Verify enterprise workbench', 1)[1].split('- name:', 1)[0]
    for target in ('test-capstone-agent', 'test-kernel', 'test-capstone-app',
                   'build-capstone-app', 'test-capstone-client', 'test-registered-workers',
                   'test-generic-tools', 'test_enterprise_research_pack.py', 'test_research_policy_compatibility.py',
                   'test_host_runtime_contract.py', 'test_native_presentation.py',
                   'test_hosted.py', 'test_hosted_thread.py'):
        assert target in block
    for target in ('check-pr', 'check-release', 'test-pandapower-application', 'test-pypsa'):
        assert target not in block
    app = text.split('- name: Verify App only', 1)[1].split('- name:', 1)[0]
    assert 'test-capstone-app' in app and 'build-capstone-app' in app
    assert 'test-capstone-agent' not in app and 'check-types' not in app


def test_workbench_pytest_targets_exist():
    text=(ROOT/'.github/workflows/verify.yml').read_text()
    block=text.split('- name: Verify enterprise workbench',1)[1].split('- name:',1)[0]
    for line in block.splitlines():
        if ' pytest ' not in line:
            continue
        for token in line.split(' pytest ',1)[1].split():
            if token.startswith(('packages/','tools/')):
                assert list(ROOT.glob(token)),f'Missing workbench test target: {token}'
