"""Choose a bounded development gate; unknown changes require product checks."""
from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import unquote
import subprocess
import tomllib


DOC_FILES = {"README.md", "README.zh-CN.md", "AGENTS.md", "CLAUDE.md",
             "tools/render_project_overview.py"}
GOVERNANCE_FILES = {".github/workflows/verify.yml", "tools/ci_scope.py",
                    "configs/development/issue-automation.json",
                    "tools/tests/test_ci_scope.py", "tools/tests/test_ci_workbench_scope.py",
                    "tools/tests/test_verification_targets.py", "tools/tests/test_ci_gateway_controls.py",
                    "tools/tests/test_ci_gateway_bindings.py", "tools/tests/test_ci_execution_lifecycle.py"}

# Assembly and native-runtime contracts have bounded cross-package gates.
# Authority protocols, solvers and unknown dependencies still require product.
FOUNDATION_FILES = {
    'packages/capability-agent-kernel/src/capability_agent/' + path
    for path in ('application/composition.py', 'application/profile.py',
                 'application/registry.py', 'application/native.py', 'application/runner.py',
                 'domain/__init__.py', 'domain/manifest.py', 'domain/profile.py', 'tools/catalog.py')
} | {
    'packages/pandapower-application/src/pandapower_application/application/composition.py',
    'packages/pandapower-application/src/pandapower_application/hosted.py',
    'packages/pandapower-application/src/pandapower_application/thread_model_diagram.py',
    'packages/pypsa-agent/src/pypsa_agent/thread_model_diagram.py',
    'packages/pypsa-agent/src/pypsa_agent/worker.py',
}

CONVERSATION_RUNTIME_FILES = {
    'deploy/general-pi.Dockerfile',
    'packages/pi-capability-tools/src/research-tools.mjs',
    'packages/pi-capability-tools/src/research-context-window.mjs',
}
# These modules and their direct consumers are named in the conversation gate.
# Other backend edits must not inherit its smaller test set just because a
# resource file changed in the same PR.
CONVERSATION_BACKEND_MODULES = {'delegated_runtime', 'harness', 'thread_work', 'native_diagnosis'}
CONVERSATION_BACKEND_TESTS = {'test_' + name for name in CONVERSATION_BACKEND_MODULES} | {
    'test_thread_http_api', 'test_enterprise_normal_chat', 'test_thread_work_execution',
    'test_thread_worker', 'test_attempt_research',
}
# The adaptive gate runs the full agent, Kernel and owning research Pack suites.
# These two ledger/channel modules are not an allowance for arbitrary Kernel code.
ADAPTIVE_KERNEL_FILES = {
    'packages/capability-agent-kernel/src/capability_agent/application/context_store.py',
    'packages/capability-agent-kernel/src/capability_agent/runtime/research_channel.py',
}
ADAPTIVE_BACKEND_MODULES = {
    'enterprise_application', 'intent_runtime', 'native_conversation', 'native_graph_context',
    'native_research_bridge', 'native_task_context', 'task_planning_policy',
}
ADAPTIVE_RESOURCE_FILES = {
    'packages/capstone-agent/src/capstone_agent/resources/' + name
    for name in ('enterprise-graph-runtime.mjs', 'general-sdk.mjs', 'graph-context-client.mjs',
                 'research-policy-catalog.json', 'task-planning-policy-1.6.md')
}
ADAPTIVE_PACK_ROOT = 'packages/enterprise-research-domain-pack/'


def adaptive_agent_paths(paths: list[str]) -> bool:
    """Accept only the registered adaptive stack and its fully tested consumers."""
    anchored = False
    for path in paths:
        location = PurePosixPath(path)
        if '..' in location.parts:
            return False
        if path in ADAPTIVE_KERNEL_FILES:
            anchored = True
        elif (location.parent == PurePosixPath('packages/capstone-agent/src/capstone_agent')
              and location.suffix == '.py' and location.stem in ADAPTIVE_BACKEND_MODULES):
            anchored = True
        elif (path == ADAPTIVE_PACK_ROOT + 'src/enterprise_research/__init__.py'
              or re.fullmatch(re.escape(ADAPTIVE_PACK_ROOT) + r'src/enterprise_research/resources/'
                              r'(?:versions/\d+\.\d+\.\d+/)?(?:system-policy|research-method|progress-guidance)\.md', path)):
            anchored = True
        elif path in ADAPTIVE_RESOURCE_FILES or path in DOC_FILES or path in GOVERNANCE_FILES:
            continue
        elif (location.parent == PurePosixPath('packages/capstone-agent/src/capstone_agent')
              and location.suffix == '.py' and location.stem in CONVERSATION_BACKEND_MODULES | {'general_pi_server'}):
            continue
        elif (path.startswith(('packages/capstone-agent/tests/', 'packages/capability-agent-kernel/tests/',
                               ADAPTIVE_PACK_ROOT + 'tests/')) and location.suffix == '.py'):
            continue
        elif ((location.parent == PurePosixPath('packages/capstone-agent/tests') and path.endswith('.test.mjs'))
              or path.startswith('packages/capstone-agent/tests/fixtures/') and location.suffix in {'.mjs', '.json'}):
            continue
        elif path.startswith('packages/capstone-app/src/') and (location.suffix in {'.ts', '.tsx', '.css'}
              or path.startswith('packages/capstone-app/src/fixtures/') and location.suffix == '.json'):
            continue
        elif path.startswith(('docs/', 'tools/project_overview/')):
            continue
        else:
            return False
    return anchored


