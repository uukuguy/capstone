"""Bounded semantic operations over registered PyPSA model revisions."""

from __future__ import annotations

import copy
import hashlib
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import pypsa  # pyright: ignore[reportMissingImports] -- resolved in the authority venv

from pypsa_model_authority import model_library
from pypsa_model_authority.catalog import load_registered_model
from pypsa_model_authority.store import (
    ModelStore, ModelStoreError, canonical_bytes, network_from_revision,
)


PUBLISHED_CAPABILITIES = (
    "model.open", "model.derive", "model.derive_series", "model.inspect", "model.validate",
    "model.topology",
)


class ModelCapabilityError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": str(self)}


def execute(
    capability: str, arguments: Mapping[str, object], workspace: Path, *, run_id: str
) -> dict[str, object]:
    store = ModelStore(workspace, run_id=run_id)
    if capability == "environment.describe":
        _exact_keys(arguments, set())
        return {
            "protocol": "pypsa-model-capability", "protocol_version": "1.0",
            "service": "pypsa-model-authority", "service_version": "0.1.0",
            "pypsa_version": pypsa.__version__,
            "executable_capabilities": [{"id": item} for item in PUBLISHED_CAPABILITIES],
        }
    if capability == "model.open":
        _exact_keys(arguments, {"catalog_id"})
        catalog_id = _text(arguments, "catalog_id")
        if catalog_id.startswith("pypsa-example/"):
            try:
                entry = model_library.get_official_example(catalog_id)
                model_library.verified_asset_path(catalog_id)
            except model_library.ModelLibraryError as exc:
                raise ModelCapabilityError("catalog_unavailable", str(exc)) from exc
            revision = {
                "schema": "pypsa-model-revision/1.1", "run_id": store.run_id,
                "catalog_id": entry.catalog_id, "parent_ref": None, "edits": [],
                "source_kind": "official-pypsa-netcdf",
                "source_sha256": entry.sha256, "source_size_bytes": entry.size_bytes,
                "pypsa_version": pypsa.__version__,
            }
            try:
                network_from_revision(revision)
            except (ModelStoreError, ValueError, KeyError, TypeError) as exc:
                raise ModelCapabilityError("invalid_registered_model", "official PyPSA Network cannot be loaded") from exc
            return _publish(store, capability, revision)
        try:
            source = load_registered_model(catalog_id)
        except LookupError as exc:
            raise ModelCapabilityError("catalog_not_found", "registered PyPSA model was not found") from exc
        revision = _revision(
            store.run_id, source, catalog_id=catalog_id,
            parent_ref=None, edits=[],
        )
        return _publish(store, capability, revision)
    if capability in {"model.derive", "model.derive_series"}:
        _exact_keys(arguments, {"model_ref", "load_id", "p_set_mw"})
        model_ref = _text(arguments, "model_ref")
        load_id = _text(arguments, "load_id")
        try:
            parent = store.load_model(model_ref)
        except ModelStoreError as exc:
            raise ModelCapabilityError("invalid_model_ref", str(exc)) from exc
        if parent.get("schema") == "pypsa-model-revision/1.1":
            raise ModelCapabilityError("unsupported_model", "official example demand derivation is not registered")
        if capability == "model.derive_series":
            raw = arguments.get("p_set_mw")
            if (
                not isinstance(raw, list) or not 2 <= len(raw) <= 24
                or len(raw) != len(cast(list[object], parent["snapshots"]))
            ):
                raise ModelCapabilityError("invalid_arguments", "snapshot demand must match the bounded model time index")
            value: float | list[float] = [_finite_nonnegative(item, "p_set_mw") for item in raw]
        else:
            value = _finite_nonnegative(arguments.get("p_set_mw"), "p_set_mw")
        components = cast(dict[str, Any], copy.deepcopy(parent["components"]))
        loads = cast(list[dict[str, Any]], components["loads"])
        matched = [item for item in loads if item["id"] == load_id]
        if len(matched) != 1:
            raise ModelCapabilityError("load_not_found", "load is not present in the model revision")
        if "scenario_p_set_mw" in matched[0]:
            raise ModelCapabilityError("invalid_model", "scenario demand requires a registered scenario formulation")
        matched[0]["p_set_mw"] = value
        revision = _revision(
            store.run_id,
            {"components": components, "snapshots": parent["snapshots"],
             "snapshot_weightings": parent["snapshot_weightings"],
             **({"investment_periods": parent["investment_periods"]} if "investment_periods" in parent else {}),
             **({"scenarios": parent["scenarios"]} if "scenarios" in parent else {})},
            catalog_id=str(parent["catalog_id"]), parent_ref=model_ref,
            edits=[*cast(list[dict[str, object]], parent["edits"]), {
                "operation": "load.p_set_series" if capability == "model.derive_series" else "load.p_set",
                "load_id": load_id, "p_set_mw": value,
            }],
        )
        return _publish(store, capability, revision)
    if capability == "model.inspect":
        _exact_keys(arguments, {"model_ref"})
        model_ref = _text(arguments, "model_ref")
        try:
            revision = store.load_model(model_ref)
            network = network_from_revision(revision)
        except ModelStoreError as exc:
            raise ModelCapabilityError("invalid_model_ref", str(exc)) from exc
        except (ValueError, KeyError, TypeError) as exc:
            raise ModelCapabilityError("invalid_model_ref", "model reference failed integrity verification") from exc
        details = {
            "component_counts": {
                "Bus": len(network.buses), "Load": len(network.loads),
                "Generator": len(network.generators), "Line": len(network.lines),
                **({"Carrier": len(network.carriers)} if len(network.carriers) else {}),
                **({"Link": len(network.links)} if len(network.links) else {}),
                **({"Store": len(network.stores)} if len(network.stores) else {}),
                **({"StorageUnit": len(network.storage_units)} if len(network.storage_units) else {}),
                **({"Transformer": len(network.transformers)} if len(network.transformers) else {}),
            },
            "load_p_set_mw": {
                str(name): float(value) for name, value in (
                    network.loads.p_set.head(10).items()
                    if revision.get("schema") == "pypsa-model-revision/1.1"
                    else network.loads.p_set.items()
                )
            },
            "snapshot_count": len(network.snapshots),
        }
        if revision.get("schema") == "pypsa-model-revision/1.1":
            details["omitted_load_count"] = max(0, len(network.loads) - 10)
        return _publish_result(store, capability, model_ref, details)
    if capability == "model.topology":
        _exact_keys(arguments, {"model_ref"})
        model_ref = _text(arguments, "model_ref")
        try:
            network = store.load_network(model_ref)
        except (ModelStoreError, ValueError, KeyError, TypeError) as exc:
            raise ModelCapabilityError("invalid_model_ref", "model reference failed integrity verification") from exc
        limit = 50
        buses = [
            {
                "id": str(name), "carrier": str(row.carrier),
                "x": _optional_finite(row.x), "y": _optional_finite(row.y),
            }
            for name, row in network.buses.sort_index().head(limit).iterrows()
        ]
        selected_buses = {bus["id"] for bus in buses}
        coordinate_pairs = {
            (bus["x"], bus["y"]) for bus in buses
            if bus["x"] is not None and bus["y"] is not None
        }
        coordinate_status = (
            "provided-unverified" if len(coordinate_pairs) >= 2
            else "schematic-required"
        )
        lines = [
            {
                "id": str(name), "from_bus": str(row.bus0), "to_bus": str(row.bus1),
                "s_nom_mva": _optional_finite(row.s_nom),
            }
            for name, row in network.lines.sort_index().iterrows()
            if str(row.bus0) in selected_buses and str(row.bus1) in selected_buses
        ][:limit]
        links = [
            {
                "id": str(name), "from_bus": str(row.bus0), "to_bus": str(row.bus1),
                "p_nom_mw": _optional_finite(row.p_nom),
            }
            for name, row in network.links.sort_index().iterrows()
            if str(row.bus0) in selected_buses and str(row.bus1) in selected_buses
        ][:limit]
        transformers = [
            {
                "id": str(name), "from_bus": str(row.bus0), "to_bus": str(row.bus1),
                "s_nom_mva": _optional_finite(row.s_nom),
            }
            for name, row in network.transformers.sort_index().iterrows()
            if str(row.bus0) in selected_buses and str(row.bus1) in selected_buses
        ][:limit]
        return _publish_result(store, capability, model_ref, {
            "buses": buses, "lines": lines, "links": links, "transformers": transformers,
            "omitted_counts": {
                "buses": max(0, len(network.buses) - limit),
                "lines": len(network.lines) - len(lines),
                "links": len(network.links) - len(links),
                "transformers": len(network.transformers) - len(transformers),
            },
            "selection": "first 50 buses by ID and their internal branches",
            "coordinate_status": coordinate_status,
            "snapshot_count": len(network.snapshots),
        })
    if capability == "model.validate":
        _exact_keys(arguments, {"model_ref"})
        model_ref = _text(arguments, "model_ref")
        try:
            revision = store.load_model(model_ref)
            network = network_from_revision(revision)
        except (ModelStoreError, ValueError, KeyError, TypeError) as exc:
            raise ModelCapabilityError("invalid_model_ref", "model reference failed validation") from exc
        if revision.get("schema") == "pypsa-model-revision/1.1":
            if not len(network.buses) or not len(network.snapshots):
                raise ModelCapabilityError("invalid_model", "official model has no buses or snapshots")
            checked_rules = ["unknown_buses", "time_series", "shapes"]
            try:
                network.consistency_check(strict=checked_rules)
            except ValueError as exc:
                raise ModelCapabilityError("invalid_model", "official model failed structural consistency checks") from exc
            return _publish_result(store, capability, model_ref, {
                "valid": True, "snapshot_count": len(network.snapshots),
                "component_counts": {"Bus": len(network.buses), "Line": len(network.lines)},
                "checked_rules": checked_rules,
            })
        component_data = cast(dict[str, Any], revision["components"])
        bus_ids = {str(bus["id"]) for bus in component_data["buses"]}
        endpoints = [
            *(item["bus"] for kind in ("loads", "generators", "stores") for item in component_data.get(kind, [])),
            *(item[key] for item in component_data.get("lines", []) for key in ("from_bus", "to_bus")),
            *(item[key] for item in component_data.get("links", []) for key in ("from_bus", "to_bus")),
            *(item["to_bus2"] for item in component_data.get("links", []) if "to_bus2" in item),
        ]
        if any(endpoint not in bus_ids for endpoint in endpoints):
            raise ModelCapabilityError("invalid_model", "registered model contains a disconnected component endpoint")
        scenarios = revision.get("scenarios")
        if isinstance(scenarios, dict):
            demand_details = {
                "scenario_total_demand_mw": {
                    scenario: _total_demand(component_data["loads"], len(network.snapshots), scenario)
                    for scenario in scenarios
                },
            }
        else:
            demand_details = {
                "total_demand_mw": _total_demand(component_data["loads"], len(network.snapshots), None),
            }
        return _publish_result(store, capability, model_ref, {
            "valid": True, "snapshot_count": len(network.snapshots), **demand_details,
        })
    raise ModelCapabilityError("capability_not_published", "PyPSA model capability is not published")


