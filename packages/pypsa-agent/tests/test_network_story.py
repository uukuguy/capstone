from __future__ import annotations

from collections.abc import Mapping

from pypsa_agent.network_story import build_pypsa_story


class TopologyExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def invoke(self, capability: str, arguments: dict[str, object]) -> dict[str, object]:
        self.calls.append((capability, arguments))
        assert capability == "operator.diagram"
        return {
            "model_ref": arguments["model_ref"],
            "coordinate_system": "geographic",
            "buses": [
                {"id": "north", "label": "north", "x": 10.0, "y": 20.0, "vn_kv": 220.0},
                {"id": "south", "label": "south", "x": 11.0, "y": 21.0, "vn_kv": 220.0},
            ],
            "branches": [
                {"id": "line:main", "kind": "line", "label": "main",
                 "from_bus": "north", "to_bus": "south"},
                {"id": "line:aux", "kind": "line", "label": "aux",
                 "from_bus": "south", "to_bus": "north"},
                {"id": "link:converter", "kind": "link", "label": "converter",
                 "from_bus": "north", "to_bus": "south"},
            ],
        }


class StaticPlanner:
    def __init__(self, value: Mapping[str, object]) -> None:
        self.value = value
        self.requests: list[Mapping[str, object]] = []

    def plan(self, request: Mapping[str, object]) -> Mapping[str, object]:
        self.requests.append(request)
        return self.value


def _steps() -> tuple[dict[str, object], ...]:
    return (
        {"ordinal": 1, "result_refs": (), "dispatch": None},
        {"ordinal": 2, "result_refs": (), "dispatch": None},
        {
            "ordinal": 3,
            "result_refs": ("pypsa-result:dispatch",),
            "dispatch": {
                "model_ref": "model:baseline",
                "result_ref": "pypsa-result:dispatch",
                "top_line_loading": [
                    {"line_id": "main", "max_loading_pct": 68.5},
                    {"line_id": "aux", "max_loading_pct": 42.1},
                ],
            },
        },
    )


def test_pypsa_story_fallback_uses_authority_ranked_final_focus() -> None:
    story = build_pypsa_story(
        executor=TopologyExecutor(),
        model_ref="model:baseline",
        model_id="regional-six-bus",
        case_id="regional-demand-stress",
        completed_steps=_steps(),
        planner=None,
    )

    final = story["steps"][2]
    assert final["current_focus_ids"] == ["line:main", "line:aux"]
    assert final["overlay"]["values"] == [
        {"id": "line:main", "value": 68.5},
        {"id": "line:aux", "value": 42.1},
    ]
    assert final["overlay"]["source_ref"] == "pypsa-result:dispatch"
    assert story["plan_source"] == "fallback"


def test_pypsa_story_planner_can_change_focus_but_not_authority_values() -> None:
    planner = StaticPlanner({
        "plan_source": "llm",
        "steps": [{
            "ordinal": 3,
            "focus_candidate_keys": ["c2"],
            "primary_candidate_key": "c2",
            "presentation": "highlight",
        }],
    })
    story = build_pypsa_story(
        executor=TopologyExecutor(),
        model_ref="model:baseline",
        model_id="regional-six-bus",
        case_id="regional-demand-stress",
        completed_steps=_steps(),
        planner=planner,
    )

    final = story["steps"][2]
    assert final["current_focus_ids"] == ["line:aux"]
    assert final["overlay"]["values"][0]["value"] == 68.5
    assert final["overlay"]["source_ref"] == "pypsa-result:dispatch"
    assert all("value" not in candidate and "source_ref" not in candidate
               for candidate in planner.requests[0]["steps"][2]["candidates"])


def test_pypsa_story_invalid_planner_selection_uses_fallback() -> None:
    story = build_pypsa_story(
        executor=TopologyExecutor(),
        model_ref="model:baseline",
        model_id="regional-six-bus",
        case_id="regional-demand-stress",
        completed_steps=_steps(),
        planner=StaticPlanner({
            "plan_source": "llm",
            "steps": [{"ordinal": 3, "focus_candidate_keys": ["unknown"]}],
        }),
    )

    assert story["plan_source"] == "fallback"
    assert story["steps"][2]["current_focus_ids"] == ["line:main", "line:aux"]
