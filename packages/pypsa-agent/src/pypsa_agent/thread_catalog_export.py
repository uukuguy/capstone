"""Authority-owned federated Thread catalog export for PyPSA."""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Sequence

from pypsa_model_authority.catalog import list_registered_models, load_registered_model
from pypsa_model_authority.store import canonical_bytes


_MAX_MODELS = 128


def _revision_ref(record: dict[str, object]) -> str:
    digest = record.get("source_sha256")
    if not isinstance(digest, str):
        catalog_id = record.get("catalog_id")
        if not isinstance(catalog_id, str):
            raise ValueError("registered PyPSA catalog record is invalid")
        digest = hashlib.sha256(canonical_bytes(load_registered_model(catalog_id))).hexdigest()
    if (
        len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ValueError("registered PyPSA model revision is invalid")
    return f"revision:sha256:{digest}"


def build_catalog_document() -> dict[str, object]:
    """Return every registered PyPSA model as public immutable metadata."""

    records = list_registered_models()
    if len(records) > _MAX_MODELS:
        raise ValueError("registered PyPSA catalog is too large")
    models: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw_record in records:
        if not isinstance(raw_record, dict):
            raise ValueError("registered PyPSA catalog record is invalid")
        catalog_id = raw_record.get("catalog_id")
        if not isinstance(catalog_id, str) or not catalog_id:
            raise ValueError("registered PyPSA catalog ID is invalid")
        if catalog_id in seen:
            raise ValueError(f"duplicate registered PyPSA model: {catalog_id}")
        seen.add(catalog_id)
        display_name = raw_record.get("display_name") or catalog_id
        if not isinstance(display_name, str) or not display_name.strip():
            raise ValueError(f"registered PyPSA display name is invalid: {catalog_id}")
        models.append(
            {
                "model_id": catalog_id,
                "authority_model_ref": f"pypsa:{catalog_id}",
                "display_name": display_name,
                "diagram_provider_id": "pypsa",
                "implementation_family": "pypsa",
                "revision_ref": _revision_ref(raw_record),
            },
        )
    if "regional-six-bus" not in seen:
        raise ValueError("registered PyPSA default model is missing")
    models.sort(key=lambda model: str(model["model_id"]))
    return {
        "schema": "capstone-federated-catalog/1",
        "default_model_id": "regional-six-bus",
        "models": models,
        "profiles": [
            {
                "profile_id": "pypsa-business-cases",
                "profile_version": "1.0.0",
                "display_name": "PyPSA Business Cases",
                "implementation_families": ["pypsa"],
                "default": True,
            },
        ],
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Write exactly one JSON document to stdout for the control plane."""

    if argv is None:
        argv = sys.argv[1:]
    if len(argv) == 3 and argv[0] == "--diagram":
        from .thread_model_diagram import model_diagram
        json.dump(model_diagram(argv[1], argv[2]), sys.stdout, separators=(",", ":"))
        sys.stdout.write("\n")
        return 0
    if argv:
        raise SystemExit("catalog export does not accept arguments")
    json.dump(build_catalog_document(), sys.stdout, sort_keys=True, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


__all__ = ["build_catalog_document", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
