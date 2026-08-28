from __future__ import annotations

import json
from pathlib import Path

from capability_agent.application import prepare_domain_runtime


def test_inventory_profile_materializes_exact_provider_free_tool_inventory(
    tmp_path: Path,
    inventory_profile,
) -> None:
    profile, executor = inventory_profile
    workspace = tmp_path / "run"

    prepared = prepare_domain_runtime(
        profile,
        executable=tmp_path / "inventoryctl",
        workspace=workspace,
        tool_catalog_path=workspace / "tool-catalog.json",
        guide_index_path=workspace / "guide-index.json",
    )

    catalog = json.loads(prepared.tool_catalog_path.read_text(encoding="utf-8"))
    assert executor.calls == [("environment.describe", {})]
    assert [tool["name"] for tool in catalog["tools"]] == [
        "inventory_asset_list",
        "inventory_record_decision",
    ]
