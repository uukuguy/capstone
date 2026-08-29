from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from inventory_domain.authority import (
    InventoryArtifactAuthority,
    InventoryIntegrityError,
)
from inventory_domain.execution import InventoryctlExecutor


def _result(workspace: Path):
    executable = shutil.which("inventoryctl")
    assert executable is not None
    executor = InventoryctlExecutor(executable=Path(executable), workspace=workspace)
    opened = executor.invoke("catalog.open", {"catalog_id": "warehouse-a"})
    result = executor.invoke(
        "asset.list", {"context_ref": opened["context_ref"], "limit": 2}
    )
    return executor, opened, result


def _artifact_path(workspace: Path, reference: str, directory: str) -> Path:
    return workspace / "evidence" / directory / f"{reference.rsplit(':', 1)[1]}.json"


def test_authority_admits_only_linked_current_run_artifacts(tmp_path) -> None:
    _, _, result = _result(tmp_path)
    authority = InventoryArtifactAuthority(tmp_path)

    admitted = authority.admit(
        "asset.list", result, tuple(result["evidence_refs"])
    )

    assert [item.reference for item in admitted.context] == [result["context_ref"]]
    assert [item.reference for item in admitted.results] == [result["result_ref"]]
    assert [item.reference for item in admitted.evidence] == result["evidence_refs"]
    assert authority.verify_result(result["result_ref"]).document["capability"] == (
        "asset.list"
    )
    assert authority.audit_answer_references(
        tuple(result["evidence_refs"]), (result["result_ref"],)
    ) == ()


def test_foreign_run_and_reference_kind_fail_closed(tmp_path) -> None:
    _, _, result = _result(tmp_path / "run-a")
    foreign = tmp_path / "run-b"
    foreign.mkdir()
    authority = InventoryArtifactAuthority(foreign)

    with pytest.raises(InventoryIntegrityError, match=r"current.?run"):
        authority.verify_result(result["result_ref"])
    with pytest.raises(InventoryIntegrityError, match="result reference"):
        InventoryArtifactAuthority(tmp_path / "run-a").verify_result(
            result["evidence_refs"][0]
        )


def test_tampered_or_symlinked_result_fails_closed(tmp_path) -> None:
    _, _, result = _result(tmp_path)
    result_path = _artifact_path(tmp_path, result["result_ref"], "results")
    original = result_path.read_bytes()
    result_path.write_bytes(original.replace(b'"count":2', b'"count":9'))

    with pytest.raises(InventoryIntegrityError, match="digest"):
        InventoryArtifactAuthority(tmp_path).verify_result(result["result_ref"])

    result_path.write_bytes(original)
    replacement = tmp_path / "replacement.json"
    replacement.write_bytes(original)
    result_path.unlink()
    result_path.symlink_to(replacement)
    with pytest.raises(InventoryIntegrityError, match="without following links"):
        InventoryArtifactAuthority(tmp_path).verify_result(result["result_ref"])


def test_symlinked_workspace_root_fails_closed(tmp_path) -> None:
    real = tmp_path / "real"
    _result(real)
    linked = tmp_path / "linked"
    linked.symlink_to(real, target_is_directory=True)

    with pytest.raises(InventoryIntegrityError, match="workspace root"):
        InventoryArtifactAuthority(linked).verify_result(
            next((real / "evidence/results").glob("*.json")).stem.join(
                ["inventory-result:sha256:", ""]
            )
        )


def test_answer_audit_reports_unlinked_evidence(tmp_path) -> None:
    executor, opened, first = _result(tmp_path)
    second = executor.invoke(
        "stock.summary", {"context_ref": opened["context_ref"]}
    )
    authority = InventoryArtifactAuthority(tmp_path)

    diagnostics = authority.audit_answer_references(
        tuple(second["evidence_refs"]), (first["result_ref"],)
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].category == "unlinked_evidence"
    assert diagnostics[0].severity == "error"


def test_admission_rejects_model_modified_result_payload(tmp_path) -> None:
    _, _, result = _result(tmp_path)
    modified = dict(result)
    modified["count"] = 99

    with pytest.raises(InventoryIntegrityError, match="returned result"):
        InventoryArtifactAuthority(tmp_path).admit(
            "asset.list", modified, tuple(result["evidence_refs"])
        )
