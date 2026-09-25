"""Fixed cross-carrier balances over registered PyPSA revisions."""

from __future__ import annotations

import math
from collections.abc import Mapping
from importlib.metadata import version
from pathlib import Path
from typing import Any

from pypsa_model_authority.store import ModelStore, ModelStoreError


PUBLISHED_SECTOR = (
    "sector.hydrogen_balance", "sector.heat_balance",
    "sector.hydrogen_storage", "sector.heat_storage", "sector.multiport_balance",
)
_FORMULATIONS = {
    "sector.hydrogen_balance": (
        "electricity-hydrogen", "hydrogen", "electrolyser", "hydrogen-demand",
        "single-snapshot-electricity-hydrogen-balance/1.0",
    ),
    "sector.heat_balance": (
        "electricity-heat-pump", "heat", "heat-pump", "heat-demand",
        "single-snapshot-electricity-heat-pump-balance/1.0",
    ),
}
_EXTRA_FORMULATIONS = {
    "sector.hydrogen_storage": ("hydrogen-storage", "two-snapshot-hydrogen-store-balance/1.0"),
    "sector.heat_storage": ("heat-pump-storage", "two-snapshot-variable-cop-heat-store-balance/1.0"),
    "sector.multiport_balance": ("chp-hydrogen-heat", "single-snapshot-multiport-chp-balance/1.0"),
}


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
    if capability in _FORMULATIONS:
        catalog_id, output_carrier, link_id, load_id, formulation = _FORMULATIONS[capability]
        valid_shape = (
            set(network.buses.carrier) == {"electricity", output_carrier}
            and tuple(network.links.index) == (link_id,)
            and tuple(network.loads.index) == (load_id,)
            and tuple(network.generators.index) == ("electricity-supply",)
            and len(network.snapshots) == 1
        )
    else:
        catalog_id, formulation = _EXTRA_FORMULATIONS[capability]
        valid_shape = (
            capability == "sector.hydrogen_storage"
            and len(network.snapshots) == 2
            and tuple(network.stores.index) == ("hydrogen-store",)
        ) or (
            capability == "sector.heat_storage"
            and len(network.snapshots) == 2
            and tuple(network.links.index) == ("heat-pump",)
            and tuple(network.stores.index) == ("heat-store",)
        ) or (
            capability == "sector.multiport_balance"
            and len(network.snapshots) == 1
            and set(network.links.index) == {"chp", "electrolyser"}
        )
    if revision.get("catalog_id") != catalog_id or not valid_shape:
        raise SectorError("invalid_model", "registered model has no published sector formulation")
    status, condition = network.optimize(
        solver_name="highs", log_to_console=False, include_objective_constant=False,
    )
    if (status, condition) != ("ok", "optimal"):
        raise SectorError("solve_failed", f"sector solve terminated with {status}/{condition}")
    if capability == "sector.hydrogen_storage":
        details = _hydrogen_storage_details(network)
    elif capability == "sector.heat_storage":
        details = _heat_storage_details(network)
    elif capability == "sector.multiport_balance":
        details = _multiport_details(network)
    else:
        details = _single_link_details(network, capability, link_id, load_id)
    details.update({
        "status": status, "condition": condition,
        "objective_kind": "operating_cost", "objective": _finite(network.objective),
    })
    document: dict[str, object] = {
        "schema": "pypsa-sector-result/1.0", "run_id": run_id,
        "source_binding_id": source_root.name, "target_binding_id": target_root.name,
        "model_ref": model_ref, "capability": capability,
        "formulation": formulation,
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


def _single_link_details(network: Any, capability: str, link_id: str, load_id: str) -> dict[str, object]:
    snapshot = network.snapshots[0]
    electricity = _finite(network.generators_t.p.at[snapshot, "electricity-supply"])
    input_energy = _finite(network.links_t.p0.at[snapshot, link_id])
    delivered = _finite(-network.links_t.p1.at[snapshot, link_id])
    demand = _finite(network.loads_t.p.at[snapshot, load_id])
    efficiency = _finite(network.links.at[link_id, "efficiency"])
    if any(value < -1e-6 for value in (electricity, input_energy, delivered)):
        raise SectorError("invalid_solver_result", "sector energy flow has an invalid sign")
    if (
        abs(electricity - input_energy) > 1e-6
        or abs(delivered - demand) > 1e-6
        or abs(delivered - input_energy * efficiency) > 1e-6
    ):
        raise SectorError("invalid_solver_result", "sector energy balance is inconsistent")
    if capability == "sector.hydrogen_balance":
        return {
            "electricity_generation_mwh": electricity,
            "conversion_input_mwh": input_energy,
            "hydrogen_delivered_mwh": delivered,
            "conversion_loss_mwh": _finite(input_energy - delivered),
            "conversion_efficiency": efficiency,
        }
    return {
        "electricity_generation_mwh": electricity,
        "electricity_input_mwh": input_energy,
        "heat_delivered_mwh": delivered,
        "coefficient_of_performance": efficiency,
    }


def _hydrogen_storage_details(network: Any) -> dict[str, object]:
    inputs = [_finite(value) for value in network.links_t.p0["electrolyser"].tolist()]
    outputs = [_finite(-value) for value in network.links_t.p1["electrolyser"].tolist()]
    demands = [_finite(value) for value in network.loads_t.p["hydrogen-demand"].tolist()]
    stored = [_finite(value) for value in network.stores_t.e["hydrogen-store"].tolist()]
    generation = [_finite(value) for value in network.generators_t.p["electricity-supply"].tolist()]
    previous = 0.0
    for produced, demand, level, electric, link_input in zip(outputs, demands, stored, generation, inputs):
        if (
            min(produced, demand, level, electric, link_input) < -1e-6
            or abs(electric - link_input) > 1e-6
            or abs(level - (previous + produced - demand)) > 1e-6
        ):
            raise SectorError("invalid_solver_result", "storage balance is inconsistent")
        previous = level
    return {
        "electricity_input_mwh": inputs,
        "hydrogen_delivered_mwh": demands,
        "hydrogen_store_energy_mwh": stored,
    }


def _multiport_details(network: Any) -> dict[str, object]:
    snapshot = network.snapshots[0]
    gas = _finite(network.links_t.p0.at[snapshot, "chp"])
    electricity = _finite(-network.links_t.p1.at[snapshot, "chp"])
    heat = _finite(-network.links_t.p2.at[snapshot, "chp"])
    hydrogen = _finite(-network.links_t.p1.at[snapshot, "electrolyser"])
    electrolysis_input = _finite(network.links_t.p0.at[snapshot, "electrolyser"])
    if (
        min(gas, electricity, heat, hydrogen, electrolysis_input) < -1e-6
        or abs(gas - _finite(network.generators_t.p.at[snapshot, "gas-supply"])) > 1e-6
        or abs(electricity - electrolysis_input - _finite(network.loads_t.p.at[snapshot, "electricity-demand"])) > 1e-6
        or abs(heat - _finite(network.loads_t.p.at[snapshot, "heat-demand"])) > 1e-6
        or abs(hydrogen - _finite(network.loads_t.p.at[snapshot, "hydrogen-demand"])) > 1e-6
    ):
        raise SectorError("invalid_solver_result", "multiport balance is inconsistent")
    return {
        "gas_input_mwh": gas,
        "electricity_delivered_mwh": electricity,
        "heat_delivered_mwh": heat,
        "hydrogen_delivered_mwh": hydrogen,
    }


def _heat_storage_details(network: Any) -> dict[str, object]:
    inputs = [_finite(value) for value in network.links_t.p0["heat-pump"].tolist()]
    outputs = [_finite(-value) for value in network.links_t.p1["heat-pump"].tolist()]
    coefficients = [_finite(value) for value in network.links_t.efficiency["heat-pump"].tolist()]
    demands = [_finite(value) for value in network.loads_t.p["heat-demand"].tolist()]
    stored = [_finite(value) for value in network.stores_t.e["heat-store"].tolist()]
    generation = [_finite(value) for value in network.generators_t.p["electricity-supply"].tolist()]
    previous = 0.0
    for produced, demand, level, electric, link_input, coefficient in zip(
        outputs, demands, stored, generation, inputs, coefficients, strict=True,
    ):
        if (
            min(produced, demand, level, electric, link_input, coefficient) < -1e-6
            or abs(electric - link_input) > 1e-6
            or abs(produced - link_input * coefficient) > 1e-6
            or abs(level - (previous + produced - demand)) > 1e-6
        ):
            raise SectorError("invalid_solver_result", "heat storage balance is inconsistent")
        previous = level
    return {
        "electricity_input_mwh": inputs,
        "coefficient_of_performance": coefficients,
        "heat_delivered_mwh": demands,
        "heat_store_energy_mwh": stored,
    }


def _finite(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SectorError("invalid_solver_result", "solver returned a non-numeric result")
    result = float(value)
    if not math.isfinite(result):
        raise SectorError("invalid_solver_result", "solver returned a non-finite result")
    return result
