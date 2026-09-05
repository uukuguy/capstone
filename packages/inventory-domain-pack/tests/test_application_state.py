import pytest

from inventory_domain.models import ActiveCatalogState, AssetResultState, InventoryStateDelta
from inventory_domain.state import INVENTORY_STATE_SCHEMA, InventoryStateAdapter


def test_inventory_state_adapter_accepts_detached_empty_state() -> None:
    adapter = InventoryStateAdapter()

    adapter.validate(binding_id="inventory", state={})
    context = adapter.build_context(binding_id="inventory", state={})

    assert context.model_dump(mode="json") == {
        "binding_id": "inventory",
        "state": {
            "state_schema": INVENTORY_STATE_SCHEMA,
            "state_revision": 0,
            "active_context_ref": None,
            "catalogs": {},
            "asset_results": {},
            "stock_summaries": {},
        },
        "admitted_refs": (),
    }


def test_state_merge_keeps_first_producer_and_rejects_content_conflict() -> None:
    adapter = InventoryStateAdapter()
    context_ref = "inventory-context:sha256:" + "a" * 64
    revision_ref = "inventory-revision:sha256:" + "b" * 64
    result_ref = "inventory-result:sha256:" + "c" * 64
    delta = InventoryStateDelta(
        projector="inventory-asset-v1",
        active_catalog=ActiveCatalogState(catalog_id="warehouse", context_ref=context_ref, revision_ref=revision_ref, asset_count=1, producer_turn_id="first"),
        asset_results=[AssetResultState(result_ref=result_ref, context_ref=context_ref, revision_ref=revision_ref, capability="asset.list", asset_count=1, assets=[{"asset_id": "A"}], artifact_path="evidence/results/x.json", evidence_refs=[], producer_turn_id="first")],
    )
    first = adapter.merge(binding_id="inventory", state={}, delta=delta)
    replay = adapter.merge(binding_id="inventory", state=first, delta=delta.model_copy(update={"asset_results": [delta.asset_results[0].model_copy(update={"producer_turn_id": "replay"})]}))

    assert replay["asset_results"][result_ref]["producer_turn_id"] == "first"
    conflicting = delta.model_copy(update={"asset_results": [delta.asset_results[0].model_copy(update={"asset_count": 2})]})
    with pytest.raises(ValueError, match="content conflict"):
        adapter.merge(binding_id="inventory", state=first, delta=conflicting)
