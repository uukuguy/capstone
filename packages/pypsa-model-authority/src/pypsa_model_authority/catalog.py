"""Allowlisted, installed model sources."""

from __future__ import annotations

import json
from importlib.resources import files

from pypsa_model_authority import model_library


PROJECT_MODEL_IDS = (
    "two-bus", "unit-commitment", "security-triangle", "congested-two-bus",
    "rolling-storage", "regional-six-bus", "capacity-two-bus",
    "capacity-commitment", "capacity-pathway", "capacity-scenarios",
    "electricity-hydrogen", "electricity-heat-pump", "hydrogen-storage",
    "chp-hydrogen-heat", "heat-pump-storage",
)


def list_registered_models() -> tuple[dict[str, object], ...]:
    project: tuple[dict[str, object], ...] = tuple({
        "catalog_id": catalog_id,
        "display_name": catalog_id.replace("-", " ").title(),
        "source_kind": "capstone-registered-json", "installed": True,
    } for catalog_id in PROJECT_MODEL_IDS)
    official: list[dict[str, object]] = []
    for entry in model_library.list_official_examples():
        try:
            model_library.verified_asset_path(entry.catalog_id)
            installed = True
        except model_library.ModelLibraryError:
            installed = False
        official.append({
            "catalog_id": entry.catalog_id, "display_name": entry.display_name,
            "source_kind": "official-pypsa-netcdf", "pypsa_version": "1.3.0",
            "source_url": entry.source_url, "source_sha256": entry.sha256,
            "size_bytes": entry.size_bytes, "business_theme": entry.business_theme,
            "installed": installed,
        })
    return (*project, *official)


def load_registered_model(catalog_id: str) -> dict[str, object]:
    if catalog_id not in PROJECT_MODEL_IDS:
        raise LookupError("registered PyPSA model was not found")
    resource = files("pypsa_model_authority").joinpath(
        "resources", "models", f"{catalog_id}.json"
    )
    document = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("catalog_id") != catalog_id:
        raise LookupError("registered PyPSA model was not found")
    return document
