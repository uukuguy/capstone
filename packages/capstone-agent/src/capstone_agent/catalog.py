"""Bounded presentation catalog for source-registered scripted applications."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from capstone_agent.session import WorkerRegistry


_APP_TITLES = {
    "pandapower-static-analysis": "pandapower 电网静态分析",
    "pypsa-business-cases": "PyPSA 业务案例",
}
_GRID_CASES = {
    "pandapower-scripted-task": ("IEEE-39 潮流与线路筛查", "在登记网络内打开模型、求解交流潮流并筛查线路。"),
    "pandapower-scripted-test": ("IEEE-39 约束与单支路校核", "读取模型约束并对已解析线路执行静态校核。"),
}
_GRID_BOUNDARY = "仅说明本次登记模型及静态仿真结果；不代表实时运行状态或运行许可。"


def _grid_case(root: Path, case_id: str) -> dict[str, Any]:
    document = json.loads((root / "validation" / "application" / f"{case_id}.json").read_text(
        encoding="utf-8"
    ))
    if document.get("case_id") != case_id or document.get("application_id") != "pandapower-static-analysis":
        raise ValueError("grid case registration differs from catalog source")
    instructions = [question["text"] for question in document["questions"]]
    if len(instructions) != 3 or any(not isinstance(value, str) or not value for value in instructions):
        raise ValueError("grid case instructions are invalid")
    title, summary = _GRID_CASES[case_id]
    return {
        "case_id": case_id, "title": title, "summary": summary,
        "model_origin": "IEEE-39",
        "scenario_assumption": "按案例固定指令和登记模型进行本轮计算。",
        "interpretation_boundary": _GRID_BOUNDARY,
        "instructions": instructions,
    }


def _pypsa_cases(root: Path) -> dict[str, dict[str, Any]]:
    document = json.loads((root / "validation" / "pypsa-cases" / "cases.json").read_text(
        encoding="utf-8"
    ))
    if document.get("schema") != "capstone-pypsa-business-cases/1.0":
        raise ValueError("PyPSA case catalog schema is invalid")
    cards = {}
    for case in document["cases"]:
        if case.get("status") != "runnable":
            continue
        intro = case["introduction"]
        instructions = intro["demo_instructions"]
        if len(instructions) != 3 or any(not isinstance(value, str) or not value for value in instructions):
            raise ValueError("PyPSA case instructions are invalid")
        cards[case["id"]] = {
            "case_id": case["id"], "title": case["title"],
            "summary": intro["summary"], "model_origin": case["model_id"],
            "scenario_assumption": intro["business_problem"],
            "interpretation_boundary": intro["interpretation_boundary"],
            "instructions": instructions,
        }
    return cards


def build_catalog(registry: WorkerRegistry, repo_root: Path) -> dict[str, Any]:
    """Expose only registered, runnable three-turn cases from trusted sources."""
    pypsa = _pypsa_cases(repo_root)
    applications = []
    for spec in registry.specs:
        if spec.application_id == "pandapower-static-analysis":
            cases = [_grid_case(repo_root, case_id) for case_id in spec.scripted_cases or ()
                     if case_id in _GRID_CASES]
        elif spec.application_id == "pypsa-business-cases":
            cases = [pypsa[case_id] for case_id in spec.scripted_cases or () if case_id in pypsa]
        else:
            continue
        applications.append({
            "application_id": spec.application_id,
            "title": _APP_TITLES[spec.application_id],
            "cases": cases,
        })
    return {"schema": "capstone-catalog/1.0", "applications": applications}
