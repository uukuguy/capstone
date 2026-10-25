"""Check that development shortcuts never hide product or release changes."""
from tools.ci_scope import classify, check_document_links
import pytest
from pathlib import Path
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def test_documentation_and_overview_changes():
    assert classify(["docs/status/PROJECT-OVERVIEW.html", "README.md"]) == "docs"
    assert classify(["tools/project_overview/template.html", "tools/render_project_overview.py"]) == "docs"


def test_governance_changes_require_gate_tests():
    assert classify([".github/workflows/verify.yml", "tools/ci_scope.py", "docs/RUNBOOK.md"]) == "governance"
    assert classify(["tools/tests/test_verification_targets.py"]) == "governance"
    assert classify(["tools/issue_automation/cli.py", "tools/tests/test_issue_automation_cli.py"]) == "governance"


def test_issue_automation_policy_uses_its_governance_gate():
    paths = ["configs/development/issue-automation.json", "tools/issue_automation/policy.py"]
    assert classify(paths) == "governance"
    assert classify(paths, target="main") == "release"
    assert classify(paths, release=True) == "release"
    assert classify(paths + ["configs/runtime/agent-resources.json"]) == "product"


def test_product_and_unknown_paths_fail_closed():
    for path in ["packages/capstone-agent/src/server.py", "Makefile", "uv.lock",
                 ".github/workflows/deploy.yml", "tools/unregistered_tool.py",
                 "README.md.py", "docs/../packages/model.py"]:
        assert classify(["docs/RUNBOOK.md", path]) == "product"
    assert classify([]) == "product"


def test_main_and_explicit_release_always_use_complete_gate():
    assert classify(["README.md"], target="main") == "release"
    assert classify(["README.md"], release=True) == "release"


def test_shared_agent_python_changes_select_dependency_regression():
    paths = ["packages/capstone-agent/src/capstone_agent/harness.py",
             "packages/capstone-agent/tests/test_enterprise_context.py",
             "docs/status/CURRENT-STATE.md"]
    assert classify(paths) == "shared-agent"
    assert classify(paths, target="main") == "release"
    assert classify(paths, release=True) == "release"


@pytest.mark.parametrize("extra", [
    "packages/capstone-agent/pyproject.toml",
    "packages/capstone-agent/uv.lock",
    "packages/capstone-agent/src/capstone_agent/kernel_pi_session.py",
    "packages/capstone-agent/src/capstone_agent/pi_delegation.py",
    "packages/capability-agent-kernel/src/capability_agent/core.py",
    "packages/pypsa-domain-pack/src/solver.py",
    "deploy/Dockerfile",
    "Makefile",
    "packages/capstone-agent/src/../pyproject.toml",
])
def test_shared_agent_mixed_runtime_or_unknown_change_expands_gate(extra):
    assert classify(["packages/capstone-agent/src/capstone_agent/harness.py", extra]) == "product"


def test_shared_agent_and_governance_keep_product_regression():
    assert classify(["packages/capstone-agent/src/capstone_agent/harness.py",
                     "tools/ci_scope.py"]) == "shared-agent"


def test_native_runtime_has_bounded_consumer_regression():
    paths = ['packages/capstone-agent/src/capstone_agent/general_pi_server.py',
             'packages/capstone-agent/src/capstone_agent/resources/general-sdk.mjs',
             'packages/capstone-agent/tests/fixtures/data-gateway-research.test.mjs',
             'configs/runtime/data-gateway.json', 'compose.yaml', 'deploy/general-pi.Dockerfile']
    assert classify(paths) == 'native-runtime'
    assert classify(paths + ['packages/grid-simulator/src/grid_simulator/powermcp_sidecar.py']) == 'native-runtime'
    assert classify(paths + ['packages/pypsa-agent/src/pypsa_agent/worker.py']) == 'native-runtime'
    assert classify(paths, target='main') == 'release'
    assert classify(paths, release=True) == 'release'
    for extra in ['packages/grid-simulator/src/grid_simulator/solver.py',
                  'packages/capstone-agent/src/capstone_agent/pi_delegation.py',
                  'packages/grid-agent/uv.lock', 'deploy/Dockerfile', 'Makefile']:
        assert classify(paths + [extra]) == 'product'


