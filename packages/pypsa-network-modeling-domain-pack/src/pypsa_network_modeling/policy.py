"""Domain-owned claim and answer admission rules."""

from __future__ import annotations

from capability_agent.domain.answer_admission import (
    AnswerAdmissionDecision, AnswerAdmissionInput,
)
from capability_agent.trajectory.answers import AnswerClaim, AnswerSubmission

from pypsa_network_modeling.state import require_reference


class ModelAnswerEvidencePolicy:
    _CATEGORIES = frozenset({"model", "observation", "evidence", "offline_information"})

    def validate_claim(self, claim: AnswerClaim) -> None:
        if claim.category not in self._CATEGORIES:
            raise ValueError("PyPSA model claim category is unsupported")
        for ref in claim.result_refs:
            require_reference(ref, "result")
        for ref in claim.evidence_refs:
            require_reference(ref, "evidence")
        if claim.category != "offline_information" and not (claim.result_refs or claim.evidence_refs):
            raise ValueError("PyPSA model claim has no authority lineage")
        if claim.category == "offline_information" and (claim.result_refs or claim.evidence_refs):
            raise ValueError("offline model information cannot carry authority references")

    def validate_submission(self, submission: AnswerSubmission) -> None:
        for ref in submission.result_refs:
            require_reference(ref, "result")
        for ref in submission.claim_evidence_refs:
            require_reference(ref, "evidence")


class ModelAnswerAdmissionPolicy:
    def __init__(self, authority: object) -> None:
        self.authority = authority

    def admit(self, request: AnswerAdmissionInput) -> AnswerAdmissionDecision:
        if request.result_refs and request.evidence_refs:
            return AnswerAdmissionDecision(
                "authority_backed", "lineage_verified", request.answer_output,
                ("current_run_model_lineage_verified",),
            )
        return AnswerAdmissionDecision(
            "limited", "limited", request.answer_output,
            ("no_current_run_model_result",),
        )
