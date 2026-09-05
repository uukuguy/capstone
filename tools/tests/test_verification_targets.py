from __future__ import annotations

from fnmatch import fnmatchcase
import json
import subprocess
import tomllib
from pathlib import Path
from pathlib import PurePosixPath


ROOT = Path(__file__).resolve().parents[2]


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
        phony = next(
            line
            for line in (ROOT / "Makefile").read_text(encoding="utf-8").splitlines()
            if line.startswith(".PHONY:")
        )
        all_targets = phony.removeprefix(".PHONY:").split()
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

    assert 'os: [ubuntu-latest, macos-latest]' in workflow
    assert 'python: ["3.12", "3.14"]' in workflow
    assert "UV_PYTHON: ${{ matrix.python }}" in workflow
    assert "astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d" in workflow
    assert 'node-version: "22.19.0"' in workflow
    for command in ("make setup", "make install-pi", "make doctor", "make check-release"):
        assert f"- run: {command}" in workflow


def test_type_checking_config_covers_exactly_all_production_source_roots() -> None:
    config = json.loads((ROOT / "pyrightconfig.json").read_text(encoding="utf-8"))
    source_roots = {
        "packages/capability-agent-kernel/src",
        "packages/pandapower-domain-pack/src",
        "packages/inventory-domain-pack/src",
        "packages/grid-agent/src",
        "packages/grid-simulator/src",
        "packages/inventory-reference-service/src",
    }

    assert config["include"] == [
        "packages/capability-agent-kernel/src",
        "packages/pandapower-domain-pack/src",
        "packages/inventory-domain-pack/src",
        "packages/grid-agent/src",
        "packages/grid-simulator/src",
        "packages/inventory-reference-service/src",
    ]
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
