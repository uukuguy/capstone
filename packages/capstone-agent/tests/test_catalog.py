from __future__ import annotations

from pathlib import Path

from capstone_agent.catalog import build_catalog
from capstone_agent.registry import build_registry


ROOT = Path(__file__).resolve().parents[3]


def test_catalog_lists_only_registered_runnable_three_turn_cases() -> None:
    catalog = build_catalog(build_registry(ROOT), ROOT)
    assert catalog["schema"] == "capstone-catalog/1.0"
    by_id = {app["application_id"]: app for app in catalog["applications"]}
    assert set(by_id) == {"pandapower-static-analysis", "pypsa-business-cases"}
    grid = {case["case_id"]: case for case in by_id["pandapower-static-analysis"]["cases"]}
    pypsa = {case["case_id"]: case for case in by_id["pypsa-business-cases"]["cases"]}
    assert set(grid) == {"pandapower-scripted-task", "pandapower-scripted-test"}
    assert set(pypsa) == {"regional-demand-stress", "scigrid-dispatch", "ac-dc-interconnection"}
    assert all(len(case["instructions"]) == 3 for case in [*grid.values(), *pypsa.values()])
    assert all(case["interpretation_boundary"] for case in [*grid.values(), *pypsa.values()])
    assert grid["pandapower-scripted-task"]["instructions"][0] == (
        "打开 IEEE-39 网络并解析线路 11 的端点。"
    )
