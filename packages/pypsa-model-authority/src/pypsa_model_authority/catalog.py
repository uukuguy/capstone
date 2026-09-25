"""Allowlisted, installed model sources."""

from __future__ import annotations

import json
from importlib.resources import files


def load_registered_model(catalog_id: str) -> dict[str, object]:
    if catalog_id not in {"two-bus", "unit-commitment", "security-triangle", "capacity-two-bus", "electricity-hydrogen", "electricity-heat-pump", "hydrogen-storage", "chp-hydrogen-heat", "heat-pump-storage"}:
        raise LookupError("registered PyPSA model was not found")
    resource = files("pypsa_model_authority").joinpath(
        "resources", "models", f"{catalog_id}.json"
    )
    document = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("catalog_id") != catalog_id:
        raise LookupError("registered PyPSA model was not found")
    return document
