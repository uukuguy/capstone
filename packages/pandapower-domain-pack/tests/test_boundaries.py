from __future__ import annotations

import ast
from pathlib import Path

import pytest


def test_domain_package_sources_do_not_import_grid_agent() -> None:
    source_root = Path(__file__).parents[1] / "src" / "pandapower_domain"
    forbidden = ("grid_agent", "pandapowerNet", "import pandapower")

    for path in source_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not any(token in text for token in forbidden), path


def test_domain_package_has_no_concrete_cli_or_sibling_state_imports() -> None:
    source_root = Path(__file__).parents[1] / "src" / "pandapower_domain"
    forbidden_modules = (
        "grid_agent.cli",
        "grid_agent.application",
        "inventory_domain",
        "inventory_reference",
    )
    offenders: list[str] = []
    for path in sorted(source_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = (node.module,)
            else:
                continue
            for module in modules:
                if any(
                    module == forbidden or module.startswith(f"{forbidden}.")
                    for forbidden in forbidden_modules
                ):
                    offenders.append(f"{path.relative_to(source_root)} imports {module}")
    assert offenders == []


@pytest.mark.parametrize(
    "state",
    [
        {"owner_binding_id": "inventory"},
        {"source_binding_id": "inventory"},
        {"target_binding_id": "inventory"},
        {"owner_binding_ids": ["grid", "inventory"]},
        {"foreign_binding_id": "inventory"},
        {"foreign_ref": "inventory:result:sha256:" + "a" * 64},
    ],
)
def test_domain_state_adapter_rejects_cross_binding_state_writes(
    state: dict[str, object],
) -> None:
    from pandapower_domain.state import PandapowerStateAdapter

    with pytest.raises(ValueError, match="foreign binding ownership"):
        PandapowerStateAdapter().validate(binding_id="grid", state=state)
