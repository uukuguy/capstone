from __future__ import annotations

from pypsa_agent.network_view import build_pypsa_network_view


class TopologyExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def invoke(self, capability: str, arguments: dict[str, object]) -> dict[str, object]:
        self.calls.append((capability, arguments))
        assert capability == "operator.diagram"
        return {
            "model_ref": arguments["model_ref"], "coordinate_system": "geographic",
            "buses": [{"id": "north", "label": "north", "x": 10.0, "y": 20.0, "vn_kv": 220.0},
                      {"id": "south", "label": "south", "x": 11.0, "y": 21.0, "vn_kv": 220.0}],
            "branches": [
                {"id": "line:main", "kind": "line", "label": "main",
                 "from_bus": "north", "to_bus": "south"},
                {"id": "link:converter", "kind": "link", "label": "converter",
                 "from_bus": "north", "to_bus": "south"},
            ],
        }


def test_pypsa_view_uses_selected_authority_model_and_branch_kinds() -> None:
    executor = TopologyExecutor()
    view = build_pypsa_network_view(executor, "model:baseline", "regional-six-bus", 1,
                                    "regional-demand-stress", None, ())
    assert executor.calls == [("operator.diagram", {"model_ref": "model:baseline"})]
    assert view["schema"] == "capstone-network-view/2.0"
    assert view["diagram"]["model"]["revision"] == "model:baseline"
    assert {branch["id"] for branch in view["diagram"]["branches"]} == {"line:main", "link:converter"}
    assert view["diagram"]["coordinate_system"] == "geographic"
    assert view["layer"]["overlay"] is None


def test_pypsa_view_colors_only_committed_dispatch_for_matching_revision() -> None:
    dispatch = {
        "model_ref": "model:growth", "result_ref": "pypsa-result:dispatch",
        "top_line_loading": [{"line_id": "main", "max_loading_pct": 68.5}],
    }
    view = build_pypsa_network_view(TopologyExecutor(), "model:growth", "regional-six-bus", 3,
                                    "regional-demand-stress", dispatch,
                                    ("pypsa-result:dispatch",))
    assert view["layer"]["overlay"]["values"] == [{"id": "line:main", "value": 68.5}]
    assert view["layer"]["overlay"]["source_ref"] == "pypsa-result:dispatch"

    wrong_revision = build_pypsa_network_view(
        TopologyExecutor(), "model:baseline", "regional-six-bus", 3,
        "regional-demand-stress", dispatch, ("pypsa-result:dispatch",),
    )
    assert wrong_revision["layer"]["overlay"] is None

    uncommitted = build_pypsa_network_view(
        TopologyExecutor(), "model:growth", "regional-six-bus", 3,
        "regional-demand-stress", dispatch, (),
    )
    assert uncommitted["layer"]["overlay"] is None


def test_pypsa_view_anticipates_registered_link_target() -> None:
    view = build_pypsa_network_view(TopologyExecutor(), "model:baseline", "ac-dc-six-bus", 1,
                                    "ac-dc-interconnection", None, ())
    assert view["layer"]["next_focus_ids"] == ["link:converter"]
