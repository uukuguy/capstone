"""Allowlisted, installed model sources."""

from __future__ import annotations

import json
from importlib.resources import files


def load_registered_model(catalog_id: str) -> dict[str, object]:
    if catalog_id != "two-bus":
        raise LookupError("registered PyPSA model was not found")
    resource = files("pypsa_model_authority").joinpath(
        "resources", "models", "two-bus.json"
    )
    document = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("catalog_id") != catalog_id:
        raise LookupError("registered PyPSA model was not found")
    return document
