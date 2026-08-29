from __future__ import annotations

import json
from importlib.resources import files

from pydantic import ValidationError

from inventory_reference.models import InventoryCatalog


def load_registered_catalog(catalog_id: str) -> InventoryCatalog:
    if not catalog_id or any(part in catalog_id for part in ("/", "\\", "..")):
        raise LookupError(f"registered inventory catalog was not found: {catalog_id}")
    resource = files("inventory_reference").joinpath(
        "resources", "catalogs", f"{catalog_id}.json"
    )
    try:
        payload = resource.read_text(encoding="utf-8")
        value = json.loads(payload)
        catalog = InventoryCatalog.model_validate(value)
    except (FileNotFoundError, ModuleNotFoundError, json.JSONDecodeError, ValidationError):
        raise LookupError(
            f"registered inventory catalog was not found: {catalog_id}"
        ) from None
    if catalog.catalog_id != catalog_id:
        raise LookupError(f"registered inventory catalog was not found: {catalog_id}")
    return catalog
