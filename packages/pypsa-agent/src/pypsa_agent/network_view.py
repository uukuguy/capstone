"""PyPSA authority-backed operator diagram and admitted step layer."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any, Protocol


class DiagramExecutor(Protocol):
    def invoke(self, capability: str, arguments: dict[str, object]) -> dict[str, object]: ...


def build_pypsa_network_view(
    executor: DiagramExecutor, model_ref: str, model_id: str, ordinal: int,
    case_id: str, dispatch: Mapping[str, object] | None,
    committed_refs: Sequence[str],
) -> dict[str, Any]:
    if case_id not in {"regional-demand-stress", "scigrid-dispatch", "ac-dc-interconnection"}:
        raise ValueError("PyPSA network view case is not registered")
    topology = executor.invoke("operator.diagram", {"model_ref": model_ref})
    if topology.get("model_ref") != model_ref:
        raise ValueError("PyPSA diagram belongs to another revision")
    buses = topology.get("buses")
    branches = topology.get("branches")
    if not isinstance(buses, list) or not isinstance(branches, list):
        raise ValueError("PyPSA diagram is invalid")
    visible_ids = {
        branch["id"] for branch in branches
        if isinstance(branch, Mapping) and isinstance(branch.get("id"), str)
    }
    links = [
        branch["id"] for branch in branches
        if isinstance(branch, Mapping) and branch.get("kind") == "link"
        and isinstance(branch.get("id"), str)
    ]
    focus: list[str] = []
    if case_id == "ac-dc-interconnection" and ordinal == 2:
        focus = links[:20]
    next_focus = links[:20] if case_id == "ac-dc-interconnection" and ordinal == 1 else []
    overlay = None
    if ordinal == 3 and isinstance(dispatch, Mapping):
        ref = dispatch.get("result_ref")
        ranked = dispatch.get("top_line_loading")
        if (dispatch.get("model_ref") == model_ref and isinstance(ref, str)
                and ref in committed_refs and isinstance(ranked, list)):
            values = []
            for item in ranked:
                if not isinstance(item, Mapping):
                    continue
                identifier = f"line:{item.get('line_id')}"
                number = item.get("max_loading_pct")
                if (identifier in visible_ids and type(number) in (int, float)
                        and math.isfinite(number)):
                    values.append({"id": identifier, "value": float(number)})
            if values:
                overlay = {"metric": "loading_percent", "unit": "%",
                           "source_ref": ref, "values": values}
                focus = [item["id"] for item in values[:3]]
    return {
        "schema": "capstone-network-view/2.0", "ordinal": ordinal,
        "diagram": {
            "schema": "capstone-network-diagram/1.0",
            "model": {"id": model_id, "revision": model_ref, "source": "pypsamodelctl"},
            "coordinate_system": topology.get("coordinate_system"),
            "buses": buses, "branches": branches,
        },
        "layer": {"focus_ids": focus, "next_focus_ids": next_focus, "overlay": overlay},
    }
