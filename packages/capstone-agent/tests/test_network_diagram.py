"""Closed operator diagram and per-turn layer admission."""

from __future__ import annotations

import copy

import pytest

from capstone_agent.network_diagram import normalize_network_projection
from capstone_agent.protocol import Frame


def projection(ordinal: int = 1) -> dict[str, object]:
    return {
        "schema": "capstone-network-view/2.0", "ordinal": ordinal,
        "diagram": {
            "schema": "capstone-network-diagram/1.0",
            "model": {"id": "ieee39", "revision": "revision:one", "source": "gridctl"},
            "coordinate_system": "schematic",
            "buses": [
                {"id": "0", "label": "Bus 0", "x": 1.0, "y": 2.0, "vn_kv": 345.0},
                {"id": "1", "label": "Bus 1", "x": 2.0, "y": 3.0, "vn_kv": 345.0},
            ],
            "branches": [{"id": "line:11", "kind": "line", "label": "Line 11",
                          "from_bus": "0", "to_bus": "1"}],
        },
        "layer": {"focus_ids": ["line:11"], "next_focus_ids": [], "overlay": None},
    }


def test_projection_normalizes_fingerprint_and_separate_frames() -> None:
    normalized = normalize_network_projection(projection(), admitted_refs=())
    diagram = normalized["diagram"]
    layer = normalized["layer"]
    assert diagram["fingerprint"].startswith("topology:sha256:")
    assert diagram["ref"].startswith("diagram:sha256:")
    assert layer["diagram_ref"] == diagram["ref"]
    assert layer["model_revision"] == "revision:one"
    assert Frame.from_line(Frame("session-1", 2, "network_diagram", {
        "diagram": diagram,
    }).to_line()).payload["diagram"] == diagram
    assert Frame.from_line(Frame("session-1", 3, "network_layer", {
        "ordinal": 1, "layer": layer,
    }).to_line()).payload["layer"] == layer


@pytest.mark.parametrize("mutate", [
    lambda view: view["diagram"]["buses"].append(dict(view["diagram"]["buses"][0])),
    lambda view: view["diagram"]["branches"][0].update(to_bus="missing"),
    lambda view: view["diagram"]["buses"][0].update(x=float("nan")),
    lambda view: view["layer"].update(focus_ids=["foreign"]),
    lambda view: view["layer"].update(overlay={"metric": "loading_percent", "unit": "%",
        "source_ref": "result:foreign", "values": [{"id": "line:11", "value": 72.0}]}),
])
def test_projection_rejects_invalid_topology_or_unadmitted_values(mutate) -> None:
    raw = copy.deepcopy(projection())
    mutate(raw)
    with pytest.raises(ValueError):
        normalize_network_projection(raw, admitted_refs=())


def test_projection_accepts_only_current_step_line_result() -> None:
    raw = projection(3)
    raw["layer"]["overlay"] = {"metric": "loading_percent", "unit": "%",
        "source_ref": "result:current", "values": [{"id": "line:11", "value": 72.0}]}
    selected = normalize_network_projection(raw, admitted_refs=("result:current",))
    assert selected["layer"]["overlay"]["values"] == [{"id": "line:11", "value": 72.0}]
    assert selected["layer"]["ordinal"] == 3
