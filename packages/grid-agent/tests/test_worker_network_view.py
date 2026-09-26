from __future__ import annotations

from grid_agent.network_view import build_grid_network_view


class NetworkExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def invoke(self, capability: str, arguments: dict[str, object]) -> dict[str, object]:
        self.calls.append((capability, arguments))
        assert capability == "operator.diagram.get"
        return {"context_ref": "context:one", "revision_ref": "revision:one",
                "coordinate_system": "schematic",
                "buses": [
                    {"id": "0", "label": "Bus 0", "x": 1.0, "y": 2.0, "vn_kv": 345.0},
                    {"id": "1", "label": "Bus 1", "x": 2.0, "y": 3.0, "vn_kv": 345.0},
                ],
                "branches": [{"id": "line:11", "kind": "line", "label": "Line 11",
                              "from_bus": "0", "to_bus": "1"}]}


def test_grid_view_uses_registered_dataset_endpoints_and_step_focus() -> None:
    executor = NetworkExecutor()
    view = build_grid_network_view(executor, "context:one", 1,
                                   "pandapower-scripted-task", (), ())
    assert view["diagram"]["model"] == {"id": "ieee39", "revision": "revision:one", "source": "gridctl"}
    assert view["diagram"]["branches"][0]["from_bus"] == "0"
    assert view["diagram"]["branches"][0]["to_bus"] == "1"
    assert view["layer"]["focus_ids"] == ["line:11"]
    assert view["layer"]["next_focus_ids"] == []
    assert view["layer"]["overlay"] is None
    assert executor.calls == [("operator.diagram.get", {"context_ref": "context:one"})]


def test_grid_view_colors_only_ranked_lines_from_current_committed_result() -> None:
    rank = {"capability": "result.branches.rank", "result": {
        "result_ref": "result:current", "revision_ref": "revision:one",
        "metric": "loading_percent", "branches": [
            {"element_kind": "line", "pandapower_index": 11,
             "loading_percent": 74.2},
        ],
    }}
    view = build_grid_network_view(NetworkExecutor(), "context:one", 3,
                                   "pandapower-scripted-task", ("result:current",), (rank,))
    assert view["layer"]["overlay"]["metric"] == "loading_percent"
    assert view["layer"]["overlay"]["values"] == [{"id": "line:11", "value": 74.2}]
    assert view["layer"]["overlay"]["source_ref"] == "result:current"
    assert view["layer"]["focus_ids"] == ["line:11"]

    stale = build_grid_network_view(NetworkExecutor(), "context:one", 3,
                                   "pandapower-scripted-task", (), (rank,))
    assert stale["layer"]["overlay"] is None


def test_grid_view_anticipates_registered_line_target_only_when_visible() -> None:
    view = build_grid_network_view(NetworkExecutor(), "context:one", 1,
                                   "pandapower-scripted-test", (), ())
    assert view["layer"]["next_focus_ids"] == []
