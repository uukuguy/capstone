from __future__ import annotations

import pytest

from inventory_reference.operations import InventoryCapabilityError, execute


def _open(workspace):
    return execute("catalog.open", {"catalog_id": "warehouse-a"}, workspace)


def test_open_list_get_and_summarize_registered_inventory(tmp_path) -> None:
    opened = _open(tmp_path)

    listed = execute(
        "asset.list",
        {
            "context_ref": opened["context_ref"],
            "location": "shanghai-a",
            "limit": 2,
        },
        tmp_path,
    )
    fetched = execute(
        "asset.get",
        {
            "context_ref": opened["context_ref"],
            "asset_id": "asset-breaker-001",
        },
        tmp_path,
    )
    summary = execute(
        "stock.summary",
        {"context_ref": opened["context_ref"]},
        tmp_path,
    )

    assert opened["revision_ref"].startswith("inventory-revision:sha256:")
    assert opened["context_ref"].startswith("inventory-context:sha256:")
    assert [item["asset_id"] for item in listed["assets"]] == [
        "asset-breaker-001",
        "asset-gloves-001",
    ]
    assert listed["result_ref"].startswith("inventory-result:sha256:")
    assert listed["evidence_refs"][0].startswith("inventory-evidence:sha256:")
    assert fetched["asset"]["name"] == "Vacuum circuit breaker"
    assert summary["asset_count"] == 5
    assert summary["total_quantity_on_hand"] == 91
    assert summary["reorder_candidate_count"] == 2
    assert summary["reorder_asset_ids"] == [
        "asset-bearing-001",
        "asset-gloves-001",
    ]


@pytest.mark.parametrize(
    ("capability", "arguments", "code"),
    (
        ("asset.create", {}, "capability_not_published"),
        ("catalog.open", {"catalog_id": "../warehouse-a"}, "catalog_not_found"),
        ("asset.list", {"context_ref": "inventory-context:sha256:" + "0" * 64}, "context_not_found"),
        ("asset.list", {"context_ref": "bad", "limit": 1}, "invalid_context_ref"),
    ),
)
def test_read_only_boundary_and_foreign_context_fail_closed(
    tmp_path, capability, arguments, code
) -> None:
    with pytest.raises(InventoryCapabilityError) as caught:
        execute(capability, arguments, tmp_path)

    assert caught.value.code == code
    assert caught.value.recovery


def test_asset_filters_and_argument_validation_are_deterministic(tmp_path) -> None:
    opened = _open(tmp_path)
    context_ref = opened["context_ref"]

    filtered = execute(
        "asset.list",
        {"context_ref": context_ref, "category": "mechanical", "limit": 10},
        tmp_path,
    )
    assert [item["asset_id"] for item in filtered["assets"]] == [
        "asset-bearing-001",
        "asset-pump-001",
    ]

    with pytest.raises(InventoryCapabilityError) as caught:
        execute("asset.list", {"context_ref": context_ref, "limit": 0}, tmp_path)
    assert caught.value.code == "invalid_arguments"

    with pytest.raises(InventoryCapabilityError) as caught:
        execute(
            "asset.get",
            {"context_ref": context_ref, "asset_id": "asset-unknown"},
            tmp_path,
        )
    assert caught.value.code == "asset_not_found"
