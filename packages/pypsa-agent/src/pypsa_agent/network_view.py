"""PyPSA authority-backed operator network projection."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any, Protocol


class TopologyExecutor(Protocol):
    def invoke(self, capability: str, arguments: dict[str, object]) -> dict[str, object]: ...


def build_pypsa_network_view(
    executor: TopologyExecutor, model_ref: str, model_id: str, ordinal: int,
    case_id: str, dispatch: Mapping[str, object] | None,
    committed_refs: Sequence[str],
) -> dict[str, Any]:
    if case_id not in {"regional-demand-stress", "scigrid-dispatch", "ac-dc-interconnection"}:
        raise ValueError("PyPSA network view case is not registered")
    topology = executor.invoke("model.topology", {"model_ref": model_ref})
    if topology.get("model_ref") != model_ref:
        raise ValueError("PyPSA topology belongs to another revision")
    raw_buses = topology.get("buses")
    if not isinstance(raw_buses, list):
        raise ValueError("PyPSA topology has no bus list")
    buses = [{
        "id": str(bus["id"]), "label": str(bus["id"]),
        "x": bus.get("x"), "y": bus.get("y"),
    } for bus in raw_buses if isinstance(bus, Mapping)]
    bus_ids = {bus["id"] for bus in buses}
    branches = []
    for kind, key in (("line", "lines"), ("link", "links"), ("transformer", "transformers")):
        raw_branches = topology.get(key)
        if not isinstance(raw_branches, list):
            raise ValueError("PyPSA topology branch list is invalid")
        for raw in raw_branches:
            if not isinstance(raw, Mapping):
                raise ValueError("PyPSA topology branch is invalid")
            source = str(raw["from_bus"])
            target = str(raw["to_bus"])
            if source in bus_ids and target in bus_ids:
                branches.append({"id": f"{kind}:{raw['id']}", "kind": kind,
                                 "label": str(raw["id"]),
                                 "from_bus": source, "to_bus": target})
    omitted_counts = topology.get("omitted_counts")
    if not isinstance(omitted_counts, Mapping):
        raise ValueError("PyPSA topology omission counts are invalid")
    omitted_branches = sum(int(omitted_counts[key]) for key in
                           ("lines", "links", "transformers"))
    if len(branches) > 100:
        omitted_branches += len(branches) - 100
        branches = branches[:100]
    visible_ids = {branch["id"] for branch in branches}
    focus: list[str] = []
    if case_id == "ac-dc-interconnection" and ordinal == 2:
        focus = [branch["id"] for branch in branches if branch["kind"] == "link"][:20]
    next_focus = ([branch["id"] for branch in branches if branch["kind"] == "link"][:20]
                  if case_id == "ac-dc-interconnection" and ordinal == 1 else [])
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
        "schema": "capstone-network-view/1.0", "ordinal": ordinal,
        "model": {"id": model_id, "revision": model_ref, "source": "pypsamodelctl"},
        "coordinate_status": topology["coordinate_status"],
        "buses": buses, "branches": branches,
        "omitted": {"buses": int(omitted_counts["buses"]),
                    "branches": omitted_branches},
        "focus_ids": focus, "next_focus_ids": next_focus, "overlay": overlay,
    }
