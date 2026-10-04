from __future__ import annotations

import math

import pytest

from capstone_agent.result_projection import (
    ResultProjection,
    normalize_result_projection,
)
from capstone_agent.thread_protocol import ThreadProtocolError, ThreadSnapshot


def valid_projection() -> dict[str, object]:
    return {
        "schema": "capstone-result-projection/1.0",
        "result_id": "result_projection_1",
        "result_ref": "result:sha256:" + "a" * 64,
        "evidence_refs": ["evidence:sha256:" + "b" * 64],
        "thread_id": "thread_1",
        "run_id": "run_1",
        "turn_id": "turn_1",
        "attempt_id": "attempt_1",
        "model_context_id": "context_1",
        "model_id": "ieee39",
        "model_revision": "revision:sha256:" + "c" * 64,
        "source": {
            "capability_id": "analysis.powerflow.ac.run",
            "domain_pack_id": "pandapower-static-analysis",
            "implementation_family": "pandapower",
        },
        "status": "completed",
        "summary": [{"metric_id": "total_active_loss", "label": "有功损耗", "value": 43.64, "unit": "MW"}],
        "tables": [{
            "table_id": "line_loading",
            "title": "线路负载率",
            "columns": [{"column_id": "line", "label": "线路"}, {"column_id": "loading", "label": "负载率", "unit": "%"}],
            "rows": [{"row_id": "line_11", "cells": {"line": "11", "loading": 67.15}, "element_ref": {"element_kind": "line", "element_id": "line_11"}}],
        }],
        "element_refs": [{"element_kind": "line", "element_id": "line_11"}],
        "overlay": {"metric": "loading_percent", "unit": "%", "source_ref": "result:sha256:" + "a" * 64, "values": [{"element_id": "line_11", "value": 67.15}]},
    }


def test_result_projection_accepts_bounded_admitted_projection() -> None:
    projection = ResultProjection.from_document(
        normalize_result_projection(
            valid_projection(),
            admitted_refs={"result:sha256:" + "a" * 64, "evidence:sha256:" + "b" * 64},
            diagram_ids={"line_11"},
            expected_model_revision="revision:sha256:" + "c" * 64,
        )
    )

    assert projection.result_ref.startswith("result:sha256:")
    assert projection.summary[0].unit == "MW"
    assert projection.tables[0].rows[0].element_ref.element_id == "line_11"


def test_result_projection_accepts_hierarchical_model_id() -> None:
    document = valid_projection()
    document["model_id"] = "pypsa-example/scigrid_de"

    projection = ResultProjection.from_document(
        normalize_result_projection(
            document,
            admitted_refs={"result:sha256:" + "a" * 64, "evidence:sha256:" + "b" * 64},
            diagram_ids={"line_11"},
            expected_model_revision="revision:sha256:" + "c" * 64,
        )
    )

    assert projection.model_id == "pypsa-example/scigrid_de"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda value: value["result_ref"].__class__ and value.update(result_ref="result:sha256:" + "d" * 64), "not admitted"),
        (lambda value: value.update(model_revision="revision:sha256:" + "d" * 64), "revision"),
        (lambda value: value.update(summary=[{"metric_id": "loss", "label": "损耗", "value": math.inf, "unit": "MW"}]), "finite"),
        (lambda value: value["element_refs"].__class__ and value["element_refs"].__setitem__(0, {"element_kind": "line", "element_id": "line_99"}), "element"),
    ],
)
def test_result_projection_rejects_untrusted_or_invalid_data(change, message: str) -> None:
    document = valid_projection()
    change(document)

    with pytest.raises(ValueError, match=message):
        normalize_result_projection(
            document,
            admitted_refs={"result:sha256:" + "a" * 64, "evidence:sha256:" + "b" * 64},
            diagram_ids={"line_11"},
            expected_model_revision="revision:sha256:" + "c" * 64,
        )


def test_unavailable_projection_has_no_metrics() -> None:
    document = valid_projection()
    document.update(status="unavailable", summary=[], tables=[], element_refs=[], overlay=None, unavailable_reason="能力未发布")

    projection = ResultProjection.from_document(
        normalize_result_projection(document, admitted_refs={"result:sha256:" + "a" * 64, "evidence:sha256:" + "b" * 64})
    )

    assert projection.status == "unavailable"
    assert projection.unavailable_reason == "能力未发布"
    assert projection.summary == ()


@pytest.mark.parametrize("field", ["result_ref", "evidence_refs"])
def test_available_projection_requires_admitted_references(field: str) -> None:
    document = valid_projection()
    document[field] = None if field == "result_ref" else []
    with pytest.raises(ValueError, match="references"):
        ResultProjection.from_document(document)


def test_thread_snapshot_round_trips_result_projection() -> None:
    projection = valid_projection()
    snapshot = ThreadSnapshot.from_document({
        "schema": "capstone-thread-snapshot/1",
        "thread_id": "thread_1",
        "run": {"run_id": "run_1", "state": "open"},
        "active_model_context": {
            "id": "context_1", "model_id": "ieee39", "model_revision": "revision:sha256:" + "c" * 64,
            "implementation_family": "pandapower", "selection_revision": "selection_1",
        },
        "active_grid_page_id": "page_ieee39", "current_attempt": None,
        "last_event_seq": 2, "base_event_seq": 0, "result_projections": [projection],
    })

    assert snapshot.result_projections[0].result_id == "result_projection_1"
    assert snapshot.to_document()["result_projections"][0]["model_revision"] == projection["model_revision"]


@pytest.mark.parametrize("field", ["thread_id", "run_id"])
def test_thread_snapshot_rejects_projection_from_another_thread_or_run(field: str) -> None:
    projection = valid_projection()
    projection[field] = "other_thread" if field == "thread_id" else "other_run"
    with pytest.raises(ThreadProtocolError, match="identity"):
        ThreadSnapshot.from_document({
            "schema": "capstone-thread-snapshot/1",
            "thread_id": "thread_1",
            "run": {"run_id": "run_1", "state": "open"},
            "active_model_context": {
                "id": "context_1", "model_id": "ieee39", "model_revision": projection["model_revision"],
                "implementation_family": "pandapower", "selection_revision": "selection_1",
            },
            "active_grid_page_id": "page_ieee39", "current_attempt": None,
            "last_event_seq": 2, "base_event_seq": 0, "result_projections": [projection],
        })
