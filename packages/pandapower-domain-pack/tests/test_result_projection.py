from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from pandapower_domain.result_projection import PandapowerResultProjector


RESULT_REF = "result:sha256:" + "a" * 64
EVIDENCE_REF = "evidence:sha256:" + "b" * 64
REVISION_REF = "revision:sha256:" + "c" * 64


def test_derived_result_uses_verified_child_diagram_and_revision() -> None:
    child_context = context()
    parent_ref = "context:sha256:" + "e" * 64
    checked = []
    def verify_descendant(reference, ancestor):
        checked.append((reference, ancestor))
        assert reference == child_context["context_ref"] and ancestor == parent_ref
        return SimpleNamespace(document=child_context)
    authority = SimpleNamespace(
        verify_result=lambda _: SimpleNamespace(document=calculation()),
        verify_context=lambda _: SimpleNamespace(document=child_context),
        verify_context_descendant=verify_descendant,
    )
    def invoke(capability, arguments):
        assert arguments == {"context_ref": child_context["context_ref"]}
        return diagram()
    payloads = PandapowerResultProjector().project_admitted(
        authority=authority, invoke=invoke, context_ref=parent_ref,
        model_revision="revision:sha256:" + "f" * 64,
        model_context_id="context_1", model_id="ieee39", thread_id="thread_1",
        run_id="run_1", turn_id="turn_1", attempt_id="attempt_1",
        result_refs=(RESULT_REF,), result_evidence={RESULT_REF: (EVIDENCE_REF,)},
    )
    assert len(checked) == 1
    assert payloads[0]["model_revision"] == REVISION_REF
    assert payloads[0]["overlay"]["values"][0]["value"] == 67.15


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


@pytest.mark.parametrize("operation,metadata", [
    ("opf.ac", {"converged": True, "objective": 12.5}),
    ("constraints.violations", {"violation_count": 0, "constraint_source": "model"}),
    ("topology.unsupplied", {"unsupplied_bus_count": 2}),
])
def test_registered_analysis_projects_sourced_metadata_without_stale_calculation_tables(operation, metadata):
    data = {**calculation(), "producer_capability": operation, "operation": operation,
            "status": "succeeded", "metadata": metadata,
            "datasets": {"result.res_bus": {"rows": [{"index": 3, "vm_pu": 1.02}]}}}
    payload = PandapowerResultProjector().project(context(), data, thread_id="thread_1",
        run_id="run_1", turn_id="turn_1", attempt_id="attempt_1",
        admitted_refs={RESULT_REF, EVIDENCE_REF}, diagram=diagram())
    assert payload["status"] == "completed"
    assert {m["metric_id"]: m["value"] for m in payload["summary"]} == metadata
    if operation != "opf.ac":
        assert payload["tables"] == []


def test_opf_projects_every_supplied_line_and_price_with_declared_units():
    data = {**calculation(), "producer_capability": "analysis.run", "operation": "opf.ac",
            "status": "succeeded", "metadata": {"converged": True, "objective": 12.5},
            "datasets": {
                "result.res_line": {"fields": [{"name": "loading_percent", "unit": "%"}],
                                    "rows": [{"index": 11, "loading_percent": 60.25}]},
                "result.res_bus": {"fields": [{"name": "lam_p", "unit": None}],
                                   "rows": [{"index": 3, "vm_pu": 1.02, "lam_p": 14.04}]},
            }}
    payload = PandapowerResultProjector().project(context(), data, thread_id="thread_1",
        run_id="run_1", turn_id="turn_1", attempt_id="attempt_1",
        admitted_refs={RESULT_REF, EVIDENCE_REF}, diagram=diagram())
    assert payload["status"] == "completed"
    tables = {t["table_id"]: t for t in payload["tables"]}
    assert tables["res_line"]["rows"][0]["cells"] == {"index": 11, "loading_percent": 60.25}
    assert tables["res_bus"]["rows"][0]["cells"] == {"index": 3, "vm_pu": 1.02, "lam_p": 14.04}
    price = next(c for c in tables["res_bus"]["columns"] if c["column_id"] == "lam_p")
    assert "unit" not in price


def test_contingency_projects_failed_scenarios_and_undefined_constraints():
    data = {**calculation(), "producer_capability": "analysis.contingency.n_minus_one.run",
            "status": "succeeded", "scenario_count": 2,
            "constraint_evaluation": {"status": "not_defined"}, "scenarios": [
                {"element_kind": "line", "pandapower_index": 7, "status": "succeeded",
                 "converged": True, "max_loading_percent": 80, "min_vm_pu": 0.98, "max_vm_pu": 1.02},
                {"element_kind": "trafo", "pandapower_index": 3, "status": "failed", "converged": False},
            ]}
    payload = PandapowerResultProjector().project(context(), data, thread_id="thread_1",
        run_id="run_1", turn_id="turn_1", attempt_id="attempt_1",
        admitted_refs={RESULT_REF, EVIDENCE_REF}, diagram=diagram())
    assert payload["status"] == "partial"
    assert payload["tables"][0]["rows"][1]["cells"]["status"] == "failed"
    assert {m["metric_id"]: m["value"] for m in payload["summary"]}["constraint_evaluation"] == "not_defined"