@pytest.mark.parametrize('path', [
    'packages/capstone-agent/src/capstone_agent/general_pi_server.py',
    'packages/capstone-agent/src/capstone_agent/general_pi_executor.py',
    'packages/capstone-agent/src/capstone_agent/resources/general-sdk.mjs',
    'packages/capstone-agent/src/capstone_agent/resources/application-capacity.json',
    'packages/capstone-agent/tests/fixtures/systematic-diagnosis.test.mjs',
    'packages/capstone-agent/tests/fixtures/case.json',
    'packages/capstone-agent/tests/general-sdk-shell.test.mjs',
    'packages/capstone-agent/tests/general-sdk-capacity.test.mjs',
    'packages/capstone-agent/tests/managed-subagents-sdk.test.mjs',
    'packages/capstone-agent/tests/delivery-review-sdk.test.mjs',
    'packages/capstone-agent/tests/research-guidance.test.mjs',
    'deploy/general-pi.Dockerfile',
    'packages/pi-capability-tools/src/research-tools.mjs',
    'packages/pi-capability-tools/src/research-context-window.mjs',
])
def test_conversation_runtime_uses_affected_consumer_gate(path):
    assert classify([path]) == 'conversation-runtime'
    mixed = [path, 'packages/capstone-agent/src/capstone_agent/thread_work.py',
             'packages/capstone-agent/tests/test_native_diagnosis.py',
             'packages/capstone-app/src/ThreadWorkAdapter.tsx',
             'packages/capstone-app/src/fixtures/nativeGraph-tools.json', 'tools/ci_scope.py', 'docs/RUNBOOK.md']
    assert classify(mixed) == 'conversation-runtime'
    assert classify(mixed, target='main') == 'release'
    assert classify(mixed, release=True) == 'release'


@pytest.mark.parametrize('extra', [
    'compose.yaml', 'configs/runtime/data-gateway.json',
    'packages/grid-simulator/src/grid_simulator/powermcp_sidecar.py',
    'packages/capability-agent-kernel/src/capability_agent/application/composition.py',
])
def test_conversation_mixed_foundation_or_native_infrastructure_widens(extra):
    assert classify(['packages/capstone-agent/src/capstone_agent/resources/general-sdk.mjs', extra]) == 'native-runtime'


@pytest.mark.parametrize('extra', [
    'packages/grid-agent/src/grid_agent/authority.py',
    'packages/grid-simulator/src/grid_simulator/solver.py',
    'packages/pypsa-agent/src/pypsa_agent/solver.py',
    'packages/pypsa-domain-pack/src/solver.py',
    'packages/capstone-agent/src/capstone_agent/kernel_pi_session.py',
    'packages/capstone-agent/src/capstone_agent/pi_delegation.py',
    'packages/capstone-agent/pyproject.toml', 'packages/grid-agent/uv.lock',
    'packages/capstone-app/package-lock.json', 'packages/capstone-app/src/unknown.json',
    'packages/pi-capability-tools/src/new-professional-tools.mjs',
    'packages/pi-capability-tools/package.json', 'deploy/Dockerfile', 'Makefile', 'unknown.file',
    'packages/capstone-agent/tests/unregistered/test-professional.test.mjs',
])
def test_conversation_unknown_professional_or_dependency_change_still_requires_product(extra):
    assert classify(['packages/capstone-agent/src/capstone_agent/resources/general-sdk.mjs', extra]) == 'product'


def test_conversation_does_not_bypass_verified_mcp_dependency_consumer_gate():
    assert classify(['packages/capstone-agent/src/capstone_agent/resources/general-sdk.mjs',
                     'packages/capstone-agent/pyproject.toml'], runtime_dependencies=True) == 'native-runtime'