RUNTIME_FILES = {
    'compose.yaml', 'deploy/local.env.example',
    'configs/runtime/data-gateway.json', 'scripts/verify_data_gateway_research.py',
    'packages/grid-simulator/src/grid_simulator/powermcp_sidecar.py',
}
RUNTIME_DEPENDENCIES = {'packages/capstone-agent/pyproject.toml'} | {
    f'packages/{package}/uv.lock' for package in ('capstone-agent', 'pandapower-application', 'pypsa-agent')
}
# MCP's additional transport/auth packages. Any other dependency change expands
# the gate, including a solver version changed only through a downstream lock.
MCP_PACKAGES = {'mcp', 'httpx-sse', 'sse-starlette', 'pydantic-settings',
                'python-multipart', 'pywin32', 'pyjwt'}

# This is an exact addition contract, not a general exemption for transport code.
# Changing any legacy method, timeout, origin, authentication or task semantics
# still requires product verification, even in a source-view PR.
SOURCE_CONTROL_METHODS = '''
    def grid_source_catalog(self):
        return self._call('GET', '/grid-sources', timeout=2, total_timeout=3)

    def grid_source_scopes(self):
        from .grid_source_topology import EXCHANGE_SECONDS
        return self._call('GET', '/grid-sources/data-gateway/scopes',
                          timeout=EXCHANGE_SECONDS + 2, total_timeout=EXCHANGE_SECONDS + 3)

    def grid_source_resolve_scope(self, document):
        from .grid_source_topology import EXCHANGE_SECONDS
        return self._call('POST', '/grid-sources/data-gateway/resolve-scope', document=document,
                          timeout=EXCHANGE_SECONDS + 2, total_timeout=EXCHANGE_SECONDS + 3)

    def grid_source_topology(self, document):
        from .grid_source_topology import EXCHANGE_SECONDS, checked_topology_request
        return self._call('POST', '/grid-sources/data-gateway/topology',
                          document=checked_topology_request(document),
                          timeout=EXCHANGE_SECONDS + 2, total_timeout=EXCHANGE_SECONDS + 3)
'''
SOURCE_ERROR_CODES = {'grid_source_unavailable', 'grid_source_request_invalid', 'grid_source_view_changed',
                      'grid_source_response_invalid', 'grid_source_observation_unavailable'}
SOURCE_BACKEND_MODULES = {'grid_source_topology', 'grid_source_http', 'host_api',
                          'general_pi_server', 'pi_delegation', 'delegated_runtime', 'data_gateway_relay', 'data_gateway_mcp',
                          # The gate runs all test_thread*.py and host consumers,
                          # including native model release and professional guards.
                          'thread_model_workspace', 'thread_service'}
SOURCE_BACKEND_TESTS = {'test_grid_source_topology', 'test_grid_source_http', 'test_general_pi_native',
    'test_general_pi_server', 'test_pi_delegation', 'test_host_api', 'test_thread_http_api',
    'test_thread_model_workspace', 'test_data_gateway_mcp', 'test_data_gateway_relay',
    'test_network_policy_http', 'test_native_network_policy', 'test_delegated_runtime', 'test_graph_host_observation'}
SOURCE_FILES = {'configs/runtime/data-gateway.json', 'deploy/general-pi.Dockerfile',
               'packages/capstone-agent/src/capstone_agent/resources/general-context.mjs',
               'packages/capstone-agent/src/capstone_agent/resources/general-data-gateway.mjs',
               'packages/capstone-agent/tests/fixtures/data-gateway-research.test.mjs'}
SOURCE_ANCHORS = {'packages/capstone-agent/src/capstone_agent/grid_source_topology.py',
                  'packages/capstone-agent/src/capstone_agent/grid_source_http.py',
                  'packages/capstone-agent/src/capstone_agent/data_gateway_mcp.py',
                  'packages/capstone-agent/src/capstone_agent/data_gateway_relay.py'}


def source_transport_document(old: str, new: str) -> bool:
    """Admit only the exact source-control additions; compare all legacy AST."""
    expected = {node.name: ast.dump(node) for node in ast.parse(
        'class HttpGeneralPiExecutor:\n' + SOURCE_CONTROL_METHODS).body[0].body}

    def normalize(text):
        tree = ast.parse(text)
        classes = [node for node in tree.body if isinstance(node, ast.ClassDef)
                   and node.name == 'HttpGeneralPiExecutor']
        if len(classes) != 1:
            raise ValueError('transport class missing or duplicated')
        owner = classes[0]
        kept, seen = [], set()
        for node in owner.body:
            if isinstance(node, ast.FunctionDef) and node.name in expected:
                if node.name in seen or ast.dump(node) != expected[node.name]:
                    raise ValueError('unregistered source forwarding implementation')
                seen.add(node.name)
                continue
            if isinstance(node, ast.FunctionDef) and node.name == '_call':
                for assignment in ast.walk(node):
                    if (isinstance(assignment, ast.Assign) and len(assignment.targets) == 1
                            and isinstance(assignment.targets[0], ast.Name)
                            and assignment.targets[0].id == 'known' and isinstance(assignment.value, ast.Set)):
                        assignment.value.elts = [item for item in assignment.value.elts
                            if not (isinstance(item, ast.Constant) and item.value in SOURCE_ERROR_CODES)]
            kept.append(node)
        owner.body = kept
        return ast.dump(tree)
    try:
        return normalize(old) == normalize(new)
    except (SyntaxError, ValueError, TypeError):
        return False


