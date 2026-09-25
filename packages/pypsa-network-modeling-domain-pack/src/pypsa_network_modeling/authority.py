"""Domain admission of model authority results and evidence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from pypsa_model_authority.references import (
    VerifiedDocument, verify_evidence, verify_model, verify_result,
)


@dataclass(frozen=True, slots=True)
class VerifiedReferenceSet:
    context: tuple[VerifiedDocument, ...] = ()
    results: tuple[VerifiedDocument, ...] = ()
    evidence: tuple[VerifiedDocument, ...] = ()


class PypsaModelArtifactAuthority:
    authority_id = "pypsamodelctl"

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = Path(workspace_root)
        self.run_id = self.workspace_root.parent.parent.name

    def verify_model(self, reference: str) -> VerifiedDocument:
        return verify_model(self.workspace_root, self.run_id, reference)

    def verify_result(self, reference: str) -> VerifiedDocument:
        return verify_result(self.workspace_root, self.run_id, reference)

    def verify_evidence(self, reference: str) -> VerifiedDocument:
        return verify_evidence(self.workspace_root, self.run_id, reference)

    def admit(
        self, capability: str, result: Mapping[str, object],
        evidence_refs: tuple[str, ...],
    ) -> VerifiedReferenceSet:
        model_ref = result.get("model_ref")
        result_ref = result.get("result_ref")
        if not isinstance(model_ref, str) or not isinstance(result_ref, str):
            raise ValueError("PyPSA model result is missing authority references")
        self.verify_model(model_ref)
        verified_result = self.verify_result(result_ref)
        if (
            verified_result.document.get("capability") != capability
            or verified_result.document.get("model_ref") != model_ref
        ):
            raise ValueError("PyPSA model result does not match the invocation")
        declared = result.get("evidence_refs")
        if not isinstance(declared, list) or tuple(declared) != evidence_refs:
            raise ValueError("PyPSA model evidence declaration does not match")
        evidence = tuple(self.verify_evidence(ref) for ref in evidence_refs)
        if not evidence or any(
            item.document.get("result_ref") != result_ref for item in evidence
        ):
            raise ValueError("PyPSA model evidence is not linked to the result")
        expected = verified_result.document.get("details")
        if not isinstance(expected, dict) or any(result.get(key) != value for key, value in expected.items()):
            raise ValueError("PyPSA model result details do not match authority data")
        return VerifiedReferenceSet(results=(verified_result,), evidence=evidence)

    def audit_answer_references(
        self, claim_evidence_refs: tuple[str, ...], result_refs: tuple[str, ...]
    ) -> tuple[object, ...]:
        try:
            results = {ref: self.verify_result(ref) for ref in result_refs}
            for ref in claim_evidence_refs:
                evidence = self.verify_evidence(ref)
                if evidence.document.get("result_ref") not in results:
                    raise ValueError("evidence does not support a declared result")
        except (ValueError, RuntimeError) as exc:
            return ({"code": "invalid_pypsa_model_reference", "message": str(exc)},)
        return ()
