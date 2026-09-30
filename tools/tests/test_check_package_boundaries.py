import subprocess
import sys
import tomllib
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "tools/check_package_boundaries.py"


@pytest.mark.parametrize("module", ["capstone_agent", "capability_agent", "httpx", "pypsa"])
def test_model_capability_spi_rejects_non_stdlib_imports(tmp_path: Path, module: str) -> None:
    source = tmp_path / "packages/capstone-model-capability-spi/src/capstone_model_capability_spi"
    source.mkdir(parents=True)
    (source / "bad.py").write_text(f"import {module}\n", encoding="utf-8")
    result = run_checker(tmp_path)
    assert result.returncode == 1
    assert f"imports non-stdlib module {module}" in result.stderr


def test_model_capability_spi_allows_stdlib_and_own_relative_imports(tmp_path: Path) -> None:
    source = tmp_path / "packages/capstone-model-capability-spi/src/capstone_model_capability_spi"
    source.mkdir(parents=True)
    (source / "good.py").write_text(
        "from dataclasses import dataclass\nfrom .contracts import Descriptor\n",
        encoding="utf-8",
    )
    assert run_checker(tmp_path).returncode == 0


@pytest.mark.parametrize("declaration", [
    'dependencies = ["capability-agent-kernel==0.1.0"]',
    '[project.optional-dependencies]\nruntime = ["httpx"]',
])
def test_model_capability_spi_rejects_runtime_dependencies(tmp_path: Path, declaration: str) -> None:
    package = tmp_path / "packages/capstone-model-capability-spi"
    package.mkdir(parents=True)
    (package / "pyproject.toml").write_text(
        '[project]\nname = "capstone-model-capability-spi"\n' + declaration + "\n",
        encoding="utf-8",
    )
    result = run_checker(tmp_path)
    assert result.returncode == 1
    assert "must have no runtime dependencies" in result.stderr


def test_domain_resource_dependency_pins_authority_package_version() -> None:
    simulator = tomllib.loads((ROOT / "packages/grid-simulator/pyproject.toml").read_text())
    domain = tomllib.loads((ROOT / "packages/pandapower-domain-pack/pyproject.toml").read_text())
    expected = f"grid-simulator=={simulator['project']['version']}"
    dependencies = domain["project"]["dependencies"]
    assert expected in dependencies
    assert sum(value.startswith("grid-simulator") for value in dependencies) == 1


def test_kernel_rejects_forbidden_grid_agent_import(tmp_path: Path) -> None:
    package_src = (
        tmp_path
        / "packages/capability-agent-kernel/src/capability_agent"
    )
    package_src.mkdir(parents=True)
    (package_src / "bad.py").write_text(
        "from grid_agent import cli\n",
        encoding="utf-8",
    )

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert result.stderr.splitlines() == [
        "packages/capability-agent-kernel/src/capability_agent/bad.py "
        "contains grid-owned semantic token grid_",
        "packages/capability-agent-kernel/src/capability_agent/bad.py "
        "contains grid-owned semantic token grid_agent",
        "packages/capability-agent-kernel/src/capability_agent/bad.py imports grid_agent.cli"
    ]
    assert result.stdout == ""


@pytest.mark.parametrize(
    "source",
    [
        "import grid_simulator\n",
        "import grid_simulator.client\n",
        "from grid_simulator import capabilities\n",
        "from grid_simulator.capabilities import CapabilityRegistry\n",
        "from grid_simulator.capabilities import *\n",
        "from grid_simulator.capabilities.registry import CapabilityRegistry\n",
        "from grid_simulator.capabilities import contract_root, CapabilityRegistry\n",
    ],
)
def test_pandapower_domain_rejects_simulator_imports_except_contract_root(tmp_path: Path, source: str) -> None:
    domain = tmp_path / "packages/pandapower-domain-pack/src/pandapower_domain"
    domain.mkdir(parents=True)
    (domain / "bad.py").write_text(source, encoding="utf-8")

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert result.stderr == "packages/pandapower-domain-pack/src/pandapower_domain/bad.py imports forbidden grid_simulator symbol\n"


def test_pandapower_domain_allows_contract_root_alias(tmp_path: Path) -> None:
    domain = tmp_path / "packages/pandapower-domain-pack/src/pandapower_domain"
    domain.mkdir(parents=True)
    (domain / "resources.py").write_text("from grid_simulator.capabilities import contract_root as root\n", encoding="utf-8")

    result = run_checker(tmp_path)

    assert result.returncode == 0