def source_gateway_document(old: dict, new: dict) -> bool:
    """Admit the named read-only display/inventory additions; other edits widen."""
    additions = {'get_network_topology_view', 'discover_network_models'}
    values = []
    for document in (old, new):
        if not isinstance(document, dict) or not isinstance(document.get('allowed_tools'), list):
            return False
        value = deepcopy(document)
        tools = value['allowed_tools']
        if any(not isinstance(tool, str) for tool in tools) or len(set(tools)) != len(tools):
            return False
        value['allowed_tools'] = [tool for tool in tools if tool not in additions]
        values.append(value)
    return (values[0] == values[1]
            and all(old['allowed_tools'].count(tool) <= new['allowed_tools'].count(tool) for tool in additions))


def source_topology_diff(paths: list[str], base: str, head: str) -> bool:
    checks = {'packages/capstone-agent/src/capstone_agent/pi_delegation.py': source_transport_document,
              'configs/runtime/data-gateway.json': source_gateway_document}
    for path, check in checks.items():
        if path not in paths:
            continue
        try:
            old, new = [subprocess.check_output(['git', 'show', f'{revision}:{path}'], text=True)
                        for revision in (base, head)]
            if path.endswith('.json'):
                old, new = json.loads(old), json.loads(new)
            if not check(old, new):
                return False
        except (subprocess.CalledProcessError, ValueError, TypeError, OSError):
            return False
    return True


def source_topology_paths(paths: list[str]) -> bool:
    if not set(paths) & SOURCE_ANCHORS:
        return False
    for path in paths:
        location = PurePosixPath(path)
        if '..' in location.parts:
            return False
        if path in SOURCE_FILES or path in DOC_FILES or path in GOVERNANCE_FILES:
            continue
        if path.startswith(('docs/', 'tools/project_overview/')):
            continue
        if (location.parent == PurePosixPath('packages/capstone-agent/src/capstone_agent')
                and location.suffix == '.py' and location.stem in SOURCE_BACKEND_MODULES):
            continue
        if (location.parent == PurePosixPath('packages/capstone-agent/tests')
                and location.suffix == '.py' and location.stem in SOURCE_BACKEND_TESTS):
            continue
        if path.startswith('packages/capstone-app/src/') and (location.suffix in {'.ts', '.tsx', '.css'}
                or path.startswith('packages/capstone-app/src/fixtures/') and location.suffix == '.json'):
            continue
        return False
    return True


def runtime_dependency_document(path: str, old: dict, new: dict) -> bool:
    if path not in RUNTIME_DEPENDENCIES:
        return False

    def without_mcp(document):
        value = deepcopy(document)
        if path.endswith('pyproject.toml'):
            project = value.get('project', {})
            project['dependencies'] = [entry for entry in project.get('dependencies', [])
                                       if not re.match(r'^mcp(?:[<>=!~;\[]|$)', entry)]
        else:
            packages = []
            for package in value.get('package', []):
                if package.get('name') in MCP_PACKAGES:
                    continue
                if package.get('name') == 'capstone-agent':
                    for owner, key in ((package, 'dependencies'),
                                       (package.get('metadata', {}), 'requires-dist')):
                        if key in owner:
                            owner[key] = [item for item in owner[key] if item.get('name') != 'mcp']
                packages.append(package)
            value['package'] = packages
        return value

    return without_mcp(old) == without_mcp(new)


def runtime_dependency_diff(paths: list[str], base: str, head: str) -> bool:
    changed = set(paths) & RUNTIME_DEPENDENCIES
    if not changed:
        return False
    for path in changed:
        try:
            old, new = [tomllib.loads(subprocess.check_output(
                ['git', 'show', f'{revision}:{path}'], text=True)) for revision in (base, head)]
        except (subprocess.CalledProcessError, tomllib.TOMLDecodeError):
            return False
        if not runtime_dependency_document(path, old, new):
            return False
    return True


def _scoped_gate(paths: list[str], *, target: str = "dev", release: bool = False,
             runtime_dependencies: bool = False, source_topology: bool = False) -> str:
    if target == "main" or release:
        return "release"
    if not paths:
        return "product"
    if source_topology and source_topology_paths(paths):
        return 'source-topology'
    if adaptive_agent_paths(paths):
        return 'adaptive-agent'
    governance = False
    shared_agent = False
    foundation = False
    native_runtime = False
    conversation_runtime = False
    uncovered_backend = False
    for path in paths:
        if ".." in PurePosixPath(path).parts:
            return "product"
        if path.startswith("packages/capstone-agent/src/capstone_agent/") and (
                PurePosixPath(path).name in {"kernel_pi_session.py", "pi_delegation.py"}):
            return "product"
        if (path in CONVERSATION_RUNTIME_FILES
                or (path.startswith('packages/capstone-agent/src/capstone_agent/') and path.endswith('.py')
                    and PurePosixPath(path).name.startswith('general_pi_'))
                or (PurePosixPath(path).parent == PurePosixPath('packages/capstone-agent/tests')
                    and path.endswith('.test.mjs'))
                or (path.startswith(('packages/capstone-agent/src/capstone_agent/resources/',
                                     'packages/capstone-agent/tests/fixtures/'))
                    and path.endswith(('.mjs', '.json')))):
            conversation_runtime = True
        elif path in RUNTIME_FILES or (runtime_dependencies and path in RUNTIME_DEPENDENCIES):
            native_runtime = True
        elif path in FOUNDATION_FILES or (
                path.startswith('packages/capability-agent-kernel/tests/') and path.endswith('.py')):
            foundation = True
        elif path in GOVERNANCE_FILES or path.startswith("tools/issue_automation/") or (
                path.startswith("tools/tests/test_issue_automation") and path.endswith(".py")):
            governance = True
        elif path.endswith(".py") and path.startswith((
                "packages/capstone-agent/src/capstone_agent/",
                "packages/capstone-agent/tests/")):
            shared_agent = True
            name=PurePosixPath(path).stem
            covered=(name in CONVERSATION_BACKEND_MODULES if path.startswith('packages/capstone-agent/src/')
                     else name in CONVERSATION_BACKEND_TESTS or name.startswith('test_general_pi_'))
            uncovered_backend = uncovered_backend or not covered
        elif path.startswith("packages/capstone-app/src/") and (path.endswith((
                ".ts", ".tsx", ".css")) or path.startswith("packages/capstone-app/src/fixtures/") and path.endswith('.json')):
            shared_agent = True
        elif path not in DOC_FILES and not path.startswith(("docs/", "tools/project_overview/")):
            return "product"
    if native_runtime or foundation and conversation_runtime:
        return 'native-runtime'
    if conversation_runtime:
        if uncovered_backend:
            return 'product'
        return 'conversation-runtime'
    if foundation:
        return 'foundation'
    if shared_agent:
        return "shared-agent"
    return "governance" if governance else "docs"


