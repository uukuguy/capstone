from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from inventory_reference.artifacts import load_document, persist_document
from inventory_reference.catalog import load_registered_catalog
from inventory_reference.models import InventoryAsset


PUBLISHED_CAPABILITIES = (
    "catalog.open",
    "asset.list",
    "asset.get",
    "stock.summary",
)


class InventoryCapabilityError(RuntimeError):
    def __init__(self, code: str, message: str, recovery: str) -> None:
        super().__init__(message)
        self.code = code
        self.recovery = recovery

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": str(self),
            "recovery": self.recovery,
        }


def execute(
    capability: str,
    arguments: Mapping[str, object],
    workspace: Path,
) -> dict[str, object]:
    if capability == "environment.describe":
        _require_exact_keys(arguments, set())
        return {
            "protocol": "inventory-capability",
            "protocol_version": "1.0",
            "service": "inventory-reference-service",
            "service_version": "0.1.0",
            "executable_capabilities": [
                {"id": item} for item in PUBLISHED_CAPABILITIES
            ],
        }
    if capability not in PUBLISHED_CAPABILITIES:
        raise InventoryCapabilityError(
            "capability_not_published",
            f"inventory capability is not published: {capability}",
            "Use environment.describe and select a published read-only capability.",
        )
    if capability == "catalog.open":
        return _open_catalog(arguments, workspace)
    context, catalog = _bound_catalog(arguments, workspace)
    if capability == "asset.list":
        return _list_assets(arguments, workspace, context, catalog.assets)
    if capability == "asset.get":
        return _get_asset(arguments, workspace, context, catalog.assets)
    return _stock_summary(arguments, workspace, context, catalog.assets)


def _open_catalog(
    arguments: Mapping[str, object], workspace: Path
) -> dict[str, object]:
    _require_exact_keys(arguments, {"catalog_id"})
    catalog_id = _required_string(arguments, "catalog_id")
    try:
        catalog = load_registered_catalog(catalog_id)
    except LookupError as exc:
        raise InventoryCapabilityError(
            "catalog_not_found",
            str(exc),
            "Use the registered catalog id warehouse-a.",
        ) from exc
    revision_document = catalog.model_dump(mode="json")
    revision_ref, _ = persist_document(
        workspace, "revision", revision_document
    )
    context_document = {
        "schema_version": "inventory-context/1.0",
        "catalog_id": catalog.catalog_id,
        "revision_ref": revision_ref,
    }
    context_ref, _ = persist_document(workspace, "context", context_document)
    return {
        "catalog_id": catalog.catalog_id,
        "revision_ref": revision_ref,
        "context_ref": context_ref,
        "asset_count": len(catalog.assets),
    }


def _bound_catalog(
    arguments: Mapping[str, object], workspace: Path
) -> tuple[dict[str, object], Any]:
    context_ref = arguments.get("context_ref")
    if not isinstance(context_ref, str) or not context_ref.startswith(
        "inventory-context:sha256:"
    ):
        raise InventoryCapabilityError(
            "invalid_context_ref",
            "context_ref must be an inventory context reference",
            "Call catalog.open and pass its context_ref unchanged.",
        )
    try:
        context = load_document(workspace, context_ref, "context")
    except FileNotFoundError as exc:
        raise InventoryCapabilityError(
            "context_not_found",
            "inventory context is not in the current run",
            "Call catalog.open in the current workspace.",
        ) from exc
    except ValueError as exc:
        raise InventoryCapabilityError(
            "invalid_context_ref",
            str(exc),
            "Call catalog.open and pass its context_ref unchanged.",
        ) from exc
    catalog_id = context.get("catalog_id")
    revision_ref = context.get("revision_ref")
    if not isinstance(catalog_id, str) or not isinstance(revision_ref, str):
        raise InventoryCapabilityError(
            "context_integrity_error",
            "inventory context is incomplete",
            "Open the registered catalog again in a fresh run.",
        )
    try:
        revision = load_document(workspace, revision_ref, "revision")
        catalog = load_registered_catalog(catalog_id)
    except (FileNotFoundError, ValueError, LookupError) as exc:
        raise InventoryCapabilityError(
            "context_integrity_error",
            "inventory context revision cannot be verified",
            "Open the registered catalog again in a fresh run.",
        ) from exc
    if catalog.model_dump(mode="json") != revision or catalog.revision_ref != revision_ref:
        raise InventoryCapabilityError(
            "context_integrity_error",
            "registered inventory revision does not match the current context",
            "Open the registered catalog again in a fresh run.",
        )
    return context, catalog