def _revision(
    run_id: str, source: Mapping[str, object], *, catalog_id: str,
    parent_ref: str | None, edits: list[dict[str, object]],
) -> dict[str, object]:
    components = cast(dict[str, object], copy.deepcopy(source["components"]))
    document: dict[str, object] = {
        "schema": "pypsa-model-revision/1.0", "run_id": run_id,
        "catalog_id": catalog_id, "parent_ref": parent_ref, "edits": edits,
        "components": components,
        "component_digest": hashlib.sha256(canonical_bytes(components)).hexdigest(),
        "snapshots": list(cast(list[object], source["snapshots"])),
        "snapshot_weightings": list(cast(list[object], source["snapshot_weightings"])),
        **({"investment_periods": list(cast(list[object], source["investment_periods"]))} if "investment_periods" in source else {}),
        **({"scenarios": dict(cast(dict[str, object], source["scenarios"]))} if "scenarios" in source else {}),
        "pypsa_version": pypsa.__version__,
    }
    try:
        network_from_revision(document)
    except (ValueError, KeyError, TypeError) as exc:
        raise ModelCapabilityError("invalid_registered_model", "registered PyPSA model cannot be constructed") from exc
    return document


def _publish(store: ModelStore, capability: str, revision: dict[str, object]) -> dict[str, object]:
    model_ref = store.persist("model", revision)
    return _publish_result(
        store, capability, model_ref,
        {"catalog_id": revision["catalog_id"], "parent_ref": revision["parent_ref"]},
    )


