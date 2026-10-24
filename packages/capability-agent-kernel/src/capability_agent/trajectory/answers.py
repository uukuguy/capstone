"""Validated answer claims with caller-supplied reference semantics."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Set
from typing import Any, Protocol

from pydantic import Field

from capability_agent.trajectory.events import StrictFrozenModel
from capability_agent.runtime.capacity import runtime_limits as resolve_limits,check_capacity


class ReferenceVerifier(Protocol):
    """Verify a reference in a caller-defined answer reference group."""

    def verify(self, reference: str, group: str) -> object: ...


class AnswerClaim(StrictFrozenModel):
    statement: str = Field(min_length=1)
    category: str = Field(min_length=1)
    result_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()


class AnswerSubmission(StrictFrozenModel):
    submission_id: str = Field(min_length=1)
    answer_output: str = Field(min_length=1)
    result_refs: tuple[str, ...]
    claim_evidence_refs: tuple[str, ...]
    claims: tuple[AnswerClaim, ...]
    # Binding identity is part of the generic submission contract.  The
    # application controller supplies one binding-specific submission to each
    # domain policy, so a domain policy never has to infer ownership from an
    # opaque reference string.
    referenced_bindings: tuple[str, ...] = ()


class AnswerReferencePolicy(Protocol):
    """Inject answer reference and claim semantics at an application boundary."""

    def validate_claim(self, claim: AnswerClaim) -> None: ...

    def validate_submission(self, submission: AnswerSubmission) -> None: ...

    def validate_allowed_references(
        self, references: Iterable[str], allowed_refs: Set[str]
    ) -> None: ...

    def verify_reference(
        self, verifier: object, reference: str, group: str
    ) -> object: ...


class NeutralAnswerReferencePolicy:
    """Reference semantics based only on non-empty opaque identifiers."""

    def validate_claim(self, claim: AnswerClaim) -> None:
        _require_non_empty_references(
            (*claim.result_refs, *claim.evidence_refs),
            "claim references",
        )

    def validate_submission(self, submission: AnswerSubmission) -> None:
        _require_non_empty_references(
            (*submission.result_refs, *submission.claim_evidence_refs),
            "submission references",
        )

    def validate_allowed_references(
        self, references: Iterable[str], allowed_refs: Set[str]
    ) -> None:
        if set(references).difference(allowed_refs):
            raise ValueError("claim reference is not available to this submission")

    def verify_reference(
        self, verifier: object, reference: str, group: str
    ) -> object:
        verify = getattr(verifier, "verify", None)
        if not callable(verify):
            raise TypeError("reference verifier does not support grouped verification")
        return verify(reference, group)


def validate_submission(
    draft: Mapping[str, Any],
    verifier: ReferenceVerifier,
    allowed_refs: Set[str],
    *,
    reference_policy: AnswerReferencePolicy | None = None,
    runtime_limits=None,
) -> AnswerSubmission:
    """Validate a complete submission using injected reference semantics."""
    submission = AnswerSubmission.model_validate(draft)
    limits=resolve_limits(runtime_limits)
    check_capacity(limits,'research_claim_count',len(submission.claims),unit='claims',phase='answer_admission')
    for references in (submission.result_refs,submission.claim_evidence_refs,submission.referenced_bindings):
        check_capacity(limits,'context_references',len(references),unit='references',phase='answer_admission')
    for claim in submission.claims:
        for text in (claim.statement,claim.category):
            check_capacity(limits,'research_text_chars',len(text),unit='characters',phase='answer_admission')
        for references in (claim.result_refs,claim.evidence_refs):
            check_capacity(limits,'context_references',len(references),unit='references',phase='answer_admission')
    policy = reference_policy or NeutralAnswerReferencePolicy()
    policy.validate_submission(submission)
    for claim in submission.claims:
        policy.validate_claim(claim)

    claim_result_refs = _ordered_unique(
        reference
        for claim in submission.claims
        for reference in claim.result_refs
    )
    claim_evidence_refs = _ordered_unique(
        reference
        for claim in submission.claims
        for reference in claim.evidence_refs
    )

    undeclared_results = set(claim_result_refs).difference(submission.result_refs)
    if undeclared_results:
        raise ValueError("claim result refs must be declared in answer-level result_refs")
    undeclared_evidence = set(claim_evidence_refs).difference(
        submission.claim_evidence_refs
    )
    if undeclared_evidence:
        raise ValueError(
            "claim evidence refs must be declared in answer-level claim_evidence_refs"
        )

    policy.validate_allowed_references(
        (*submission.result_refs, *submission.claim_evidence_refs), allowed_refs
    )

    for reference in _ordered_unique(submission.result_refs):
        policy.verify_reference(verifier, reference, "result_refs")
    for reference in _ordered_unique(submission.claim_evidence_refs):
        policy.verify_reference(verifier, reference, "claim_evidence_refs")
    return submission


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _require_non_empty_references(
    references: Iterable[str], field: str
) -> None:
    if any(not reference for reference in references):
        raise ValueError(f"{field} must not contain empty identifiers")


__all__ = [
    "AnswerClaim",
    "AnswerReferencePolicy",
    "AnswerSubmission",
    "NeutralAnswerReferencePolicy",
    "ReferenceVerifier",
    "validate_submission",
]
