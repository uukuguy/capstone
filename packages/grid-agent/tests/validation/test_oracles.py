import pytest

from grid_agent.validation.oracles import (
    ORACLES,
    ToolResultEvent,
    contains_all,
    error_matches,
    result_matches,
    result_satisfies,
    topology_branch_endpoints,
    truthful_limitation,
)


def test_contains_all_matches_required_values_case_insensitively() -> None:
    assert contains_all("示例范围为 2.5 到 3.5 PU。", {"values": ["2.5", "3.5", "pu"]})
    assert not contains_all("示例范围为 2.5 到 3.4 pu。", {"values": ["2.5", "3.5", "pu"]})


def test_truthful_limitation_matches_known_limitation_terms() -> None:
    assert truthful_limitation("line:index:171 not found in ieee39", {})
    assert not truthful_limitation("线路 line:index:171 的最大负载率为 30%。", {})


def test_topology_oracle_matches_declared_result_fields() -> None:
    event = ToolResultEvent(
        capability="topology.branch.endpoints.get",
        result={
            "branch": {"kind": "line", "namespace": "pandapower_index", "identifier": "11"},
            "from_bus": {"name": "6", "asset_ref": "asset:bus:sha256:" + "a" * 64},
            "to_bus": {"name": "11", "asset_ref": "asset:bus:sha256:" + "b" * 64},
        },
        evidence_refs=("evidence:sha256:" + "c" * 64,),
    )
    expected = {
        "branch": {"kind": "line", "namespace": "pandapower_index", "identifier": "11"},
        "from_bus": {"name": "6"},
        "to_bus": {"name": "11"},
    }
    assert topology_branch_endpoints(event, expected) is True


def test_topology_oracle_rejects_wrong_structured_endpoint_even_when_prose_is_polished() -> None:
    event = ToolResultEvent(
        capability="topology.branch.endpoints.get",
        result={"from_bus": {"name": "6"}, "to_bus": {"name": "12"}},
        evidence_refs=("evidence:sha256:" + "d" * 64,),
    )
    assert topology_branch_endpoints(event, {"from_bus": {"name": "6"}, "to_bus": {"name": "11"}}) is False


def test_generic_structured_result_oracle_matches_declared_subset() -> None:
    event = ToolResultEvent(
        capability="analysis.powerflow.ac.run",
        result={"converged": True, "total_active_loss": {"value": 43.6411257608517, "unit": "MW"}},
        evidence_refs=("evidence:sha256:" + "e" * 64,),
    )

    assert result_matches(event, {"converged": True, "total_active_loss": {"unit": "MW"}}) is True


def loss_oracle_arguments() -> dict:
    return {
        "matches": {"converged": True, "total_active_loss": {"unit": "MW"}, "count": 1},
        "numeric_tolerances": {
            "total_active_loss.value": {"expected": 43.6411257608517, "abs_tol": 1e-9, "rel_tol": 0},
        },
    }


def test_explicit_numeric_tolerance_accepts_linux_roundoff_without_relaxing_exact_oracle() -> None:
    event = ToolResultEvent(
        capability="analysis.powerflow.ac.run",
        result={"converged": True, "count": 1, "total_active_loss": {"value": 43.64112576085046, "unit": "MW"}},
        evidence_refs=("evidence:sha256:" + "e" * 64,),
    )
    oracle = ORACLES.get("result_matches_with_tolerance")
    assert callable(oracle)
    assert oracle(event, loss_oracle_arguments()) is True
    assert result_matches(event, {"total_active_loss": {"value": 43.6411257608517}}) is False


@pytest.mark.parametrize("result", [
    {"converged": True, "count": 1, "total_active_loss": {"value": 43.6411257628517, "unit": "MW"}},
    {"converged": True, "count": 1, "total_active_loss": {"value": 43.6411257608517, "unit": "kW"}},
    {"converged": False, "count": 1, "total_active_loss": {"value": 43.6411257608517, "unit": "MW"}},
    {"converged": 1, "count": 1, "total_active_loss": {"value": 43.6411257608517, "unit": "MW"}},
    {"converged": True, "count": True, "total_active_loss": {"value": 43.6411257608517, "unit": "MW"}},
    {"converged": True, "count": 2, "total_active_loss": {"value": 43.6411257608517, "unit": "MW"}},
    {"converged": True, "count": 1, "total_active_loss": {"unit": "MW"}},
    {"converged": True, "count": 1, "total_active_loss": {"value": True, "unit": "MW"}},
    {"converged": True, "count": 1, "total_active_loss": {"value": float("nan"), "unit": "MW"}},
    {"converged": True, "count": 1, "total_active_loss": {"value": float("inf"), "unit": "MW"}},
    {"converged": True, "count": 1, "total_active_loss": {"value": "43.6411257608517", "unit": "MW"}},
])
def test_explicit_numeric_tolerance_preserves_required_fields_and_rejects_invalid_numbers(result: dict) -> None:
    oracle = ORACLES.get("result_matches_with_tolerance")
    assert callable(oracle)
    assert oracle(ToolResultEvent("analysis.powerflow.ac.run", result, ()), loss_oracle_arguments()) is False


@pytest.mark.parametrize("field,value", [
    ("expected", True), ("expected", float("nan")), ("expected", float("inf")),
    ("abs_tol", -1), ("abs_tol", float("inf")), ("abs_tol", True),
    ("rel_tol", -1), ("rel_tol", float("nan")), ("rel_tol", False),
])
def test_explicit_numeric_tolerance_rejects_invalid_limits(field: str, value: object) -> None:
    arguments = loss_oracle_arguments()
    arguments["numeric_tolerances"]["total_active_loss.value"][field] = value
    oracle = ORACLES.get("result_matches_with_tolerance")
    assert callable(oracle)
    event = ToolResultEvent("analysis.powerflow.ac.run", {"converged": True, "count": 1, "total_active_loss": {"value": 43.6411257608517, "unit": "MW"}}, ())
    assert oracle(event, arguments) is False


def test_generic_error_oracle_matches_typed_error_subset() -> None:
    event = ToolResultEvent(
        capability="result.branches.rank",
        result={},
        evidence_refs=(),
        ok=False,
        error={"code": "unknown_result", "allowed_recovery_actions": ["run analysis.powerflow.ac.run first"]},
    )

    assert error_matches(event, {"code": "unknown_result"}) is True


def test_result_satisfies_checks_subsets_nonempty_paths_and_minimums() -> None:
    event = ToolResultEvent(
        capability="analysis.result.risk.rank",
        result={"status": "succeeded", "summary": {"ranked_count": 3}, "rankings": [{"rank": 1}]},
        evidence_refs=("evidence:sha256:" + "f" * 64,),
    )

    assert result_satisfies(
        event,
        {
            "matches": {"status": "succeeded"},
            "nonempty_paths": ["rankings"],
            "minimums": {"summary.ranked_count": 1},
        },
    )
    assert not result_satisfies(event, {"minimums": {"summary.ranked_count": 4}})
