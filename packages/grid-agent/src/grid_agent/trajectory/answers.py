"""Grid compatibility answers with the historical reference contract."""

from __future__ import annotations

from collections.abc import Mapping, Set
from typing import Any, Protocol, cast

from pydantic import model_validator

from capability_agent.trajectory.answers import (
    AnswerClaim as _NeutralAnswerClaim,
    AnswerSubmission as _NeutralAnswerSubmission,
    AnswerReferencePolicy,
    ReferenceVerifier as _NeutralReferenceVerifier,
    validate_submission as _validate_submission,
)
from grid_agent.trajectory.answer_policy import GridAnswerReferencePolicy


class ReferenceVerifier(Protocol):
    def verify_result(self, reference: str) -> object: ...

    def verify_evidence(self, reference: str) -> object: ...


class AnswerClaim(_NeutralAnswerClaim):
    @model_validator(mode="after")
    def validate_grid_lineage(self) -> "AnswerClaim":
        GridAnswerReferencePolicy().validate_claim(self)
        return self


AnswerSubmission = _NeutralAnswerSubmission


def validate_submission(
    draft: Mapping[str, Any],
    verifier: ReferenceVerifier,
    allowed_refs: Set[str],
    *,
    reference_policy: AnswerReferencePolicy | None = None,
) -> AnswerSubmission:
    """Validate a grid answer while keeping the kernel API policy-injectable."""
    submission = AnswerSubmission.model_validate(draft)
    for claim in submission.claims:
        AnswerClaim.model_validate(claim.model_dump(mode="json"))
    return _validate_submission(
        submission.model_dump(mode="json"),
        cast(_NeutralReferenceVerifier, verifier),
        allowed_refs,
        reference_policy=cast(
            AnswerReferencePolicy,
            reference_policy or GridAnswerReferencePolicy(),
        ),
    )


__all__ = [
    "AnswerClaim",
    "AnswerSubmission",
    "ReferenceVerifier",
    "validate_submission",
]
