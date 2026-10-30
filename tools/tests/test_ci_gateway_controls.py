"""Gateway administration checks cover its consumers without research/solver suites."""
from pathlib import Path

import pytest

from tools.ci_scope import classify, gateway_deployment_document

ROOT = Path(__file__).resolve().parents[2]
GATEWAY = [
    'packages/capstone-agent/src/capstone_agent/gateway_connections.py',
    'packages/capstone-agent/src/capstone_agent/gateway_connections_http.py',
    'packages/capstone-agent/src/capstone_agent/gateway_connections_runtime.py',
    'packages/capstone-agent/src/capstone_agent/general_pi_server.py',
    'packages/capstone-agent/src/capstone_agent/host_api.py',
    'packages/capstone-agent/src/capstone_agent/pi_delegation.py',
    'packages/capstone-agent/tests/test_gateway_connections.py',
    'packages/capstone-app/src/SessionNavigation.tsx',
    'compose.yaml', 'deploy/general-pi.Dockerfile', 'docs/RUNBOOK.md',
]


def test_gateway_management_uses_bounded_development_gate():
    assert classify(GATEWAY, gateway_deployment=True) == 'gateway-controls'
    assert classify(GATEWAY) != 'gateway-controls'
    assert classify([path for path in GATEWAY if path not in {'compose.yaml', 'deploy/general-pi.Dockerfile'}]) == 'gateway-controls'
    assert classify(GATEWAY, target='main') == 'release'
    assert classify(GATEWAY, release=True) == 'release'


@pytest.mark.parametrize('path', [
    'packages/capstone-agent/src/capstone_agent/thread_service.py',
    'packages/capstone-agent/src/capstone_agent/data_gateway_mcp.py',
    'packages/capstone-agent/src/capstone_agent/resources/general-sdk.mjs',
    'packages/capability-agent-kernel/src/capability_agent/runtime/step_events.py',
    'packages/capstone-agent/pyproject.toml',
    'packages/grid-simulator/src/grid_simulator/solver.py',
])
def test_gateway_gate_does_not_hide_other_execution_or_authority_changes(path):
    assert classify([*GATEWAY, path], gateway_deployment=True) != 'gateway-controls'


def test_only_registered_gateway_deployment_additions_are_admitted():
    anchor='      CAPSTONE_DATA_GATEWAY_CONNECTION_FILE: ${CAPSTONE_DATA_GATEWAY_CONNECTION_FILE:-}\n'
    addition='      CAPSTONE_GATEWAY_LOOPBACK_HOST: ${CAPSTONE_GATEWAY_LOOPBACK_HOST:-host.docker.internal}\n'
    old='services:\n  general-pi:\n    environment:\n'+anchor
    assert gateway_deployment_document('compose.yaml',old,old+addition)
    assert not gateway_deployment_document('compose.yaml',old,old+addition+'      WORKER_IMAGE: unsafe\n')
    assert not gateway_deployment_document('compose.yaml',old,addition+old)
    assert not gateway_deployment_document('compose.yaml',old,old+addition+addition)
    copy='COPY packages/capstone-agent/src/capstone_agent/data_gateway_relay.py capstone_agent/data_gateway_relay.py\n'
    extra='COPY packages/capstone-agent/src/capstone_agent/gateway_connections.py capstone_agent/gateway_connections.py\n'
    assert gateway_deployment_document('deploy/general-pi.Dockerfile',copy,copy+extra)
    assert not gateway_deployment_document('deploy/general-pi.Dockerfile',copy,copy+extra+'RUN unsafe\n')
    assert not gateway_deployment_document('deploy/general-pi.Dockerfile',copy,extra+copy)


def test_gateway_workflow_runs_direct_consumers_and_app_only():
    workflow = (ROOT / '.github/workflows/verify.yml').read_text()
    assert 'gateway-controls|' in workflow
    block = workflow.split('- name: Verify gateway controls', 1)[1].split('- name:', 1)[0]
    assert 'timeout-minutes: 5' in block
    for target in ('check-package-boundaries', 'check-types', 'test-capstone-app',
                   'build-capstone-app', 'test_gateway_connections*.py',
                   'test_general_pi_server.py', 'test_general_pi_native.py',
                   'test_pi_delegation.py', 'test_host_api.py', 'test_thread_http_api.py',
                   'test_network_policy_http.py', 'test_native_network_policy.py',
                   'test_grid_source_http.py', 'test_grid_electrical_view.py', 'test_thread_input_catalog.py',
                   'test_host_runtime_contract.py', 'test_image_layer_order.py'):
        assert target in block
    for forbidden in ('test-capstone-agent', 'test-kernel', 'test-registered-workers',
                      'test-pypsa', 'test-pandapower', 'check-release'):
        assert forbidden not in block
    for line in block.splitlines():
        if ' pytest ' in line:
            for target in line.split(' pytest ', 1)[1].split():
                if target.startswith(('packages/', 'tools/')):
                    assert list(ROOT.glob(target)), target
