from __future__ import annotations

from fnmatch import fnmatchcase
import json
import os
import subprocess
import tomllib
import pytest
from pathlib import Path
from pathlib import PurePosixPath


ROOT = Path(__file__).resolve().parents[2]


def test_adaptive_agent_gate_keeps_full_owned_suites_without_professional_solvers():
    workflow = (ROOT / '.github/workflows/verify.yml').read_text()
    assert 'adaptive-agent|' in workflow
    block = workflow.split('      - name: Verify adaptive agent consumers\n', 1)[1].split('      - name:', 1)[0]
    assert "if: steps.scope.outputs.gate == 'adaptive-agent'" in block
    assert 'timeout-minutes: 15' in block
    for expected in ('check-package-boundaries', 'check-types', 'test-capstone-agent', 'test-kernel',
                     'test-capstone-app', 'build-capstone-app', 'test-capstone-client', 'test-registered-workers',
                     'node --test packages/capstone-agent/tests/*.test.mjs packages/capstone-agent/tests/fixtures/*.test.mjs',
                     'node --test packages/pi-capability-tools/test/*.test.mjs',
                     'pytest packages/enterprise-research-domain-pack/tests -q'):
        assert expected in block
    for forbidden in ('make check-pr', 'make check-release', 'test-domain-package', 'test-local-rebuild',
                      'packages/grid-agent/tests', 'packages/grid-simulator/tests', 'packages/pypsa-agent/tests',
                      'packages/pandapower-domain-pack/tests', 'test_user_local_installer.py'):
        assert forbidden not in block


def test_source_topology_gate_covers_direct_consumers_without_solver_or_release_suites():
    workflow = (ROOT / '.github/workflows/verify.yml').read_text()
    assert 'source-topology|' in workflow
    block = workflow.split('      - name: Verify source topology consumers\n', 1)[1].split('      - name:', 1)[0]
    assert "if: steps.scope.outputs.gate == 'source-topology'" in block
    assert 'timeout-minutes: 10' in block
    for expected in ('check-package-boundaries', 'check-types', 'test-capstone-app', 'build-capstone-app',
                     'test-capstone-client', 'test_grid_source_*.py', 'test_pi_delegation.py',
                     'test_general_pi_*.py', 'test_host*.py', 'test_thread*.py',
                     'test_data_gateway_*.py', 'test_network_policy_http.py', 'test_native_network_policy.py',
                     'test_enterprise_normal_chat.py', 'test_native_session_profile.py',
                     'test_harness.py', 'test_delegated_runtime.py',
                     'test_graph_host_observation.py',
                     'node --test packages/capstone-agent/tests/*.test.mjs packages/capstone-agent/tests/fixtures/*.test.mjs',
                     'tools/tests/test_image_layer_order.py', 'tools/tests/test_host_runtime_contract.py'):
        assert expected in block
    for forbidden in ('test-capstone-agent', 'test-kernel', 'test-registered-workers', 'test-domain-package',
                      'test-local-rebuild', 'test-inventory-pi', 'test-pi-capture-runtime',
                      'packages/grid-agent/tests', 'packages/grid-simulator/tests', 'packages/pypsa-agent/tests',
                      'make check-pr', 'make check-release', 'test_user_local_installer.py'):
        assert forbidden not in block
    foundation = workflow.split('      - name: Verify shared foundation assembly\n', 1)[1].split('      - name:', 1)[0]
    assert 'source-topology' not in foundation


def _dry_run(target: str) -> str:
    completed = subprocess.run(
        ["make", "-n", target], cwd=ROOT, text=True, capture_output=True, check=True
    )
    return completed.stdout


def test_offline_aggregate_covers_all_packages_without_grid_e2e() -> None:
    output = _dry_run("test")
    for expected in (
        "packages/capability-agent-kernel/tests",
        "packages/grid-agent/tests --ignore=packages/grid-agent/tests/e2e",
        "packages/grid-simulator/tests",
        "packages/pandapower-domain-pack/tests",
        "packages/inventory-domain-pack/tests --ignore=packages/inventory-domain-pack/tests/test_generic_pi_transport.py",
        "packages/inventory-reference-service/tests",
        "packages/pi-grid-tools",
        "packages/pi-capability-tools",
        "packages/trajectory-workbench",
        "tools/tests/test_verification_targets.py",
        "tools/tests/test_runtime_risk_exception.py",
        "tools/tests/test_projection_benchmark.py",
        "tools/tests/test_local_build_cache_cleanup.py",
        "tools/tests/test_image_layer_order.py",
        "tools/tests/test_native_report.py",
    ):
        assert expected in output
    assert "pytest packages/grid-agent/tests/e2e -q" not in output


