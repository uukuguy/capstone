"""Present registered analysis artifacts without reinterpreting their results."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

_LABELS = {
    "converged": "计算收敛", "objective": "优化目标值", "violation_count": "越限记录数",
    "constraint_source": "约束来源", "unsupplied_bus_count": "失电母线数",
    "checked_value_count": "已核验数值数", "unavailable_value_count": "未核验数值数",
    "scenario_count": "校核场景数", "constraint_evaluation": "约束评估",
    "index": "模型索引", "vm_pu": "电压", "lam_p": "有功边际价格", "lam_q": "无功边际价格",
    "loading_percent": "负载率", "p_mw": "有功出力", "q_mvar": "无功出力",
    "kind": "越限类型", "severity": "等级", "value": "计算值", "limit": "限值", "unit": "单位",
    "element_kind": "停运元件类型", "pandapower_index": "停运元件索引", "status": "执行状态",
    "max_loading_percent": "最大负载率", "min_vm_pu": "最低电压", "max_vm_pu": "最高电压",
}
_OPERATIONS = {
    "powerflow.ac": ("converged",),
    "opf.ac": ("converged", "objective"), "opf.dc": ("converged", "objective"),
    "constraints.violations": ("violation_count", "constraint_source", "checked_value_count", "unavailable_value_count"),
    "topology.unsupplied": ("unsupplied_bus_count",),
}
_OPF_TABLES = (
    ("result.res_line", "线路负载率", ("index", "loading_percent")),
    ("result.res_bus", "母线电压与边际价格", ("index", "vm_pu", "lam_p", "lam_q")),
    ("result.res_gen", "发电机出力", ("index", "p_mw", "q_mvar", "vm_pu")),
    ("result.res_ext_grid", "外部电网出力", ("index", "p_mw", "q_mvar")),
)
_POWERFLOW_TABLES = (
    ("result.res_line", "线路负载率", ("index", "loading_percent")),
    ("result.res_bus", "母线电压", ("index", "vm_pu")),
    ("result.res_gen", "发电机出力", ("index", "p_mw", "q_mvar", "vm_pu")),
    ("result.res_ext_grid", "外部电网出力", ("index", "p_mw", "q_mvar")),
)


def _scalar(value: object) -> object:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str) and len(value) <= 256:
        return value
    if isinstance(value, (int, float)) and math.isfinite(value):
        return value
    raise ValueError("analysis projection value is invalid")


def _table(table_id: str, title: str, fields: tuple[str, ...], rows: list,
           schema: object = None) -> dict[str, object]:
    if any(not isinstance(row, Mapping) for row in rows):
        raise ValueError("analysis projection rows are invalid")
    selected = tuple(field for field in fields if any(isinstance(row, Mapping) and field in row for row in rows))
    if not selected:
        selected = (fields[0],)
    units = {field.get("name"): field.get("unit") for field in schema
             if isinstance(field, Mapping)} if isinstance(schema, list) else {}
    columns = []
    for field in selected:
        column: dict[str, object] = {"column_id": field, "label": _LABELS[field]}
        unit = units.get(field)
        if isinstance(unit, str) and unit:
            column["unit"] = unit
        columns.append(column)
    return {"table_id": table_id, "title": title, "columns": columns,
            "rows": [{"row_id": f"{table_id}:{index}",
                      "cells": {field: _scalar(row[field]) for field in selected if field in row}}
                     for index, row in enumerate(rows[:128]) if isinstance(row, Mapping)]}


def project_analysis_result(calculation: Mapping[str, Any], base: dict[str, object]) -> dict[str, object] | None:
    operation = calculation.get("operation")
    if not isinstance(operation, str):
        operation = ""
    contingency = calculation.get("capability_id", calculation.get("producer_capability")) == "analysis.contingency.n_minus_one.run"
    if not contingency and operation not in _OPERATIONS:
        return None
    if not base["evidence_refs"]:
        raise ValueError("calculation evidence is required")
    output = {**base, "status": "completed", "summary": [], "tables": []}
    metadata = calculation.get("metadata", {})
    metadata = metadata if isinstance(metadata, Mapping) else {}
    summary: list[dict[str, object]] = []
    tables: list[dict[str, object]] = []
    reasons = []
    def metric(key: str, value: object) -> None:
        summary.append({"metric_id": key, "label": _LABELS[key], "value": _scalar(value)})
    if contingency:
        scenarios = calculation.get("scenarios", [])
        if not isinstance(scenarios, list):
            raise ValueError("contingency scenarios are invalid")
        if "scenario_count" in calculation:
            metric("scenario_count", calculation["scenario_count"])
        evaluation = calculation.get("constraint_evaluation")
        if isinstance(evaluation, Mapping) and "status" in evaluation:
            metric("constraint_evaluation", evaluation["status"])
        tables.append(_table("contingency_scenarios", "逐场景校核结果",
            ("element_kind", "pandapower_index", "status", "converged", "max_loading_percent", "min_vm_pu", "max_vm_pu"), scenarios,
            [{"name": "max_loading_percent", "unit": "%"}, {"name": "min_vm_pu", "unit": "p.u."},
             {"name": "max_vm_pu", "unit": "p.u."}]))
        if any(isinstance(row, Mapping) and row.get("status") != "succeeded" for row in scenarios):
            reasons.append("部分场景计算未成功，失败状态已保留")
        if len(scenarios) > 128:
            reasons.append("场景超过展示上限，显示前128条；完整记录保留在原结果中")
    else:
        partial_evaluation = operation == "constraints.violations" and calculation.get("status") == "partial"
        if (calculation.get("status") != "succeeded" and not partial_evaluation) or metadata.get("converged") is False:
            metric("status", calculation.get("status"))
            return {**output, "status": "partial", "summary": summary,
                    "unavailable_reason": "计算未成功，失败状态和原始记录已保留"}
        if partial_evaluation:
            reasons.append("部分指标缺少限值或计算值；已核验结果保留，零项越限不表示全部合格")
        for key in _OPERATIONS[operation]:
            if key in metadata:
                metric(key, metadata[key])
        datasets = calculation.get("datasets", {})
        datasets = datasets if isinstance(datasets, Mapping) else {}
        table_specs = _OPF_TABLES if operation in {"opf.ac", "opf.dc"} else (
            (("result.res_violation", "约束越限记录", ("index", "kind", "severity", "value", "limit", "unit")),)
            if operation == "constraints.violations" else ())
        if operation == "powerflow.ac":
            table_specs = _POWERFLOW_TABLES
        for name, title, fields in table_specs:
            dataset = datasets.get(name)
            if not isinstance(dataset, Mapping) or not isinstance(dataset.get("rows"), list):
                continue
            rows = dataset["rows"]
            tables.append(_table(name.removeprefix("result."), title, fields, rows, dataset.get("fields")))
            if len(rows) > 128:
                reasons.append("部分明细超过展示上限，各表显示前128条；完整记录保留在原结果中")
    output["summary"], output["tables"] = summary, tables
    if reasons:
        output["status"] = "partial"
        output["unavailable_reason"] = "；".join(dict.fromkeys(reasons))
    return output