def _app_path(path: str) -> bool:
    location = PurePosixPath(path)
    if path.startswith('packages/capstone-app/public/') and location.name.startswith('LICENSE'):
        return True
    return (path.startswith(('packages/capstone-app/src/', 'packages/capstone-app/public/'))
            and location.suffix in {'.ts', '.tsx', '.css', '.json', '.svg', '.png', '.html', '.woff2'}
            or path in {'packages/capstone-app/' + name for name in
                        ('package.json', 'package-lock.json', 'vite.config.ts', 'tsconfig.json',
                         'tsconfig.app.json', 'tsconfig.node.json', 'index.html')})


def _control_path(path: str) -> bool:
    return (path in DOC_FILES | GOVERNANCE_FILES or path.startswith(('docs/', 'tools/project_overview/'))
            or path.startswith('.superpowers/sdd/') and path.endswith('.md'))


def _workbench_path(path: str) -> bool:
    # Full owning suites cover new modules too. Authority bridges, dependency
    # manifests and unrelated Kernel changes deliberately remain outside.
    if path.endswith('/kernel_pi_session.py'):
        return False
    location = PurePosixPath(path)
    if _app_path(path) or _control_path(path):
        return True
    if path.startswith(('packages/capstone-agent/src/capstone_agent/',
                        'packages/capstone-agent/tests/',
                        'packages/enterprise-research-domain-pack/src/',
                        'packages/enterprise-research-domain-pack/tests/',
                        'packages/pi-capability-tools/src/', 'packages/pi-capability-tools/test/')):
        return location.suffix in {'.py', '.mjs', '.json', '.md'}
    if path.startswith('packages/capability-agent-kernel/tests/'):
        return location.suffix == '.py'
    return path in ADAPTIVE_KERNEL_FILES | {
        'packages/capability-agent-kernel/src/capability_agent/runtime/step_events.py',
        'compose.yaml', 'deploy/local.env.example', 'deploy/general-pi.Dockerfile',
        'deploy/launch_host_runtime.py', 'configs/runtime/data-gateway.json',
        'configs/runtime/workbench-llm-profiles.json',
        'configs/runtime/general-pi/model-transport.json', 'tools/native_report.py',
        'tools/native_analysis_smoke.py', 'tools/tests/test_host_runtime_contract.py',
        'tools/tests/test_image_layer_order.py', 'tools/tests/test_native_presentation.py',
        'tools/tests/test_native_report.py',
    }


def gateway_deployment_document(path: str, old: str, new: str) -> bool:
    if path == 'compose.yaml':
        anchor = '      CAPSTONE_DATA_GATEWAY_CONNECTION_FILE: ${CAPSTONE_DATA_GATEWAY_CONNECTION_FILE:-}\n'
        additions = ['      CAPSTONE_GATEWAY_LOOPBACK_HOST: ${CAPSTONE_GATEWAY_LOOPBACK_HOST:-host.docker.internal}\n']
    elif path == 'deploy/general-pi.Dockerfile':
        anchor = 'COPY packages/capstone-agent/src/capstone_agent/data_gateway_relay.py capstone_agent/data_gateway_relay.py\n'
        additions = ['COPY packages/capstone-agent/src/capstone_agent/' + name + '.py capstone_agent/' + name + '.py\n'
                     for name in ('gateway_connections', 'gateway_connections_runtime')]
    else:
        return False
    def normalize(text):
        if text.count(anchor) != 1:
            raise ValueError('missing deployment anchor')
        block = anchor
        for line in additions:
            if text.count(line) > 1:
                raise ValueError('duplicate deployment entry')
            if line in text:
                block += line
        if block not in text:
            raise ValueError('gateway additions outside registered location')
        return text.replace(block, anchor, 1)
    try:
        return normalize(old) == normalize(new)
    except ValueError:
        return False


def gateway_deployment_diff(paths: list[str], base: str, head: str) -> bool:
    for path in set(paths) & {'compose.yaml', 'deploy/general-pi.Dockerfile'}:
        try:
            old, new = [subprocess.check_output(['git', 'show', f'{revision}:{path}'], text=True)
                        for revision in (base, head)]
            if not gateway_deployment_document(path, old, new):
                return False
        except (subprocess.CalledProcessError, OSError):
            return False
    return True


def gateway_controls_paths(paths: list[str], *, deployment: bool = False) -> bool:
    """Bound gateway administration to its own modules and direct host consumers."""
    modules = {'gateway_connections', 'gateway_connections_http', 'gateway_connections_runtime'}
    source = 'packages/capstone-agent/src/capstone_agent/'
    if not any(path == source + name + '.py' for name in modules for path in paths):
        return False
    sources = {source + name + '.py' for name in modules | {'general_pi_server', 'host_api', 'pi_delegation'}}
    tests = {'packages/capstone-agent/tests/test_' + name + '.py' for name in modules | {
        'general_pi_server', 'general_pi_native', 'pi_delegation', 'host_api',
        'thread_http_api', 'network_policy_http', 'native_network_policy'}}
    deployments = {'compose.yaml', 'deploy/general-pi.Dockerfile'} if deployment else set()
    tests |= {'tools/tests/test_host_runtime_contract.py', 'tools/tests/test_image_layer_order.py'}
    return all(_app_path(path) or _control_path(path) or path in sources | tests | deployments
               for path in paths)


