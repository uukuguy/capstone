from __future__ import annotations

import math

import pytest

from pandapower_domain.result_projection import PandapowerResultProjector


RESULT_REF = "result:sha256:" + "a" * 64
EVIDENCE_REF = "evidence:sha256:" + "b" * 64
REVISION_REF = "revision:sha256:" + "c" * 64


def context() -> dict[str, object]:
    return {
        "context_ref": "context:sha256:" + "d" * 64,
        "model_context_id": "context_1",
        "model_id": "ieee39",
        "revision_ref": REVISION_REF,
        "counts": {"bus": 39, "line": 35, "trafo": 11},
    }


def calculation() -> dict[str, object]:
    return {
        "result_ref": RESULT_REF,
        "status": "converged",
        "producer_capability": "analysis.powerflow.ac.run",
        "revision_ref": REVISION_REF,
        "context_ref": context()["context_ref"],
        "evidence_refs": [EVIDENCE_REF],
        "summary": {
            "total_active_loss": {"value": 43.64, "unit": "MW"},
            "line_results": [{"element_id": "line_11", "label": "线路 11", "loading_percent": 67.15, "active_loss_mw": 0.72}],
        },
    }


def diagram() -> dict[str, object]:
    return {"model": {"id": "ieee39", "revision": REVISION_REF}, "branches": [{"id": "line_11", "kind": "line"}], "buses": []}


def test_projector_returns_public_shaped_pandapower_result_payload() -> None:
    payload = PandapowerResultProjector().project(
        context(), calculation(), thread_id="thread_1", run_id="run_1", turn_id="turn_1", attempt_id="attempt_1",
        admitted_refs={RESULT_REF, EVIDENCE_REF}, diagram=diagram(),
    )

    assert payload["source"] == {
        "capability_id": "analysis.powerflow.ac.run",
        "domain_pack_id": "pandapower-static-analysis",
        "implementation_family": "pandapower",
    }
    assert payload["summary"][0] == {"metric_id": "total_active_loss", "label": "有功损耗", "value": 43.64, "unit": "MW"}
    assert payload["tables"][0]["rows"][0]["element_ref"] == {"element_kind": "line", "element_id": "line_11"}
    assert payload["overlay"]["values"] == [{"element_id": "line_11", "value": 67.15}]


def test_projector_rejects_missing_admitted_evidence_or_unknown_element() -> None:
    with pytest.raises(ValueError, match="evidence"):
        PandapowerResultProjector().project(
            context(), calculation(), thread_id="thread_1", run_id="run_1", turn_id="turn_1", attempt_id="attempt_1",
            admitted_refs={RESULT_REF}, diagram=diagram(),
        )

    broken = calculation()
    broken["summary"] = {"line_results": [{"element_id": "line_99", "loading_percent": 10.0}]}
    with pytest.raises(ValueError, match="diagram"):
        PandapowerResultProjector().project(
            context(), broken, thread_id="thread_1", run_id="run_1", turn_id="turn_1", attempt_id="attempt_1",
            admitted_refs={RESULT_REF, EVIDENCE_REF}, diagram=diagram(),
        )


def test_projector_rejects_non_finite_values_and_marks_nonconverged_unavailable() -> None:
    broken = calculation()
    broken["summary"] = {"total_active_loss": {"value": math.inf, "unit": "MW"}}
    with pytest.raises(ValueError, match="finite"):
        PandapowerResultProjector().project(
            context(), broken, thread_id="thread_1", run_id="run_1", turn_id="turn_1", attempt_id="attempt_1",
            admitted_refs={RESULT_REF, EVIDENCE_REF}, diagram=diagram(),
        )

    failed = calculation()
    failed["status"] = "not_converged"
    payload = PandapowerResultProjector().project(
        context(), failed, thread_id="thread_1", run_id="run_1", turn_id="turn_1", attempt_id="attempt_1",
        admitted_refs={RESULT_REF, EVIDENCE_REF}, diagram=diagram(),
    )
    assert payload["status"] == "partial"
    assert payload["summary"] == []
    assert payload["unavailable_reason"] == "交流潮流未收敛"


def test_projector_accepts_verified_gridctl_powerflow_document() -> None:
    calculation_document = {
        "result_ref": RESULT_REF,
        "capability_id": "analysis.powerflow.ac.run",
        "context_ref": context()["context_ref"], "revision_ref": REVISION_REF,
        "convergence": {"converged": True},
        "losses": {"total_active_loss": {"value": 2.5, "unit": "MW"}},
        "branch_results": [{
            "element_kind": "line", "pandapower_index": 11,
            "name": "11", "loading_percent": 67.15, "pl_mw": 0.72,
        }],
        "evidence_refs": [EVIDENCE_REF],
    }
    payload = PandapowerResultProjector().project(
        context(), calculation_document, thread_id="thread_1", run_id="run_1",
        turn_id="turn_1", attempt_id="attempt_1", admitted_refs={RESULT_REF, EVIDENCE_REF},
        diagram={"model": {"id": "ieee39", "revision": REVISION_REF},
                 "branches": [{"id": "line:11", "kind": "line"}], "buses": []},
    )

    assert payload["summary"][0] == {
        "metric_id": "total_active_loss", "label": "有功损耗", "value": 2.5, "unit": "MW",
    }
    assert payload["tables"][0]["rows"][0]["cells"] == {
        "line": "11", "loading_percent": 67.15, "active_loss_mw": 0.72,
    }