def _publish_result(
    store: ModelStore, capability: str, model_ref: str, details: dict[str, object]
) -> dict[str, object]:
    result: dict[str, object] = {
        "schema": "pypsa-model-result/1.0", "run_id": store.run_id,
        "capability": capability, "model_ref": model_ref, "details": details,
    }
    result_ref = store.persist("result", result)
    evidence_ref = store.persist("evidence", {
        "schema": "pypsa-model-evidence/1.0", "run_id": store.run_id,
        "model_ref": model_ref, "result_ref": result_ref,
    })
    return {
        "model_ref": model_ref, "result_ref": result_ref,
        "evidence_refs": [evidence_ref], **details,
    }


def _exact_keys(arguments: Mapping[str, object], expected: set[str]) -> None:
    if not isinstance(arguments, Mapping) or set(arguments) != expected:
        raise ModelCapabilityError("invalid_arguments", "capability arguments do not match the published contract")


def _text(arguments: Mapping[str, object], key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value or len(value) > 200:
        raise ModelCapabilityError("invalid_arguments", f"{key} must be bounded text")
    return value


def _finite_nonnegative(value: object, key: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ModelCapabilityError("invalid_arguments", f"{key} must be a finite nonnegative number")
    return float(value)


def _optional_finite(value: float | int | str | None) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _total_demand(loads: list[dict[str, Any]], count: int, scenario: str | None) -> list[float]:
    totals = [0.0] * count
    for load in loads:
        scenario_values = load.get("scenario_p_set_mw", {})
        demand = scenario_values.get(scenario, load["p_set_mw"]) if scenario is not None else load["p_set_mw"]
        values = demand if isinstance(demand, list) else [demand] * count
        if len(values) != count:
            raise ModelCapabilityError("invalid_model", "registered demand time index is inconsistent")
        for index, raw in enumerate(values):
            totals[index] += _finite_nonnegative(raw, "p_set_mw")
    return totals
