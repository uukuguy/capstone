from __future__ import annotations

from pathlib import Path


def test_domain_package_sources_do_not_import_grid_agent() -> None:
    source_root = Path(__file__).parents[1] / "src" / "pandapower_domain"
    forbidden = ("grid_agent", "pandapowerNet", "import pandapower")

    for path in source_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not any(token in text for token in forbidden), path
