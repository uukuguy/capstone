"""Fixed electricity-to-hydrogen balance over a registered PyPSA revision."""

from __future__ import annotations

import math
from collections.abc import Mapping
from importlib.metadata import version
from pathlib import Path

from pypsa_model_authority.store import ModelStore, ModelStoreError


PUBLISHED_SECTOR = ("sector.hydrogen_balance",)


class SectorError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": str(self)}


def execute_sector(
    capability: str, arguments: Mapping[str, object],
    target_workspace: Path, source_workspace: Path, *, run_id: str,
) -> dict[str, object]:
    if capability not in PUBLISHED_SECTOR:
        raise SectorError("capability_not_published", "sector capability is not published")
    if not isinstance(arguments, Mapping) or set(arguments) != {"model_ref"}:
        raise SectorError("invalid_arguments", "sector arguments do not match the contract")
    model_ref = arguments["model_ref"]
    if not isinstance(model_ref, str):
        raise SectorError("invalid_arguments", "model_ref must be text")
    target_root = Path(target_workspace)
    source_root = Path(source_workspace)
    if (
        source_root.parent != target_root.parent
        or source_root.name == target_root.name
        or target_root.parent.parent.name != run_id
    ):
        raise SectorError("invalid_workspace", "sector workspaces do not share the current run")
    source = ModelStore(source_root, run_id=run_id)
    target = ModelStore(target_root, run_id=run_id)
    try:
        revision = source.load_model(model_ref)
        network = source.load_network(model_ref)
    except (ModelStoreError, ValueError, KeyError, TypeError) as exc:
        raise SectorError("invalid_model_ref", "model reference is unavailable in the current run") from exc
    if (
        revision.get("catalog_id") != "electricity-hydrogen"
        or set(network.buses.carrier) != {"electricity", "hydrogen"}
        or len(network.links) != 1
    ):
        raise SectorError("invalid_model", "registered model has no published sector formulation")
    status, condition = network.optimize(
        solver_name="highs", log_to_console=False, include_objective_constant=False,
    )
    if (status, condition) != ("ok", "optimal"):
        raise SectorError("solve_failed", f"sector solve terminated with {status}/{condition}")
    snapshot = network.snapshots[0]
    electricity = _finite(network.generators_t.p.at[snapshot, "electricity-supply"])
    input_energy = _finite(network.links_t.p0.at[snapshot, "electrolyser"])
    delivered = _finite(-network.links_t.p1.at[snapshot, "electrolyser"])
    demand = _finite(network.loads_t.p.at[snapshot, "hydrogen-demand"])
    objective = _finite(network.objective)
    loss = _finite(input_energy - delivered)
    if any(value < -1e-6 for value in (electricity, input_energy, delivered, loss)):
        raise SectorError("invalid_solver_result", "sector energy flow has an invalid sign")
    if abs(electricity - input_energy) > 1e-6 or abs(delivered - demand) > 1e-6:
        raise SectorError("invalid_solver_result", "sector energy balance is inconsistent")
    details: dict[str, object] = {
        "status": status, "condition": condition,
        "objective_kind": "operating_cost", "objective": objective,
        "electricity_generation_mwh": electricity,
        "conversion_input_mwh": input_energy,
        "hydrogen_delivered_mwh": delivered,
        "conversion_loss_mwh": loss,
        "conversion_efficiency": _finite(network.links.at["electrolyser", "efficiency"]),
    }
    document: dict[str, object] = {
        "schema": "pypsa-sector-result/1.0", "run_id": run_id,
        "source_binding_id": source_root.name, "target_binding_id": target_root.name,
        "model_ref": model_ref, "capability": capability,
        "formulation": "single-snapshot-electricity-hydrogen-balance/1.0",
        "solver": {"name": "highs", "version": version("highspy")},
        "status": status, "condition": condition, "details": details,
    }
    result_ref = target.persist("result", document)
    evidence_ref = target.persist("evidence", {
        "schema": "pypsa-sector-evidence/1.0", "run_id": run_id,
        "source_binding_id": source_root.name, "target_binding_id": target_root.name,
        "model_ref": model_ref, "result_ref": result_ref,
        "formulation": document["formulation"],
    })
    return {"model_ref": model_ref, "result_ref": result_ref, "evidence_refs": [evidence_ref], **details}


def _finite(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SectorError("invalid_solver_result", "solver returned a non-numeric result")
    result = float(value)
    if not math.isfinite(result):
        raise SectorError("invalid_solver_result", "solver returned a non-finite result")
    return result
