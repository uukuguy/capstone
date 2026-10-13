import pytest

from pandapower_domain.network_annotations import project_scene_annotations, select_contingency_scene


def sources():
    diagram = {"buses": [{"id": "0"}, {"id": "1"}], "branches": [{"id": "line:4"}]}
    result = {"context_ref": "context:derived", "revision_ref": "revision:derived",
              "datasets": {"result.res_bus": {"rows": [{"index": 0, "vm_pu": 1.01}, {"index": 1, "vm_pu": None}]}}}
    topology = {"context_ref": "context:derived", "revision_ref": "revision:derived",
                "components": [{"bus_indices": [0], "bus_list_complete": True, "bus_count": 1,
                                "supply_reference_bus_indices": [0]},
                               {"bus_indices": [1], "bus_list_complete": True, "bus_count": 1,
                                "supply_reference_bus_indices": []}]}
    lines = {"context_ref": "context:derived", "revision_ref": "revision:derived",
             "rows": [{"index": 4, "in_service": False}]}
    return diagram, result, topology, lines


def test_scene_distinguishes_disconnection_no_reference_and_unsolved_values():
    value = project_scene_annotations(*sources(), source_ref="result:current")
    assert value["scene"]["model_revision"] == "revision:derived"
    assert value["states"] == [
        {"label": "已断开", "style": "disconnected", "ids": ["line:4"], "source_ref": "result:current"},
        {"label": "电压未求解", "style": "unresolved", "ids": ["1"], "source_ref": "result:current"},
    ]
    assert value["regions"][1]["label"] == "分区 2：无供电参考"
    assert value["regions"][1]["emphasis"] is True
    assert value["regions"][0]["emphasis"] is False
    assert "失电" not in str(value)


def test_foreign_context_and_incomplete_topology_cannot_create_scene_membership():
    diagram, result, topology, lines = sources()
    topology["context_ref"] = "context:foreign"
    with pytest.raises(ValueError):
        project_scene_annotations(diagram, result, topology, lines, source_ref="result:current")
    topology["context_ref"] = "context:derived"
    topology["components"][1]["bus_list_complete"] = False
    value = project_scene_annotations(diagram, result, topology, lines, source_ref="result:current")
    assert len(value["regions"]) == 1


def test_contingency_outage_uses_recorded_scenario_not_base_operating_state():
    diagram, result, topology, lines = sources()
    result["outage"] = {"kind": "line", "index": 4}
    lines["rows"][0]["in_service"] = True
    value = project_scene_annotations(diagram, result, topology, lines, source_ref="result:scenario")
    assert value["states"][0]["ids"] == ["line:4"]
    assert value["regions"] == []


def test_overload_marker_uses_solved_loading_not_null_or_outaged_rows():
    diagram, result, topology, lines = sources()
    lines["rows"][0]["in_service"] = True
    result["datasets"]["result.res_line"] = {"rows": [{"index": 4, "loading_percent": 112.5}]}
    value = project_scene_annotations(diagram, result, topology, lines, source_ref="result:current")
    assert value["states"][0]["label"] == "负载率超过 100%"
    result["datasets"]["result.res_line"]["rows"][0]["loading_percent"] = None
    value = project_scene_annotations(diagram, result, topology, lines, source_ref="result:current")
    assert all(item["style"] != "warning" for item in value["states"])


def test_open_terminal_switch_is_explicit_and_not_a_normal_connection():
    diagram, result, topology, lines = sources()
    lines["rows"] = []
    lines["branch_states"] = [{"id": "line:4", "in_service": True, "connected": False,
                              "open_switches": [{"index": 9, "bus_id": "1"}]}]
    value = project_scene_annotations(diagram, result, topology, lines, source_ref="result:current")
    state = value["states"][0]
    assert state["label"] == "开关断开"
    assert state["ids"] == ["line:4"]
    assert state["markers"] == [{"id": "line:4", "bus_id": "1", "label": "开关 9"}]


def test_contingency_selection_uses_actual_reported_loading_and_preserves_parent_source():
    roots = [("result:parent", {"scenarios": [
        {"scenario_result_ref": "result:low", "status": "succeeded", "max_loading_percent": 97.0},
        {"scenario_result_ref": "result:high", "status": "succeeded", "max_loading_percent": 143.0},
        {"scenario_result_ref": "result:failed", "status": "failed", "max_loading_percent": None},
    ]})]
    assert select_contingency_scene(roots) == ("result:parent", "result:high")
    assert select_contingency_scene([("result:ordinary", {"datasets": {}})]) is None
