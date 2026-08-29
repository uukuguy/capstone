from __future__ import annotations

import pytest

from capability_agent.domain import VerifiedInvocation

from inventory_domain.projection import (
    InventoryProjectorLookupError,
    InventoryProjectorRegistry,
)


def test_inventory_projectors_emit_domain_owned_state_deltas() -> None:
    registry = InventoryProjectorRegistry()
    context = registry.require("inventory-context-v1").project(
        VerifiedInvocation(
            capability="catalog.open",
            projector_id="inventory-context-v1",
            result_kind="inventory.context",
            result={
                "catalog_id": "warehouse-a",
                "context_ref": "inventory-context:sha256:" + "1" * 64,
                "revision_ref": "inventory-revision:sha256:" + "2" * 64,
                "asset_count": 5,
            },
            arguments={"catalog_id": "warehouse-a"},
            turn_id="turn-1",
            result_paths={},
            active_revision_ref=None,
        )
    )
    assets = registry.require("inventory-asset-v1").project(
        VerifiedInvocation(
            capability="asset.list",
            projector_id="inventory-asset-v1",
            result_kind="inventory.asset-list",
            result={
                "context_ref": "inventory-context:sha256:" + "1" * 64,
                "revision_ref": "inventory-revision:sha256:" + "2" * 64,
                "result_ref": "inventory-result:sha256:" + "3" * 64,
                "assets": [{"asset_id": "asset-breaker-001", "quantity_on_hand": 12}],
                "evidence_refs": ["inventory-evidence:sha256:" + "4" * 64],
            },
            arguments={},
            turn_id="turn-2",
            result_paths={
                "inventory-result:sha256:" + "3" * 64: "evidence/results/3.json"
            },
            active_revision_ref=None,
        )
    )

    assert context.model_dump()["active_catalog"]["catalog_id"] == "warehouse-a"
    assert assets.model_dump()["asset_results"][0]["asset_count"] == 1
    assert assets.model_dump()["asset_results"][0]["artifact_path"] == (
        "evidence/results/3.json"
    )


def test_unknown_inventory_projector_fails_closed() -> None:
    with pytest.raises(InventoryProjectorLookupError, match="unknown projector"):
        InventoryProjectorRegistry().require("grid-powerflow-v1")
