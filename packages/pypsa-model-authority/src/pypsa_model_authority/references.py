"""Public, bounded verification API for authority-owned run artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pypsa_model_authority.store import ModelStore, ModelStoreError


@dataclass(frozen=True, slots=True)
class VerifiedDocument:
    reference: str
    document: dict[str, object]
    path: Path


def verify_model(workspace: Path, run_id: str, reference: str) -> VerifiedDocument:
    store = ModelStore(workspace, run_id=run_id)
    document = store.load_model(reference)
    return VerifiedDocument(reference, document, store.model_path(reference))


def verify_result(workspace: Path, run_id: str, reference: str) -> VerifiedDocument:
    store = ModelStore(workspace, run_id=run_id)
    document = store.load(reference, "result")
    model_ref = document.get("model_ref")
    if not isinstance(model_ref, str):
        raise ModelStoreError("result has no model reference")
    store.load_model(model_ref)
    if document.get("schema") != "pypsa-model-result/1.0":
        raise ModelStoreError("result schema is invalid")
    return VerifiedDocument(reference, document, store.artifact_path(reference, "result"))


def verify_evidence(workspace: Path, run_id: str, reference: str) -> VerifiedDocument:
    store = ModelStore(workspace, run_id=run_id)
    document = store.load(reference, "evidence")
    result_ref = document.get("result_ref")
    model_ref = document.get("model_ref")
    if not isinstance(result_ref, str) or not isinstance(model_ref, str):
        raise ModelStoreError("evidence lineage is incomplete")
    result = verify_result(workspace, run_id, result_ref)
    if result.document.get("model_ref") != model_ref:
        raise ModelStoreError("evidence model lineage is invalid")
    if document.get("schema") != "pypsa-model-evidence/1.0":
        raise ModelStoreError("evidence schema is invalid")
    return VerifiedDocument(reference, document, store.artifact_path(reference, "evidence"))


def verify_operation_result(
    workspace: Path, source_workspace: Path, run_id: str, reference: str
) -> VerifiedDocument:
    """Verify a target-owned operation result against its source model revision."""
    store = ModelStore(workspace, run_id=run_id)
    document = store.load(reference, "result")
    model_ref = document.get("model_ref")
    if (
        document.get("schema") != "pypsa-operation-result/1.0"
        or document.get("target_binding_id") != Path(workspace).name
        or document.get("source_binding_id") != Path(source_workspace).name
        or document.get("status") != "ok"
        or not isinstance(model_ref, str)
    ):
        raise ModelStoreError("operation result lineage is invalid")
    verify_model(source_workspace, run_id, model_ref)
    details = document.get("details")
    if not isinstance(details, dict) or details.get("status") != "ok":
        raise ModelStoreError("operation result details are invalid")
    predecessor = details.get("dispatch_result_ref")
    if predecessor is not None:
        if not isinstance(predecessor, str):
            raise ModelStoreError("operation result predecessor is invalid")
        earlier = verify_operation_result(workspace, source_workspace, run_id, predecessor).document
        if (
            earlier.get("schema") != "pypsa-operation-result/1.0"
            or earlier.get("capability") != "operations.dispatch"
            or earlier.get("model_ref") != model_ref
        ):
            raise ModelStoreError("operation result predecessor lineage is invalid")
    return VerifiedDocument(reference, document, store.artifact_path(reference, "result"))


def verify_operation_evidence(
    workspace: Path, source_workspace: Path, run_id: str, reference: str
) -> VerifiedDocument:
    store = ModelStore(workspace, run_id=run_id)
    document = store.load(reference, "evidence")
    result_ref = document.get("result_ref")
    if (
        document.get("schema") != "pypsa-operation-evidence/1.0"
        or document.get("target_binding_id") != Path(workspace).name
        or document.get("source_binding_id") != Path(source_workspace).name
        or not isinstance(result_ref, str)
    ):
        raise ModelStoreError("operation evidence lineage is invalid")
    result = verify_operation_result(workspace, source_workspace, run_id, result_ref)
    if (
        document.get("model_ref") != result.document.get("model_ref")
        or document.get("formulation") != result.document.get("formulation")
    ):
        raise ModelStoreError("operation evidence result binding differs")
    return VerifiedDocument(reference, document, store.artifact_path(reference, "evidence"))


def verify_planning_result(
    workspace: Path, source_workspace: Path, run_id: str, reference: str
) -> VerifiedDocument:
    store = ModelStore(workspace, run_id=run_id)
    document = store.load(reference, "result")
    model_ref = document.get("model_ref")
    if (
        document.get("schema") != "pypsa-planning-result/1.0"
        or document.get("target_binding_id") != Path(workspace).name
        or document.get("source_binding_id") != Path(source_workspace).name
        or document.get("capability") not in {
            "planning.capacity_expand", "planning.capacity_commitment", "planning.multi_period",
            "planning.stochastic", "planning.near_optimal_capacity",
        }
        or document.get("status") != "ok"
        or not isinstance(model_ref, str)
    ):
        raise ModelStoreError("planning result lineage is invalid")
    verify_model(source_workspace, run_id, model_ref)
    details = document.get("details")
    if not isinstance(details, dict) or details.get("status") != "ok":
        raise ModelStoreError("planning result details are invalid")
    return VerifiedDocument(reference, document, store.artifact_path(reference, "result"))


def verify_planning_evidence(
    workspace: Path, source_workspace: Path, run_id: str, reference: str
) -> VerifiedDocument:
    store = ModelStore(workspace, run_id=run_id)
    document = store.load(reference, "evidence")
    result_ref = document.get("result_ref")
    if (
        document.get("schema") != "pypsa-planning-evidence/1.0"
        or document.get("target_binding_id") != Path(workspace).name
        or document.get("source_binding_id") != Path(source_workspace).name
        or not isinstance(result_ref, str)
    ):
        raise ModelStoreError("planning evidence lineage is invalid")
    result = verify_planning_result(workspace, source_workspace, run_id, result_ref)
    if (
        document.get("model_ref") != result.document.get("model_ref")
        or document.get("formulation") != result.document.get("formulation")
    ):
        raise ModelStoreError("planning evidence result binding differs")
    return VerifiedDocument(reference, document, store.artifact_path(reference, "evidence"))


def verify_sector_result(
    workspace: Path, source_workspace: Path, run_id: str, reference: str
) -> VerifiedDocument:
    store = ModelStore(workspace, run_id=run_id)
    document = store.load(reference, "result")
    model_ref = document.get("model_ref")
    if (
        document.get("schema") != "pypsa-sector-result/1.0"
        or document.get("target_binding_id") != Path(workspace).name
        or document.get("source_binding_id") != Path(source_workspace).name
        or document.get("capability") not in {
            "sector.hydrogen_balance", "sector.heat_balance",
            "sector.hydrogen_storage", "sector.heat_storage", "sector.multiport_balance",
        }
        or document.get("status") != "ok"
        or document.get("condition") != "optimal"
        or not isinstance(model_ref, str)
    ):
        raise ModelStoreError("sector result lineage is invalid")
    verify_model(source_workspace, run_id, model_ref)
    details = document.get("details")
    if not isinstance(details, dict) or details.get("status") != "ok":
        raise ModelStoreError("sector result details are invalid")
    return VerifiedDocument(reference, document, store.artifact_path(reference, "result"))


def verify_sector_evidence(
    workspace: Path, source_workspace: Path, run_id: str, reference: str
) -> VerifiedDocument:
    store = ModelStore(workspace, run_id=run_id)
    document = store.load(reference, "evidence")
    result_ref = document.get("result_ref")
    if (
        document.get("schema") != "pypsa-sector-evidence/1.0"
        or document.get("target_binding_id") != Path(workspace).name
        or document.get("source_binding_id") != Path(source_workspace).name
        or not isinstance(result_ref, str)
    ):
        raise ModelStoreError("sector evidence lineage is invalid")
    result = verify_sector_result(workspace, source_workspace, run_id, result_ref)
    if (
        document.get("model_ref") != result.document.get("model_ref")
        or document.get("formulation") != result.document.get("formulation")
    ):
        raise ModelStoreError("sector evidence result binding differs")
    return VerifiedDocument(reference, document, store.artifact_path(reference, "evidence"))