def test_application_rejects_grid_owned_semantic_literals(tmp_path: Path) -> None:
    application_src = (
        tmp_path
        / "packages/capability-agent-kernel/src/capability_agent/application"
    )
    application_src.mkdir(parents=True)
    (application_src / "bad.py").write_text(
        'GRID_TOOL = "grid_analysis_powerflow_ac"\n',
        encoding="utf-8",
    )

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert result.stderr.splitlines() == [
        "packages/capability-agent-kernel/src/capability_agent/application/bad.py "
        "contains grid-owned semantic token grid_",
    ]
    assert result.stdout == ""


def test_kernel_rejects_grid_owned_semantic_literals_outside_application(
    tmp_path: Path,
) -> None:
    runtime_src = (
        tmp_path
        / "packages/capability-agent-kernel/src/capability_agent/runtime"
    )
    runtime_src.mkdir(parents=True)
    (runtime_src / "bad.py").write_text(
        'CAPABILITY = "power-flow"\n',
        encoding="utf-8",
    )

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert result.stderr.splitlines() == [
        "packages/capability-agent-kernel/src/capability_agent/runtime/bad.py "
        "contains grid-owned semantic token power-flow",
    ]
    assert result.stdout == ""


@pytest.mark.parametrize(
    ("literal", "reported_token"),
    (
        ("grid_agent", "grid_agent"),
        ("grid_simulator", "grid_simulator"),
        ("pandapower_domain", "pandapower_domain"),
        ("pandapower", "pandapower"),
        ("gridctl", "gridctl"),
        ("grid_", "grid_"),
        ("power flow", "power-flow"),
        ("voltage", "voltage"),
        ("bus", "bus"),
        ("branch", "branch"),
        ("n-1", "n-1"),
    ),
)
def test_kernel_rejects_each_grid_owned_semantic_literal(
    tmp_path: Path,
    literal: str,
    reported_token: str,
) -> None:
    package_src = tmp_path / "packages/capability-agent-kernel/src/capability_agent"
    package_src.mkdir(parents=True)
    (package_src / "bad.py").write_text(
        f'CAPABILITY = "{literal}"\n',
        encoding="utf-8",
    )

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert any(
        f"contains grid-owned semantic token {reported_token}" in line
        for line in result.stderr.splitlines()
    )
    assert result.stdout == ""


@pytest.mark.parametrize(
    "source",
    [
        "from grid_agent.application import prepare_domain_runtime\n",
        "from grid_agent.domain import ArtifactAuthority\n",
        "from grid_agent.domains import build_pandapower_profile\n",
    ],
)
def test_cli_rejects_compatibility_application_assembly_imports(
    tmp_path: Path,
    source: str,
) -> None:
    cli_src = tmp_path / "packages/grid-agent/src/grid_agent/cli"
    cli_src.mkdir(parents=True)
    (cli_src / "app.py").write_text(source, encoding="utf-8")

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert result.stderr.startswith("packages/grid-agent/src/grid_agent/cli/app.py imports ")
    assert result.stdout == ""


def test_cli_may_import_generic_application_composition(tmp_path: Path) -> None:
    cli_src = tmp_path / "packages/grid-agent/src/grid_agent/cli"
    cli_src.mkdir(parents=True)
    (cli_src / "app.py").write_text(
        "from grid_agent.application.composition import run_generic_application\n",
        encoding="utf-8",
    )

    result = run_checker(tmp_path)

    assert result.returncode == 0
    assert result.stdout == "package-boundaries: ok\n"
    assert result.stderr == ""


@pytest.mark.parametrize(
    "source",
    [
        "from grid_agent.domain import ArtifactAuthority\n",
        "from grid_agent.tools.catalog import ToolCatalog\n",
        "from grid_agent.domains.pandapower import build_pandapower_profile\n",
    ],
)
def test_non_cli_production_modules_reject_compatibility_shim_imports(
    tmp_path: Path,
    source: str,
) -> None:
    production_src = tmp_path / "packages/grid-agent/src/grid_agent/analysis"
    production_src.mkdir(parents=True)
    (production_src / "projector.py").write_text(source, encoding="utf-8")

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert result.stderr.startswith(
        "packages/grid-agent/src/grid_agent/analysis/projector.py imports "
    )
    assert result.stdout == ""


def test_compatibility_shim_modules_are_precisely_exempt(tmp_path: Path) -> None:
    shim = tmp_path / "packages/grid-agent/src/grid_agent/domain/authority.py"
    shim.parent.mkdir(parents=True)
    shim.write_text(
        "from capability_agent.domain.authority import ArtifactAuthority\n",
        encoding="utf-8",
    )

    result = run_checker(tmp_path)

    assert result.returncode == 0
    assert result.stdout == "package-boundaries: ok\n"