GATEWAY_BINDING_MODULES = {
    'data_gateway_views', 'data_gateway_relay', 'data_gateway_mcp',
    'grid_source_topology', 'grid_source_http', 'grid_electrical_view',
    'general_pi_server', 'pi_delegation', 'delegated_runtime',
    'native_tool_diagnostics',
}
GATEWAY_BINDING_RESOURCES = {
    'gateway-tool-use', 'general-tool-discovery', 'tool-composition',
}

EXECUTION_LIFECYCLE_ANCHOR = 'packages/capability-agent-kernel/src/capability_agent/runtime/execution_queue.py'
EXECUTION_LIFECYCLE_FILES = {EXECUTION_LIFECYCLE_ANCHOR,
    'configs/runtime/application-capacity.json',
    'packages/capstone-agent/src/capstone_agent/resources/application-capacity.json',
    'packages/capstone-agent/tests/test_application_capacity.py',
    'packages/capstone-agent/tests/test_relay_backpressure.py',
    'packages/capability-agent-kernel/tests/runtime/test_execution_queue.py',
    'packages/pandapower-application/src/pandapower_application/domain_tools.py',
    'packages/pandapower-application/tests/test_domain_execution_lifecycle.py',
    'packages/pandapower-domain-pack/src/pandapower_domain/execution.py',
    'packages/pandapower-domain-pack/tests/test_execution.py',
    'packages/capstone-agent/tests/application-tool-dispatch.test.mjs',
    '.github/workflows/verify.yml', 'tools/ci_scope.py',
    'tools/tests/test_ci_execution_lifecycle.py', 'tools/tests/test_ci_gateway_bindings.py',
    'tools/tests/test_execution_lifecycle_packaging.py',
    'tools/tests/test_host_runtime_contract.py', 'tools/tests/test_image_layer_order.py',
} | {'packages/capstone-agent/src/capstone_agent/' + name + '.py'
     for name in GATEWAY_BINDING_MODULES | {'native_graph_events', 'tool_execution_receipt'}} | {
    'packages/capstone-agent/tests/test_' + name + '.py'
    for name in GATEWAY_BINDING_MODULES | {'tool_execution_receipt', 'graph_host_observation', 'gateway_progressive', 'progress'}
} | {'packages/capstone-agent/src/capstone_agent/resources/' + name for name in (
    'gateway-tool-use.mjs', 'general-tool-discovery.mjs', 'tool-composition.mjs',
    'general-data-gateway.mjs', 'general-sdk.mjs', 'general-domain-tools.mjs', 'tool-composition-policy.json',
    'tool-call-scheduler.mjs', 'delegation-tool.mjs', 'llm-call-tools.mjs')
} | {'packages/capstone-agent/tests/fixtures/' + name + '.test.mjs' for name in (
    'gateway-tool-use', 'tool-discovery', 'tool-composition', 'data-gateway-research', 'general-sdk-graph')
} | {'packages/capstone-app/src/' + name for name in (
    'CapstoneAssistantThread.tsx', 'CapstoneAssistantThread.test.tsx',
    'ExecutionGraphProcess.tsx', 'ExecutionGraphProcess.test.tsx',
    'ProcessCallTrace.tsx', 'ProcessCallTrace.test.tsx', 'executionGraph.ts', 'executionGraph.test.ts',
    'processCallTrace.css', 'toolExecutionReceipt.ts', 'toolExecutionReceipt.test.ts', 'toolExecutionReceipt.fixture.ts',
    'electricalModelView.ts', 'electricalModelView.test.ts')
} | {'docs/status/' + name for name in (
    'CURRENT-STATE.md', 'INDEX.md', 'JOURNAL.md', 'PROJECT-OVERVIEW.html', 'VERSION-CONTROL.md', 'RESUME-NEXT-SESSION.md')
} | {'docs/' + name for name in (
    'superpowers/specs/2026-10-07-capstone-core-evolution-discussion.md',
    'superpowers/plans/2026-10-16-enterprise-unified-execution.md',
    'reports/2026-11-07-capstone-progressive-gateway-v1.md',
    'reports/2026-11-07-gateway-progressive-disclosure-proposal.md',
    'reports/2026-11-08-tool-execution-lifecycle.md',
    'superpowers/plans/2026-11-07-gateway-contract-context-reuse.md',
    'superpowers/plans/2026-11-07-progressive-gateway-v1.md',
    'superpowers/plans/2026-11-08-tool-execution-lifecycle.md',
    'superpowers/specs/2026-11-07-gateway-contract-context-reuse-design.md',
    'superpowers/specs/2026-11-08-tool-execution-lifecycle-design.md')}


