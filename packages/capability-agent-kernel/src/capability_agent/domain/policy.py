"""Domain answer-evidence and policy contracts."""

from __future__ import annotations

from typing import Protocol

from capability_agent.trajectory.answers import AnswerClaim, AnswerSubmission


class AnswerEvidencePolicy(Protocol):
    def validate_claim(self, claim: AnswerClaim) -> None: ...

    def validate_submission(self, submission: AnswerSubmission) -> None: ...


class DomainPolicyProvider(Protocol):
    def load(self) -> str: ...


__all__ = ["AnswerEvidencePolicy", "DomainPolicyProvider"]