def test_runtime_dependency_scope_checks_content_not_only_path():
    from tools.ci_scope import runtime_dependency_document
    from copy import deepcopy
    path = 'packages/capstone-agent/pyproject.toml'
    old = {'project': {'dependencies': ['httpx>=0.28,<1']}}
    new = deepcopy(old)
    new['project']['dependencies'].append('mcp>=1.30,<2')
    assert runtime_dependency_document(path, old, new)
    new['project']['dependencies'].append('pandapower==3.5')
    assert not runtime_dependency_document(path, old, new)
    assert not runtime_dependency_document('packages/grid-agent/pyproject.toml', old, new)
    old = {'version': 1, 'package': [
        {'name': 'capstone-agent', 'dependencies': [{'name': 'httpx'}]},
        {'name': 'pandapower', 'version': '3.4.0'}]}
    new = deepcopy(old)
    new['package'][0]['dependencies'].append({'name': 'mcp'})
    new['package'].append({'name': 'mcp', 'version': '1.30.0'})
    assert runtime_dependency_document('packages/grid-agent/uv.lock', old, new)
    new['package'][1]['version'] = '3.5.0'
    assert not runtime_dependency_document('packages/grid-agent/uv.lock', old, new)


def test_verified_runtime_dependency_diff_still_cannot_hide_unknown_source():
    paths = ['packages/capstone-agent/pyproject.toml', 'packages/grid-agent/uv.lock']
    assert classify(paths, runtime_dependencies=True) == 'native-runtime'
    assert classify(paths + ['packages/grid-simulator/src/grid_simulator/solver.py'],
                    runtime_dependencies=True) == 'product'


def test_foundation_assembly_has_an_explicit_dependency_gate():
    from tools.ci_scope import FOUNDATION_FILES
    for path in FOUNDATION_FILES:
        assert classify([path, 'tools/ci_scope.py']) == 'foundation'
    paths = ['packages/capability-agent-kernel/tests/application/test_pack_selection.py',
             'packages/capstone-agent/src/capstone_agent/application.py']
    assert classify(paths) == 'foundation'
    assert classify(paths, target='main') == 'release'
    for extra in ['packages/capability-agent-kernel/src/capability_agent/runtime/environment.py',
                  'packages/capability-agent-kernel/src/capability_agent/domain/authority.py',
                  'packages/grid-agent/src/grid_agent/new_executor.py',
                  'packages/pypsa-domain-pack/src/solver.py', 'Makefile']:
        assert classify(paths + [extra]) == 'product'


def test_app_source_and_shared_agent_use_the_same_contract_gate():
    app = "packages/capstone-app/src/threadProtocol.ts"
    assert classify([app]) == "shared-agent"
    assert classify([app, "packages/capstone-agent/src/capstone_agent/thread_protocol.py"]) == "shared-agent"
    assert classify([app, "packages/capstone-app/package-lock.json"]) == "product"
    assert classify([app, "packages/capstone-app/vite.config.ts"]) == "product"


def workflow_scope_script():
    workflow = (ROOT / ".github/workflows/verify.yml").read_text()
    script = workflow.split("        run: |\n", 1)[1].split("      - name: Install uv", 1)[0]
    return "\n".join(line.removeprefix("          ") for line in script.splitlines())


def test_workflow_classifier_failure_cannot_produce_green_gate(tmp_path):
    output = tmp_path / "output"
    result = subprocess.run(["bash", "-e", "-c", workflow_scope_script()], cwd=ROOT,
                            env={**os.environ, "BASE_SHA": "missing-revision",
                                 "HEAD_SHA": "HEAD", "TARGET_BRANCH": "dev",
                                 "RELEASE_CHECK": "false", "GITHUB_OUTPUT": str(output)},
                            capture_output=True)
    assert result.returncode != 0
    assert not output.exists()


def test_new_main_branch_event_still_requires_release(tmp_path):
    output = tmp_path / "output"
    result = subprocess.run(["bash", "-e", "-c", workflow_scope_script()], cwd=ROOT,
                            env={**os.environ, "BASE_SHA": "0" * 40, "HEAD_SHA": "HEAD",
                                 "TARGET_BRANCH": "main", "RELEASE_CHECK": "false",
                                 "GITHUB_OUTPUT": str(output)}, capture_output=True)
    assert result.returncode == 0
    assert output.read_text().strip() == "gate=release"