EXECUTION_LIFECYCLE_FILES |= {
    'README.md', 'README.zh-CN.md', 'configs/runtime/agent-resources.json',
    'packages/capstone-agent/src/capstone_agent/skill_activity.py',
    'packages/capstone-agent/src/capstone_agent/progress.py',
    'packages/capstone-agent/src/capstone_agent/resources/investigation-skills.mjs',
    'packages/capstone-agent/tests/test_investigation_skills.py',
    'packages/capstone-agent/tests/fixtures/investigation-skills.test.mjs',
    'packages/capstone-app/src/skillActivity.test.tsx',
    'packages/capstone-app/src/processTiming.ts',
    'packages/capstone-app/src/processTiming.test.ts',
    'docs/superpowers/specs/2026-11-08-investigation-skills-design.md',
    'docs/superpowers/plans/2026-11-08-investigation-skills.md',
    'docs/reports/2026-11-08-investigation-skills.md',
} | {'configs/runtime/general-pi/skills/' + name + '/SKILL.md' for name in (
    'brainstorming', 'task-planning-and-tracking', 'systematic-debugging',
    'verification-before-completion', 'data-investigation', 'data-quality-and-comparability')}


def execution_lifecycle_paths(paths: list[str], *, deployment: bool = False) -> bool:
    manifest = Path(__file__).resolve().parents[1] / 'configs/development/investigation-closeout-gate.json'
    joint = json.loads(manifest.read_text())['groups'] if manifest.exists() else {}
    covered = {path for group in joint.values() for path in group['paths'] if group.get('command')}
    allowed = EXECUTION_LIFECYCLE_FILES | covered | {
        'configs/development/investigation-closeout-gate.json', 'tools/check_investigation_closeout.py',
    } | ({'compose.yaml', 'deploy/general-pi.Dockerfile'} if deployment else set())
    return EXECUTION_LIFECYCLE_ANCHOR in paths and all(path in allowed for path in paths)


def execution_lifecycle_deployment_document(path: str, old: str, new: str) -> bool:
    """Permit only the tested scheduler staging and worker receipt-volume binding."""
    if path == 'deploy/general-pi.Dockerfile':
        # The grouped recipe also stages frozen skill scope and report readers.
        # Admit only this reviewed transition, not arbitrary COPY regrouping.
        # Source-path classification and consumer gates remain independent.
        from hashlib import sha256
        reviewed = (
            '09ed804e47b5f246f6cc3b5a532b6ccb0eceb5f8d1a7b311d2918d6e83cbcbb7',
            '094341dd6feb9b66cb3b7f20342dd8e0bed64567ef1a5d42fada74473e3b86cf',
        )
        if (sha256(old.encode()).hexdigest(), sha256(new.encode()).hexdigest()) == reviewed:
            return True
    if path == 'compose.yaml':
        anchor = '      CAPSTONE_THREAD_FAMILY: pandapower\n    command: [worker]'
        replacement = '      CAPSTONE_THREAD_FAMILY: pandapower\n      CAPSTONE_DOMAIN_EXECUTION_RECEIPTS_ROOT: /app/runs/domain-control\n    command: [worker]'
    elif path == 'deploy/general-pi.Dockerfile':
        source = 'packages/capstone-agent/src/capstone_agent/'
        # Only the named skill modules and the SDK import smoke may accompany
        # the existing owner staging; other Docker changes still fail closed.
        new = new.replace(
            f'COPY {source}general_pi_server.py {source}skill_activity.py capstone_agent/\n',
            f'COPY {source}general_pi_server.py capstone_agent/general_pi_server.py\n', 1)
        new = new.replace(
            f'{source}resources/managed-resource-tools.mjs {source}resources/investigation-skills.mjs capstone_agent/resources/',
            f'{source}resources/managed-resource-tools.mjs capstone_agent/resources/', 1)
        new = new.replace('await import("./capstone_agent/resources/general-sdk.mjs"); ', '', 1)
        anchor = ''.join(f'COPY {source}{name}.py capstone_agent/{name}.py\n' for name in (
            '__init__', 'runtime_resources', 'resource_installation'))
        replacement = ('COPY ' + source + '__init__.py \\\n'
            '     ' + source + 'tool_execution_receipt.py \\\n'
            '     ' + source + 'runtime_resources.py \\\n'
            '     ' + source + 'resource_installation.py capstone_agent/\n'
            '# Stage only the stdlib-only Kernel primitive. Namespace packages avoid loading\n'
            '# unrelated Kernel public exports into the isolated native host.\n'
            'COPY packages/capability-agent-kernel/src/capability_agent/runtime/execution_queue.py capability_agent/runtime/execution_queue.py\n')
    else:
        return False
    return old.count(anchor) == 1 and new == old.replace(anchor, replacement, 1)


def execution_lifecycle_deployment_diff(paths: list[str], base: str, head: str) -> bool:
    for path in ('compose.yaml', 'deploy/general-pi.Dockerfile'):
        if path not in paths:
            continue
        try:
            old, new = [subprocess.check_output(['git', 'show', f'{revision}:{path}'], text=True)
                        for revision in (base, head)]
            if not execution_lifecycle_deployment_document(path, old, new):
                return False
        except (subprocess.CalledProcessError, OSError):
            return False
    return True


def gateway_bindings_deployment_document(old: str, new: str) -> bool:
    """Only the new view adapter COPY may change in this development route."""
    addition = ('COPY packages/capstone-agent/src/capstone_agent/data_gateway_views.py '
                'capstone_agent/data_gateway_views.py\n')
    return (old.count(addition) <= new.count(addition) <= 1
            and old.replace(addition, '') == new.replace(addition, ''))


def gateway_bindings_deployment_diff(paths: list[str], base: str, head: str) -> bool:
    path = 'deploy/general-pi.Dockerfile'
    if path not in paths:
        return True
    try:
        old, new = [subprocess.check_output(['git', 'show', f'{revision}:{path}'], text=True)
                    for revision in (base, head)]
        return gateway_bindings_deployment_document(old, new)
    except (subprocess.CalledProcessError, OSError):
        return False


