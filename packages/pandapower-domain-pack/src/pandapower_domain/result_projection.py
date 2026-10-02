"""Pandapower-owned mapping from admitted calculations to result payloads.

This module deliberately returns plain domain-owned data.  The Capstone
application validates it against the public Thread ResultProjection contract.
"""

from __future__ import annotations

import math
import re
from collections.abc import Collection, Mapping
from typing import Any


_REF = re.compile(r"^(context|result|evidence|revision):sha256:[0-9a-f]{64}$")


def _mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        result = dump(mode="python")
        if isinstance(result, Mapping):
            return result
    raise ValueError("pandapower result projection input must be a mapping")


def _string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} is invalid")
    return value


def _ref(value: object, name: str, kind: str) -> str:
    text = _string(value, name)
    match = _REF.fullmatch(text)
    if match is None or match.group(1) != kind:
        raise ValueError(f"{name} is invalid")
    return text


def _finite(value: object, name: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def _diagram_ids(diagram: Mapping[str, Any]) -> set[str]:
    ids: set[str] = set()
    for key in ("buses", "branches"):
        records = diagram.get(key, [])
        if isinstance(records, list):
            ids.update(item["id"] for item in records if isinstance(item, Mapping) and isinstance(item.get("id"), str))
    return ids


class PandapowerResultProjector:
    """Build a bounded business result payload from a verified calculation."""

    domain_pack_id = "pandapower-static-analysis"
    implementation_family = "pandapower"

    def project(
        self,
        context: object,
        calculation: object,
        *,
        thread_id: str,
        run_id: str,
        turn_id: str,
        attempt_id: str,
        admitted_refs: Collection[str],
        diagram: object,
    ) -> dict[str, object]:
        context_document = _mapping(context)
        calculation_document = _mapping(calculation)
        diagram_document = _mapping(diagram)
        context_ref = _ref(context_document.get("context_ref"), "context_ref", "context")
        revision_ref = _ref(context_document.get("revision_ref"), "revision_ref", "revision")
        if calculation_document.get("context_ref") != context_ref or calculation_document.get("revision_ref") != revision_ref:
            raise ValueError("calculation context or revision does not match diagram")
        result_ref = _ref(calculation_document.get("result_ref"), "result_ref", "result")
        evidence_refs_raw = calculation_document.get("evidence_refs")
        if not isinstance(evidence_refs_raw, list) or not evidence_refs_raw:
            raise ValueError("calculation evidence is required")
        evidence_refs = [_ref(item, "evidence_ref", "evidence") for item in evidence_refs_raw]
        admitted = set(admitted_refs)
        if result_ref not in admitted or any(item not in admitted for item in evidence_refs):
            raise ValueError("calculation result or evidence is not admitted")
        model_id = _string(context_document.get("model_id"), "model_id")
        capability = _string(
            calculation_document.get("producer_capability", calculation_document.get("capability_id")),
            "producer_capability",
        )
        base: dict[str, object] = {
            "schema": "capstone-result-projection/1.0", "result_id": f"result_projection_{attempt_id}",
            "result_ref": result_ref, "evidence_refs": evidence_refs,
            "thread_id": thread_id, "run_id": run_id, "turn_id": turn_id, "attempt_id": attempt_id,
            "model_context_id": _string(context_document.get("model_context_id", "context_" + context_ref[-12:]), "model_context_id"), "model_id": model_id, "model_revision": revision_ref,
            "source": {"capability_id": capability, "domain_pack_id": self.domain_pack_id, "implementation_family": self.implementation_family},
            "status": "completed", "summary": [], "tables": [], "element_refs": [], "overlay": None,
        }
        convergence = calculation_document.get("convergence")
        converged = calculation_document.get("status") == "converged"
        if isinstance(convergence, Mapping):
            converged = convergence.get("converged") is True
        if not converged:
            base["status"] = "partial"
            base["unavailable_reason"] = "交流潮流未收敛"
            return base
        summary = calculation_document.get("summary")
        if not isinstance(summary, Mapping):
            losses = calculation_document.get("losses")
            summary = {
                "total_active_loss": losses.get("total_active_loss")
                if isinstance(losses, Mapping) else None,
                "line_results": [],
            }
            branch_results = calculation_document.get("branch_results")
            if isinstance(branch_results, list):
                for record in branch_results:
                    if not isinstance(record, Mapping) or record.get("element_kind") != "line":
                        continue
                    index = record.get("pandapower_index")
                    if type(index) is not int:
                        continue
                    row: dict[str, object] = {
                        "element_id": f"line:{index}",
                        "label": record.get("name", f"线路 {index}"),
                        "loading_percent": record.get("loading_percent"),
                    }
                    if "pl_mw" in record:
                        row["active_loss_mw"] = record["pl_mw"]
                    summary["line_results"].append(row)
        metrics: list[dict[str, object]] = []
        loss = summary.get("total_active_loss")
        if isinstance(loss, Mapping):
            metrics.append({"metric_id": "total_active_loss", "label": "有功损耗", "value": _finite(loss.get("value"), "total_active_loss"), "unit": _string(loss.get("unit"), "total_active_loss.unit")})
        counts = context_document.get("counts")
        if not isinstance(counts, Mapping):
            counts = {
                "bus": len(diagram_document.get("buses", []))
                if isinstance(diagram_document.get("buses"), list) else 0,
                "line": sum(
                    1 for item in diagram_document.get("branches", [])
                    if isinstance(item, Mapping) and item.get("kind") == "line"
                ) if isinstance(diagram_document.get("branches"), list) else 0,
                "trafo": sum(
                    1 for item in diagram_document.get("branches", [])
                    if isinstance(item, Mapping) and item.get("kind") in {"trafo", "trafo3w"}
                ) if isinstance(diagram_document.get("branches"), list) else 0,
            }
        if isinstance(counts, Mapping):
            for key, label in (("bus", "母线"), ("line", "线路"), ("trafo", "变压器")):
                value = counts.get(key)
                if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                    metrics.append({"metric_id": f"network_{key}_count", "label": f"{label}数量", "value": value, "unit": "个"})
        base["summary"] = metrics
        known_ids = _diagram_ids(diagram_document)
        line_records = summary.get("line_results", [])
        if not isinstance(line_records, list):
            raise ValueError("line_results is invalid")
        columns = [
            {"column_id": "line", "label": "线路"},
            {"column_id": "loading_percent", "label": "负载率", "unit": "%"},
            {"column_id": "active_loss_mw", "label": "有功损耗", "unit": "MW"},
        ]
        rows: list[dict[str, object]] = []
        element_refs: list[dict[str, str]] = []
        overlay_values: list[dict[str, object]] = []
        for item in line_records[:128]:
            record = _mapping(item)
            element_id = _string(record.get("element_id"), "line_results.element_id")
            if element_id not in known_ids:
                raise ValueError("line result element is not in diagram")
            loading = _finite(record.get("loading_percent"), "line_results.loading_percent")
            cells: dict[str, object] = {"line": _string(record.get("label", element_id), "line_results.label"), "loading_percent": loading}
            if "active_loss_mw" in record:
                cells["active_loss_mw"] = _finite(record["active_loss_mw"], "line_results.active_loss_mw")
            element = {"element_kind": "line", "element_id": element_id}
            rows.append({"row_id": element_id, "cells": cells, "element_ref": element})
            element_refs.append(element)
            overlay_values.append({"element_id": element_id, "value": loading})
        if rows:
            base["tables"] = [{"table_id": "line_loading", "title": "线路负载率", "columns": columns, "rows": rows}]
            base["element_refs"] = element_refs
            base["overlay"] = {"metric": "loading_percent", "unit": "%", "source_ref": result_ref, "values": overlay_values}
        return base
