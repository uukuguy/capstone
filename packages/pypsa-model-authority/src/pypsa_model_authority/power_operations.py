"""Fixed PyPSA solver workflows over registered, immutable source revisions."""

from __future__ import annotations

import math
from collections.abc import Mapping
from importlib.metadata import version
from pathlib import Path
from typing import Any

from pypsa_model_authority.store import ModelStore, ModelStoreError


PUBLISHED_OPERATIONS = (
    "operations.dispatch",
    "operations.commitment",
    "operations.security_dispatch",
    "operations.ac_validate",
)


class OperationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": str(self)}


def execute_operation(
    capability: str,
    arguments: Mapping[str, object],
    target_workspace: Path,
    source_workspace: Path,
    *,
    run_id: str,
) -> dict[str, object]:
    """Execute one allowlisted formulation; publish only successful results."""
    if capability not in PUBLISHED_OPERATIONS:
        raise OperationError("capability_not_published", "operation is not published")
    expected = {"model_ref"}
    if capability == "operations.security_dispatch":
        expected.add("outage_set_id")
    if capability == "operations.ac_validate":
        expected.add("dispatch_result_ref")
    if not isinstance(arguments, Mapping) or set(arguments) != expected:
        raise OperationError("invalid_arguments", "operation arguments do not match the contract")
    model_ref = arguments["model_ref"]
    if not isinstance(model_ref, str):
        raise OperationError("invalid_arguments", "model_ref must be text")

    target_root = Path(target_workspace)
    source_root = Path(source_workspace)
    if (
        source_root.parent != target_root.parent
        or source_root.name == target_root.name
        or target_root.parent.parent.name != run_id
    ):
        raise OperationError("invalid_workspace", "operation workspaces do not share the current run")
    source = ModelStore(source_root, run_id=run_id)
    target = ModelStore(target_root, run_id=run_id)
    try:
        revision = source.load_model(model_ref)
        network = source.load_network(model_ref)
    except (ModelStoreError, ValueError, KeyError, TypeError) as exc:
        raise OperationError("invalid_model_ref", "model reference is unavailable in the current run") from exc

    if capability == "operations.ac_validate":
        return _validate_ac(target, network, revision, model_ref, arguments)
    if capability == "operations.security_dispatch":
        if arguments["outage_set_id"] != "triangle-l3" or revision.get("catalog_id") != "security-triangle":
            raise OperationError("invalid_outage_set", "outage set is not registered for this model")
        status, condition = network.optimize.optimize_security_constrained(
            branch_outages=["l3"], solver_name="highs", log_to_console=False,
        )
        formulation = "security-constrained-linear-opf/1.0"
        objective_kind = "security_constrained_operating_cost"
    elif capability == "operations.commitment":
        if not network.generators.committable.any():
            raise OperationError("invalid_model", "registered model has no committable generator")
        status, condition = network.optimize(
            solver_name="highs", log_to_console=False,
            include_objective_constant=False,
        )
        formulation = "fixed-capacity-unit-commitment/1.0"
        objective_kind = "operating_and_startup_cost"
    else:
        if network.generators.committable.any() or network.generators.p_nom_extendable.any():
            raise OperationError("invalid_model", "dispatch requires fixed, noncommittable generators")
        status, condition = network.optimize(
            solver_name="highs", log_to_console=False,
            include_objective_constant=False,
        )
        formulation = "fixed-capacity-linear-dispatch/1.0"
        objective_kind = "operating_cost"
    if (status, condition) != ("ok", "optimal"):
        raise OperationError("solve_failed", f"operation terminated with {status}/{condition}")

    details: dict[str, object] = {
        "status": status,
        "condition": condition,
        "objective_kind": objective_kind,
        "objective": _finite(network.objective),
        "generator_dispatch_mw": _series_by_component(network.generators_t.p),
    }
    if capability == "operations.commitment":
        details["commitment_status"] = {
            name: [int(round(value)) for value in values]
            for name, values in _series_by_component(network.generators_t.status).items()
        }
    if capability == "operations.security_dispatch":
        details["outage_set_id"] = "triangle-l3"
    return _publish(target, source_root.name, model_ref, capability, formulation, details)