def gateway_bindings_startup_document(old: str, new: str) -> bool:
    """Admit only the catalog entry binding at the existing discovery call."""
    anchor = ('  return createToolDiscovery({tools:createDataGatewayTools(config),'
              'publications:config.dataGateway.catalog.tools,\n')
    addition = '    initialNames:config.dataGateway.catalog.entry_tools??[],\n'
    return (old.count(anchor) == new.count(anchor) == 1
            and old.count(addition) == 0 and new.count(addition) == 1
            and anchor + addition in new
            and old == new.replace(addition, '', 1))


def gateway_bindings_startup_diff(paths: list[str], base: str, head: str) -> bool:
    path = 'packages/capstone-agent/src/capstone_agent/resources/general-sdk.mjs'
    if path not in paths:
        return False
    try:
        old, new = [subprocess.check_output(['git', 'show', f'{revision}:{path}'], text=True)
                    for revision in (base, head)]
        return gateway_bindings_startup_document(old, new)
    except (subprocess.CalledProcessError, OSError):
        return False


def gateway_bindings_paths(paths: list[str], *, deployment: bool = False, startup: bool = False) -> bool:
    source = 'packages/capstone-agent/src/capstone_agent/'
    resources = {source + 'resources/' + name + '.mjs' for name in GATEWAY_BINDING_RESOURCES}
    progressive = {source + name for name in ('data_gateway_mcp.py', 'data_gateway_relay.py',
                    'resources/general-data-gateway.mjs')} <= set(paths)
    if progressive:
        resources.update(source + 'resources/' + name + '.mjs' for name in ('general-data-gateway', 'general-sdk'))
    if startup:
        resources.add(source + 'resources/general-sdk.mjs')
    anchors = {source + 'data_gateway_views.py'} | {
        source + 'resources/' + name + '.mjs' for name in (
            'gateway-tool-use', 'general-tool-discovery', 'tool-composition')}
    if not set(paths) & anchors:
        return False
    sources = {source + name + '.py' for name in GATEWAY_BINDING_MODULES}
    tests = {'packages/capstone-agent/tests/test_' + name + '.py'
             for name in GATEWAY_BINDING_MODULES | {
                 'graph_host_observation', 'gateway_progressive', 'progress'}}
    fixtures = {'packages/capstone-agent/tests/fixtures/' + name + '.test.mjs'
                for name in ('gateway-tool-use', 'tool-discovery', 'tool-composition',
                             'data-gateway-research')}
    deployments = {'deploy/general-pi.Dockerfile'} if deployment else set()
    app_consumers = {'packages/capstone-app/src/electricalModelView.ts',
                     'packages/capstone-app/src/electricalModelView.test.ts'}
    return all('..' not in PurePosixPath(path).parts and (
        path in sources | resources | tests | fixtures | deployments | app_consumers
        or path in {'tools/tests/test_host_runtime_contract.py', 'tools/tests/test_image_layer_order.py'}
        or _control_path(path)) for path in paths)


SESSION_CAPACITY_FILES = {
    'packages/capstone-agent/src/capstone_agent/' + name for name in (
        'thread_worker.py', 'thread_worker_capacity.py', 'thread_service.py',
        'native_hosted_worker.py', 'general_pi_server.py',
        'resources/tool-composition.mjs', 'resources/observation-read-budget.mjs')
} | {
    'packages/capstone-agent/tests/' + name for name in (
        'test_thread_worker_capacity.py', 'test_thread_worker_postgres_capacity.py',
        'test_thread_work_execution.py', 'test_enterprise_normal_chat.py',
        'fixtures/tool-composition.test.mjs')
} | {'tools/tests/test_image_layer_order.py', 'tools/tests/test_ci_session_capacity.py',
     'packages/capstone-app/src/CapstoneAssistantThread.tsx',
     'packages/capstone-app/src/ThinkingProcess.test.tsx'}


def session_capacity_deployment_document(path: str, old: str, new: str) -> bool:
    line = {
        'compose.yaml': '  CAPSTONE_NATIVE_MAX_CONCURRENT_ATTEMPTS: ${CAPSTONE_NATIVE_MAX_CONCURRENT_ATTEMPTS:-1}\n',
        'deploy/general-pi.Dockerfile': '     packages/capstone-agent/src/capstone_agent/resources/observation-read-budget.mjs \\\n',
    }.get(path)
    return bool(line and old.count(line) <= new.count(line) <= 1
                and old.replace(line, '') == new.replace(line, ''))


def session_capacity_deployment_diff(paths: list[str], base: str, head: str) -> bool:
    for path in set(paths) & {'compose.yaml', 'deploy/general-pi.Dockerfile'}:
        try:
            old, new = [subprocess.check_output(['git', 'show', f'{revision}:{path}'], text=True)
                        for revision in (base, head)]
            if not session_capacity_deployment_document(path, old, new):
                return False
        except (subprocess.CalledProcessError, OSError):
            return False
    return True


def session_capacity_paths(paths: list[str], *, deployment: bool = False) -> bool:
    anchors = {'packages/capstone-agent/src/capstone_agent/thread_worker.py',
               'packages/capstone-agent/src/capstone_agent/resources/observation-read-budget.mjs'}
    return bool(set(paths) & anchors) and all(
        path in SESSION_CAPACITY_FILES or path in GOVERNANCE_FILES or path in DOC_FILES
        or path.startswith(('docs/', 'tools/project_overview/'))
        or deployment and path in {'compose.yaml', 'deploy/general-pi.Dockerfile'}
        for path in paths)


