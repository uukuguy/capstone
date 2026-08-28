"""Grid-owned answer claim and reference rules for compatibility callers."""

from __future__ import annotations

from collections.abc import Iterable, Set
from typing import Protocol

from capability_agent.trajectory.answers import AnswerClaim, AnswerSubmission


class GridReferenceVerifier(Protocol):
    def verify_result(self, reference: str) -> object: ...

    def verify_evidence(self, reference: str) -> object: ...


class GridAnswerReferencePolicy:
    """Keep the historical simulator reference contract at the grid boundary."""

    _CATEGORIES = frozenset(
        {
            "topology",
            "constraint",
            "numerical_result",
            "risk_judgment",
            "offline_information",
        }
    )

    def validate_claim(self, claim: AnswerClaim) -> None:
        if claim.category not in self._CATEGORIES:
            raise ValueError("claim category is not supported")
        has_lineage = bool(claim.result_refs or claim.evidence_refs)
        if claim.category == "offline_information" and has_lineage:
            raise ValueError("offline-information claim must not include simulator refs")
        if claim.category != "offline_information" and not has_lineage:
            raise ValueError("simulator-backed claim requires result or evidence refs")

    def validate_submission(self, submission: AnswerSubmission) -> None:
        _require_reference_kind(submission.result_refs, "result", "result_refs")
        _require_reference_kind(
            submission.claim_evidence_refs,
            "evidence",
            "claim_evidence_refs",
        )

    def validate_allowed_references(
        self, references: Iterable[str], allowed_refs: Set[str]
    ) -> None:
        if set(references).difference(allowed_refs):
            raise ValueError("claim reference is not known in the current run")

    def verify_reference(
        self, verifier: object, reference: str, group: str
    ) -> object:
        if group == "result_refs":
            return _require_verifier(verifier).verify_result(reference)
        if group == "claim_evidence_refs":
            return _require_verifier(verifier).verify_evidence(reference)
        raise ValueError("reference group is not supported")


def _require_verifier(verifier: object) -> GridReferenceVerifier:
    if not isinstance(verifier, _VerifierAdapter):
        return _VerifierAdapter(verifier)
    return verifier


class _VerifierAdapter:
    def __init__(self, verifier: object) -> None:
        self._verifier = verifier

    def verify_result(self, reference: str) -> object:
        verify = getattr(self._verifier, "verify_result", None)
        if not callable(verify):
            raise TypeError("reference verifier does not support result verification")
        return verify(reference)

    def verify_evidence(self, reference: str) -> object:
        verify = getattr(self._verifier, "verify_evidence", None)
        if not callable(verify):
            raise TypeError("reference verifier does not support evidence verification")
        return verify(reference)


def _require_reference_kind(
    references: Iterable[str],
    kind: str,
    field: str,
) -> None:
    prefix = f"{kind}:sha256:"
    if any(
        not reference.startswith(prefix)
        or len(reference) != len(prefix) + 64
        or any(
            character not in "0123456789abcdef"
            for character in reference[len(prefix) :]
        )
        for reference in references
    ):
        raise ValueError(f"{field} must contain only {kind}:sha256 references")


__all__ = ["GridAnswerReferencePolicy", "GridReferenceVerifier"]
