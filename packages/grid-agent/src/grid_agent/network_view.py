"""Pandapower authority-backed operator diagram and admitted step layer."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any, Protocol


class NetworkExecutor(Protocol):
    def invoke(self, capability: str, arguments: dict[str, object]) -> dict[str, object]: ...


def build_grid_network_view(
    executor: NetworkExecutor, context_ref: str, ordinal: int, case_id: str,
    committed_refs: Sequence[str], calls: Sequence[Mapping[str, object]],
) -> dict[str, Any]:
    if case_id not in {"pandapower-scripted-task", "pandapower-scripted-test"}:
        raise ValueError("network view case is not registered")
    topology = executor.invoke("operator.diagram.get", {"context_ref": context_ref})
    if topology.get("context_ref") != context_ref:
        raise ValueError("network diagram belongs to another context")
    revision = topology.get("revision_ref")
    buses = topology.get("buses")
    branches = topology.get("branches")
    if not isinstance(revision, str) or not isinstance(buses, list) or not isinstance(branches, list):
        raise ValueError("network diagram is invalid")
    branch_ids = {
        branch["id"] for branch in branches
        if isinstance(branch, Mapping) and isinstance(branch.get("id"), str)
    }
    focus_id = (
        "line:11" if case_id == "pandapower-scripted-task" and ordinal == 1
        else "line:17" if case_id == "pandapower-scripted-test" and ordinal in {2, 3}
        else None
    )
    focus = [focus_id] if focus_id in branch_ids else []
    next_focus_id = "line:17" if case_id == "pandapower-scripted-test" and ordinal == 1 else None
    next_focus = [next_focus_id] if next_focus_id in branch_ids else []
    overlay = None
    if case_id == "pandapower-scripted-task" and ordinal == 3:
        for call in reversed(calls):
            if call.get("capability") != "result.branches.rank":
                continue
            result = call.get("result")
            if not isinstance(result, Mapping):
                continue
            ref = result.get("result_ref")
            if (not isinstance(ref, str) or ref not in committed_refs
                    or result.get("revision_ref") != revision
                    or result.get("metric") != "loading_percent"):
                continue
            ranked = result.get("branches")
            if not isinstance(ranked, list):
                continue
            values = []
            for item in ranked:
                if not isinstance(item, Mapping) or item.get("element_kind") != "line":
                    continue
                identifier = f"line:{item.get('pandapower_index')}"
                number = item.get("loading_percent")
                if (identifier in branch_ids and type(number) in (int, float)
                        and math.isfinite(number)):
                    values.append({"id": identifier, "value": float(number)})
            if values:
                overlay = {"metric": "loading_percent", "unit": "%",
                           "source_ref": ref, "values": values}
                focus = [item["id"] for item in values[:3]]
            break
    return {
        "schema": "capstone-network-view/2.0", "ordinal": ordinal,
        "diagram": {
            "schema": "capstone-network-diagram/1.0",
            "model": {"id": "ieee39", "revision": revision, "source": "gridctl"},
            "coordinate_system": topology.get("coordinate_system"),
            "buses": buses, "branches": branches,
        },
        "layer": {"focus_ids": focus, "next_focus_ids": next_focus, "overlay": overlay},
    }
