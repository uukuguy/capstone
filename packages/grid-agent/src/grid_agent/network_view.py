"""Pandapower authority-backed operator network projection."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any, Protocol


class NetworkExecutor(Protocol):
    def invoke(self, capability: str, arguments: dict[str, object]) -> dict[str, object]: ...


def _dataset_rows(
    executor: NetworkExecutor, context_ref: str, dataset: str,
    fields: list[str], limit: int,
) -> tuple[list[dict[str, object]], int, str]:
    rows: list[dict[str, object]] = []
    offset = 0
    revision: str | None = None
    row_count: int | None = None
    while len(rows) < limit:
        page = executor.invoke("model.dataset.query", {
            "context_ref": context_ref, "dataset": dataset, "select": fields,
            "sort": {"field": "index", "direction": "ascending"},
            "offset": offset, "limit": min(50, limit - len(rows)),
        })
        if page.get("context_ref") != context_ref or page.get("dataset") != dataset:
            raise ValueError("network page differs from the opened model")
        current_revision = page.get("revision_ref")
        count = page.get("row_count")
        selected = page.get("rows")
        if (not isinstance(current_revision, str) or not current_revision
                or type(count) is not int or count < 0 or not isinstance(selected, list)
                or any(not isinstance(item, dict) for item in selected)):
            raise ValueError("network page is invalid")
        if revision is not None and revision != current_revision:
            raise ValueError("network revision changed between pages")
        if row_count is not None and row_count != count:
            raise ValueError("network row count changed between pages")
        revision, row_count = current_revision, count
        rows.extend(selected)
        next_offset = page.get("next_offset")
        if next_offset is None:
            break
        if type(next_offset) is not int or next_offset <= offset:
            raise ValueError("network pagination is invalid")
        offset = next_offset
    assert revision is not None and row_count is not None
    return rows[:limit], row_count, revision


def build_grid_network_view(
    executor: NetworkExecutor, context_ref: str, ordinal: int, case_id: str,
    committed_refs: Sequence[str], calls: Sequence[Mapping[str, object]],
) -> dict[str, Any]:
    if case_id not in {"pandapower-scripted-task", "pandapower-scripted-test"}:
        raise ValueError("network view case is not registered")
    bus_rows, bus_count, revision = _dataset_rows(
        executor, context_ref, "network.buses", ["index", "name"], 50,
    )
    branch_rows, branch_count, branch_revision = _dataset_rows(
        executor, context_ref, "network.branches",
        ["index", "kind", "name", "from_bus_index", "to_bus_index"], 100,
    )
    if revision != branch_revision:
        raise ValueError("network datasets have different revisions")
    buses = [{"id": str(row["index"]), "label": str(row["name"]), "x": None, "y": None}
             for row in bus_rows]
    bus_ids = {bus["id"] for bus in buses}
    branches = [{
        "id": f"{row['kind']}:{row['index']}", "kind": str(row["kind"]),
        "label": str(row["name"]), "from_bus": str(row["from_bus_index"]),
        "to_bus": str(row["to_bus_index"]),
    } for row in branch_rows if str(row["from_bus_index"]) in bus_ids
        and str(row["to_bus_index"]) in bus_ids]
    branch_ids = {branch["id"] for branch in branches}
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
        "schema": "capstone-network-view/1.0", "ordinal": ordinal,
        "model": {"id": "ieee39", "revision": revision, "source": "gridctl"},
        "coordinate_status": "schematic-required",
        "buses": buses, "branches": branches,
        "omitted": {"buses": max(0, bus_count - len(buses)),
                    "branches": max(0, branch_count - len(branches))},
        "focus_ids": focus, "next_focus_ids": next_focus, "overlay": overlay,
    }
