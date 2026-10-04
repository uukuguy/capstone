"""Public result projection for admitted PyPSA power operations.

The operation authority owns the full result document.  This module exposes
only bounded, reader-facing scalars and summaries; the Capstone application
still validates the returned document and binds it to the current Thread.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Collection, Mapping, Sequence
from typing import Any

_REFERENCE = re.compile(r"^pypsa-(model|result|evidence):sha256:[0-9a-f]{64}$")
_CAPABILITIES = frozenset({
    "operations.dispatch", "operations.commitment", "operations.security_dispatch",
    "operations.ac_validate", "operations.rolling_dispatch", "operations.congested_opf",
})
_MAX_ROWS = 128


def _reference(value: object, kind: str, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} is invalid")
    match = _REFERENCE.fullmatch(value)
    if match is None or match.group(1) != kind:
        raise ValueError(f"{name} is invalid")
    return value


def _document(value: object, name: str) -> Mapping[str, Any]:
    document = getattr(value, "document", value)
    if not isinstance(document, Mapping):
        raise TypeError(f"{name} is invalid")
    return document


def _finite(value: object, name: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def _series(value: object, name: str) -> list[float]:
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError(f"{name} is invalid")
    return [float(_finite(item, name)) for item in value]


def _summary(metric_id: str, label: str, value: object, unit: str | None = None) -> dict[str, object]:
    item: dict[str, object] = {
        "metric_id": metric_id, "label": label, "value": value,
    }
    if unit is not None:
        item["unit"] = unit
    return item


def _table(
    table_id: str, title: str, columns: list[dict[str, object]], rows: list[dict[str, object]],
) -> dict[str, object]:
    return {"table_id": table_id, "title": title, "columns": columns, "rows": rows}


def _component_table(
    value: object, *, table_id: str, title: str, value_label: str, unit: str,
) -> tuple[dict[str, object] | None, bool]:
    if value is None:
        return None, False
    if not isinstance(value, Mapping):
        raise TypeError(f"{table_id} is invalid")
    component_id = {
        "generator_dispatch": "generator", "generation_by_carrier": "carrier",
        "store_energy": "store", "line_active_power": "line", "line_flow": "line",
        "bus_voltage": "bus", "bus_marginal_price": "bus",
        "commitment_status": "generator",
    }.get(table_id, "component")
    rows: list[dict[str, object]] = []
    truncated = False
    for index, (component, raw_values) in enumerate(value.items()):
        if not isinstance(component, str) or not component or index >= _MAX_ROWS:
            truncated = True
            if index >= _MAX_ROWS:
                break
            continue
        values = _series(raw_values, f"{table_id}.{component}")
        rows.append({
            "row_id": f"{table_id}:{component}",
            "cells": {
                component_id: component,
                "peak": max(values),
                "average": sum(values) / len(values),
            },
        })
    if not rows:
        return None, truncated
    return _table(
        table_id, title,
        [
            {"column_id": component_id, "label": value_label},
            {"column_id": "peak", "label": "峰值", "unit": unit},
            {"column_id": "average", "label": "平均值", "unit": unit},
        ], rows,
    ), truncated


class PypsaOperationsResultProjector:
    """Map verified PyPSA operation artifacts to ``ResultProjection`` data."""

    domain_pack_id = "pypsa-power-operations"
    implementation_family = "pypsa"

    def project_admitted(
        self, *, authority: object, invoke: Callable[[str, Mapping[str, object]], object],
        context_ref: str, model_revision: str, model_context_id: str, model_id: str, thread_id: str,
        run_id: str, turn_id: str, attempt_id: str, result_refs: Collection[str],
        result_evidence: Mapping[str, Collection[str]],
    ) -> tuple[dict[str, object], ...]:
        del invoke
        _reference(context_ref, "model", "context_ref")
        verify_result = getattr(authority, "verify_result", None)
        verify_evidence = getattr(authority, "verify_evidence", None)
        if not callable(verify_result) or not callable(verify_evidence):
            raise TypeError("PyPSA operation projection authority is unavailable")
        projections: list[dict[str, object]] = []
        for result_ref in result_refs:
            _reference(result_ref, "result", "result_ref")
            result = _document(verify_result(result_ref), "operation result")
            if result.get("model_ref") != context_ref:
                raise ValueError("PyPSA operation result model differs from active context")
            evidence_refs = tuple(result_evidence.get(result_ref, ()))
            if not evidence_refs:
                raise ValueError("PyPSA operation result evidence is unavailable")
            for evidence_ref in evidence_refs:
                _reference(evidence_ref, "evidence", "evidence_ref")
                evidence = _document(verify_evidence(evidence_ref), "operation evidence")
                if evidence.get("result_ref") != result_ref:
                    raise ValueError("PyPSA operation evidence does not support the result")
            projections.append(self.project(
                result, result_ref=result_ref, evidence_refs=evidence_refs,
                model_revision=model_revision, model_context_id=model_context_id, model_id=model_id,
                thread_id=thread_id, run_id=run_id, turn_id=turn_id,
                attempt_id=attempt_id,
            ))
        return tuple(projections)

    def project(
        self, result: Mapping[str, Any], *, result_ref: str,
        evidence_refs: Collection[str], model_revision: str, model_context_id: str, model_id: str,
        thread_id: str, run_id: str, turn_id: str, attempt_id: str,
    ) -> dict[str, object]:
        capability = result.get("capability")
        if not isinstance(capability, str):
            raise TypeError("operation result capability is invalid")
        base: dict[str, object] = {
            "schema": "capstone-result-projection/1.0",
            "result_id": f"result_projection_{attempt_id}_{result_ref[-16:]}",
            "result_ref": result_ref, "evidence_refs": list(evidence_refs),
            "thread_id": thread_id, "run_id": run_id, "turn_id": turn_id,
            "attempt_id": attempt_id, "model_context_id": model_context_id,
            "model_id": model_id, "model_revision": model_revision,
            "source": {
                "capability_id": capability,
                "domain_pack_id": self.domain_pack_id,
                "implementation_family": self.implementation_family,
            },
            "status": "unavailable", "summary": [], "tables": [],
            "element_refs": [], "overlay": None,
        }
        if capability not in _CAPABILITIES:
            base["unavailable_reason"] = "该 PyPSA 操作暂未提供结构化展示投影"
            return base
        details = result.get("details")
        if not isinstance(details, Mapping):
            raise TypeError("operation result details are invalid")
        if result.get("schema") != "pypsa-operation-result/1.0":
            raise ValueError("operation result schema is invalid")
        status = result.get("status")
        condition = result.get("condition")
        if status != "ok":
            raise ValueError("operation result status is invalid")
        if not isinstance(condition, str) or not condition:
            raise ValueError("operation result condition is invalid")
        base["status"] = "completed" if condition in {"optimal", "converged"} else "partial"
        summary: list[dict[str, object]] = [
            _summary("condition", "求解状态", condition),
        ]
        objective = details.get("objective")
        if objective is not None:
            summary.append(_summary("objective", "目标值", _finite(objective, "objective")))
        omitted = details.get("omitted_line_count")
        if omitted is not None:
            summary.append(_summary("omitted_lines", "未展示线路", _finite(omitted, "omitted_line_count"), "条"))
        if "outage_set_id" in details and isinstance(details["outage_set_id"], str):
            summary.append(_summary("outage_set", "故障集合", details["outage_set_id"]))
        tables: list[dict[str, object]] = []
        truncated = False
        for key, table_id, title, label, unit in (
            ("generator_dispatch_mw", "generator_dispatch", "机组出力", "机组", "MW"),
            ("generation_by_carrier_mw", "generation_by_carrier", "按能源类型出力", "能源类型", "MW"),
            ("store_energy_mwh", "store_energy", "储能水平", "储能单元", "MWh"),
            ("line_active_power_mw", "line_active_power", "线路有功功率", "线路", "MW"),
            ("line_flow_mw", "line_flow", "线路潮流", "线路", "MW"),
            ("bus_voltage_pu", "bus_voltage", "母线电压", "母线", "pu"),
            ("bus_marginal_price", "bus_marginal_price", "母线边际价格", "母线", "€/MWh"),
            ("commitment_status", "commitment_status", "机组启停状态", "机组", "次"),
        ):
            table, was_truncated = _component_table(
                details.get(key), table_id=table_id, title=title,
                value_label=label, unit=unit,
            )
            if table is not None:
                tables.append(table)
            truncated = truncated or was_truncated
        top_loading = details.get("top_line_loading")
        if top_loading is not None and (
            not isinstance(top_loading, Sequence) or isinstance(top_loading, (str, bytes))
        ):
            raise TypeError("top_line_loading is invalid")
        if top_loading is not None:
            rows: list[dict[str, object]] = []
            for index, item in enumerate(top_loading):
                if index >= _MAX_ROWS:
                    truncated = True
                    break
                if not isinstance(item, Mapping):
                    raise TypeError("top line loading row is invalid")
                if not isinstance(item.get("line_id"), str):
                    raise TypeError("top line loading line_id is invalid")
                rows.append({
                    "row_id": f"line_loading:{item['line_id']}",
                    "cells": {
                        "line": item["line_id"],
                        "loading_percent": _finite(item.get("max_loading_pct"), "max_loading_pct"),
                    },
                })
            if rows:
                tables.append(_table(
                    "line_loading", "线路负载率",
                    [
                        {"column_id": "line", "label": "线路"},
                        {"column_id": "loading_percent", "label": "最大负载率", "unit": "%"},
                    ], rows,
                ))
        base["summary"] = summary
        base["tables"] = tables
        if truncated:
            base["status"] = "partial"
            base["unavailable_reason"] = "结果明细超过界面展示上限，已显示有界摘要"
        return base


__all__ = ["PypsaOperationsResultProjector"]
