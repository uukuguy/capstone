"""Display admitted inventory records through the public context view."""
from __future__ import annotations

from collections.abc import Mapping

from inventory_domain.state import (
    INVENTORY_STATE_SCHEMA, InventoryDomainContext, InventoryStateAdapter,
    context_mapping, parse_inventory_state,
)


def _view(context: object) -> InventoryDomainContext:
    raw = context_mapping(context)
    if "domains" in raw:
        domains = raw["domains"]
        if not isinstance(domains, Mapping):
            raise ValueError("inventory presentation domains are invalid")
        matches = [
            (key, value) for key, value in domains.items()
            if isinstance(value, Mapping) and value.get("schema_id") == INVENTORY_STATE_SCHEMA
        ]
        if len(matches) != 1:
            raise ValueError("inventory state envelope is ambiguous or unavailable")
        binding_id, envelope = matches[0]
        state = envelope.get("state")
    else:
        binding_id, state = raw.get("binding_id"), raw.get("state")
    if not isinstance(binding_id, str) or not isinstance(state, Mapping):
        raise ValueError("inventory presentation context is invalid")
    return InventoryStateAdapter().build_context(binding_id=binding_id, state=state)


class InventoryPresentationProvider:
    def render_context(self, context: object) -> Mapping[str, object]:
        view = _view(context)
        state = parse_inventory_state(view.binding_id, view.state)
        catalog = (
            state.catalogs[state.active_context_ref]
            if state.active_context_ref is not None else None
        )
        assets: list[dict[str, object]] = []
        summaries: list[dict[str, object]] = []
        if catalog is not None:
            identity = (catalog.context_ref, catalog.revision_ref)
            assets = [
                {
                    "result_ref": ref, "asset_count": record.asset_count,
                    "evidence_refs": list(record.evidence_refs),
                }
                for ref, record in sorted(state.asset_results.items())
                if (record.context_ref, record.revision_ref) == identity
            ]
            summaries = [
                {
                    "result_ref": ref, "asset_count": record.asset_count,
                    "total_quantity_on_hand": record.total_quantity_on_hand,
                    "reorder_candidate_count": record.reorder_candidate_count,
                    "evidence_refs": list(record.evidence_refs),
                }
                for ref, record in sorted(state.stock_summaries.items())
                if (record.context_ref, record.revision_ref) == identity
            ]
        return {
            "binding_id": view.binding_id,
            "active_catalog": catalog.model_dump(mode="json") if catalog is not None else None,
            "asset_result_count": len(assets),
            "stock_summary_count": len(summaries),
            "asset_results": assets,
            "stock_summaries": summaries,
        }

    def render_report(self, context: object) -> str:
        rendered = self.render_context(context)
        lines = ["## Read-only Inventory", ""]
        catalog = rendered["active_catalog"]
        if catalog is None:
            return "\n".join((*lines, "No current-run catalog has been selected.", ""))
        if not isinstance(catalog, Mapping):
            raise ValueError("inventory presentation catalog is invalid")
        lines.extend((
            f"Catalog: {catalog['catalog_id']}",
            f"Context: {catalog['context_ref']}",
            f"Revision: {catalog['revision_ref']}",
            "",
            "Values below are returned by the inventory authority.",
        ))
        for key in ("asset_results", "stock_summaries"):
            records = rendered[key]
            if not isinstance(records, list):
                raise ValueError("inventory presentation records are invalid")
            for record in records:
                if not isinstance(record, Mapping):
                    raise ValueError("inventory presentation record is invalid")
                lines.append(f"- Result {record['result_ref']}: asset count {record['asset_count']}")
                if key == "stock_summaries":
                    lines.append(
                        f"  Quantity on hand: {record['total_quantity_on_hand']}; "
                        f"reorder candidates: {record['reorder_candidate_count']}"
                    )
        return "\n".join(lines) + "\n"
