from __future__ import annotations

from collections.abc import Mapping

from grid_agent.network_story import build_grid_story


class NetworkExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def invoke(self, capability: str, arguments: dict[str, object]) -> dict[str, object]:
        self.calls.append((capability, arguments))
        assert capability == "operator.diagram.get"
        return {
            "context_ref": arguments["context_ref"],
            "revision_ref": "revision:one",
            "coordinate_system": "schematic",
            "buses": [
                {"id": "0", "label": "Bus 0", "x": 1.0, "y": 2.0, "vn_kv": 345.0},
                {"id": "1", "label": "Bus 1", "x": 2.0, "y": 3.0, "vn_kv": 345.0},
            ],
            "branches": [
                {"id": "line:11", "kind": "line", "label": "Line 11",
                 "from_bus": "0", "to_bus": "1"},
                {"id": "line:17", "kind": "line", "label": "Line 17",
                 "from_bus": "1", "to_bus": "0"},
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
        {"ordinal": 1, "result_refs": (), "calls": ()},
        {"ordinal": 2, "result_refs": (), "calls": ()},
        {
            "ordinal": 3,
            "result_refs": ("result:step-3",),
            "calls": (
                {
                    "capability": "result.branches.rank",
                    "result": {
                        "result_ref": "result:step-3",
                        "revision_ref": "revision:one",
                        "metric": "loading_percent",
                        "branches": [
                            {"element_kind": "line", "pandapower_index": 11,
                             "loading_percent": 83.2},
                            {"element_kind": "line", "pandapower_index": 17,
                             "loading_percent": 71.4},
                        ],
                    },
                },
            ),
        },
    )


def test_grid_story_fallback_reproduces_authority_ranked_final_focus() -> None:
    story = build_grid_story(
        executor=NetworkExecutor(),
        context_ref="context:one",
        case_id="pandapower-scripted-task",
        completed_steps=_steps(),
        planner=None,
    )

    final = story["steps"][2]
    assert final["current_focus_ids"] == ["line:11", "line:17"]
    assert final["overlay"]["values"] == [
        {"id": "line:11", "value": 83.2},
        {"id": "line:17", "value": 71.4},
    ]
    assert final["overlay"]["source_ref"] == "result:step-3"
    assert story["plan_source"] == "fallback"


def test_grid_story_planner_can_change_focus_but_not_authority_values() -> None:
    planner = StaticPlanner({
        "plan_source": "llm",
        "steps": [{
            "ordinal": 3,
            "focus_candidate_keys": ["c2"],
            "primary_candidate_key": "c2",
            "presentation": "highlight",
        }],
    })
    story = build_grid_story(
        executor=NetworkExecutor(),
        context_ref="context:one",
        case_id="pandapower-scripted-task",
        completed_steps=_steps(),
        planner=planner,
    )

    final = story["steps"][2]
    assert final["current_focus_ids"] == ["line:17"]
    assert final["overlay"]["values"][0]["value"] == 83.2
    assert final["overlay"]["source_ref"] == "result:step-3"
    request = planner.requests[0]
    candidates = request["steps"][2]["candidates"]
    assert all("value" not in candidate and "source_ref" not in candidate
               for candidate in candidates)


def test_grid_story_invalid_planner_selection_uses_fallback() -> None:
    story = build_grid_story(
        executor=NetworkExecutor(),
        context_ref="context:one",
        case_id="pandapower-scripted-task",
        completed_steps=_steps(),
        planner=StaticPlanner({
            "plan_source": "llm",
            "steps": [{"ordinal": 3, "focus_candidate_keys": ["unknown"]}],
        }),
    )

    assert story["plan_source"] == "fallback"
    assert story["steps"][2]["current_focus_ids"] == ["line:11", "line:17"]


def test_grid_story_does_not_promote_next_step_focus_into_an_earlier_snapshot() -> None:
    story = build_grid_story(
        executor=NetworkExecutor(),
        context_ref="context:one",
        case_id="pandapower-scripted-test",
        completed_steps=_steps(),
        planner=None,
    )

    assert story["steps"][0]["current_focus_ids"] == []
    assert story["steps"][1]["current_focus_ids"] == ["line:17"]
    assert story["steps"][2]["current_focus_ids"] == ["line:17"]
