from __future__ import annotations

import json
import shutil
from pathlib import Path

from capability_agent.application import prepare_domain_runtime

from inventory_domain.profile import build_inventory_profile


def test_installed_inventory_profile_materializes_public_spi_runtime(tmp_path) -> None:
    executable_name = shutil.which("inventoryctl")
    assert executable_name is not None
    workspace = tmp_path / "run"
    workspace.mkdir()
    profile = build_inventory_profile()

    prepared = prepare_domain_runtime(
        profile,
        executable=Path(executable_name),
        workspace=workspace,
        tool_catalog_path=workspace / "tool-catalog.json",
        guide_index_path=workspace / "guide-index.json",
    )

    catalog = json.loads(prepared.tool_catalog_path.read_text(encoding="utf-8"))
    assert profile.manifest.domain_id == "inventory-readonly"
    assert profile.manifest.protocol == "inventory-capability"
    assert profile.manifest.protocol_version == "1.0"
    assert profile.manifest.executable_name == "inventoryctl"
    assert profile.manifest.tool_name_prefix == "inventory_"
    assert profile.manifest.authority_id == "inventoryctl"
    assert [document["id"] for document in prepared.capability_documents] == [
        "asset.get",
        "asset.list",
        "catalog.open",
        "stock.summary",
    ]
    assert [tool["name"] for tool in catalog["tools"]] == [
        "inventory_asset_get",
        "inventory_asset_list",
        "inventory_catalog_open",
        "inventory_record_decision",
        "inventory_stock_summary",
    ]
    assert prepared.authority.authority_id == "inventoryctl"
    assert prepared.authority.workspace_root == workspace
