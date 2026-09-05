"""Inventory output bound to the active catalog and supplied admission scope."""
from __future__ import annotations

from collections.abc import Mapping
import re

from pydantic import BaseModel, ConfigDict

from capability_agent.domain.output import CommittedAnswer
from inventory_domain.state import (
    InventoryStateAdapter, context_mapping, parse_inventory_state,
    validate_inventory_reference,
)


class _OutputPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    catalog_id: str | None
    context_ref: str | None
    revision_ref: str | None
    asset_result_refs: list[str]
    stock_summary_refs: list[str]
    report_artifact_ref: str | None


def _structure(payload: Mapping[str, object]) -> _OutputPayload:
    parsed = _OutputPayload.model_validate(payload, strict=True)
    triple = (parsed.catalog_id, parsed.context_ref, parsed.revision_ref)
    if any(item is None for item in triple):
        if any(item is not None for item in triple):
            raise ValueError("inventory catalog triple is incomplete")
        if parsed.asset_result_refs or parsed.stock_summary_refs:
            raise ValueError("inventory result references require an active catalog")
    else:
        if not parsed.catalog_id:
            raise ValueError("inventory catalog identity is empty")
        validate_inventory_reference(parsed.context_ref, "context")
        validate_inventory_reference(parsed.revision_ref, "revision")
    for reference in (*parsed.asset_result_refs, *parsed.stock_summary_refs):
        validate_inventory_reference(reference, "result")
    if parsed.report_artifact_ref is not None:
        _require_report_reference(parsed.report_artifact_ref)
    return parsed


def _require_report_reference(reference: object) -> None:
    if not isinstance(reference, str) or re.fullmatch(
        r"artifact:sha256:[a-f0-9]{64}", reference
    ) is None:
        raise ValueError("inventory report artifact reference is invalid")


def _scope(raw: Mapping[str, object], name: str) -> frozenset[str]:
    values = raw.get(name, ())
    if not isinstance(values, (tuple, list)) or any(
        not isinstance(value, str) for value in values
    ):
        raise ValueError("inventory output admission scope is invalid")
    return frozenset(values)


def _expected(context: object) -> tuple[str, dict[str, object]]:
    raw = context_mapping(context)
    binding_id = raw.get("binding_id")
    state = raw.get("state")
    if not isinstance(binding_id, str) or not isinstance(state, Mapping):
        raise ValueError("inventory output context is invalid")
    parsed = parse_inventory_state(binding_id, state)
    admitted = _scope(raw, "admitted_refs")
    required = InventoryStateAdapter().build_context(
        binding_id=binding_id, state=state
    ).admitted_refs
    if not set(required).issubset(admitted):
        raise ValueError("inventory context references are not admitted")
    report = raw.get("report_artifact_ref")
    if report is not None:
        _require_report_reference(report)
        if report not in _scope(raw, "admitted_artifact_refs"):
            raise ValueError("inventory report reference is not admitted")
    catalog = (
        parsed.catalogs[parsed.active_context_ref]
        if parsed.active_context_ref is not None else None
    )
    assets: list[str] = []
    summaries: list[str] = []
    if catalog is not None:
        assets = sorted(
            ref for ref, record in parsed.asset_results.items()
            if (record.context_ref, record.revision_ref)
            == (catalog.context_ref, catalog.revision_ref)
        )
        summaries = sorted(
            ref for ref, record in parsed.stock_summaries.items()
            if (record.context_ref, record.revision_ref)
            == (catalog.context_ref, catalog.revision_ref)
        )
    payload: dict[str, object] = {
        "catalog_id": catalog.catalog_id if catalog is not None else None,
        "context_ref": catalog.context_ref if catalog is not None else None,
        "revision_ref": catalog.revision_ref if catalog is not None else None,
        "asset_result_refs": assets,
        "stock_summary_refs": summaries,
        "report_artifact_ref": report,
    }
    _structure(payload)
    return binding_id, payload


class InventoryOutputContract:
    schema_id = "inventory-readonly-output/1.0"

    def build(
        self, *, binding_id: str, context: object,
        committed_answers: tuple[CommittedAnswer, ...],
    ) -> Mapping[str, object]:
        del committed_answers
        owner, payload = _expected(context)
        if owner != binding_id:
            raise ValueError("inventory output binding mismatch")
        return payload

    def validate(self, payload: Mapping[str, object]) -> None:
        parsed = _structure(payload)
        if (
            parsed.context_ref is not None or parsed.report_artifact_ref is not None
            or parsed.asset_result_refs or parsed.stock_summary_refs
        ):
            raise ValueError("inventory output reference admission requires context")

    def validate_with_context(
        self, payload: Mapping[str, object], *, context: object | None
    ) -> None:
        parsed = _structure(payload)
        _, expected = _expected(context)
        if parsed.model_dump(mode="json") != expected:
            raise ValueError("inventory output does not match its active admitted context")
