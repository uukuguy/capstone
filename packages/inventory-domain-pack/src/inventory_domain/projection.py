from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from capability_agent.domain.projection import VerifiedInvocation

from inventory_domain.models import (
    ActiveCatalogState,
    AssetResultState,
    InventoryStateDelta,
    StockSummaryState,
)


class InventoryProjectorLookupError(LookupError):
    pass


@dataclass(frozen=True, slots=True)
class _InventoryProjector:
    projector_id: str

    def project(self, invocation: VerifiedInvocation) -> InventoryStateDelta:
        if self.projector_id == "inventory-context-v1":
            return _context_delta(invocation)
        if self.projector_id == "inventory-asset-v1":
            return _asset_delta(invocation)
        if self.projector_id == "inventory-stock-summary-v1":
            return _summary_delta(invocation)
        raise InventoryProjectorLookupError(
            f"unknown projector: {self.projector_id}"
        )


class InventoryProjectorRegistry:
    def __init__(self) -> None:
        self._projectors = {
            projector_id: _InventoryProjector(projector_id)
            for projector_id in (
                "inventory-context-v1",
                "inventory-asset-v1",
                "inventory-stock-summary-v1",
            )
        }

    def require(self, projector_id: str) -> _InventoryProjector:
        try:
            return self._projectors[projector_id]
        except KeyError as exc:
            raise InventoryProjectorLookupError(
                f"unknown projector: {projector_id}"
            ) from exc


def _context_delta(invocation: VerifiedInvocation) -> InventoryStateDelta:
    result = invocation.result
    return InventoryStateDelta(
        projector=invocation.projector_id,
        active_catalog=ActiveCatalogState(
            catalog_id=_string(result, "catalog_id"),
            context_ref=_string(result, "context_ref"),
            revision_ref=_string(result, "revision_ref"),
            asset_count=_integer(result, "asset_count"),
            producer_turn_id=invocation.turn_id,
        ),
    )


def _asset_delta(invocation: VerifiedInvocation) -> InventoryStateDelta:
    result = invocation.result
    result_ref = _string(result, "result_ref")
    raw_assets = result.get("assets")
    if raw_assets is None:
        asset = result.get("asset")
        raw_assets = [asset] if isinstance(asset, Mapping) else []
    if not isinstance(raw_assets, list) or not all(
        isinstance(item, Mapping) for item in raw_assets
    ):
        raise ValueError("inventory asset projection requires asset mappings")
    artifact_path = invocation.result_paths.get(result_ref, "")
    if not artifact_path:
        raise ValueError(
            f"inventory asset projection requires artifact path: {result_ref}"
        )
    return InventoryStateDelta(
        projector=invocation.projector_id,
        asset_results=[
            AssetResultState(
                result_ref=result_ref,
                context_ref=_string(result, "context_ref"),
                revision_ref=_string(result, "revision_ref"),
                capability=invocation.capability,
                asset_count=len(raw_assets),
                assets=[dict(item) for item in raw_assets],
                artifact_path=artifact_path,
                evidence_refs=_strings(result.get("evidence_refs")),
                producer_turn_id=invocation.turn_id,
            )
        ],
    )


def _summary_delta(invocation: VerifiedInvocation) -> InventoryStateDelta:
    result = invocation.result
    result_ref = _string(result, "result_ref")
    artifact_path = invocation.result_paths.get(result_ref, "")
    if not artifact_path:
        raise ValueError(
            f"inventory summary projection requires artifact path: {result_ref}"
        )
    return InventoryStateDelta(
        projector=invocation.projector_id,
        stock_summaries=[
            StockSummaryState(
                result_ref=result_ref,
                context_ref=_string(result, "context_ref"),
                revision_ref=_string(result, "revision_ref"),
                asset_count=_integer(result, "asset_count"),
                total_quantity_on_hand=_integer(
                    result, "total_quantity_on_hand"
                ),
                reorder_candidate_count=_integer(
                    result, "reorder_candidate_count"
                ),
                reorder_asset_ids=_strings(result.get("reorder_asset_ids")),
                artifact_path=artifact_path,
                evidence_refs=_strings(result.get("evidence_refs")),
                producer_turn_id=invocation.turn_id,
            )
        ],
    )


def _string(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise ValueError(f"inventory projection requires {key}")
    return item


def _integer(value: Mapping[str, Any], key: str) -> int:
    item = value.get(key)
    if isinstance(item, bool) or not isinstance(item, int):
        raise ValueError(f"inventory projection requires integer {key}")
    return item


def _strings(value: object) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return []
    return list(value)
