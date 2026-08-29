from __future__ import annotations

from inventory_domain.resources import InventoryResourceSet


def test_packaged_inventory_resources_are_complete_and_stable() -> None:
    resources = InventoryResourceSet.load()

    assert sorted(path.name for path in resources.capability_contract_root.glob("*.json")) == [
        "asset.get.json",
        "asset.list.json",
        "catalog.open.json",
        "stock.summary.json",
    ]
    assert resources.system_policy_path.is_file()
    assert (resources.guide_root / "SKILL.md").is_file()
    assert (resources.guide_root / "references/capability-map.md").is_file()
    assert InventoryResourceSet.load() is resources
