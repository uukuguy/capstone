"""Fixed capacity-expansion formulation over registered PyPSA revisions."""

from __future__ import annotations

import math
from collections.abc import Mapping
from importlib.metadata import version
from pathlib import Path

from pypsa_model_authority.store import ModelStore, ModelStoreError


PUBLISHED_PLANNING = ("planning.capacity_expand",)


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
    if revision.get("catalog_id") != "capacity-two-bus" or not bool(network.generators.p_nom_extendable.any()):
        raise PlanningError("invalid_model", "registered model has no published expansion formulation")
    status, condition = network.optimize(
        solver_name="highs", log_to_console=False, include_objective_constant=False,
    )
    if (status, condition) != ("ok", "optimal"):
        raise PlanningError("solve_failed", f"planning terminated with {status}/{condition}")
    capacities = {
        str(name): _finite(value)
        for name, value in network.generators.p_nom_opt.items()
        if bool(network.generators.at[name, "p_nom_extendable"])
    }
    investment_cost = _finite(sum(
        capacities[str(name)] * float(network.generators.at[name, "capital_cost"])
        for name in network.generators.index if str(name) in capacities
    ))
    operating_cost = _finite(sum(
        float(network.generators_t.p.at[snapshot, name])
        * float(network.generators.at[name, "marginal_cost"])
        * float(network.snapshot_weightings.generators.at[snapshot])
        for snapshot in network.snapshots for name in network.generators.index
    ))
    objective = _finite(network.objective)
    details: dict[str, object] = {
        "status": status, "condition": condition,
        "objective_kind": "investment_plus_operating_cost",
        "objective": objective,
        "investment_cost": investment_cost,
        "operating_cost": operating_cost,
        "generator_capacity_mw": capacities,
    }
    document: dict[str, object] = {
        "schema": "pypsa-planning-result/1.0", "run_id": run_id,
        "source_binding_id": source_root.name, "target_binding_id": target_root.name,
        "model_ref": model_ref, "capability": capability,
        "formulation": "single-period-generator-capacity-expansion/1.0",
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
