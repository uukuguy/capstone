from __future__ import annotations

import json
from pathlib import Path

from capability_agent.application import prepare_domain_runtime
from capability_agent.tools import GuideIndex, ToolCatalog


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


def test_kernel_helpers_use_neutral_default_schema_ids(
    tmp_path: Path,
    inventory_profile,
) -> None:
    profile, _ = inventory_profile
    prepared = prepare_domain_runtime(
        profile,
        executable=tmp_path / "inventoryctl",
        workspace=tmp_path / "run",
        tool_catalog_path=tmp_path / "run/catalog.json",
        guide_index_path=tmp_path / "run/guides.json",
    )

    catalog_payload = json.loads(
        prepared.tool_catalog_path.read_text(encoding="utf-8")
    )
    guide_payload = json.loads(
        prepared.guide_index_path.read_text(encoding="utf-8")
    )
    assert catalog_payload["protocol"] == "inventory-tool-catalog"
    assert guide_payload["protocol"] == "inventory-guide-index"

    default_catalog = ToolCatalog.from_documents(
        profile.contract_source.load(), tool_name_prefix="inventory_"
    )
    default_catalog_payload = json.loads(
        default_catalog.materialize(tmp_path / "run/default-catalog.json").read_text(
            encoding="utf-8"
        )
    )
    default_guide = GuideIndex.load(profile.manifest.guide_root)
    default_guide_payload = json.loads(
        default_guide.materialize(tmp_path / "run/default-guides.json").read_text(
            encoding="utf-8"
        )
    )
    assert default_catalog_payload["protocol"] == "inventory-tool-catalog"
    assert default_guide_payload["protocol"] == "capability-guide-index"
    assert ToolCatalog.__module__ == "capability_agent.tools.catalog"
    assert GuideIndex.__module__ == "capability_agent.tools.guide"
