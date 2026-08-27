from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
DOMAIN_ROOT = ROOT / "packages/grid-agent/src/grid_agent/domain"
COMPOSITION = ROOT / "packages/grid-agent/src/grid_agent/application/composition.py"

FORBIDDEN_PREFIXES = (
    "grid_agent.simulator",
    "grid_agent.domains",
    "grid_agent.analysis.domain_projection",
    "grid_agent.analysis.integrity",
)


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.extend(f"{node.module}.{alias.name}" for alias in node.names)
    return imports


def _starts_with_forbidden_prefix(module: str) -> bool:
    return any(
        module == forbidden or module.startswith(f"{forbidden}.")
        for forbidden in FORBIDDEN_PREFIXES
    )


def test_imported_modules_expands_import_from_aliases(tmp_path: Path) -> None:
    source = tmp_path / "imports_builtin_profile.py"
    source.write_text(
        "from grid_agent.domains import pandapower\n",
        encoding="utf-8",
    )

    assert _imported_modules(source) == ["grid_agent.domains.pandapower"]


def test_neutral_domain_modules_do_not_import_grid_runtime_boundaries() -> None:
    offenders: list[str] = []
    for path in sorted(DOMAIN_ROOT.glob("*.py"), key=lambda item: item.name):
        for module in _imported_modules(path):
            if _starts_with_forbidden_prefix(module):
                offenders.append(f"{path.relative_to(ROOT)} imports {module}")

    assert offenders == []


def test_generic_composer_does_not_select_builtin_pandapower_profile() -> None:
    imported = _imported_modules(COMPOSITION)

    assert not any(_starts_with_forbidden_prefix(module) for module in imported)
