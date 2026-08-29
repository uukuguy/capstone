from __future__ import annotations

from inventory_reference.catalog import load_registered_catalog


def test_registered_catalog_has_stable_revision_and_inventory_shape() -> None:
    catalog = load_registered_catalog("warehouse-a")

    assert catalog.catalog_id == "warehouse-a"
    assert catalog.revision_ref.startswith("inventory-revision:sha256:")
    assert len(catalog.assets) == 5
    assert sum(
        asset.quantity_on_hand <= asset.reorder_level for asset in catalog.assets
    ) == 2
    assert {asset.category for asset in catalog.assets} == {
        "electrical",
        "mechanical",
        "safety",
    }


def test_unknown_registered_catalog_fails_closed() -> None:
    try:
        load_registered_catalog("../warehouse-a")
    except LookupError as exc:
        assert str(exc) == "registered inventory catalog was not found: ../warehouse-a"
    else:
        raise AssertionError("unknown catalog must fail closed")