def _list_assets(
    arguments: Mapping[str, object],
    workspace: Path,
    context: Mapping[str, object],
    assets: tuple[InventoryAsset, ...],
) -> dict[str, object]:
    _require_exact_keys(arguments, {"context_ref", "category", "location", "limit"})
    category = _optional_string(arguments, "category")
    location = _optional_string(arguments, "location")
    limit = arguments.get("limit", 50)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise _invalid_arguments("limit must be an integer from 1 through 100")
    selected = [
        asset
        for asset in sorted(assets, key=lambda item: item.asset_id)
        if (category is None or asset.category == category)
        and (location is None or asset.location == location)
    ][:limit]
    return _persist_result(
        workspace,
        "asset.list",
        context,
        {
            "assets": [asset.model_dump(mode="json") for asset in selected],
            "count": len(selected),
            "filters": {
                key: value
                for key, value in (("category", category), ("location", location))
                if value is not None
            },
        },
    )


def _get_asset(
    arguments: Mapping[str, object],
    workspace: Path,
    context: Mapping[str, object],
    assets: tuple[InventoryAsset, ...],
) -> dict[str, object]:
    _require_exact_keys(arguments, {"context_ref", "asset_id"})
    asset_id = _required_string(arguments, "asset_id")
    asset = next((item for item in assets if item.asset_id == asset_id), None)
    if asset is None:
        raise InventoryCapabilityError(
            "asset_not_found",
            f"registered inventory asset was not found: {asset_id}",
            "Use asset.list to discover registered asset identifiers.",
        )
    return _persist_result(
        workspace,
        "asset.get",
        context,
        {"asset": asset.model_dump(mode="json")},
    )


def _stock_summary(
    arguments: Mapping[str, object],
    workspace: Path,
    context: Mapping[str, object],
    assets: tuple[InventoryAsset, ...],
) -> dict[str, object]:
    _require_exact_keys(arguments, {"context_ref"})
    candidates = sorted(
        (
            asset.asset_id
            for asset in assets
            if asset.quantity_on_hand <= asset.reorder_level
        )
    )
    return _persist_result(
        workspace,
        "stock.summary",
        context,
        {
            "asset_count": len(assets),
            "total_quantity_on_hand": sum(
                asset.quantity_on_hand for asset in assets
            ),
            "reorder_candidate_count": len(candidates),
            "reorder_asset_ids": candidates,
        },
    )


def _persist_result(
    workspace: Path,
    capability: str,
    context: Mapping[str, object],
    data: dict[str, object],
) -> dict[str, object]:
    context_ref = _context_reference(context)
    revision_ref = str(context["revision_ref"])
    result_document = {
        "schema_version": "inventory-result/1.0",
        "capability": capability,
        "context_ref": context_ref,
        "revision_ref": revision_ref,
        "data": data,
    }
    result_ref, _ = persist_document(workspace, "result", result_document)
    evidence_document = {
        "schema_version": "inventory-evidence/1.0",
        "capability": capability,
        "context_ref": context_ref,
        "revision_ref": revision_ref,
        "result_ref": result_ref,
        "facts": data,
    }
    evidence_ref, _ = persist_document(workspace, "evidence", evidence_document)
    return {
        **data,
        "capability": capability,
        "context_ref": context_ref,
        "revision_ref": revision_ref,
        "result_ref": result_ref,
        "evidence_refs": [evidence_ref],
    }


def _context_reference(context: Mapping[str, object]) -> str:
    from inventory_reference.artifacts import content_reference

    return content_reference("context", context)


def _require_exact_keys(arguments: Mapping[str, object], allowed: set[str]) -> None:
    unexpected = sorted(set(arguments) - allowed)
    if unexpected:
        raise _invalid_arguments(f"unexpected arguments: {', '.join(unexpected)}")


def _required_string(arguments: Mapping[str, object], key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value:
        raise _invalid_arguments(f"{key} must be a non-empty string")
    return value


def _optional_string(arguments: Mapping[str, object], key: str) -> str | None:
    value = arguments.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise _invalid_arguments(f"{key} must be a non-empty string")
    return value


def _invalid_arguments(message: str) -> InventoryCapabilityError:
    return InventoryCapabilityError(
        "invalid_arguments",
        message,
        "Use the published capability input schema.",
    )