def test_release_graph_has_all_named_layers_without_recursion() -> None:
    output = _dry_run("check-release")
    for expected in (
        "pyright",
        "packages/grid-agent/tests/e2e -q",
        "validation-application-instantiation",
        "test_package_artifacts.sh",
        "test_source_setup.sh",
        "test_pi_capture_runtime.mjs",
    ):
        assert expected in output
    assert output.count("packages/capability-agent-kernel/tests") == 1
    assert output.count("npm run check --prefix packages/trajectory-workbench") == 1
    assert output.count("python3 tools/check_package_boundaries.py") == 1
    assert output.count("tools/tests/test_runtime_risk_exception.py") == 1
    assert output.count("node tools/test_pi_capture_runtime.mjs") == 4
    assert "npm audit" not in output


def test_child_failure_propagates_from_aggregate(tmp_path: Path) -> None:
    leaves = {
        "check-fast": ("check-package-boundaries", "check-types", "test"),
        "check-integration": ("test-pi-capture-runtime", "test-e2e", "validate", "validate-application"),
        "check-release": ("test-packages", "test-source-setup"),
    }
    for aggregate, dependencies in leaves.items():
        all_targets = [target
            for line in (ROOT / "Makefile").read_text(encoding="utf-8").splitlines()
            if line.startswith(".PHONY:")
            for target in line.removeprefix(".PHONY:").split()]
        successful_stub = tmp_path / f"{aggregate}-success.mk"
        successful_stub.write_text(
            ".PHONY: " + " ".join(all_targets) + "\n"
            + "\n".join(f"{target}:\n\t@true" for target in all_targets),
            encoding="utf-8",
        )
        successful = subprocess.run(
            ["make", "-f", str(ROOT / "Makefile"), "-f", str(successful_stub), aggregate],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        assert successful.returncode == 0, successful.stderr

        for failed in dependencies:
            stub = tmp_path / f"{aggregate}-{failed}.mk"
            stub.write_text(
                ".PHONY: " + " ".join(all_targets) + "\n"
                + "\n".join(f"{target}:\n\t@true" for target in all_targets)
                + f"\n{failed}:\n\t@false\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                ["make", "-f", str(ROOT / "Makefile"), "-f", str(stub), aggregate],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            assert completed.returncode != 0, f"{aggregate} swallowed {failed} failure"


def test_verify_workflow_installs_pinned_uv_and_declares_release_matrix() -> None:
    workflow = (ROOT / ".github/workflows/verify.yml").read_text(encoding="utf-8")

    assert 'os: ${{ fromJSON(' in workflow
    assert 'UV_PYTHON: "3.12"' in workflow
    assert 'python-version: "3.12"' in workflow
    assert 'matrix.python' not in workflow
    policy = json.loads((ROOT / "configs/development/issue-automation.json").read_text())
    expected_jobs = ("verify (macos-latest)",)
    defaults = json.loads(subprocess.check_output([
        "python3", "-c", "import json; from tools.issue_automation.policy import Policy; print(json.dumps(Policy().required_ci))",
    ], cwd=ROOT, text=True))
    assert tuple(defaults) == expected_jobs
    assert tuple(policy["required_ci"]) == expected_jobs
    assert "astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d" in workflow
    assert 'node-version: "22.19.0"' in workflow
    for command in ("make setup", "make install-pi", "make doctor"):
        assert f"- run: {command}" in workflow
    assert 'run: make check-pr' in workflow
    assert 'run: make check-release' in workflow
    assert 'branches: [dev, main]' in workflow
    assert "github.event_name == 'workflow_dispatch' && inputs.release" in workflow


@pytest.mark.parametrize("event,base,ref,release,expected", [
    ("pull_request", "dev", "51/merge", False, ["macos-latest"]),
    ("pull_request", "main", "51/merge", False, ["ubuntu-latest", "macos-latest"]),
    ("push", "", "dev", False, ["macos-latest"]),
    ("push", "", "main", False, ["ubuntu-latest", "macos-latest"]),
    ("workflow_dispatch", "", "dev", False, ["macos-latest"]),
    ("workflow_dispatch", "", "feature/example", True, ["ubuntu-latest", "macos-latest"]),
    ("workflow_dispatch", "", "main", False, ["ubuntu-latest", "macos-latest"]),
])
def test_verify_runner_matrix_matches_development_and_release_context(event, base, ref, release, expected):
    workflow = (ROOT / ".github/workflows/verify.yml").read_text()
    matrix = next(line.strip() for line in workflow.splitlines() if line.strip().startswith("os:"))
    expression = matrix.removeprefix("os: ${{ ").removesuffix(" }}")
    for name, value in {"github.event_name": event, "github.base_ref": base,
                        "github.ref_name": ref, "inputs.release": release}.items():
        expression = expression.replace(name, repr(value))
    expression = expression.replace("&&", " and ").replace("||", " or ")
    # Evaluate the workflow's boolean/JSON subset with no builtins.
    assert eval(expression, {"__builtins__": {}, "fromJSON": json.loads}) == expected
    assert 'if [ "$TARGET_BRANCH" = "main" ] || [ "$RELEASE_CHECK" = "true" ]; then\n            gate=release' in workflow


def test_pr_checks_formal_worker_without_legacy_cli_or_packaging() -> None:
    output = _dry_run("check-pr")
    for expected in ("pyright", "packages/capstone-agent/tests", "test_registered_workers.py",
                     "packages/grid-simulator/tests", "packages/pandapower-domain-pack/tests"):
        assert expected in output
    assert "--ignore=packages/grid-agent/tests/cli" in output
    assert "--ignore=packages/grid-agent/tests/compat" in output
    for retired_or_release_only in ("pytest packages/grid-agent/tests/e2e -q", "test_package_artifacts.sh",
                                    "test_source_setup.sh", "validation/run.py"):
        assert retired_or_release_only not in output


def test_shared_agent_ci_checks_dependencies_with_a_time_budget() -> None:
    workflow = (ROOT / ".github/workflows/verify.yml").read_text()
    block = workflow.split("      - name: Verify shared agent dependencies\n", 1)[1].split("      - name:", 1)[0]
    assert "if: steps.scope.outputs.gate == 'shared-agent'" in block
    assert "timeout-minutes: 15" in block
    for target in ("check-package-boundaries", "check-types", "test-capstone-agent",
                   "test-kernel", "test-capstone-app", "build-capstone-app", "test-capstone-client",
                   "test-registered-workers"):
        assert target in block
    assert "make check-pr" not in block


def test_foundation_ci_keeps_professional_adapters_and_time_budget() -> None:
    workflow = (ROOT / '.github/workflows/verify.yml').read_text()
    block = workflow.split('      - name: Verify shared foundation assembly\n', 1)[1].split('      - name:', 1)[0]
    assert "if: steps.scope.outputs.gate == 'foundation' || steps.scope.outputs.gate == 'native-runtime'" in block
    assert 'timeout-minutes: 15' in block
    for expected in ('test-kernel', 'test-capstone-agent', 'test-registered-workers',
                     'test-domain-package', 'packages/pypsa-agent/tests', 'test-capstone-app', 'check-types',
                     'test_thread_model_diagram.py', 'test_hosted_runtime_warmup.py',
                     'test_generic_entrypoint.py', 'test_composition.py', 'test_hosted_thread.py',
                     'test_application_conformance.py', 'test_multi_binding_application.py'):
        assert expected in block


def test_native_runtime_ci_checks_mcp_and_deployment_consumers():
    workflow = (ROOT / '.github/workflows/verify.yml').read_text()
    block = workflow.split('      - name: Verify native runtime consumers\n', 1)[1].split('      - name:', 1)[0]
    assert "if: steps.scope.outputs.gate == 'native-runtime'" in block
    assert 'timeout-minutes: 10' in block
    for expected in ('test-local-rebuild', 'test-inventory-pi', 'test-pi-capture-runtime',
                     'test_powermcp_audit.py', 'fixtures/*.test.mjs'):
        assert expected in block
    assert 'make check-pr' not in block
    assert 'make check-release' not in block


def test_conversation_runtime_ci_excludes_unchanged_professional_suites():
    workflow = (ROOT / '.github/workflows/verify.yml').read_text()
    assert 'conversation-runtime|' in workflow
    block = workflow.split('      - name: Verify conversation runtime consumers\n', 1)[1].split('      - name:', 1)[0]
    assert "if: steps.scope.outputs.gate == 'conversation-runtime'" in block
    assert 'timeout-minutes: 10' in block
    for expected in ('check-package-boundaries', 'check-types',
                     'test-capstone-app', 'build-capstone-app', 'test-capstone-client',
                     'tests/test_general_pi_*.py', 'tests/test_harness.py', 'tests/test_delegated_runtime.py',
                     'tests/test_thread_http_api.py', 'tests/test_thread_work.py', 'tests/test_thread_worker.py',
                     'tests/test_enterprise_normal_chat.py', 'tests/test_attempt_research.py',
                     'tests/test_native_diagnosis.py', 'tests/test_thread_work_execution.py',
                     'node --test packages/capstone-agent/tests/*.test.mjs packages/capstone-agent/tests/fixtures/*.test.mjs',
                     'tools/tests/test_image_layer_order.py', 'tools/tests/test_host_runtime_contract.py'):
        assert expected in block
    for forbidden in ('test-capstone-agent', 'test-kernel', 'test-domain-package', 'test-registered-workers', 'test-local-rebuild',
                      'test-inventory-pi', 'test-pi-capture-runtime', 'make check-pr', 'make check-release',
                      'packages/grid-agent/tests', 'packages/grid-simulator/tests', 'packages/pypsa-agent/tests',
                      'packages/pandapower-domain-pack/tests', 'packages/inventory-domain-pack/tests',
                      'test_package_artifacts.sh', 'test_source_setup.sh', 'test_user_local_installer.py'):
        assert forbidden not in block
    foundation = workflow.split('      - name: Verify shared foundation assembly\n', 1)[1].split('      - name:', 1)[0]
    assert 'conversation-runtime' not in foundation


def test_iteration_requires_explicit_scope_and_propagates_failure(tmp_path: Path) -> None:
    empty = subprocess.run(["make", "check-iteration"], cwd=ROOT, capture_output=True)
    assert empty.returncode != 0
    stub = tmp_path / "checks.mk"
    marker = tmp_path / "executed"
    stub.write_text(f".PHONY: selected-check\nselected-check:\n\t@touch '{marker}'\n\t@false\n")
    failed = subprocess.run(["make", "-f", str(ROOT / "Makefile"), "-f", str(stub),
                             "check-iteration", "CHECK_TARGETS=selected-check"],
                            cwd=ROOT, capture_output=True,
                            env={**os.environ, "MAKEFILES": str(stub)})
    assert failed.returncode != 0
    assert marker.is_file(), "selected check must execute before its failure propagates"


def test_type_checking_config_covers_exactly_all_production_source_roots() -> None:
    config = json.loads((ROOT / "pyrightconfig.json").read_text(encoding="utf-8"))
    source_roots = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "packages").glob("*/src")
        if path.is_dir() and (path.parent / "pyproject.toml").is_file()
    }

    assert len(config["include"]) == len(source_roots)
    assert set(config["include"]) == source_roots
    assert config["typeCheckingMode"] == "standard"
    assert config["pythonVersion"] == "3.12"

    excluded_paths = config.get("exclude", []) + config.get("ignore", [])
    for excluded in excluded_paths:
        assert isinstance(excluded, str)
        excluded_path = PurePosixPath(excluded)
        for source_root in source_roots:
            assert not (
                PurePosixPath(source_root).is_relative_to(excluded_path)
                or fnmatchcase(source_root, excluded)
            ), (
                f"{excluded} excludes production source root {source_root}"
            )


def test_pyright_is_pinned_in_the_project_and_frozen_lock() -> None:
    project = tomllib.loads(
        (ROOT / "packages/grid-agent/pyproject.toml").read_text(encoding="utf-8")
    )
    assert "pyright==1.1.408" in project["dependency-groups"]["dev"]

    lock = tomllib.loads((ROOT / "packages/grid-agent/uv.lock").read_text(encoding="utf-8"))
    pyright_packages = [
        package
        for package in lock["package"]
        if package.get("name") == "pyright"
    ]
    assert len(pyright_packages) == 1
    assert pyright_packages[0]["version"] == "1.1.408"
