"""Reader-facing scene annotations from verified pandapower result and model facts."""

from collections.abc import Mapping
import math
from typing import Any


def project_base_disconnections(diagram: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Keep model switch states available before any calculation is run."""
    rows = diagram.get("branch_states")
    if not isinstance(rows, list):
        return []
    return [{"id": row["id"], "markers": [
        {"bus_id": switch["bus_id"], "label": f"开关 {switch['index']}：断开"}
        for switch in row.get("open_switches", [])]}
        for row in rows if row.get("connected") is False]


def select_contingency_scene(
    results: list[tuple[str, Mapping[str, Any]]],
) -> tuple[str, str] | None:
    """Select the solved scenario with the highest Authority-reported line loading."""
    candidates = []
    for parent_ref, document in results:
        for scenario in document.get("scenarios", []):
            loading = scenario.get("max_loading_percent")
            reference = scenario.get("scenario_result_ref")
            if (scenario.get("status") == "succeeded" and isinstance(reference, str)
                    and type(loading) in (int, float) and math.isfinite(loading)):
                candidates.append((loading, parent_ref, reference))
    if not candidates:
        return None
    _, parent, child = max(candidates, key=lambda item: item[0])
    return parent, child


def project_scene_annotations(
    diagram: Mapping[str, Any], result: Mapping[str, Any],
    topology: Mapping[str, Any], lines: Mapping[str, Any], *, source_ref: str,
) -> dict[str, Any]:
    """The caller verifies the admitted result and its bound-context ancestry."""
    context, revision = result["context_ref"], result["revision_ref"]
    for facts in (topology, lines):
        if facts.get("context_ref") != context or facts.get("revision_ref") != revision:
            raise ValueError("annotation facts do not match the result scene")
    buses = {item["id"] for item in diagram["buses"]}
    branches = {item["id"] for item in diagram["branches"]}
    states: list[dict[str, Any]] = []
    outage = result.get("outage")
    if isinstance(outage, Mapping):
        identifier = f"{outage.get('kind')}:{outage.get('index')}"
        disconnected = [identifier] if identifier in branches else [
            item for item in branches if item in {identifier + ":mv", identifier + ":lv"}]
    else:
        branch_states = lines.get("branch_states")
        disconnected = ([row["id"] for row in branch_states if row.get("in_service") is False and row["id"] in branches]
                        if isinstance(branch_states, list) else
                        [f"line:{row['index']}" for row in lines.get("rows", [])
                         if row.get("in_service") is False and f"line:{row['index']}" in branches])
    if disconnected:
        states.append({"label": "已断开", "style": "disconnected", "ids": disconnected, "source_ref": source_ref})
    switched = []
    markers = []
    unavailable = []
    for row in lines.get("branch_states", []):
        identifier = row["id"]
        if identifier not in branches or identifier in disconnected:
            continue
        opened = [item for item in row.get("open_switches", []) if item.get("bus_id") in buses]
        if opened:
            switched.append(identifier)
            markers.extend({"id": identifier, "bus_id": item["bus_id"], "label": f"开关 {item['index']}"} for item in opened)
        elif row.get("connected") is False:
            unavailable.append(identifier)
    if switched:
        states.append({"label": "开关断开", "style": "disconnected", "ids": switched,
                       "markers": markers, "source_ref": source_ref})
    if unavailable:
        states.append({"label": "连接不可用", "style": "unresolved", "ids": unavailable, "source_ref": source_ref})
    datasets = result.get("datasets", {})
    overloaded = []
    for row in datasets.get("result.res_line", {}).get("rows", []):
        value = row.get("loading_percent")
        identifier = f"line:{row['index']}"
        if (type(value) in (int, float) and math.isfinite(value) and value > 100
                and identifier in branches and identifier not in disconnected):
            overloaded.append(identifier)
    if overloaded:
        states.append({"label": "负载率超过 100%", "style": "warning", "ids": overloaded, "source_ref": source_ref})
    rows = datasets.get("result.res_bus", {}).get("rows", [])
    unresolved = [str(row["index"]) for row in rows
                  if "vm_pu" in row and row["vm_pu"] is None and str(row["index"]) in buses]
    if unresolved:
        states.append({"label": "电压未求解", "style": "unresolved", "ids": unresolved, "source_ref": source_ref})
    regions = []
    # Contingency results retain the parent context; its topology cannot describe the outage.
    if not isinstance(outage, Mapping):
        for index, component in enumerate(topology.get("components", []), 1):
            members = [str(value) for value in component.get("bus_indices", [])]
            if (component.get("bus_list_complete") is not True or not members
                    or len(members) != component.get("bus_count") or not set(members) <= buses):
                continue
            reference = "有供电参考" if component.get("supply_reference_bus_indices") else "无供电参考"
            regions.append({"label": f"分区 {index}：{reference}", "ids": members, "source_ref": source_ref,
                            "emphasis": not bool(component.get("supply_reference_bus_indices"))})
    label = f"停运场景：{outage.get('kind')} {outage.get('index')}" if isinstance(outage, Mapping) else "分析场景"
    return {"scene": {"label": label,
                      "context_ref": context, "model_revision": revision, "source_ref": source_ref},
            "states": states, "regions": regions}
