from types import SimpleNamespace

import pytest

from pypsa_power_operations.result_projection import PypsaOperationsResultProjector

RESULT = "pypsa-result:sha256:" + "a" * 64
EVIDENCE = "pypsa-evidence:sha256:" + "b" * 64
MODEL = "pypsa-model:sha256:" + "c" * 64


class Authority:
    def __init__(self, document: dict[str, object]) -> None:
        self.document = document

    def verify_result(self, reference: str) -> SimpleNamespace:
        assert reference == RESULT
        return SimpleNamespace(document=self.document)

    def verify_evidence(self, reference: str) -> SimpleNamespace:
        assert reference == EVIDENCE
        return SimpleNamespace(document={
            "schema": "pypsa-operation-evidence/1.0",
            "result_ref": RESULT,
        })


def _result(capability: str = "operations.dispatch") -> dict[str, object]:
    return {
        "schema": "pypsa-operation-result/1.0",
        "run_id": "run_1",
        "source_binding_id": "source",
        "target_binding_id": "operations",
        "model_ref": MODEL,
        "capability": capability,
        "formulation": "fixed-capacity-linear-dispatch/1.0",
        "status": "ok",
        "condition": "optimal",
        "details": {
            "status": "ok",
            "condition": "optimal",
            "objective_kind": "operating_cost",
            "objective": 12.5,
            "generator_dispatch_mw": {
                "wind": [2.0, 4.0],
                "gas": [1.0, 3.0],
            },
            "top_line_loading": [
                {"line_id": "line-1", "max_loading_pct": 72.5},
            ],
            "omitted_line_count": 3,
        },
    }


def _project(document: dict[str, object]) -> dict[str, object]:
    return PypsaOperationsResultProjector().project_admitted(
        authority=Authority(document), invoke=lambda *_: None,
        context_ref=MODEL, model_revision="revision:sha256:" + "d" * 64,
        model_context_id="ctx_1",
        model_id="two-bus", thread_id="thread_1", run_id="run_1",
        turn_id="turn_1", attempt_id="attempt_1", result_refs=(RESULT,),
        result_evidence={RESULT: (EVIDENCE,)},
    )[0]


def test_project_dispatch_result_into_bounded_public_summary_and_tables() -> None:
    projection = _project(_result())

    assert projection["schema"] == "capstone-result-projection/1.0"
    assert projection["status"] == "completed"
    assert projection["evidence_refs"] == [EVIDENCE]
    assert {item["metric_id"] for item in projection["summary"]} >= {
        "objective", "condition",
    }
    tables = {item["table_id"]: item for item in projection["tables"]}
    assert tables["generator_dispatch"]["rows"][0]["cells"]["generator"] == "wind"
    assert tables["line_loading"]["rows"][0]["cells"]["loading_percent"] == 72.5
    assert projection["element_refs"] == []
    assert projection["overlay"] is None


def test_project_unsupported_operation_as_typed_unavailable() -> None:
    projection = _project(_result("operations.experimental"))

    assert projection["status"] == "unavailable"
    assert projection["summary"] == []
    assert projection["tables"] == []
    assert "暂未提供结构化展示" in projection["unavailable_reason"]


def test_project_rejects_evidence_not_admitted_for_result() -> None:
    with pytest.raises(ValueError, match="evidence"):
        PypsaOperationsResultProjector().project_admitted(
            authority=Authority(_result()), invoke=lambda *_: None,
            context_ref=MODEL, model_revision="revision:sha256:" + "d" * 64,
            model_context_id="ctx_1",
            model_id="two-bus", thread_id="thread_1", run_id="run_1",
            turn_id="turn_1", attempt_id="attempt_1", result_refs=(RESULT,),
            result_evidence={RESULT: ()},
        )


def test_project_rejects_result_for_another_active_model() -> None:
    foreign = _result()
    foreign["model_ref"] = "pypsa-model:sha256:" + "d" * 64
    with pytest.raises(ValueError, match="model"):
        _project(foreign)
