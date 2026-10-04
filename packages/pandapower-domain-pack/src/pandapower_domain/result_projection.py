"""Pandapower-owned mapping from admitted calculations to result payloads.

This module deliberately returns plain domain-owned data.  The Capstone
application validates it against the public Thread ResultProjection contract.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Collection, Mapping
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


def _validate_diagram_identity(
    diagram: Mapping[str, Any], *, context_ref: str, revision_ref: str, model_id: str,
) -> None:
    # The live simulator returns the explicit references.  Older authority
    # fixtures expose the same identity under ``model``; accept that typed
    # compatibility shape while still requiring an exact revision/model match.
    diagram_context = diagram.get("context_ref")
    diagram_revision = diagram.get("revision_ref")
    diagram_model = diagram.get("model")
    if isinstance(diagram_model, Mapping):
        diagram_model_id = diagram_model.get("id")
        diagram_model_revision = diagram_model.get("revision")
    else:
        diagram_model_id = diagram_model_revision = None
    if diagram_context is not None and diagram_context != context_ref:
        raise ValueError("diagram context or revision does not match calculation")
    if (diagram_revision if diagram_revision is not None else diagram_model_revision) != revision_ref:
        raise ValueError("diagram context or revision does not match calculation")
    if diagram_model_id is not None and diagram_model_id != model_id:
        raise ValueError("diagram model does not match calculation")


class PandapowerResultProjector:
    """Build a bounded business result payload from a verified calculation."""

    domain_pack_id = "pandapower-static-analysis"
    implementation_family = "pandapower"

    def project_admitted(
        self,
        *,
        authority: object,
        invoke: Callable[[str, Mapping[str, object]], object],
        context_ref: str,
        model_revision: str | None = None,
        model_context_id: str,
        model_id: str,
        thread_id: str,
        run_id: str,
        turn_id: str,
        attempt_id: str,
        result_refs: Collection[str],
        result_evidence: Mapping[str, Collection[str]],
    ) -> tuple[dict[str, object], ...]:
        """Collect and project admitted artifacts behind the Domain Pack boundary."""

        verify_context = getattr(authority, "verify_context", None)
        verify_result = getattr(authority, "verify_result", None)
        if not callable(verify_context) or not callable(verify_result):
            raise ValueError("pandapower result projection authority is unavailable")
        context_artifact = verify_context(context_ref)
        context_document = getattr(context_artifact, "document", None)
        if not isinstance(context_document, Mapping):
            raise ValueError("pandapower context projection is invalid")
        revision_ref = context_document.get("revision_ref")
        if not isinstance(revision_ref, str):
            raise ValueError("pandapower context projection revision is invalid")
        context_input = {
            **dict(context_document),
            "context_ref": context_ref,
            "revision_ref": revision_ref,
            "model_context_id": model_context_id,
            "model_id": model_id,
        }
        if model_revision is not None:
            context_input["model_revision"] = model_revision
        if isinstance(context_document.get("counts"), Mapping):
            context_input["counts"] = dict(context_document["counts"])
        diagram = invoke("operator.diagram.get", {"context_ref": context_ref})
        if not isinstance(diagram, Mapping):
            raise ValueError("pandapower diagram projection is invalid")
        admitted_refs = tuple(result_refs) + tuple(ref for refs in result_evidence.values() for ref in refs)
        projections: list[dict[str, object]] = []
        for result_ref in result_refs:
            artifact = verify_result(result_ref)
            calculation = getattr(artifact, "document", None)
            if not isinstance(calculation, Mapping):
                raise ValueError("pandapower result projection is invalid")
            evidence = tuple(result_evidence.get(result_ref, ()))
            # The application-bound association is the only evidence set that
            # may cross into a public projection. Replace an empty or stale
            # authority hint instead of allowing it to hide the current-run
            # evidence admitted for this result.
            calculation = {**dict(calculation), "evidence_refs": list(evidence)}
            if not calculation.get("evidence_refs"):
                raise ValueError("pandapower result projection evidence is unavailable")
            projections.append(self.project(
                context_input,
                calculation,
                thread_id=thread_id,
                run_id=run_id,
                turn_id=turn_id,
                attempt_id=attempt_id,
                admitted_refs=admitted_refs,
                diagram=diagram,
            ))
        return tuple(projections)

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
        _validate_diagram_identity(
            diagram_document,
            context_ref=context_ref,
            revision_ref=revision_ref,
            model_id=_string(context_document.get("model_id"), "model_id"),
        )
        result_ref = _ref(calculation_document.get("result_ref"), "result_ref", "result")
        model_id = _string(context_document.get("model_id"), "model_id")
        capability_hint = calculation_document.get(
            "producer_capability", calculation_document.get("capability_id"),
        )
        if not isinstance(capability_hint, str):
            capability_hint = calculation_document.get("operation")
        capability_hint = _string(capability_hint, "producer_capability")
        supported = capability_hint == "analysis.powerflow.ac.run" or calculation_document.get("operation") == "powerflow.ac"
        evidence_refs_raw = calculation_document.get("evidence_refs")
        if not isinstance(evidence_refs_raw, list):
            if supported:
                raise ValueError("calculation evidence is required")
            evidence_refs_raw = []
        evidence_refs = [_ref(item, "evidence_ref", "evidence") for item in evidence_refs_raw]
        admitted = set(admitted_refs)
        if result_ref not in admitted or any(item not in admitted for item in evidence_refs):
            raise ValueError("calculation result or evidence is not admitted")
        if not supported:
            return {
                "schema": "capstone-result-projection/1.0",
                "result_id": f"result_projection_{attempt_id}_{result_ref[-16:]}",
                "result_ref": result_ref, "evidence_refs": evidence_refs,
                "thread_id": thread_id, "run_id": run_id, "turn_id": turn_id, "attempt_id": attempt_id,
                "model_context_id": _string(context_document.get("model_context_id", "context_" + context_ref[-12:]), "model_context_id"),
                "model_id": model_id, "model_revision": revision_ref,
                "source": {"capability_id": capability_hint, "domain_pack_id": self.domain_pack_id, "implementation_family": self.implementation_family},
                "status": "unavailable", "summary": [], "tables": [], "element_refs": [], "overlay": None,
                "unavailable_reason": "该结果类型暂未提供结构化展示投影",
            }
        if not evidence_refs:
            raise ValueError("calculation evidence is required")
        capability = capability_hint if capability_hint != "powerflow.ac" else "analysis.powerflow.ac.run"
        base: dict[str, object] = {
            "schema": "capstone-result-projection/1.0", "result_id": f"result_projection_{attempt_id}_{result_ref[-16:]}",
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
                        "label": record.get("name") if isinstance(record.get("name"), str) and record.get("name") else f"线路 {index}",
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
        # The application normalizer uses this domain-owned declaration to
        # reject stale or fabricated result targets before they reach a
        # public Thread snapshot.  It is an internal handoff field and is
        # removed at the Kernel boundary.
        base["_diagram_element_ids"] = sorted(known_ids)
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
        if len(line_records) > 128:
            base["status"] = "partial"
            base["unavailable_reason"] = "线路结果超过展示上限，已截取前 128 条"
        for item in line_records[:128]:
            record = _mapping(item)
            element_id = _string(record.get("element_id"), "line_results.element_id")
            if element_id not in known_ids:
                raise ValueError("line result element is not in diagram")
            loading_raw = record.get("loading_percent")
            loading = None if loading_raw is None else _finite(loading_raw, "line_results.loading_percent")
            cells: dict[str, object] = {"line": _string(record.get("label", element_id), "line_results.label"), "loading_percent": loading}
            if "active_loss_mw" in record and record["active_loss_mw"] is not None:
                cells["active_loss_mw"] = _finite(record["active_loss_mw"], "line_results.active_loss_mw")
            element = {"element_kind": "line", "element_id": element_id}
            rows.append({"row_id": element_id, "cells": cells, "element_ref": element})
            element_refs.append(element)
            if loading is not None:
                overlay_values.append({"element_id": element_id, "value": loading})
        if rows:
            base["tables"] = [{"table_id": "line_loading", "title": "线路负载率", "columns": columns, "rows": rows}]
            base["element_refs"] = element_refs
            if overlay_values:
                base["overlay"] = {"metric": "loading_percent", "unit": "%", "source_ref": result_ref, "values": overlay_values}
        return base
