from __future__ import annotations

import pytest

from capstone_agent.network_view import normalize_network_view
from capstone_agent.protocol import Frame


def _view() -> dict[str, object]:
    return {
        "schema": "capstone-network-view/1.0", "ordinal": 1,
        "model": {"id": "ieee39", "revision": "revision:one", "source": "gridctl"},
        "coordinate_status": "schematic-required",
        "buses": [
            {"id": "0", "label": "Bus 0", "x": None, "y": None},
            {"id": "1", "label": "Bus 1", "x": None, "y": None},
        ],
        "branches": [{"id": "line:11", "kind": "line", "label": "Line 11",
                      "from_bus": "0", "to_bus": "1"}],
        "omitted": {"buses": 0, "branches": 0},
        "focus_ids": ["line:11"], "next_focus_ids": ["line:11"], "overlay": None,
    }


def test_network_view_accepts_bounded_topology_and_frame() -> None:
    view = normalize_network_view(_view())
    frame = Frame("session-1", 2, "network_view", {"ordinal": 1, "view": view})
    assert Frame.from_line(frame.to_line()) == frame


@pytest.mark.parametrize("change", [
    lambda view: view["branches"][0].update(to_bus="9"),
    lambda view: view["buses"].append(dict(view["buses"][0])),
    lambda view: view["buses"][0].update(x=float("nan")),
    lambda view: view.update(focus_ids=["foreign"]),
    lambda view: view.update(next_focus_ids=["foreign"]),
    lambda view: view.update(overlay={"metric": "loading_percent", "unit": "%",
        "source_ref": "result:current", "values": [{"id": "foreign", "value": 72.0}]}),
    lambda view: (view["branches"][0].update(kind="link"),
        view.update(overlay={"metric": "loading_percent", "unit": "%",
            "source_ref": "result:current", "values": [{"id": "line:11", "value": 72.0}]})),
])
def test_network_view_rejects_unverifiable_elements(change) -> None:
    view = _view()
    change(view)
    with pytest.raises(ValueError):
        normalize_network_view(view)
