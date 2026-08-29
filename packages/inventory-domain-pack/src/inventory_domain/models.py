from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ActiveCatalogState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalog_id: str
    context_ref: str
    revision_ref: str
    asset_count: int = Field(ge=0)
    producer_turn_id: str


class AssetResultState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_ref: str
    context_ref: str
    revision_ref: str
    capability: str
    asset_count: int = Field(ge=0)
    assets: list[dict[str, Any]]
    artifact_path: str
    evidence_refs: list[str]
    producer_turn_id: str


class StockSummaryState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_ref: str
    context_ref: str
    revision_ref: str
    asset_count: int = Field(ge=0)
    total_quantity_on_hand: int = Field(ge=0)
    reorder_candidate_count: int = Field(ge=0)
    reorder_asset_ids: list[str]
    artifact_path: str
    evidence_refs: list[str]
    producer_turn_id: str


class InventoryStateDelta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projector: str
    active_catalog: ActiveCatalogState | None = None
    asset_results: list[AssetResultState] = Field(default_factory=list)
    stock_summaries: list[StockSummaryState] = Field(default_factory=list)
