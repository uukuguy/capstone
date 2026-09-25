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
