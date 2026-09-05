"""Validated, detached inventory state; authority verification precedes reduction."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
import re
from types import MappingProxyType
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from capability_agent.domain.projection import DomainStateDelta
from inventory_domain.models import (
    ActiveCatalogState, AssetResultState, InventoryStateDelta, StockSummaryState,
)

INVENTORY_STATE_SCHEMA = "inventory-readonly-state/1.0"


class InventoryState(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    state_schema: Literal["inventory-readonly-state/1.0"] = "inventory-readonly-state/1.0"
    state_revision: int = Field(default=0, ge=0)
    active_context_ref: str | None = None
    catalogs: dict[str, ActiveCatalogState] = Field(default_factory=dict)
    asset_results: dict[str, AssetResultState] = Field(default_factory=dict)
    stock_summaries: dict[str, StockSummaryState] = Field(default_factory=dict)


def validate_inventory_reference(reference: object, kind: str) -> None:
    if not isinstance(reference, str) or re.fullmatch(
        rf"inventory-{re.escape(kind)}:sha256:[a-f0-9]{{64}}", reference
    ) is None:
        raise ValueError(f"inventory {kind} reference is invalid")


def json_copy(value: object) -> object:
    """Detach JSON-compatible mappings, including frozen Kernel snapshots."""
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("inventory state keys must be strings")
        return {key: json_copy(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_copy(item) for item in value]
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is float and isfinite(value):
        return value
    raise ValueError("inventory state must contain finite JSON values")


def context_mapping(context: object) -> dict[str, object]:
    if isinstance(context, Mapping):
        value = context
    else:
        dump = getattr(context, "model_dump", None)
        if not callable(dump):
            raise ValueError("inventory context has no public serialized view")
        value = dump(mode="json")
    copied = json_copy(value)
    if not isinstance(copied, dict):
        raise ValueError("inventory context must be an object")
    return copied


def parse_inventory_state(binding_id: str, state: Mapping[str, object]) -> InventoryState:
    if not isinstance(binding_id, str) or not binding_id or binding_id.strip() != binding_id:
        raise ValueError("inventory binding identity is invalid")
    if not isinstance(state, Mapping):
        raise ValueError("inventory state must be an object")
    if state and set(state) != set(InventoryState.model_fields):
        raise ValueError("inventory state fields are incomplete or unknown")
    parsed = InventoryState.model_validate(json_copy(state), strict=True)
    for key, catalog in parsed.catalogs.items():
        validate_inventory_reference(key, "context")
        validate_inventory_reference(catalog.revision_ref, "revision")
        if key != catalog.context_ref:
            raise ValueError("inventory catalog key does not match its reference")
    if parsed.active_context_ref is not None:
        validate_inventory_reference(parsed.active_context_ref, "context")
        if parsed.active_context_ref not in parsed.catalogs:
            raise ValueError("inventory active catalog is missing")
    if parsed.asset_results.keys() & parsed.stock_summaries.keys():
        raise ValueError("inventory state content conflict across result kinds")
    for records in (parsed.asset_results, parsed.stock_summaries):
        for key, record in records.items():
            validate_inventory_reference(key, "result")
            validate_inventory_reference(record.context_ref, "context")
            validate_inventory_reference(record.revision_ref, "revision")
            if key != record.result_ref:
                raise ValueError("inventory result key does not match its reference")
            catalog = parsed.catalogs.get(record.context_ref)
            if catalog is None or catalog.revision_ref != record.revision_ref:
                raise ValueError("inventory result has an unknown catalog or revision")
            for evidence in record.evidence_refs:
                validate_inventory_reference(evidence, "evidence")
    return parsed


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class InventoryDomainContext:
    binding_id: str
    state: Mapping[str, object]
    admitted_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        frozen = _freeze(json_copy(self.state))
        assert isinstance(frozen, Mapping)
        object.__setattr__(self, "state", frozen)
        object.__setattr__(self, "admitted_refs", tuple(self.admitted_refs))

    def model_dump(self, *, mode: str = "python") -> dict[str, object]:
        del mode
        return {
            "binding_id": self.binding_id,
            "state": json_copy(self.state),
            "admitted_refs": self.admitted_refs,
        }


class InventoryStateAdapter:
    schema_id = INVENTORY_STATE_SCHEMA

    def validate(self, *, binding_id: str, state: Mapping[str, object]) -> None:
        parse_inventory_state(binding_id, state)

    def merge(
        self, *, binding_id: str, state: Mapping[str, object], delta: DomainStateDelta
    ) -> Mapping[str, object]:
        current = parse_inventory_state(binding_id, state)
        change = InventoryStateDelta.model_validate(
            json_copy(delta.model_dump(mode="python")), strict=True
        )
        if change.projector not in {
            "inventory-context-v1", "inventory-asset-v1", "inventory-stock-summary-v1"
        }:
            raise ValueError("inventory state projector is unknown")
        result = current.model_dump(mode="json")
        if change.active_catalog is not None:
            catalog = change.active_catalog
            _upsert(result["catalogs"], catalog.context_ref, catalog.model_dump(mode="json"))
            result["active_context_ref"] = catalog.context_ref
        for group, records in (
            ("asset_results", change.asset_results),
            ("stock_summaries", change.stock_summaries),
        ):
            for record in records:
                _upsert(result[group], record.result_ref, record.model_dump(mode="json"))
        result["state_revision"] = current.state_revision + 1
        return parse_inventory_state(binding_id, result).model_dump(mode="json")

    def build_context(
        self, *, binding_id: str, state: Mapping[str, object]
    ) -> InventoryDomainContext:
        parsed = parse_inventory_state(binding_id, state)
        refs: set[str] = set()
        for catalog in parsed.catalogs.values():
            refs.update((catalog.context_ref, catalog.revision_ref))
        for records in (parsed.asset_results, parsed.stock_summaries):
            for record in records.values():
                refs.update((record.result_ref, record.context_ref, record.revision_ref))
                refs.update(record.evidence_refs)
        return InventoryDomainContext(
            binding_id, parsed.model_dump(mode="json"), tuple(sorted(refs))
        )


def _upsert(
    records: dict[str, object], key: str, value: dict[str, object]
) -> None:
    old = records.get(key)
    if old is not None:
        if not isinstance(old, Mapping):
            raise ValueError("inventory state record is invalid")
        old_content = {name: item for name, item in old.items() if name != "producer_turn_id"}
        new_content = {name: item for name, item in value.items() if name != "producer_turn_id"}
        if old_content != new_content:
            raise ValueError("inventory state content conflict")
        return
    records[key] = value
