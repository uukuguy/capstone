from __future__ import annotations

import pytest

from capability_agent.trajectory.answers import AnswerClaim, AnswerSubmission
from capability_agent.domain.answer_admission import AnswerAdmissionInput
from pandapower_domain.answer_admission import PandapowerAnswerAdmissionPolicy
from pandapower_domain.answer_policy import PandapowerAnswerEvidencePolicy


def test_current_turn_verified_guide_preserves_informational_answer() -> None:
    from hashlib import sha256
    from pandapower_domain.profile import build_pandapower_profile
    from capability_agent.tools.guide import GuideIndex

    root = build_pandapower_profile().manifest.guide_root
    text = GuideIndex.load(root).open("contingency-analysis").text.strip()
    policy = PandapowerAnswerAdmissionPolicy(guide_root=root)
    request = AnswerAdmissionInput(
        question="N-1静态安全校核需要检查哪些越限类型?",
        answer_output="需检查电压上下限、线路过载及潮流不收敛。",
        result_refs=(), evidence_refs=(),
        guide_reads=(("contingency-analysis", sha256(text.encode()).hexdigest()),),
    )
    decision = policy.admit(request)
    assert decision.mode == "offline_information"
    assert decision.assurance == "guide_access_verified"
    assert decision.answer_output == request.answer_output

    from dataclasses import replace
    assert policy.admit(replace(request, authority_attempted=True)).mode == "limited"
    assert policy.admit(replace(request, guide_reads=(("contingency-analysis", "0" * 64),))).mode == "limited"


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


@pytest.mark.parametrize(
    "question,answer",
    [
        ("what is the bus voltage?", "The voltage is 230 kV."),
        ("which line is most loaded?", "Line 7 is first at 91 MW."),
        ("run the N-1 case", "The outage is secure."),
        ("what does this result mean?", "The result is 10 MW."),
        ("which buses are connected by this line?", "The line connects buses 1 and 2."),
    ],
)
def test_admission_without_current_run_results_is_limited(
    question: str, answer: str
) -> None:
    decision = PandapowerAnswerAdmissionPolicy().admit(
        AnswerAdmissionInput(
            question=question,
            answer_output=answer,
            result_refs=(),
            evidence_refs=(),
        )
    )

    assert decision.mode == "limited"
    assert decision.assurance == "limited"
    assert "no_current_run_result" in decision.diagnostic_codes
    assert decision.answer_output != answer
    assert "execution limitation" in decision.answer_output


def test_admission_with_validated_result_is_lineage_not_semantic_verification() -> None:
    decision = PandapowerAnswerAdmissionPolicy().admit(
        AnswerAdmissionInput(
            question="what is the bus voltage?",
            answer_output="The voltage is 999 kV and is ranked first.",
            result_refs=("result:sha256:" + "a" * 64,),
            evidence_refs=("evidence:sha256:" + "b" * 64,),
        )
    )

    assert decision.mode == "authority_backed"
    assert decision.assurance == "lineage_verified"
    assert "semantic_verification" not in decision.diagnostic_codes
