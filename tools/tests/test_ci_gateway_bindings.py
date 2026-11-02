"""Dynamic gateway bindings use a bounded development verification route."""
from pathlib import Path

import pytest

from tools.ci_scope import classify

ROOT = Path(__file__).resolve().parents[2]
SOURCE = 'packages/capstone-agent/src/capstone_agent/'


def test_workflow_environment_has_no_case_insensitive_duplicate_keys():
    import re
    text = (ROOT / '.github/workflows/verify.yml').read_text()
    block = text.split('    env:\n', 1)[1].split('    strategy:', 1)[0]
    names = re.findall(r'^      ([A-Za-z_][A-Za-z0-9_]*):', block, re.MULTILINE)
    assert len(names) == len({name.casefold() for name in names})
CHANGES = [SOURCE + name + '.py' for name in (
    'data_gateway_relay', 'data_gateway_views', 'grid_source_topology',
    'grid_electrical_view', 'general_pi_server', 'pi_delegation', 'delegated_runtime',
)] + [SOURCE + 'resources/' + name + '.mjs' for name in (
    'gateway-tool-use', 'general-tool-discovery', 'tool-composition',
)] + ['packages/capstone-agent/tests/test_data_gateway_views.py',
      'packages/capstone-agent/tests/fixtures/tool-discovery.test.mjs',
      'tools/tests/test_ci_gateway_bindings.py', 'tools/ci_scope.py',
      '.github/workflows/verify.yml', 'docs/status/VERSION-CONTROL.md']


def test_dynamic_bindings_select_their_direct_consumers():
    assert classify(CHANGES) == 'gateway-bindings'
    assert classify(CHANGES, source_topology=True) == 'gateway-bindings'
    assert classify(CHANGES, target='main') == 'release'
    assert classify(CHANGES, release=True) == 'release'


def test_gateway_scope_includes_only_exact_electrical_view_consumers():
    ui = ['packages/capstone-app/src/electricalModelView.ts',
          'packages/capstone-app/src/electricalModelView.test.ts']
    assert classify([*CHANGES, *ui]) == 'gateway-bindings'
    assert classify(ui) == 'app'
    assert classify([*CHANGES, *ui, 'packages/capstone-app/src/ThreadRuntime.tsx']) != 'gateway-bindings'


@pytest.mark.parametrize('path', [
    SOURCE + 'thread_service.py', SOURCE + 'unregistered_gateway.py',
    SOURCE + 'resources/unregistered.mjs', 'packages/capstone-agent/pyproject.toml',
    'packages/capstone-app/src/App.tsx',
    'packages/grid-simulator/src/grid_simulator/solver.py',
    'packages/capstone-agent/tests/test_unregistered.py',
])
def test_gateway_bindings_do_not_absorb_uncovered_changes(path):
    assert classify([*CHANGES, path]) != 'gateway-bindings'


def test_docker_addition_needs_exact_diff_validation():
    from tools.ci_scope import gateway_bindings_deployment_document
    copy = 'COPY packages/capstone-agent/src/capstone_agent/data_gateway_views.py capstone_agent/data_gateway_views.py\n'
    old = 'FROM python:3.12\nWORKDIR /app\n'
    assert gateway_bindings_deployment_document(old, old + copy)
    assert not gateway_bindings_deployment_document(old, old + copy + copy)
    assert not gateway_bindings_deployment_document(old, old + copy + 'RUN unsafe\n')
    assert not gateway_bindings_deployment_document(old, old.replace('3.12', '3.13') + copy)
    paths = [*CHANGES, 'deploy/general-pi.Dockerfile']
    assert classify(paths) != 'gateway-bindings'
    assert classify(paths, gateway_bindings_deployment=True) == 'gateway-bindings'


def test_startup_binding_is_the_only_allowed_sdk_diff():
    from tools.ci_scope import gateway_bindings_startup_document
    anchor = '  return createToolDiscovery({tools:createDataGatewayTools(config),publications:config.dataGateway.catalog.tools,\n'
    addition = '    initialNames:config.dataGateway.catalog.entry_tools??[],\n'
    old = 'export function createGatewayToolDiscovery(config) {\n' + anchor + '    admittedNames});\n}\n'
    new = old.replace(anchor, anchor + addition)
    assert gateway_bindings_startup_document(old, new)
    assert not gateway_bindings_startup_document(old, new + addition)
    assert not gateway_bindings_startup_document(old, new.replace('admittedNames', 'ungrantedNames'))
    assert not gateway_bindings_startup_document(old, addition + old)
    assert not gateway_bindings_startup_document(new, old)
    assert not gateway_bindings_startup_document(new, new)


