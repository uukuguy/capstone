"""Registered expansion decisions remain tied to source revisions and target evidence."""

from __future__ import annotations

import pytest

from pypsa_model_authority.operations import execute
from pypsa_model_authority.capacity_planning import PlanningError, execute_planning
from pypsa_model_authority.references import verify_planning_evidence, verify_planning_result


def test_registered_capacity_expansion_uses_real_solver_and_target_evidence(tmp_path) -> None:
    source = tmp_path / "runs" / "plan-run" / "domains" / "model"
    target = source.parent / "planning"
    opened = execute("model.open", {"catalog_id": "capacity-two-bus"}, source, run_id="plan-run")
    result = execute_planning(
        "planning.capacity_expand", {"model_ref": opened["model_ref"]},
        target, source, run_id="plan-run",
    )
    assert result["condition"] == "optimal"
    assert result["generator_capacity_mw"] == pytest.approx({"supply": 40.0})
    assert result["objective"] == pytest.approx(4800.0)
    assert result["investment_cost"] == pytest.approx(4000.0)
    assert result["operating_cost"] == pytest.approx(800.0)
    assert verify_planning_result(target, source, "plan-run", result["result_ref"]).document["model_ref"] == opened["model_ref"]
    assert verify_planning_evidence(target, source, "plan-run", result["evidence_refs"][0]).document["result_ref"] == result["result_ref"]


def test_foreign_or_infeasible_expansion_has_no_success_artifacts(tmp_path) -> None:
    source = tmp_path / "runs" / "plan-run" / "domains" / "model"
    target = source.parent / "planning"
    opened = execute("model.open", {"catalog_id": "capacity-two-bus"}, source, run_id="plan-run")
    with pytest.raises(PlanningError, match="current run|unavailable"):
        execute_planning(
            "planning.capacity_expand", {"model_ref": opened["model_ref"]},
            tmp_path / "runs" / "other" / "domains" / "planning",
            tmp_path / "runs" / "other" / "domains" / "model", run_id="other",
        )
    overloaded = execute("model.derive", {
        "model_ref": opened["model_ref"], "load_id": "demand", "p_set_mw": 200.0,
    }, source, run_id="plan-run")
    with pytest.raises(PlanningError, match="infeasible|warning"):
        execute_planning(
            "planning.capacity_expand", {"model_ref": overloaded["model_ref"]},
            target, source, run_id="plan-run",
        )
    assert not (target / "results").exists()
