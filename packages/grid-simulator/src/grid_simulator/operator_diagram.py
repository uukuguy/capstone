"""Complete, bounded operator geometry and catalogue eligibility from one source."""

from functools import lru_cache
from importlib.resources import files
import json
import math
from typing import Any

from .capabilities.schema import CapabilityContract
from .queries import element_name


class OperatorDiagramError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def operator_branch_states(net: Any, branches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Project circuit disconnections from service flags and actual terminal switches."""
    opened: dict[tuple[str, int], list[dict[str, Any]]] = {}
    switch_kinds = {"l": "line", "t": "trafo", "t3": "trafo3w"}
    for index, row in net.switch.iterrows():
        kind = switch_kinds.get(str(row.et))
        if kind is not None and not bool(row.closed):
            opened.setdefault((kind, int(row.element)), []).append({"index": int(index), "bus_id": str(row.bus)})
    active_buses = {str(index): bool(row.in_service) for index, row in net.bus.iterrows()}
    states = []
    for branch in branches:
        kind, index = branch["kind"], int(branch["id"].split(":")[1])
        if kind == "link":
            row = net.switch.loc[index]
            if not bool(row.closed):
                states.append({"id": branch["id"], "in_service": True, "connected": False,
                               "open_switches": [{"index": index, "bus_id": str(row.bus)}]})
            continue
        in_service = bool(net[kind].loc[index, "in_service"])
        switches = [item for item in opened.get((kind, index), [])
                    if item["bus_id"] in {branch["from_bus"], branch["to_bus"]}]
        connected = in_service and active_buses[branch["from_bus"]] and active_buses[branch["to_bus"]] and not switches
        if not connected:
            states.append({"id": branch["id"], "in_service": in_service,
                           "connected": False, "open_switches": switches})
    return states


@lru_cache(maxsize=1)
def operator_diagram_contract() -> CapabilityContract:
    return CapabilityContract.model_validate_json(
        files("grid_simulator").joinpath("operator_diagram_contract.json").read_text(encoding="utf-8")
    )


def operator_geometry(net: Any) -> dict[str, Any]:
    """Project every bus and branch; never truncate an unsupported model."""
    schema = operator_diagram_contract().output_schema
    properties = schema["properties"]
    if not isinstance(properties, dict):
        raise ValueError("operator diagram properties must be an object")

    def array_limit(name: str) -> int:
        definition = properties.get(name)
        value = definition.get("maxItems") if isinstance(definition, dict) else None
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"operator diagram {name} limit must be a positive integer")
        return value

    max_bytes = schema["x-maxBytes"]
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes <= 4096:
        raise ValueError("operator diagram byte limit must exceed the metadata reserve")
    if len(net.bus) > array_limit("buses") or len(net.line) + len(net.trafo) + 2 * len(net.trafo3w) > array_limit("branches"):
        raise OperatorDiagramError("diagram_limit")

    def finite(value: object) -> float | None:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return None
        return float(value) if math.isfinite(value) else None

    def point(value: object) -> tuple[float | None, float | None]:
        if not isinstance(value, str):
            return None, None
        try:
            geo = json.loads(value)
        except (TypeError, ValueError):
            return None, None
        if not isinstance(geo, dict) or geo.get("type") != "Point":
            return None, None
        coords = geo.get("coordinates")
        if not isinstance(coords, list) or len(coords) != 2:
            return None, None
        x, y = finite(coords[0]), finite(coords[1])
        return (x, y) if x is not None and y is not None else (None, None)

    buses = []
    for index, row in net.bus.sort_index().iterrows():
        x, y = point(row.get("geo"))
        name = element_name(row.get("name"), index)
        buses.append({"id": str(index), "label": name,
                      "x": x, "y": y, "vn_kv": finite(row.get("vn_kv"))})
    branches = []
    for kind, table, ends in (("line", net.line, ("from_bus", "to_bus")), ("trafo", net.trafo, ("hv_bus", "lv_bus"))):
        for index, row in table.sort_index().iterrows():
            name = element_name(row.get("name"), index)
            branches.append({"id": f"{kind}:{index}", "kind": kind,
                             "label": name,
                             "from_bus": str(row[ends[0]]), "to_bus": str(row[ends[1]])})
    for index, row in net.trafo3w.sort_index().iterrows():
        name = element_name(row.get("name"), index)
        for terminal in ("mv", "lv"):
            branches.append({"id": f"trafo3w:{index}:{terminal}", "kind": "trafo3w",
                             "label": name,
                             "from_bus": str(row["hv_bus"]), "to_bus": str(row[f"{terminal}_bus"])})
    for index, row in net.switch.sort_index().iterrows():
        if str(row.et) == "b":
            branches.append({"id": f"switch:{index}", "kind": "link", "label": f"开关 {index}",
                             "from_bus": str(row.bus), "to_bus": str(row.element)})
    if len(branches) > array_limit("branches"):
        raise OperatorDiagramError("diagram_limit")
    ids = {bus["id"] for bus in buses}
    if not buses or any(branch["from_bus"] not in ids or branch["to_bus"] not in ids for branch in branches):
        raise OperatorDiagramError("diagram_invalid")
    for row in (*buses, *branches):
        if any(not 0 < len(row[key]) <= 200 or any(ord(char) < 32 for char in row[key]) for key in ("id", "label")):
            raise OperatorDiagramError("diagram_invalid")
    geometry = {"coordinate_system": "schematic", "buses": buses, "branches": branches}
    # Reserve room for the immutable model identity and projection fingerprints.
    if len(json.dumps(geometry, ensure_ascii=False, allow_nan=False).encode()) > max_bytes - 4096:
        raise OperatorDiagramError("diagram_limit")
    return geometry
