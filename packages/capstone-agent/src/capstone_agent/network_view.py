"""Validate bounded current-run network presentation data from selected workers."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import Any


SCHEMA = "capstone-network-view/1.0"
MAX_NETWORK_VIEW_BYTES = 250_000
_BRANCH_KINDS = frozenset({"line", "link", "transformer", "trafo", "trafo3w"})
_METRICS = {"loading_percent": "%", "voltage_pu": "p.u."}


def _object(value: object, fields: set[str]) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise ValueError("network view fields are invalid")
    return value


def _text(value: object, *, limit: int = 120) -> str:
    if (not isinstance(value, str) or not value or len(value) > limit
            or any(ord(char) < 32 for char in value)):
        raise ValueError("network view text is invalid")
    return value


def _count(value: object) -> int:
    if type(value) is not int or value < 0 or value > 100_000:
        raise ValueError("network view count is invalid")
    return value


def _coordinate(value: object) -> float | None:
    if value is None:
        return None
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("network coordinate is invalid")
    return float(value)


def normalize_network_view(value: object) -> dict[str, Any]:
    """Return a closed, size-bounded projection without authority internals."""

    view = _object(value, {
        "schema", "ordinal", "model", "coordinate_status", "buses", "branches",
        "omitted", "focus_ids", "next_focus_ids", "overlay",
    })
    if view["schema"] != SCHEMA or type(view["ordinal"]) is not int or not 1 <= view["ordinal"] <= 3:
        raise ValueError("network view identity is invalid")
    model = _object(view["model"], {"id", "revision", "source"})
    selected_model = {key: _text(model[key], limit=200) for key in model}
    if view["coordinate_status"] not in {"provided-unverified", "schematic-required"}:
        raise ValueError("network coordinate status is invalid")
    if not isinstance(view["buses"], list) or not 1 <= len(view["buses"]) <= 50:
        raise ValueError("network bus count is invalid")
    if not isinstance(view["branches"], list) or len(view["branches"]) > 100:
        raise ValueError("network branch count is invalid")

    buses = []
    bus_ids: set[str] = set()
    for raw in view["buses"]:
        bus = _object(raw, {"id", "label", "x", "y"})
        identifier = _text(bus["id"])
        if identifier in bus_ids:
            raise ValueError("network bus ID is duplicated")
        bus_ids.add(identifier)
        buses.append({"id": identifier, "label": _text(bus["label"]),
                      "x": _coordinate(bus["x"]), "y": _coordinate(bus["y"])})

    branches = []
    branch_ids: set[str] = set()
    for raw in view["branches"]:
        branch = _object(raw, {"id", "kind", "label", "from_bus", "to_bus"})
        identifier = _text(branch["id"])
        kind = _text(branch["kind"])
        source = _text(branch["from_bus"])
        target = _text(branch["to_bus"])
        if (identifier in branch_ids or identifier in bus_ids or kind not in _BRANCH_KINDS
                or source not in bus_ids or target not in bus_ids):
            raise ValueError("network branch is invalid")
        branch_ids.add(identifier)
        branches.append({"id": identifier, "kind": kind, "label": _text(branch["label"]),
                         "from_bus": source, "to_bus": target})

    omitted = _object(view["omitted"], {"buses", "branches"})
    selected_omitted = {"buses": _count(omitted["buses"]),
                        "branches": _count(omitted["branches"])}
    known_ids = bus_ids | branch_ids
    def checked_focus(raw: object) -> list[str]:
        if (not isinstance(raw, list) or len(raw) > 20
                or any(not isinstance(item, str) or item not in known_ids for item in raw)
                or len(raw) != len(set(raw))):
            raise ValueError("network focus IDs are invalid")
        return list(raw)

    focus = checked_focus(view["focus_ids"])
    next_focus = checked_focus(view["next_focus_ids"])

    overlay = None
    if view["overlay"] is not None:
        raw_overlay = _object(view["overlay"], {"metric", "unit", "source_ref", "values"})
        metric = _text(raw_overlay["metric"])
        if metric not in _METRICS or raw_overlay["unit"] != _METRICS[metric]:
            raise ValueError("network overlay metric is invalid")
        values = raw_overlay["values"]
        if not isinstance(values, list) or not 1 <= len(values) <= 100:
            raise ValueError("network overlay values are invalid")
        allowed = bus_ids if metric == "voltage_pu" else branch_ids
        selected_values = []
        seen: set[str] = set()
        for raw in values:
            item = _object(raw, {"id", "value"})
            identifier = _text(item["id"])
            number = item["value"]
            if (identifier not in allowed or identifier in seen
                    or type(number) not in (int, float) or not math.isfinite(number)):
                raise ValueError("network overlay element is invalid")
            seen.add(identifier)
            selected_values.append({"id": identifier, "value": float(number)})
        overlay = {"metric": metric, "unit": _METRICS[metric],
                   "source_ref": _text(raw_overlay["source_ref"], limit=2048),
                   "values": selected_values}

    normalized = {
        "schema": SCHEMA, "ordinal": view["ordinal"], "model": selected_model,
        "coordinate_status": view["coordinate_status"],
        "buses": buses, "branches": branches, "omitted": selected_omitted,
        "focus_ids": focus, "next_focus_ids": next_focus, "overlay": overlay,
    }
    if len(json.dumps(normalized, ensure_ascii=False, allow_nan=False).encode("utf-8")) > MAX_NETWORK_VIEW_BYTES:
        raise ValueError("network view exceeds size limit")
    return normalized
