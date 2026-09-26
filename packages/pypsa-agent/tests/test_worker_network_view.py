from __future__ import annotations

from pypsa_agent.network_view import build_pypsa_network_view


class TopologyExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def invoke(self, capability: str, arguments: dict[str, object]) -> dict[str, object]:
        self.calls.append((capability, arguments))
        assert capability == "model.topology"
        return {
            "model_ref": arguments["model_ref"], "result_ref": "pypsa-result:topology",
            "buses": [{"id": "north", "x": 10.0, "y": 20.0},
                      {"id": "south", "x": 11.0, "y": 21.0}],
            "lines": [{"id": "main", "from_bus": "north", "to_bus": "south"}],
            "links": [{"id": "converter", "from_bus": "north", "to_bus": "south"}],
            "transformers": [],
            "omitted_counts": {"buses": 0, "lines": 0, "links": 0, "transformers": 0},
            "coordinate_status": "provided-unverified",
        }


def test_pypsa_view_uses_selected_authority_model_and_branch_kinds() -> None:
    executor = TopologyExecutor()
    view = build_pypsa_network_view(executor, "model:baseline", "regional-six-bus", 1,
                                    "regional-demand-stress", None, ())
    assert executor.calls == [("model.topology", {"model_ref": "model:baseline"})]
    assert view["model"]["revision"] == "model:baseline"
    assert {branch["id"] for branch in view["branches"]} == {"line:main", "link:converter"}
    assert view["coordinate_status"] == "provided-unverified"
    assert view["overlay"] is None


def test_pypsa_view_colors_only_committed_dispatch_for_matching_revision() -> None:
    dispatch = {
        "model_ref": "model:growth", "result_ref": "pypsa-result:dispatch",
        "top_line_loading": [{"line_id": "main", "max_loading_pct": 68.5}],
    }
    view = build_pypsa_network_view(TopologyExecutor(), "model:growth", "regional-six-bus", 3,
                                    "regional-demand-stress", dispatch,
                                    ("pypsa-result:dispatch",))
    assert view["overlay"]["values"] == [{"id": "line:main", "value": 68.5}]
    assert view["overlay"]["source_ref"] == "pypsa-result:dispatch"

    wrong_revision = build_pypsa_network_view(
        TopologyExecutor(), "model:baseline", "regional-six-bus", 3,
        "regional-demand-stress", dispatch, ("pypsa-result:dispatch",),
    )
    assert wrong_revision["overlay"] is None

    uncommitted = build_pypsa_network_view(
        TopologyExecutor(), "model:growth", "regional-six-bus", 3,
        "regional-demand-stress", dispatch, (),
    )
    assert uncommitted["overlay"] is None
