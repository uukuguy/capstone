"""Fixed capacity-expansion formulation over registered PyPSA revisions."""

from __future__ import annotations

import math
from collections.abc import Mapping
from importlib.metadata import version
from pathlib import Path

from pypsa_model_authority.store import ModelStore, ModelStoreError


PUBLISHED_PLANNING = (
    "planning.capacity_expand", "planning.capacity_commitment",
    "planning.multi_period", "planning.stochastic", "planning.near_optimal_capacity",
)


class PlanningError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": str(self)}


def execute_planning(
    capability: str, arguments: Mapping[str, object],
    target_workspace: Path, source_workspace: Path, *, run_id: str,
) -> dict[str, object]:
    if capability not in PUBLISHED_PLANNING:
        raise PlanningError("capability_not_published", "planning capability is not published")
    if not isinstance(arguments, Mapping) or set(arguments) != {"model_ref"}:
        raise PlanningError("invalid_arguments", "planning arguments do not match the contract")
    model_ref = arguments["model_ref"]
    if not isinstance(model_ref, str):
        raise PlanningError("invalid_arguments", "model_ref must be text")
    target_root = Path(target_workspace)
    source_root = Path(source_workspace)
    if (
        source_root.parent != target_root.parent
        or source_root.name == target_root.name
        or target_root.parent.parent.name != run_id
    ):
        raise PlanningError("invalid_workspace", "planning workspaces do not share the current run")
    source = ModelStore(source_root, run_id=run_id)
    target = ModelStore(target_root, run_id=run_id)
    try:
        revision = source.load_model(model_ref)
        network = source.load_network(model_ref)
    except (ModelStoreError, ValueError, KeyError, TypeError) as exc:
        raise PlanningError("invalid_model_ref", "model reference is unavailable in the current run") from exc
    expected_catalog = {
        "planning.capacity_expand": "capacity-two-bus",
        "planning.capacity_commitment": "capacity-commitment",
        "planning.multi_period": "capacity-pathway",
        "planning.stochastic": "capacity-scenarios",
        "planning.near_optimal_capacity": "capacity-two-bus",
    }[capability]
    if revision.get("catalog_id") != expected_catalog or not bool(network.generators.p_nom_extendable.any()):
        raise PlanningError("invalid_model", "registered model has no published expansion formulation")
    status, condition = network.optimize(
        solver_name="highs", log_to_console=False, include_objective_constant=False,
        multi_investment_periods=capability == "planning.multi_period",
    )
    if (status, condition) != ("ok", "optimal"):
        raise PlanningError("solve_failed", f"planning terminated with {status}/{condition}")
    baseline_cost = _finite(network.objective)
    if capability == "planning.near_optimal_capacity":
        status, condition = network.optimize.optimize_mga(
            sense="max", slack=0.05, solver_name="highs", log_to_console=False,
        )
        if (status, condition) != ("ok", "optimal"):
            raise PlanningError("solve_failed", f"alternative planning terminated with {status}/{condition}")
    generator_table = (
        network.generators.xs("low", level="scenario")
        if capability == "planning.stochastic" else network.generators
    )
    capacities = {
        str(name): _finite(value)
        for name, value in generator_table.p_nom_opt.items()
        if bool(generator_table.at[name, "p_nom_extendable"])
    }
    investment_cost = _finite(sum(
        capacities[str(name)] * float(generator_table.at[name, "capital_cost"])
        for name in generator_table.index if str(name) in capacities
    ))
    if capability == "planning.multi_period":
        operating = _finite(sum(
            float(network.generators_t.p.at[snapshot, name])
            * float(network.generators.at[name, "marginal_cost"])
            * float(network.snapshot_weightings.objective.at[snapshot])
            * float(network.investment_period_weightings.objective.at[snapshot[0]])
            for snapshot in network.snapshots for name in network.generators.index
        ))
        investment_cost = _finite(network.objective - operating)
    objective = _finite(network.objective)
    operating_cost = _finite(objective - investment_cost)
    if capability == "planning.near_optimal_capacity":
        operating_cost = _finite(sum(
            float(network.generators_t.p.at[snapshot, name])
            * float(network.generators.at[name, "marginal_cost"])
            * float(network.snapshot_weightings.generators.at[snapshot])
            for snapshot in network.snapshots for name in network.generators.index
        ))
        objective = _finite(sum(capacities.values()))
    details: dict[str, object] = {
        "status": status, "condition": condition,
        "objective_kind": "investment_plus_operating_cost",
        "objective": objective,
        "investment_cost": investment_cost,
        "operating_cost": operating_cost,
        "generator_capacity_mw": capacities,
    }
    if capability == "planning.capacity_commitment":
        dispatch = [_finite(value) for value in network.generators_t.p["supply"].tolist()]
        status_values = [_finite(value) for value in network.generators_t.status["supply"].tolist()]
        status_flags = [int(round(value)) for value in status_values]
        if (
            any(abs(value - flag) > 1e-6 for value, flag in zip(status_values, status_flags, strict=True))
            or any(flag not in (0, 1) for flag in status_flags)
            or any(value < -1e-6 for value in dispatch)
            or any(
                abs(dispatch[index] - _finite(network.loads_t.p.at[snapshot, "demand"])) > 1e-6
                for index, snapshot in enumerate(network.snapshots)
            )
        ):
            raise PlanningError("invalid_solver_result", "capacity commitment is inconsistent")
        details["commitment_status"] = status_flags
        details["dispatch_mwh"] = dispatch
    elif capability == "planning.multi_period":
        details["objective_kind"] = "discounted_pathway_cost"
        details["investment_periods"] = [int(period) for period in network.investment_periods]
    elif capability == "planning.stochastic":
        snapshot = network.snapshots[0]
        details["objective_kind"] = "investment_plus_expected_operating_cost"
        details["scenarios"] = {str(name): _finite(weight) for name, weight in network.scenario_weightings.weight.items()}
        details["scenario_dispatch_mwh"] = {
            str(scenario): {
                str(name): _finite(network.generators_t.p.at[snapshot, (scenario, name)])
                for name in generator_table.index
            }
            for scenario in network.scenarios
        }
    elif capability == "planning.near_optimal_capacity":
        system_cost = _finite(investment_cost + operating_cost)
        if system_cost > baseline_cost * 1.05 + 1e-5:
            raise PlanningError("invalid_solver_result", "alternative exceeds its system cost budget")
        details["objective_kind"] = "maximized_installed_generation_capacity_mw"
        details["baseline_system_cost"] = baseline_cost
        details["system_cost"] = system_cost
        details["cost_slack"] = 0.05
    document: dict[str, object] = {
        "schema": "pypsa-planning-result/1.0", "run_id": run_id,
        "source_binding_id": source_root.name, "target_binding_id": target_root.name,
        "model_ref": model_ref, "capability": capability,
        "formulation": (
            "single-period-generator-capacity-expansion/1.0"
            if capability == "planning.capacity_expand"
            else "capacity-and-unit-commitment/1.0" if capability == "planning.capacity_commitment"
            else "two-period-generator-investment-pathway/1.0"
            if capability == "planning.multi_period"
            else "two-scenario-shared-investment/1.0" if capability == "planning.stochastic"
            else "five-percent-near-optimal-capacity/1.0"
        ),
        "solver": {"name": "highs", "version": version("highspy")},
        "status": status, "condition": condition, "details": details,
    }
    result_ref = target.persist("result", document)
    evidence_ref = target.persist("evidence", {
        "schema": "pypsa-planning-evidence/1.0", "run_id": run_id,
        "source_binding_id": source_root.name, "target_binding_id": target_root.name,
        "model_ref": model_ref, "result_ref": result_ref,
        "formulation": document["formulation"],
    })
    return {"model_ref": model_ref, "result_ref": result_ref, "evidence_refs": [evidence_ref], **details}


def _finite(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PlanningError("invalid_solver_result", "solver returned a non-numeric result")
    result = float(value)
    if not math.isfinite(result):
        raise PlanningError("invalid_solver_result", "solver returned a non-finite result")
    return result