def test_sdk_startup_scope_requires_separate_proof_and_preserves_release():
    paths = [*CHANGES, SOURCE + 'resources/general-sdk.mjs']
    assert classify(paths) != 'gateway-bindings'
    assert classify(paths, gateway_bindings_startup=True) == 'gateway-bindings'
    assert classify(paths, gateway_bindings_startup=True, target='main') == 'release'
    assert classify(paths, gateway_bindings_startup=True, release=True) == 'release'
    assert classify([*paths, 'deploy/general-pi.Dockerfile'], gateway_bindings_startup=True) != 'gateway-bindings'


def test_sdk_startup_proof_uses_both_git_revisions(monkeypatch):
    from tools.ci_scope import gateway_bindings_startup_diff
    anchor = '  return createToolDiscovery({tools:createDataGatewayTools(config),publications:config.dataGateway.catalog.tools,\n'
    old = 'export function createGatewayToolDiscovery(config) {\n' + anchor + '    admittedNames});\n}\n'
    new = old.replace(anchor, anchor + '    initialNames:config.dataGateway.catalog.entry_tools??[],\n')
    calls = []
    def show(command, **kwargs):
        calls.append(command)
        return old if command[-1].startswith('base:') else new
    monkeypatch.setattr('tools.ci_scope.subprocess.check_output', show)
    path = SOURCE + 'resources/general-sdk.mjs'
    assert gateway_bindings_startup_diff([path], 'base', 'head')
    assert [call[-1] for call in calls] == ['base:' + path, 'head:' + path]
    new += 'unrelated();\n'
    assert not gateway_bindings_startup_diff([path], 'base', 'head')


def test_gateway_bindings_workflow_has_bounded_consumers_and_no_app_suite():
    workflow = (ROOT / '.github/workflows/verify.yml').read_text()
    assert 'gateway-bindings|' in workflow
    assert 'tools/tests/test_ci_gateway_bindings.py' in workflow
    block = workflow.split('- name: Verify gateway bindings', 1)[1].split('- name:', 1)[0]
    for target in ('check-package-boundaries', 'pyright', 'test_data_gateway_*.py',
                   'test_grid_source_*.py', 'test_grid_electrical_view.py',
                   'test_general_pi_server.py', 'test_pi_delegation.py',
                   'test_delegated_runtime.py',
                   'test_graph_host_observation.py', 'test_host_runtime_contract.py',
                   'test_image_layer_order.py', 'gateway-tool-use.test.mjs',
                   'tool-discovery.test.mjs', 'tool-composition.test.mjs',
                   'npm --prefix packages/capstone-app run check',
                   'npm --prefix packages/capstone-app test -- src/electricalModelView.test.ts'):
        assert target in block
    for target in ('test-capstone-app', 'build-capstone-app', 'test-capstone-agent',
                   'check-types', 'test-kernel', 'check-release', 'check-pr',
                   'test_general_pi_*.py', 'test_host_api.py', 'test_thread_http_api.py',
                   'test_thread_input_catalog.py', 'test_network_policy_http.py',
                   'test_native_network_policy.py'):
        assert target not in block
    for line in block.splitlines():
        if ' pytest ' in line:
            for target in line.split(' pytest ', 1)[1].split():
                if target.startswith(('packages/', 'tools/')):
                    assert list(ROOT.glob(target)), target


def test_gateway_setup_is_scoped_and_other_gates_keep_standard_setup():
    workflow = (ROOT / '.github/workflows/verify.yml').read_text()
    block = workflow.split('- name: Set up gateway binding dependencies', 1)[1].split('- name:', 1)[0]
    assert "if: steps.scope.outputs.gate == 'gateway-bindings'" in block
    for command in ('uv sync --project packages/grid-agent',
                    'uv sync --project packages/capstone-agent',
                    'npm ci --prefix packages/capstone-app'):
        assert command in block
    for forbidden in ('make setup', 'packages/pypsa-agent', 'workbench', 'npm run build'):
        assert forbidden not in block
    standard = workflow.split('- name: Set up standard dependencies', 1)[1].split('- name:', 1)[0]
    assert "if: steps.scope.outputs.gate != 'gateway-bindings'" in standard
    assert 'make setup' in standard
    assert '- run: make install-pi' in workflow
    assert 'run: make doctor' in workflow