def gateway_capabilities_paths(paths: list[str]) -> bool:
    source = 'packages/capstone-agent/src/capstone_agent/'
    anchor = source + 'resources/general-tool-discovery.mjs'
    modules = {'data_gateway_mcp', 'gateway_connections_http', 'general_pi_server', 'thread_service'}
    allowed = {source + name + '.py' for name in modules} | {anchor}
    allowed |= {'packages/capstone-agent/tests/' + name for name in (
        'test_data_gateway_mcp.py', 'test_general_pi_server.py',
        'test_thread_gateway.py', 'test_thread_gateway_http.py',
        'fixtures/tool-discovery.test.mjs', 'fixtures/tool-composition.test.mjs')}
    allowed |= {'packages/capstone-app/src/' + name for name in (
        'GatewayStatus.tsx', 'GatewayStatus.test.tsx',
        'WorkspaceConnectionStatus.tsx', 'WorkspaceConnectionStatus.test.tsx',
        'threadHttpTransport.ts', 'threadHttpTransport.test.ts')}
    return anchor in paths and all(path in allowed or _control_path(path) for path in paths)


def classify(paths: list[str], *, target: str = 'dev', release: bool = False,
             runtime_dependencies: bool = False, source_topology: bool = False,
             gateway_deployment: bool = False, gateway_bindings_deployment: bool = False,
             gateway_bindings_startup: bool = False, session_capacity_deployment: bool = False,
             execution_lifecycle_deployment: bool = False) -> str:
    if target == 'main' or release:
        return 'release'
    if not paths or any('..' in PurePosixPath(path).parts for path in paths):
        return 'product'
    import json
    manifest = Path(__file__).resolve().parents[1] / 'configs/development/architecture-retirement-gate.json'
    if manifest.is_file():
        retirement = json.loads(manifest.read_text())
        if set(retirement['anchors']).issubset(paths) and set(paths).issubset(retirement['paths']):
            return 'architecture-retirement'
    if execution_lifecycle_paths(paths, deployment=execution_lifecycle_deployment):
        return 'execution-lifecycle'
    if gateway_capabilities_paths(paths):
        return 'gateway-capabilities'
    if session_capacity_paths(paths, deployment=session_capacity_deployment):
        return 'session-capacity'
    if any(_app_path(path) for path in paths) and all(_app_path(path) or _control_path(path) for path in paths):
        return 'app'
    if gateway_bindings_paths(paths, deployment=gateway_bindings_deployment, startup=gateway_bindings_startup):
        return 'gateway-bindings'
    if gateway_controls_paths(paths, deployment=gateway_deployment):
        return 'gateway-controls'
    gate = _scoped_gate(paths, target=target, release=release,
                        runtime_dependencies=runtime_dependencies, source_topology=source_topology)
    if gate == 'product' and all(_workbench_path(path) for path in paths):
        return 'workbench'
    return gate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--target", default="dev")
    parser.add_argument("--release", action="store_true")
    parser.add_argument("--check-docs", action="store_true")
    args = parser.parse_args()
    # A target branch may contain independent commits. Scope only the proposed
    # branch delta, as a PR does, rather than treating target-only files as removals.
    args.base = subprocess.check_output(
        ['git', 'merge-base', args.base, args.head], text=True).strip()
    # Include both names of a rename so moving product code into docs is not a shortcut.
    output = subprocess.check_output(["git", "diff", "--no-renames", "--name-only", "-z",
                                      args.base, args.head, "--"], text=True)
    paths = [p for p in output.split("\0") if p]
    if args.check_docs:
        check_document_links(Path.cwd(), paths)
        print("Changed Markdown file links passed")
    else:
        print(classify(paths, target=args.target, release=args.release,
                       execution_lifecycle_deployment=execution_lifecycle_deployment_diff(paths, args.base, args.head),
                       session_capacity_deployment=session_capacity_deployment_diff(paths, args.base, args.head),
                       gateway_bindings_startup=gateway_bindings_startup_diff(paths, args.base, args.head),
                       gateway_bindings_deployment=gateway_bindings_deployment_diff(paths, args.base, args.head),
                       gateway_deployment=gateway_deployment_diff(paths, args.base, args.head),
                       runtime_dependencies=runtime_dependency_diff(paths, args.base, args.head),
                       source_topology=source_topology_diff(paths, args.base, args.head)))


def is_ignored_delivery_link(root: Path, document: Path, target: str) -> bool:
    """Allow absent operator delivery artifacts, never absent repository docs."""
    if target.startswith("/") or not re.fullmatch(r"[A-Za-z0-9._/-]+", target):
        return False
    parts = target.split("/")
    while parts and parts[0] in {".", ".."}:
        parts.pop(0)
    if not parts or any(not part or part.startswith(".") for part in parts):
        return False
    candidate = document.parent / target
    if any(path.is_symlink() for path in (candidate, *candidate.parents)):
        return False
    root = root.resolve()
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root / "runs/user-local-offline"):
        return False
    relative = resolved.relative_to(root)
    if any(part.startswith(".") for part in relative.parts):
        return False
    if resolved.name != "README.md" and not resolved.name.endswith((".tar.gz", ".tar.gz.sha256")):
        return False
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "check-ignore", "-q", "--", relative.as_posix()],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def check_document_links(root: Path, paths: list[str]) -> None:
    root = root.resolve()
    missing = []
    for path in paths:
        file = root / path
        if not path.endswith(".md") or not file.is_file():
            continue
        text = re.sub(r"```.*?```", "", file.read_text(), flags=re.S)
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
            target = target.strip().strip("<>").split("#", 1)[0]
            if not target or re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("/"):
                continue
            if not (file.parent / unquote(target)).exists() and not is_ignored_delivery_link(root, file, target):
                missing.append(f"{path}: {target}")
    if missing:
        raise ValueError("Missing relative document links: " + "; ".join(missing))


if __name__ == "__main__":
    main()
