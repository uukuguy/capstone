"""Closed operator diagram and step layer projection."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from collections.abc import Mapping
from typing import Any


MAX_DIAGRAM_BYTES = 4 * 1024 * 1024
MAX_BUSES = 10_000
MAX_BRANCHES = 20_000
# One complete diagram plus bounded event and page envelopes.
MAX_EVENT_PAGE_BYTES = MAX_DIAGRAM_BYTES + 64 * 1024
MAX_THREAD_JSON_BYTES = MAX_EVENT_PAGE_BYTES + 64 * 1024
_KINDS = frozenset({"line", "link", "transformer", "trafo", "trafo3w"})
_METRICS = {"loading_percent": "%", "voltage_pu": "p.u."}


def _record(value: object, keys: set[str]) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ValueError("network diagram fields are invalid")
    return value


def _text(value: object, limit: int = 200) -> str:
    if (not isinstance(value, str) or not value or len(value) > limit
            or any(ord(char) < 32 for char in value)):
        raise ValueError("network diagram text is invalid")
    return value


def _number(value: object, *, nullable: bool = False) -> float | None:
    if nullable and value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError("network diagram number is invalid")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("network diagram number is invalid")
    return number


def _digest(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, allow_nan=False,
                         sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def normalize_network_diagram(value: object) -> dict[str, Any]:
    """Validate one scalar authority diagram and derive stable geometry identity."""
    if not isinstance(value, Mapping):
        raise ValueError("network diagram is invalid")
    published = "fingerprint" in value or "ref" in value
    expected = {"schema", "model", "coordinate_system", "buses", "branches"}
    source = _record(value, expected | ({"fingerprint", "ref"} if published else set()))
    if source["schema"] != "capstone-network-diagram/1.0":
        raise ValueError("network diagram schema is invalid")
    model = _record(source["model"], {"id", "revision", "source"})
    normalized_model = {key: _text(model[key], 2048 if key == "revision" else 200)
                        for key in ("id", "revision", "source")}
    coordinate_system = source["coordinate_system"]
    if coordinate_system not in {"geographic", "schematic"}:
        raise ValueError("network coordinate system is invalid")
    raw_buses = source["buses"]
    raw_branches = source["branches"]
    if (not isinstance(raw_buses, list) or not 1 <= len(raw_buses) <= MAX_BUSES
            or not isinstance(raw_branches, list) or len(raw_branches) > MAX_BRANCHES):
        raise ValueError("network diagram component count is invalid")
    buses = []
    bus_ids: set[str] = set()
    for raw in raw_buses:
        bus = _record(raw, {"id", "label", "x", "y", "vn_kv"})
        identifier = _text(bus["id"])
        if identifier in bus_ids:
            raise ValueError("network bus ID is duplicated")
        bus_ids.add(identifier)
        x = _number(bus["x"], nullable=True)
        y = _number(bus["y"], nullable=True)
        nominal = _number(bus["vn_kv"], nullable=True)
        if (x is None) != (y is None) or (nominal is not None and nominal < 0):
            raise ValueError("network bus coordinate or voltage is invalid")
        if coordinate_system == "geographic" and (
            x is None or y is None or not -180 <= x <= 180 or not -90 <= y <= 90
        ):
            raise ValueError("geographic network bus is invalid")
        buses.append({"id": identifier, "label": _text(bus["label"]),
                      "x": x, "y": y, "vn_kv": nominal})
    branches = []
    branch_ids: set[str] = set()
    for raw in raw_branches:
        branch = _record(raw, {"id", "kind", "label", "from_bus", "to_bus"})
        identifier = _text(branch["id"])
        kind = _text(branch["kind"])
        source_id = _text(branch["from_bus"])
        target_id = _text(branch["to_bus"])
        if (identifier in branch_ids or identifier in bus_ids or kind not in _KINDS
                or source_id not in bus_ids or target_id not in bus_ids):
            raise ValueError("network branch is invalid")
        branch_ids.add(identifier)
        branches.append({"id": identifier, "kind": kind, "label": _text(branch["label"]),
                         "from_bus": source_id, "to_bus": target_id})
    geometry = {"coordinate_system": coordinate_system, "buses": buses, "branches": branches}
    fingerprint = "topology:sha256:" + _digest(geometry)
    reference = "diagram:sha256:" + _digest([normalized_model, fingerprint])
    normalized = {
        "schema": "capstone-network-diagram/1.0", "model": normalized_model,
        **geometry, "fingerprint": fingerprint, "ref": reference,
    }
    if published and (source["fingerprint"] != fingerprint or source["ref"] != reference):
        raise ValueError("network diagram identity is invalid")
    if len(json.dumps(normalized, ensure_ascii=False, allow_nan=False).encode("utf-8")) > MAX_DIAGRAM_BYTES:
        raise ValueError("network diagram exceeds size limit")
    return normalized


def normalize_network_layer(
    value: object, diagram: Mapping[str, Any], ordinal: int, *,
    admitted_refs: Sequence[str] | None,
) -> dict[str, Any]:
    if type(ordinal) is not int or not 1 <= ordinal <= 3:
        raise ValueError("network layer ordinal is invalid")
    if not isinstance(value, Mapping):
        raise ValueError("network layer is invalid")
    published = "schema" in value
    required = {"focus_ids", "next_focus_ids", "overlay"}
    source = _record(value, required | (
        {"schema", "ordinal", "diagram_ref", "model_revision"} if published else set()
    ))
    if published and (
        source["schema"] != "capstone-network-layer/1.0" or source["ordinal"] != ordinal
        or source["diagram_ref"] != diagram["ref"]
        or source["model_revision"] != diagram["model"]["revision"]
    ):
        raise ValueError("network layer identity is invalid")
    buses = {bus["id"] for bus in diagram["buses"]}
    branches = {branch["id"] for branch in diagram["branches"]}
    lines = {branch["id"] for branch in diagram["branches"] if branch["kind"] == "line"}
    ids = buses | branches

    def focus(key: str) -> list[str]:
        raw = source[key]
        if (not isinstance(raw, list) or len(raw) > 20
                or any(not isinstance(item, str) or item not in ids for item in raw)
                or len(raw) != len(set(raw))):
            raise ValueError("network focus IDs are invalid")
        return list(raw)

    overlay = None
    if source["overlay"] is not None:
        raw = _record(source["overlay"], {"metric", "unit", "source_ref", "values"})
        metric = _text(raw["metric"])
        reference = _text(raw["source_ref"], 2048)
        if (metric not in _METRICS or raw["unit"] != _METRICS[metric]
                or admitted_refs is not None and reference not in admitted_refs):
            raise ValueError("network overlay reference or metric is invalid")
        values = raw["values"]
        if not isinstance(values, list) or not 1 <= len(values) <= MAX_BRANCHES:
            raise ValueError("network overlay count is invalid")
        allowed = buses if metric == "voltage_pu" else lines
        seen: set[str] = set()
        selected = []
        for item in values:
            entry = _record(item, {"id", "value"})
            identifier = _text(entry["id"])
            number = _number(entry["value"])
            if identifier not in allowed or identifier in seen:
                raise ValueError("network overlay element is invalid")
            seen.add(identifier)
            selected.append({"id": identifier, "value": number})
        overlay = {"metric": metric, "unit": _METRICS[metric],
                   "source_ref": reference, "values": selected}
    return {
        "schema": "capstone-network-layer/1.0", "ordinal": ordinal,
        "diagram_ref": diagram["ref"], "model_revision": diagram["model"]["revision"],
        "focus_ids": focus("focus_ids"), "next_focus_ids": focus("next_focus_ids"),
        "overlay": overlay,
    }


def normalize_network_projection(value: object, *, admitted_refs: Sequence[str]) -> dict[str, Any]:
    view = _record(value, {"schema", "ordinal", "diagram", "layer"})
    if view["schema"] != "capstone-network-view/2.0":
        raise ValueError("network projection schema is invalid")
    ordinal = view["ordinal"]
    if type(ordinal) is not int:
        raise ValueError("network layer ordinal is invalid")
    diagram = normalize_network_diagram(view["diagram"])
    layer = normalize_network_layer(view["layer"], diagram, ordinal,
                                    admitted_refs=admitted_refs)
    return {"schema": "capstone-network-view/2.0", "ordinal": ordinal,
            "diagram": diagram, "layer": layer}
