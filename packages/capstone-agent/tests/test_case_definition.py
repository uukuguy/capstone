from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from typing import cast

import pytest

from capstone_agent.case_definition import CaseCatalog


def registered_catalog_fixture() -> dict[str, object]:
    return {
        "schema": "capstone-catalog/1.0",
        "applications": [
            {
                "application_id": "pandapower-static-analysis",
                "title": "pandapower 电网静态分析",
                "cases": [
                    {
                        "case_id": "pandapower-scripted-task",
                        "title": "IEEE-39 潮流与线路筛查",
                        "summary": "在登记网络内打开模型、求解交流潮流并筛查线路。",
                        "model_origin": "IEEE-39",
                        "model_ids": ["ieee39"],
                        "case_version": "1",
                        "step_titles": ["打开与解析拓扑", "执行交流潮流", "筛查线路负载率"],
                        "instructions": [
                            "打开 IEEE-39 网络并解析线路 11 的端点。",
                            "沿用已打开的网络执行一次交流潮流。",
                            "沿用当前潮流结果列出负载率最高的三条线路。",
                        ],
                    }
                ],
            },
            {
                "application_id": "pypsa-business-cases",
                "title": "PyPSA 业务案例",
                "cases": [
                    {
                        "case_id": "scigrid-dispatch",
                        "title": "德国输电网日内调度概览",
                        "summary": "对登记网络执行固定容量线性调度。",
                        "model_origin": "pypsa-example/scigrid_de",
                        "model_ids": ["pypsa-example/scigrid_de"],
                        "case_version": "1",
                        "step_titles": ["打开登记模型", "查看受限拓扑", "执行固定容量调度"],
                        "instructions": [
                            "打开已登记的 SciGRID-DE 示例网络，核对来源、快照和主要组件。",
                            "基于刚才的网络查看受限拓扑，说明预览范围。",
                            "执行各时段固定容量线性调度，报告求解状态和线路筛查结果。",
                        ],
                    }
                ],
            },
        ],
    }


def test_catalog_freezes_registered_case() -> None:
    catalog = CaseCatalog.from_registered_catalog(registered_catalog_fixture())

    case = catalog.get("pandapower-scripted-task")

    assert case.case_version == "1"
    assert case.display_name == "IEEE-39 潮流与线路筛查"
    assert case.model_ids == ("ieee39",)
    assert [step.ordinal for step in case.steps] == [1, 2, 3]
    assert [step.title for step in case.steps] == [
        "打开与解析拓扑",
        "执行交流潮流",
        "筛查线路负载率",
    ]
    assert case.case_revision.startswith("case:sha256:")


def test_catalog_parses_pypsa_registration_and_stable_digests() -> None:
    document = registered_catalog_fixture()
    first = CaseCatalog.from_registered_catalog(document).get("scigrid-dispatch")
    second = CaseCatalog.from_registered_catalog(deepcopy(document)).get("scigrid-dispatch")

    assert first == second
    assert first.steps[0].instruction_digest == sha256(
        first.steps[0].instruction.encode("utf-8")
    ).hexdigest()
    assert len({step.instruction_digest for step in first.steps}) == 3


def test_catalog_rejects_unregistered_case() -> None:
    catalog = CaseCatalog.from_registered_catalog(registered_catalog_fixture())

    with pytest.raises(LookupError, match="registered case"):
        catalog.get("does-not-exist")


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda case: case["instructions"].append(""), "instruction"),
        (lambda case: case.__setitem__("extra", True), "unknown"),
        (lambda case: case.__setitem__("instructions", ["x"] * 33), "steps"),
        (lambda case: case.__setitem__("instructions", ["x" * 4097, "y", "z"]), "instruction"),
        (lambda case: case.__setitem__("case_id", "pandapower-scripted-task"), "duplicate"),
    ],
)
def test_catalog_rejects_untrusted_case_shape(mutate, message: str) -> None:
    document = registered_catalog_fixture()
    applications = cast(list[dict[str, object]], document["applications"])
    if message == "duplicate":
        cases = cast(list[dict[str, object]], applications[1]["cases"])
        cases[0]["case_id"] = "pandapower-scripted-task"
    else:
        cases = cast(list[dict[str, object]], applications[0]["cases"])
        mutate(cases[0])

    with pytest.raises(ValueError, match=message):
        CaseCatalog.from_registered_catalog(document)


def test_catalog_rejects_unknown_root_schema() -> None:
    document = registered_catalog_fixture()
    document["schema"] = "other/1.0"

    with pytest.raises(ValueError, match="schema"):
        CaseCatalog.from_registered_catalog(document)
