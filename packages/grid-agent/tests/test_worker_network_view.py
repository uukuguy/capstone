from __future__ import annotations

from grid_agent.network_view import build_grid_network_view


class NetworkExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def invoke(self, capability: str, arguments: dict[str, object]) -> dict[str, object]:
        self.calls.append((capability, arguments))
        assert capability == "model.dataset.query"
        dataset = arguments["dataset"]
        rows = ([{"index": 0, "name": "Bus 0"}, {"index": 1, "name": "Bus 1"}]
                if dataset == "network.buses" else [{
                    "index": 11, "kind": "line", "name": "Line 11",
                    "from_bus_index": 0, "to_bus_index": 1,
                }])
        return {"context_ref": "context:one", "revision_ref": "revision:one",
                "dataset": dataset, "row_count": len(rows), "rows": rows,
                "next_offset": None}


def test_grid_view_uses_registered_dataset_endpoints_and_step_focus() -> None:
    executor = NetworkExecutor()
    view = build_grid_network_view(executor, "context:one", 1,
                                   "pandapower-scripted-task", (), ())
    assert view["model"] == {"id": "ieee39", "revision": "revision:one", "source": "gridctl"}
    assert view["branches"][0]["from_bus"] == "0"
    assert view["branches"][0]["to_bus"] == "1"
    assert view["focus_ids"] == ["line:11"]
    assert view["overlay"] is None
    assert [item[1]["dataset"] for item in executor.calls] == [
        "network.buses", "network.branches",
    ]


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
    assert view["overlay"]["metric"] == "loading_percent"
    assert view["overlay"]["values"] == [{"id": "line:11", "value": 74.2}]
    assert view["overlay"]["source_ref"] == "result:current"
    assert view["focus_ids"] == ["line:11"]

    stale = build_grid_network_view(NetworkExecutor(), "context:one", 3,
                                   "pandapower-scripted-task", (), (rank,))
    assert stale["overlay"] is None
