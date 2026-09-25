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


def test_capacity_and_commitment_are_optimized_together(tmp_path) -> None:
    source = tmp_path / "runs" / "joint-run" / "domains" / "model"
    target = source.parent / "planning"
    opened = execute("model.open", {"catalog_id": "capacity-commitment"}, source, run_id="joint-run")
    result = execute_planning(
        "planning.capacity_commitment", {"model_ref": opened["model_ref"]},
        target, source, run_id="joint-run",
    )
    assert result["condition"] == "optimal"
    assert result["generator_capacity_mw"] == pytest.approx({"supply": 40.0})
    assert result["commitment_status"] == [0, 1]
    assert result["objective"] == pytest.approx(4450.0)
    assert result["investment_cost"] == pytest.approx(4000.0)
    assert result["operating_cost"] == pytest.approx(450.0)
    assert verify_planning_evidence(target, source, "joint-run", result["evidence_refs"][0]).document["result_ref"] == result["result_ref"]


def test_registered_multi_period_pathway_builds_capacity_by_year(tmp_path) -> None:
    source = tmp_path / "runs" / "path-run" / "domains" / "model"
    target = source.parent / "planning"
    opened = execute("model.open", {"catalog_id": "capacity-pathway"}, source, run_id="path-run")
    result = execute_planning(
        "planning.multi_period", {"model_ref": opened["model_ref"]},
        target, source, run_id="path-run",
    )
    assert result["condition"] == "optimal"
    assert result["generator_capacity_mw"] == pytest.approx({"early": 20.0, "late": 20.0})
    assert result["investment_periods"] == [2025, 2030]
    assert result["objective_kind"] == "discounted_pathway_cost"
    assert verify_planning_evidence(target, source, "path-run", result["evidence_refs"][0]).document["result_ref"] == result["result_ref"]


def test_two_scenario_planning_shares_investment_across_recourse(tmp_path) -> None:
    source = tmp_path / "runs" / "scenario-run" / "domains" / "model"
    target = source.parent / "planning"
    opened = execute("model.open", {"catalog_id": "capacity-scenarios"}, source, run_id="scenario-run")
    result = execute_planning(
        "planning.stochastic", {"model_ref": opened["model_ref"]},
        target, source, run_id="scenario-run",
    )
    assert result["condition"] == "optimal"
    assert result["generator_capacity_mw"] == pytest.approx({"build": 20.0})
    assert result["scenario_dispatch_mwh"]["low"] == pytest.approx({"build": 20.0, "backup": 0.0})
    assert result["scenario_dispatch_mwh"]["high"] == pytest.approx({"build": 20.0, "backup": 20.0})
    assert result["objective_kind"] == "investment_plus_expected_operating_cost"
    assert verify_planning_evidence(target, source, "scenario-run", result["evidence_refs"][0]).document["result_ref"] == result["result_ref"]


def test_near_optimal_alternative_separates_capacity_from_cost(tmp_path) -> None:
    source = tmp_path / "runs" / "mga-run" / "domains" / "model"
    target = source.parent / "planning"
    opened = execute("model.open", {"catalog_id": "capacity-two-bus"}, source, run_id="mga-run")
    result = execute_planning(
        "planning.near_optimal_capacity", {"model_ref": opened["model_ref"]},
        target, source, run_id="mga-run",
    )
    assert result["condition"] == "optimal"
    assert result["baseline_system_cost"] == pytest.approx(4800.0)
    assert result["cost_slack"] == pytest.approx(0.05)
    assert result["generator_capacity_mw"] == pytest.approx({"supply": 42.4})
    assert result["objective_kind"] == "maximized_installed_generation_capacity_mw"
    assert result["objective"] == pytest.approx(42.4)
    assert result["system_cost"] <= 5040.0 + 1e-6
    assert verify_planning_evidence(target, source, "mga-run", result["evidence_refs"][0]).document["result_ref"] == result["result_ref"]
