from __future__ import annotations

import pytest

from capstone_agent.network_story import (
    build_cumulative_story,
    normalize_network_story,
)


def diagram() -> dict[str, object]:
    return {
        "schema": "capstone-network-diagram/1.0",
        "model": {"id": "demo", "revision": "r1", "source": "test"},
        "coordinate_system": "schematic",
        "buses": [
            {"id": "bus:1", "label": "1", "x": 0, "y": 0, "vn_kv": 110},
            {"id": "bus:2", "label": "2", "x": 1, "y": 0, "vn_kv": 110},
            {"id": "bus:3", "label": "3", "x": 2, "y": 0, "vn_kv": 110},
        ],
        "branches": [
            {"id": "line:1", "kind": "line", "label": "1", "from_bus": "bus:1", "to_bus": "bus:2"},
            {"id": "line:2", "kind": "line", "label": "2", "from_bus": "bus:2", "to_bus": "bus:3"},
        ],
    }


def steps() -> list[dict[str, object]]:
    return [
        {"ordinal": 1, "candidate_keys": {"c1": "line:1"}, "overlay": {"metric": "loading_percent", "unit": "%", "source_ref": "result:step-1", "values": [{"id": "line:1", "value": 80.0}]}},
        {"ordinal": 2, "candidate_keys": {"c1": "bus:2"}, "overlay": {"metric": "voltage_pu", "unit": "p.u.", "source_ref": "result:step-2", "values": [{"id": "bus:2", "value": 1.01}]}},
        {"ordinal": 3, "candidate_keys": {"c1": "line:2"}, "overlay": None},
    ]


def test_story_keeps_one_diagram_and_accumulates_prior_focus() -> None:
    story = build_cumulative_story(
        diagram(), steps(),
        {"plan_source": "llm", "steps": [
            {"ordinal": 1, "focus_candidate_keys": ["c1"]},
            {"ordinal": 2, "focus_candidate_keys": ["c1"]},
            {"ordinal": 3, "focus_candidate_keys": ["c1"]},
        ]},
    )
    assert story["schema"] == "capstone-network-story/1.0"
    assert story["diagram"]["ref"] == story["steps"][1]["diagram_ref"]
    assert story["steps"][1]["current_focus_ids"] == ["bus:2"]
    assert story["steps"][1]["history_focus_ids"] == ["line:1"]


def test_story_rejects_foreign_overlay_reference() -> None:
    story = build_cumulative_story(diagram(), steps(), None)
    story["steps"][0]["overlay"]["source_ref"] = "result:foreign"
    with pytest.raises(ValueError, match="admitted"):
        normalize_network_story(story, admitted_refs_by_ordinal={1: ("result:step-1",)})


def test_story_drops_unknown_plan_key_and_uses_fallback() -> None:
    story = build_cumulative_story(
        diagram(), steps(),
        {"plan_source": "llm", "steps": [{"ordinal": 1, "focus_candidate_keys": ["unknown"]}]},
    )
    assert story["plan_source"] == "fallback"
    assert story["steps"][0]["current_focus_ids"] == ["line:1"]


def test_story_does_not_take_values_or_references_from_plan() -> None:
    story = build_cumulative_story(
        diagram(), steps(),
        {"plan_source": "llm", "steps": [{
            "ordinal": 1, "focus_candidate_keys": ["c1"],
            "overlay": {"source_ref": "result:foreign", "values": [{"id": "line:2", "value": 999}]},
        }]},
    )
    assert story["steps"][0]["overlay"]["source_ref"] == "result:step-1"
    assert story["steps"][0]["overlay"]["values"] == [{"id": "line:1", "value": 80.0}]


def test_story_does_not_carry_an_incompatible_overlay_metric() -> None:
    inputs = steps()
    inputs[2]["overlay_metric"] = "loading_percent"
    story = build_cumulative_story(diagram(), inputs, None)
    assert story["steps"][2]["overlay"] is None
