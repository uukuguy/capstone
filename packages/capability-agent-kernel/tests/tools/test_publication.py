from __future__ import annotations

from pathlib import Path

import pytest

from capability_agent.tools.catalog import ToolCatalog, ToolCatalogError
from capability_agent.tools.guide import GuideIndex, GuideMaterializationError


@pytest.mark.parametrize("kind", ["catalog", "guide"])
@pytest.mark.parametrize("symlink_position", ["leaf", "parent"])
def test_materialize_rejects_symlink_without_changing_external_file(
    tmp_path: Path, kind: str, symlink_position: str
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "index.json"
    sentinel.write_text("keep me", encoding="utf-8")
    if symlink_position == "leaf":
        parent = tmp_path / "private"
        parent.mkdir()
        target = parent / "index.json"
        target.symlink_to(sentinel)
    else:
        parent = tmp_path / "redirect"
        parent.symlink_to(outside, target_is_directory=True)
        target = parent / "index.json"

    publisher = (
        ToolCatalog((), tool_name_prefix="grid_")
        if kind == "catalog"
        else GuideIndex(tmp_path, {})
    )
    with pytest.raises((ToolCatalogError, GuideMaterializationError)):
        publisher.materialize(target)

    assert sentinel.read_text(encoding="utf-8") == "keep me"
