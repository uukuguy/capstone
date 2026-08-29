from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class InventoryAsset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    asset_id: str = Field(pattern=r"^asset-[a-z0-9-]+$")
    name: str = Field(min_length=1)
    category: Literal["electrical", "mechanical", "safety"]
    location: str = Field(pattern=r"^[a-z][a-z0-9-]+$")
    quantity_on_hand: int = Field(ge=0)
    reorder_level: int = Field(ge=0)
    unit: str = Field(min_length=1)
    updated_at: str = Field(min_length=1)


class InventoryCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["inventory-catalog/1.0"]
    catalog_id: str = Field(pattern=r"^[a-z][a-z0-9-]+$")
    assets: tuple[InventoryAsset, ...]

    @property
    def revision_ref(self) -> str:
        from inventory_reference.artifacts import content_reference

        return content_reference("revision", self.model_dump(mode="json"))


class CapabilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol: Literal["inventory-capability"]
    protocol_version: Literal["1.0"]
    request_id: str = Field(min_length=1, max_length=200)
    capability: str = Field(min_length=1, max_length=200)
    arguments: dict[str, Any]