def _validate_ac(
    target: ModelStore, network: Any, revision: Mapping[str, object],
    model_ref: str, arguments: Mapping[str, object],
) -> dict[str, object]:
    del revision
    dispatch_ref = arguments["dispatch_result_ref"]
    if not isinstance(dispatch_ref, str):
        raise OperationError("invalid_arguments", "dispatch_result_ref must be text")
    try:
        dispatch = target.load(dispatch_ref, "result")
    except ModelStoreError as exc:
        raise OperationError("invalid_dispatch_ref", "dispatch result is unavailable in the current run") from exc
    if (
        dispatch.get("schema") != "pypsa-operation-result/1.0"
        or dispatch.get("capability") != "operations.dispatch"
        or dispatch.get("model_ref") != model_ref
        or dispatch.get("status") != "ok"
    ):
        raise OperationError("invalid_dispatch_ref", "dispatch result does not match the model revision")
    raw = dispatch.get("details")
    if not isinstance(raw, dict) or not isinstance(raw.get("generator_dispatch_mw"), dict):
        raise OperationError("invalid_dispatch_ref", "dispatch result has no bounded schedule")
    schedule = raw["generator_dispatch_mw"]
    if set(schedule) != set(network.generators.index):
        raise OperationError("invalid_dispatch_ref", "dispatch schedule does not match generators")
    for name, values in schedule.items():
        if not isinstance(values, list) or len(values) != len(network.snapshots):
            raise OperationError("invalid_dispatch_ref", "dispatch schedule is invalid")
        network.generators_t.p[name] = [_finite(value) for value in values]
    report = network.pf(use_seed=True)
    if not bool(report["converged"].to_numpy().all()):
        raise OperationError("ac_not_converged", "AC validation did not converge")
    details: dict[str, object] = {
        "status": "ok", "condition": "converged",
        "objective_kind": "not_applicable", "objective": None,
        "dispatch_result_ref": dispatch_ref,
        "converged": True,
        "bus_voltage_pu": _series_by_component(network.buses_t.v_mag_pu),
        "line_active_power_mw": _series_by_component(network.lines_t.p0),
    }
    return _publish(
        target, str(dispatch["source_binding_id"]), model_ref,
        "operations.ac_validate", "post-dispatch-ac-power-flow/1.0", details,
    )


def _series_by_component(frame: Any) -> dict[str, list[float]]:
    return {
        str(name): [_finite(value) for value in frame[name].tolist()]
        for name in frame.columns
    }


def _finite(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OperationError("invalid_solver_result", "solver returned a non-numeric result")
    result = float(value)
    if not math.isfinite(result):
        raise OperationError("invalid_solver_result", "solver returned a non-finite result")
    return result


def _publish(
    target: ModelStore, source_binding_id: str, model_ref: str,
    capability: str, formulation: str, details: dict[str, object],
) -> dict[str, object]:
    solver_name = "pypsa-ac-pf" if capability == "operations.ac_validate" else "highs"
    solver_version = version("pypsa") if solver_name == "pypsa-ac-pf" else version("highspy")
    document: dict[str, object] = {
        "schema": "pypsa-operation-result/1.0", "run_id": target.run_id,
        "source_binding_id": source_binding_id,
        "target_binding_id": target.root.name,
        "model_ref": model_ref, "capability": capability,
        "formulation": formulation,
        "solver": {"name": solver_name, "version": solver_version},
        "status": details["status"], "condition": details["condition"],
        "details": details,
    }
    result_ref = target.persist("result", document)
    evidence_ref = target.persist("evidence", {
        "schema": "pypsa-operation-evidence/1.0", "run_id": target.run_id,
        "source_binding_id": source_binding_id,
        "target_binding_id": target.root.name,
        "model_ref": model_ref, "result_ref": result_ref,
        "formulation": formulation,
    })
    return {
        "model_ref": model_ref, "result_ref": result_ref,
        "evidence_refs": [evidence_ref], **details,
    }
