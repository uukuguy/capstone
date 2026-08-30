from __future__ import annotations

import pytest

from capability_agent.trajectory.answers import AnswerClaim, AnswerSubmission
from pandapower_domain.answer_policy import PandapowerAnswerEvidencePolicy


@pytest.mark.parametrize(
    "category",
    [
        "numerical_result",
        "ranking",
        "voltage",
        "topology",
        "contingency",
        "loss",
        "evidence",
    ],
)
def test_answer_policy_rejects_unsupported_claim_without_current_run_refs(
    category: str,
) -> None:
    claim = AnswerClaim(statement="unsupported", category=category)

    with pytest.raises(ValueError, match="refs|result or evidence"):
        PandapowerAnswerEvidencePolicy().validate_claim(claim)


def test_answer_policy_rejects_non_grid_reference_shapes_and_accepts_offline_claim() -> None:
    policy = PandapowerAnswerEvidencePolicy()
    policy.validate_claim(AnswerClaim(statement="guide", category="offline_information"))

    with pytest.raises(ValueError, match="result:sha256"):
        policy.validate_submission(
            AnswerSubmission(
                submission_id="answer-1",
                answer_output="answer",
                result_refs=("not-a-result",),
                claim_evidence_refs=(),
                claims=(),
            )
        )


def test_answer_policy_requires_evidence_lineage_for_evidence_claims() -> None:
    policy = PandapowerAnswerEvidencePolicy()

    with pytest.raises(ValueError, match="evidence refs"):
        policy.validate_claim(
            AnswerClaim(
                statement="evidence claim",
                category="evidence",
                result_refs=("result:sha256:" + "a" * 64,),
            )
        )


def test_answer_policy_rejects_foreign_binding_submission() -> None:
    with pytest.raises(ValueError, match="foreign binding"):
        PandapowerAnswerEvidencePolicy().validate_submission(
            AnswerSubmission(
                submission_id="answer-foreign",
                answer_output="answer",
                result_refs=(),
                claim_evidence_refs=(),
                claims=(),
                referenced_bindings=("inventory",),
            )
        )
