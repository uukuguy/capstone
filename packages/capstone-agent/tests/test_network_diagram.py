"""Closed operator diagram and per-turn layer admission."""

from __future__ import annotations

import copy

import pytest

from capstone_agent.network_diagram import MAX_BUSES, normalize_network_projection
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


def test_large_complete_diagram_and_worker_frame_preserve_every_component() -> None:
    raw = projection()
    raw["diagram"]["buses"] = [
        {"id": str(i), "label": f"Bus {i}", "x": None, "y": None, "vn_kv": 220}
        for i in range(9241)
    ]
    raw["diagram"]["branches"] = [
        {"id": f"line:{i}", "kind": "line", "label": f"Line {i}",
         "from_bus": str(i % 9241), "to_bus": str((i + 1) % 9241)}
        for i in range(16000)
    ]
    raw["layer"]["focus_ids"] = []
    diagram = normalize_network_projection(raw, admitted_refs=())["diagram"]
    restored = Frame.from_line(Frame("session-1", 2, "network_diagram", {"diagram": diagram}).to_line())
    assert len(restored.payload["diagram"]["buses"]) == 9241
    assert len(restored.payload["diagram"]["branches"]) == 16000
    raw["diagram"]["buses"] *= MAX_BUSES // 9241 + 1
    with pytest.raises(ValueError):
        normalize_network_projection(raw, admitted_refs=())


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


def annotated_projection() -> dict[str, object]:
    raw = projection()
    raw["layer"]["annotations"] = {
        "scene": {"label": "派生场景", "context_ref": "context:derived",
                  "model_revision": "revision:derived", "source_ref": "result:current"},
        "states": [{"label": "已断开", "style": "disconnected", "ids": ["line:11"],
                    "source_ref": "result:current"}],
        "regions": [{"label": "分区 1：无供电参考", "ids": ["1"],
                     "source_ref": "result:current"}],
    }
    return raw


def test_scene_annotations_preserve_source_and_do_not_change_geometry_identity() -> None:
    plain = normalize_network_projection(projection(), admitted_refs=())
    selected = normalize_network_projection(annotated_projection(), admitted_refs=("result:current",))
    assert selected["diagram"] == plain["diagram"]
    assert selected["layer"]["annotations"]["scene"]["model_revision"] == "revision:derived"
    assert selected["layer"]["annotations"]["states"][0]["ids"] == ["line:11"]
    assert Frame.from_line(Frame("session-1", 3, "network_layer", {
        "ordinal": 1, "layer": selected["layer"],
    }).to_line()).payload["layer"] == selected["layer"]


@pytest.mark.parametrize("mutate", [
    lambda value: value["scene"].update(source_ref="result:foreign"),
    lambda value: value["states"][0].update(ids=["foreign"]),
    lambda value: value["states"][0].update(ids=["line:11", "line:11"]),
    lambda value: value["regions"][0].update(ids=["line:11"]),
    lambda value: value["regions"][0].update(source_ref="result:foreign"),
    lambda value: value["states"][0].update(style="invented"),
])
def test_annotations_reject_foreign_sources_or_components(mutate) -> None:
    raw = annotated_projection()
    mutate(raw["layer"]["annotations"])
    with pytest.raises(ValueError):
        normalize_network_projection(raw, admitted_refs=("result:current",))
