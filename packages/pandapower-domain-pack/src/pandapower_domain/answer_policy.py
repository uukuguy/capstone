"""Pandapower answer-reference and model-policy providers."""

from __future__ import annotations

from collections.abc import Iterable, Set
from pathlib import Path
from typing import Protocol

from capability_agent.trajectory.answers import AnswerClaim, AnswerSubmission

from pandapower_domain.resources import PandapowerResourceSet


class PandapowerReferenceVerifier(Protocol):
    def verify_result(self, reference: str) -> object: ...

    def verify_evidence(self, reference: str) -> object: ...


class PandapowerAnswerEvidencePolicy:
    """Require current-run simulator lineage for every factual grid claim."""

    categories = frozenset(
        {
            "topology",
            "constraint",
            "numerical_result",
            "risk_judgment",
            "ranking",
            "voltage",
            "contingency",
            "loss",
            "evidence",
            "offline_information",
        }
    )
    simulator_categories = categories - {"offline_information"}
    _EVIDENCE_ONLY_CATEGORIES = frozenset({"evidence"})

    def validate_claim(self, claim: AnswerClaim) -> None:
        if claim.category not in self.categories:
            raise ValueError("claim category is not supported")
        has_lineage = bool(claim.result_refs or claim.evidence_refs)
        if claim.category == "offline_information":
            if has_lineage:
                raise ValueError(
                    "offline-information claim must not include simulator refs"
                )
            return
        if claim.category in self._EVIDENCE_ONLY_CATEGORIES and not claim.evidence_refs:
            raise ValueError("evidence claim requires evidence refs")
        if not has_lineage:
            raise ValueError("simulator-backed claim requires result or evidence refs")

    def validate_submission(self, submission: AnswerSubmission) -> None:
        _require_reference_kind(submission.result_refs, "result", "result_refs")
        _require_reference_kind(
            submission.claim_evidence_refs,
            "evidence",
            "claim_evidence_refs",
        )
        if any(binding_id != "grid" for binding_id in submission.referenced_bindings):
            raise ValueError("pandapower submission references a foreign binding")

    def validate_allowed_references(
        self, references: Iterable[str], allowed_refs: Set[str]
    ) -> None:
        if set(references).difference(allowed_refs):
            raise ValueError("claim reference is not known in the current run")

    def verify_reference(
        self, verifier: object, reference: str, group: str
    ) -> object:
        target: PandapowerReferenceVerifier = _verifier(verifier)
        if group == "result_refs":
            return target.verify_result(reference)
        if group == "claim_evidence_refs":
            return target.verify_evidence(reference)
        raise ValueError("reference group is not supported")


# Short names are useful to callers composing a DomainRuntimeProfile while the
# explicit class name remains the source-facing contract.
PandapowerAnswerPolicy = PandapowerAnswerEvidencePolicy
GridAnswerReferencePolicy = PandapowerAnswerEvidencePolicy


class PandapowerPolicyProvider:
    """Load the immutable model-facing pandapower policy resource."""

    def __init__(self, policy_path: Path | None = None) -> None:
        self.policy_path = (
            Path(policy_path)
            if policy_path is not None
            else PandapowerResourceSet.load().system_policy_path
        )

    def load(self) -> str:
        try:
            text = self.policy_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise RuntimeError("pandapower system policy is unavailable") from exc
        if not text.strip():
            raise RuntimeError("pandapower system policy is empty")
        return text


def _verifier(verifier: object) -> PandapowerReferenceVerifier:
    if not callable(getattr(verifier, "verify_result", None)) or not callable(
        getattr(verifier, "verify_evidence", None)
    ):
        raise TypeError("reference verifier does not support pandapower verification")
    return verifier  # type: ignore[return-value]


def _require_reference_kind(
    references: Iterable[str], kind: str, field: str
) -> None:
    prefix = f"{kind}:sha256:"
    if any(
        not isinstance(reference, str)
        or not reference.startswith(prefix)
        or len(reference) != len(prefix) + 64
        or any(
            character not in "0123456789abcdef"
            for character in reference[len(prefix) :]
        )
        for reference in references
    ):
        raise ValueError(f"{field} must contain only {kind}:sha256 references")


__all__ = [
    "GridAnswerReferencePolicy",
    "PandapowerAnswerEvidencePolicy",
    "PandapowerAnswerPolicy",
    "PandapowerPolicyProvider",
    "PandapowerReferenceVerifier",
]
