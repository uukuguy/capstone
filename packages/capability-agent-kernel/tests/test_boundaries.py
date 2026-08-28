from __future__ import annotations

import ast
from pathlib import Path


_LEGACY_COMPATIBILITY_LITERAL_ALLOWLIST = {
    "trajectory/events.py": {
        "LEGACY_EVENT_PRODUCER": (
            "grid-agent",
            "Persisted native events historically identify the grid application.",
        ),
        "LEGACY_EVENT_SCHEMA_VERSION": (
            "grid-run-event/1.0",
            "The native event schema identifier is persisted in every run event.",
        ),
    },
    "trajectory/replay.py": {
        "LEGACY_IMPORTED_EVENT_SCHEMA_VERSION": (
            "grid-run-import-event/1.0",
            "Imported historical events retain their persisted schema identifier.",
        ),
    },
}


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


def test_kernel_source_has_no_grid_owned_semantic_literals() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "capability_agent"
    forbidden_literals = (
        "grid",
        "pandapower",
        "gridctl",
        "grid_agent",
        "grid_simulator",
        "flow direction",
        "power-flow direction",
        "不表示实时功率方向",
    )

    offenders: list[str] = []
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        allowlist = _LEGACY_COMPATIBILITY_LITERAL_ALLOWLIST.get(relative, {})
        allowed_nodes: set[int] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            names = [target.id for target in node.targets if isinstance(target, ast.Name)]
            for name in names:
                expected = allowlist.get(name)
                if expected is None:
                    continue
                assert isinstance(node.value, ast.Constant)
                assert isinstance(node.value.value, str)
                assert node.value.value == expected[0], name
                assert expected[1], name
                allowed_nodes.add(id(node.value))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and any(token in node.value.lower() for token in forbidden_literals)
                and id(node) not in allowed_nodes
            ):
                offenders.append(f"{relative}: {node.value!r}")

    assert offenders == []
