from __future__ import annotations

import ast
from pathlib import Path


def test_kernel_source_has_no_application_or_simulator_imports() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "capability_agent"
    forbidden = {
        "grid_agent",
        "grid_simulator",
        "pandapower",
        "pandapower_domain",
    }
    offenders: list[str] = []

    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = [node.module]
            else:
                continue
            for module in imported:
                if module in forbidden or any(
                    module.startswith(f"{prefix}.") for prefix in forbidden
                ):
                    offenders.append(f"{path.relative_to(root)} imports {module}")

    assert offenders == []
