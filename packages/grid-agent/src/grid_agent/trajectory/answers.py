"""Grid compatibility answers with the historical reference contract."""

from __future__ import annotations

from collections.abc import Mapping, Set
from typing import Any, Protocol, cast

from capability_agent.trajectory.answers import (
    AnswerClaim,
    AnswerSubmission,
    AnswerReferencePolicy,
    ReferenceVerifier as _NeutralReferenceVerifier,
    validate_submission as _validate_submission,
)
from grid_agent.trajectory.answer_policy import GridAnswerReferencePolicy


class ReferenceVerifier(Protocol):
    def verify_result(self, reference: str) -> object: ...

    def verify_evidence(self, reference: str) -> object: ...


def validate_submission(
    draft: Mapping[str, Any],
    verifier: ReferenceVerifier,
    allowed_refs: Set[str],
    *,
    reference_policy: AnswerReferencePolicy | None = None,
) -> AnswerSubmission:
    """Validate with the grid policy by default while keeping injection possible."""
    return _validate_submission(
        draft,
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
