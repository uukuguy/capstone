"""Authority-owned federated Thread catalog export for pandapower."""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence

from grid_simulator.engine import Pandapower340Engine
from grid_simulator.models import ModelRegistry
from grid_agent.thread_model_metadata import model_display_name


def build_catalog_document() -> dict[str, object]:
    """Return the bounded public catalog for the current hosted grid scope."""

    registry = ModelRegistry(Pandapower340Engine())
    return {
        "schema": "capstone-federated-catalog/1",
        "default_model_id": "ieee39",
        "models": [
            {
                "model_id": model.model_id,
                "authority_model_ref": f"gridctl:{model.model_id}",
                "display_name": model_display_name(model.title, model.model_id),
                "diagram_provider_id": "gridctl",
                "implementation_family": model.engine,
                "revision_ref": registry.trusted_revision_ref(model.model_id),
                **({"available": False, "unavailable_reason": reason}
                   if (reason := registry.operator_diagram_unavailable_reason(model.model_id)) else {}),
            }
            for model in registry.list()
        ],
        "profiles": [
            {
                "profile_id": "pandapower-static-analysis",
                "profile_version": "1.0.1",
                "display_name": "Pandapower Static Analysis",
                "implementation_families": ["pandapower"],
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
