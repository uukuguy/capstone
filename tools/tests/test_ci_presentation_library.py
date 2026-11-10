"""Template-library development checks stay bounded to their direct consumers."""
from pathlib import Path

from tools.ci_scope import classify

ROOT = Path(__file__).resolve().parents[2]
ANCHOR = 'packages/capstone-agent/src/capstone_agent/presentation_templates.py'


def test_template_library_route_is_focused_and_unknown_changes_do_not_inherit_it():
    paths = [ANCHOR, 'compose.yaml', 'deploy/general-pi.Dockerfile',
        'tools/native_presentation_library.py', 'configs/runtime/native-analysis.json',
        'packages/capstone-agent/src/capstone_agent/general_pi_server.py',
        'packages/capstone-agent/tests/test_native_skill_recovery.py']
    assert classify(paths) == 'presentation-library'
    assert classify([*paths,
        'packages/capstone-agent/src/capstone_agent/gateway_diagnostics.py',
        'packages/capstone-agent/src/capstone_agent/data_gateway_relay.py',
        'packages/capstone-agent/tests/test_gateway_diagnostics.py',
        'packages/capstone-app/src/serviceBusCalls.ts',
        'packages/capstone-app/src/CapstoneAssistantThread.tsx']) == 'presentation-library'
    assert classify(paths, target='main') == 'release'
    assert classify(paths, release=True) == 'release'
    assert classify(paths[1:]) != 'presentation-library'
    for extra in ('packages/grid-simulator/src/grid_simulator/new_solver.py',
                  'packages/capstone-agent/src/capstone_agent/unknown.py', 'Makefile'):
        assert classify([*paths, extra]) != 'presentation-library'


def test_template_library_workflow_runs_named_consumers_without_full_workbench_or_release():
    text = (ROOT / '.github/workflows/verify.yml').read_text()
    block = text.split('- name: Verify presentation template library', 1)[1].split('- name:', 1)[0]
    for required in ('test_presentation_templates.py', 'test_presentation_template_http.py',
                     'test_native_presentation_tasks.py', 'test_presentation_task_relay.py',
                     'test_native_skill_recovery.py', 'test_general_pi_server.py',
                     'test_host_runtime_contract.py', 'test_image_layer_order.py',
                     'test_presentation_library_render.py', 'presentation-templates.test.mjs'):
        assert required in block
    for required in ('test_gateway_diagnostics.py','test_data_gateway_relay.py',
                     'test_native_graph_events.py','serviceBusCalls.test.ts',
                     'CapstoneAssistantThread.test.tsx','ExecutionGraphProcess.test.tsx'):
        assert required in block
    assert 'check-release' not in block and 'test-capstone-agent' not in block
    assert 'test-pypsa' not in block and 'test-pandapower-application' not in block