def test_failed_opf_preserves_failure_status_without_presenting_old_result_tables():
    data = {**calculation(), "producer_capability": "analysis.run", "operation": "opf.ac",
            "status": "failed", "metadata": {"converged": False, "objective": 12.5},
            "datasets": {"result.res_line": {"rows": [{"index": 11, "loading_percent": 60.25}]}}}
    payload = PandapowerResultProjector().project(context(), data, thread_id="thread_1",
        run_id="run_1", turn_id="turn_1", attempt_id="attempt_1",
        admitted_refs={RESULT_REF, EVIDENCE_REF}, diagram=diagram())
    assert payload["status"] == "partial"
    assert payload["tables"] == []
    assert payload["summary"] == [{"metric_id": "status", "label": "执行状态", "value": "failed"}]
    assert payload["result_ref"] == RESULT_REF


@pytest.mark.parametrize("converged", [True, False])
def test_generic_ac_projection_uses_native_convergence_and_keeps_null_voltages(converged):
    data = {"result_ref": RESULT_REF, "evidence_refs": [EVIDENCE_REF],
            "context_ref": context()["context_ref"], "revision_ref": REVISION_REF,
            "result_type": "analysis.operation", "operation": "powerflow.ac",
            "status": "succeeded" if converged else "non_converged",
            "metadata": {"converged": converged},
            "datasets": {"result.res_bus": {"rows": [{"index": 11, "vm_pu": None}]},
                         "result.res_line": {"rows": [{"index": 11, "loading_percent": 60.25}]}}}
    payload = PandapowerResultProjector().project(context(), data, thread_id="thread_1",
        run_id="run_1", turn_id="turn_1", attempt_id="attempt_1",
        admitted_refs={RESULT_REF, EVIDENCE_REF}, diagram=diagram())
    assert payload["status"] == ("completed" if converged else "partial")
    if converged:
        tables = {table["table_id"]: table for table in payload["tables"]}
        assert tables["res_bus"]["rows"][0]["cells"]["vm_pu"] is None
        assert tables["res_line"]["rows"][0]["cells"]["loading_percent"] == 60.25
        assert payload["summary"] == [{"metric_id": "converged", "label": "计算收敛", "value": True}]
    else:
        assert payload["tables"] == []


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


def test_project_admitted_keeps_authority_and_diagram_access_inside_domain_pack() -> None:
    class Artifact:
        def __init__(self, document: dict[str, object]) -> None:
            self.document = document

    class Authority:
        def verify_context(self, reference: str) -> Artifact:
            assert reference == context()["context_ref"]
            return Artifact(context())

        def verify_result(self, reference: str) -> Artifact:
            assert reference == RESULT_REF
            return Artifact(calculation())

    def invoke(capability: str, arguments: dict[str, object]) -> object:
        assert capability == "operator.diagram.get"
        assert arguments == {"context_ref": context()["context_ref"]}
        return diagram()

    payloads = PandapowerResultProjector().project_admitted(
        authority=Authority(), invoke=invoke, context_ref=context()["context_ref"],
        model_context_id="context_1", model_id="ieee39", thread_id="thread_1",
        run_id="run_1", turn_id="turn_1", attempt_id="attempt_1",
        result_refs=(RESULT_REF,), result_evidence={RESULT_REF: (EVIDENCE_REF,)},
    )

    assert len(payloads) == 1
    assert payloads[0]["result_ref"] == RESULT_REF


def test_project_admitted_uses_current_run_evidence_when_authority_hint_is_empty() -> None:
    class Artifact:
        def __init__(self, document: dict[str, object]) -> None:
            self.document = document

    authority_calculation = calculation()
    authority_calculation["evidence_refs"] = []

    class Authority:
        def verify_context(self, reference: str) -> Artifact:
            assert reference == context()["context_ref"]
            return Artifact(context())

        def verify_result(self, reference: str) -> Artifact:
            assert reference == RESULT_REF
            return Artifact(authority_calculation)

    def invoke(capability: str, arguments: dict[str, object]) -> object:
        assert capability == "operator.diagram.get"
        assert arguments == {"context_ref": context()["context_ref"]}
        return diagram()

    payloads = PandapowerResultProjector().project_admitted(
        authority=Authority(), invoke=invoke, context_ref=context()["context_ref"],
        model_context_id="context_1", model_id="ieee39", thread_id="thread_1",
        run_id="run_1", turn_id="turn_1", attempt_id="attempt_1",
        result_refs=(RESULT_REF,), result_evidence={RESULT_REF: (EVIDENCE_REF,)},
    )

    assert payloads[0]["evidence_refs"] == [EVIDENCE_REF]
