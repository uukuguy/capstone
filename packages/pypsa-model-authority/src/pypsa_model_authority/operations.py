"""Bounded semantic operations over registered PyPSA model revisions."""

from __future__ import annotations

import copy
import hashlib
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import pypsa  # pyright: ignore[reportMissingImports] -- resolved in the authority venv

from pypsa_model_authority.catalog import load_registered_model
from pypsa_model_authority.store import (
    ModelStore, ModelStoreError, canonical_bytes, network_from_revision,
)


PUBLISHED_CAPABILITIES = ("model.open", "model.derive", "model.inspect")


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
        try:
            source = load_registered_model(catalog_id)
        except LookupError as exc:
            raise ModelCapabilityError("catalog_not_found", "registered PyPSA model was not found") from exc
        revision = _revision(
            store.run_id, source, catalog_id=catalog_id,
            parent_ref=None, edits=[],
        )
        return _publish(store, capability, revision)
    if capability == "model.derive":
        _exact_keys(arguments, {"model_ref", "load_id", "p_set_mw"})
        model_ref = _text(arguments, "model_ref")
        load_id = _text(arguments, "load_id")
        value = _finite_nonnegative(arguments.get("p_set_mw"), "p_set_mw")
        try:
            parent = store.load_model(model_ref)
        except ModelStoreError as exc:
            raise ModelCapabilityError("invalid_model_ref", str(exc)) from exc
        components = cast(dict[str, Any], copy.deepcopy(parent["components"]))
        loads = cast(list[dict[str, Any]], components["loads"])
        matched = [item for item in loads if item["id"] == load_id]
        if len(matched) != 1:
            raise ModelCapabilityError("load_not_found", "load is not present in the model revision")
        matched[0]["p_set_mw"] = value
        revision = _revision(
            store.run_id,
            {"components": components, "snapshots": parent["snapshots"],
             "snapshot_weightings": parent["snapshot_weightings"],
             **({"investment_periods": parent["investment_periods"]} if "investment_periods" in parent else {}),
             **({"scenarios": parent["scenarios"]} if "scenarios" in parent else {})},
            catalog_id=str(parent["catalog_id"]), parent_ref=model_ref,
            edits=[*cast(list[dict[str, object]], parent["edits"]), {"operation": "load.p_set", "load_id": load_id, "p_set_mw": value}],
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
            },
            "load_p_set_mw": {
                str(name): float(value) for name, value in network.loads.p_set.items()
            },
            "snapshot_count": len(network.snapshots),
        }
        return _publish_result(store, capability, model_ref, details)
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