def test_document_links_check_targets_and_allow_deleted_documents(tmp_path):
    (tmp_path / "guide.md").write_text("[target](target.md#topic) [web](https://example.com/)")
    with pytest.raises(ValueError, match="target.md"):
        check_document_links(tmp_path, ["guide.md"])
    (tmp_path / "target.md").write_text("# Topic")
    check_document_links(tmp_path, ["guide.md", "deleted.md"])


@pytest.fixture
def delivery_repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("/runs/\n")
    (tmp_path / "docs/status").mkdir(parents=True)
    return tmp_path


@pytest.mark.parametrize("name", ["README.md", "bundle.tar.gz", "bundle.tar.gz.sha256"])
def test_missing_ignored_delivery_links_pass_in_fresh_checkout(delivery_repo, name):
    guide = delivery_repo / "docs/status/guide.md"
    guide.write_text(f"[delivery](../../runs/user-local-offline/release/{name})")
    check_document_links(delivery_repo, ["docs/status/guide.md"])


@pytest.mark.parametrize("target", [
    "../missing.md", "../../runs/other/README.md",
    "../../runs/user-local-offline/release/other.md",
    "../../runs/user-local-offline/release/file.json",
    "../../runs/user-local-offline/.private/README.md",
    "../../runs/user-local-offline/release/../README.md",
    "../../runs/user-local-offline/%72elease/README.md",
    "../../../outside/runs/user-local-offline/README.md",
])
def test_missing_non_delivery_links_still_fail(delivery_repo, target):
    (delivery_repo / "docs/status/guide.md").write_text(f"[bad]({target})")
    with pytest.raises(ValueError, match="Missing relative"):
        check_document_links(delivery_repo, ["docs/status/guide.md"])


def test_missing_delivery_requires_git_ignore(delivery_repo):
    (delivery_repo / ".gitignore").write_text("")
    (delivery_repo / "docs/status/guide.md").write_text(
        "[delivery](../../runs/user-local-offline/release/README.md)")
    with pytest.raises(ValueError, match="Missing relative"):
        check_document_links(delivery_repo, ["docs/status/guide.md"])


def test_delivery_symlink_is_not_an_existence_exception(delivery_repo):
    delivery = delivery_repo / "runs/user-local-offline"
    delivery.mkdir(parents=True)
    (delivery / "release").symlink_to(delivery_repo / "missing", target_is_directory=True)
    (delivery_repo / "docs/status/guide.md").write_text(
        "[delivery](../../runs/user-local-offline/release/README.md)")
    with pytest.raises(ValueError, match="Missing relative"):
        check_document_links(delivery_repo, ["docs/status/guide.md"])


@pytest.mark.parametrize("target", ["javascript:alert", "/runs/user-local-offline/README.md",
                                   "https://example.com/README.md", "//example.com/README.md"])
def test_external_and_absolute_links_never_receive_delivery_exception(delivery_repo, target):
    from tools.ci_scope import is_ignored_delivery_link
    assert not is_ignored_delivery_link(delivery_repo, delivery_repo / "docs/status/guide.md", target)


def test_git_ignore_failure_cannot_exempt_delivery(delivery_repo, monkeypatch):
    import tools.ci_scope as scope
    calls = []

    def failed_git(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 128)

    monkeypatch.setattr(scope.subprocess, "run", failed_git)
    guide = delivery_repo / "docs/status/guide.md"
    guide.write_text("[delivery](../../runs/user-local-offline/release/README.md)")
    with pytest.raises(ValueError, match="Missing relative"):
        scope.check_document_links(delivery_repo, ["docs/status/guide.md"])
    assert calls == [["git", "-C", str(delivery_repo.resolve()), "check-ignore", "-q", "--",
                      "runs/user-local-offline/release/README.md"]]