def test_reports_sorted_ast_metadata_and_source_path_violations(
    tmp_path: Path,
) -> None:
    kernel_src = (
        tmp_path
        / "packages/capability-agent-kernel/src/capability_agent"
    )
    domain_src = (
        tmp_path
        / "packages/pandapower-domain-pack/src/pandapower_domain"
    )
    kernel_src.mkdir(parents=True)
    domain_src.mkdir(parents=True)
    (kernel_src / "bad_import.py").write_text(
        "\n".join(
            [
                "import pandapower as pp",
                "import grid_simulator.client as simulator_client",
                "from grid_agent import cli as grid_cli",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (domain_src / "bad_domain.py").write_text(
        "\n".join(
            [
                "from grid_agent.tools import catalog",
                'SOURCE = "packages/grid-agent/src"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    write_pyproject(
        tmp_path / "packages/capability-agent-kernel/pyproject.toml",
        'dependencies = ["grid-agent"]',
    )
    write_pyproject(
        tmp_path / "packages/pandapower-domain-pack/pyproject.toml",
        'dependencies = ["requests"]',
    )

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert result.stderr.splitlines() == [
        "packages/capability-agent-kernel/pyproject.toml depends on grid-agent",
        "packages/capability-agent-kernel/src/capability_agent/bad_import.py "
        "contains grid-owned semantic token grid_",
        "packages/capability-agent-kernel/src/capability_agent/bad_import.py "
        "contains grid-owned semantic token grid_agent",
        "packages/capability-agent-kernel/src/capability_agent/bad_import.py "
        "contains grid-owned semantic token grid_simulator",
        "packages/capability-agent-kernel/src/capability_agent/bad_import.py "
        "contains grid-owned semantic token pandapower",
        "packages/capability-agent-kernel/src/capability_agent/bad_import.py imports grid_agent.cli",
        "packages/capability-agent-kernel/src/capability_agent/bad_import.py imports grid_simulator.client",
        "packages/capability-agent-kernel/src/capability_agent/bad_import.py imports pandapower",
        "packages/pandapower-domain-pack/src/pandapower_domain/bad_domain.py contains source path packages/grid-agent/src",
        "packages/pandapower-domain-pack/src/pandapower_domain/bad_domain.py imports grid_agent.tools.catalog",
    ]
    assert result.stdout == ""


@pytest.mark.parametrize("dependency", ["Grid-Agent", "grid_agent", "grid.agent"])
def test_rejects_normalized_grid_agent_dependency_names(
    tmp_path: Path,
    dependency: str,
) -> None:
    write_pyproject(
        tmp_path / "packages/capability-agent-kernel/pyproject.toml",
        f'dependencies = ["{dependency}"]',
    )

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert result.stderr.splitlines() == [
        "packages/capability-agent-kernel/pyproject.toml depends on grid-agent"
    ]
    assert result.stdout == ""


@pytest.mark.parametrize(
    "dependency",
    [
        "grid-agent @ https://example.invalid/grid-agent.whl",
        "Grid_Agent @ file:///tmp/dist.whl",
        "grid.agent @ file:///tmp/dist.whl",
    ],
)
def test_rejects_normalized_grid_agent_direct_references(
    tmp_path: Path,
    dependency: str,
) -> None:
    write_pyproject(
        tmp_path / "packages/capability-agent-kernel/pyproject.toml",
        f'dependencies = ["{dependency}"]',
    )

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert result.stderr.splitlines() == [
        "packages/capability-agent-kernel/pyproject.toml depends on grid-agent"
    ]
    assert result.stdout == ""


def test_clean_future_roots_pass(tmp_path: Path) -> None:
    kernel_src = (
        tmp_path
        / "packages/capability-agent-kernel/src/capability_agent"
    )
    domain_src = (
        tmp_path
        / "packages/pandapower-domain-pack/src/pandapower_domain"
    )
    kernel_src.mkdir(parents=True)
    domain_src.mkdir(parents=True)
    (kernel_src / "good.py").write_text(
        "from __future__ import annotations\n",
        encoding="utf-8",
    )
    (domain_src / "good.py").write_text(
        "import pandapower_domain.helpers\n",
        encoding="utf-8",
    )
    write_pyproject(
        tmp_path / "packages/capability-agent-kernel/pyproject.toml",
        'dependencies = ["typing-extensions"]',
    )
    write_pyproject(
        tmp_path / "packages/pandapower-domain-pack/pyproject.toml",
        'dependencies = ["pandapower"]',
    )

    result = run_checker(tmp_path)

    assert result.returncode == 0
    assert result.stdout == "package-boundaries: ok\n"
    assert result.stderr == ""


def test_inventory_reference_service_rejects_framework_and_domain_imports(
    tmp_path: Path,
) -> None:
    source_root = (
        tmp_path
        / "packages/inventory-reference-service/src/inventory_reference"
    )
    source_root.mkdir(parents=True)
    (source_root / "bad.py").write_text(
        "\n".join(
            [
                "import capability_agent",
                "import grid_agent",
                "import grid_simulator",
                "import inventory_domain",
                "import pandapower",
                "import pandapower_domain",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert result.stderr.splitlines() == [
        "packages/inventory-reference-service/src/inventory_reference/bad.py imports capability_agent",
        "packages/inventory-reference-service/src/inventory_reference/bad.py imports grid_agent",
        "packages/inventory-reference-service/src/inventory_reference/bad.py imports grid_simulator",
        "packages/inventory-reference-service/src/inventory_reference/bad.py imports inventory_domain",
        "packages/inventory-reference-service/src/inventory_reference/bad.py imports pandapower",
        "packages/inventory-reference-service/src/inventory_reference/bad.py imports pandapower_domain",
    ]


def test_inventory_domain_pack_rejects_grid_and_pandapower_imports(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "packages/inventory-domain-pack/src/inventory_domain"
    source_root.mkdir(parents=True)
    (source_root / "bad.py").write_text(
        "\n".join(
            [
                "import grid_agent",
                "import grid_simulator",
                "import pandapower",
                "import pandapower_domain",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert result.stderr.splitlines() == [
        "packages/inventory-domain-pack/src/inventory_domain/bad.py imports grid_agent",
        "packages/inventory-domain-pack/src/inventory_domain/bad.py imports grid_simulator",
        "packages/inventory-domain-pack/src/inventory_domain/bad.py imports pandapower",
        "packages/inventory-domain-pack/src/inventory_domain/bad.py imports pandapower_domain",
    ]


@pytest.mark.parametrize(
    ("package", "dependency"),
    [
        ("inventory-reference-service", "capability-agent-kernel"),
        ("inventory-reference-service", "inventory-domain-pack"),
        ("inventory-reference-service", "grid-agent"),
        ("inventory-reference-service", "grid-simulator"),
        ("inventory-reference-service", "pandapower-domain-pack"),
        ("inventory-reference-service", "pandapower"),
        ("inventory-domain-pack", "grid-agent"),
        ("inventory-domain-pack", "grid-simulator"),
        ("inventory-domain-pack", "pandapower-domain-pack"),
        ("inventory-domain-pack", "pandapower"),
    ],
)
def test_inventory_packages_reject_forbidden_dependencies(
    tmp_path: Path,
    package: str,
    dependency: str,
) -> None:
    write_pyproject(
        tmp_path / f"packages/{package}/pyproject.toml",
        f'dependencies = ["{dependency}"]',
    )

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert result.stderr.splitlines() == [
        f"packages/{package}/pyproject.toml depends on {dependency}"
    ]


@pytest.mark.parametrize(
    "package",
    ["inventory-reference-service", "inventory-domain-pack"],
)
def test_inventory_packages_reject_source_layout_literals(
    tmp_path: Path,
    package: str,
) -> None:
    package_module = package.replace("-reference-service", "_reference").replace(
        "-domain-pack", "_domain"
    )
    source_root = tmp_path / f"packages/{package}/src/{package_module}"
    source_root.mkdir(parents=True)
    (source_root / "bad.py").write_text(
        'SOURCE = "packages/capability-agent-kernel/src"\n',
        encoding="utf-8",
    )

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert result.stderr.splitlines() == [
        f"packages/{package}/src/{package_module}/bad.py contains source path "
        "packages/capability-agent-kernel/src"
    ]


def test_absent_future_roots_pass(tmp_path: Path) -> None:
    result = run_checker(tmp_path)

    assert result.returncode == 0
    assert result.stdout == "package-boundaries: ok\n"
    assert result.stderr == ""


def run_checker(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKER), "--root", str(root)],
        check=False,
        text=True,
        capture_output=True,
    )


def write_pyproject(path: Path, dependency_line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "[project]",
                'name = "fixture"',
                'version = "0.0.0"',
                dependency_line,
            ]
        )
        + "\n",
        encoding="utf-8",
    )
