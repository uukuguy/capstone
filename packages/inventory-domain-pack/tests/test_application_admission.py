from __future__ import annotations

import pytest

from capability_agent.domain.answer_admission import AnswerAdmissionInput
from capability_agent.trajectory.answers import AnswerClaim, AnswerSubmission


@pytest.mark.parametrize("question,resource_id", [
    ("guide:overview", "overview"),
    ("guide:capability-map", "capability-map"),
    ("Explain read-only inventory capabilities.", "capability-map"),
    ("什么是当前运行证据？", "evidence-and-recovery"),
    ("解释缺失上下文后的恢复", "evidence-and-recovery"),
])
def test_offline_admission_returns_packaged_text_without_authority(question, resource_id):
    from inventory_domain.answer_admission import InventoryAnswerAdmissionPolicyFactory
    from inventory_domain.guide import InventoryGuideProvider

    class NoAuthorityCalls:
        def __getattr__(self, name):
            raise AssertionError("offline request must not invoke authority")

    guides = InventoryGuideProvider()
    policy = InventoryAnswerAdmissionPolicyFactory(guides)(NoAuthorityCalls())
    decision = policy.admit(AnswerAdmissionInput(question, "untrusted model prose", (), ()))
    assert (decision.mode, decision.assurance) == ("offline_information", "deterministic_information")
    assert decision.answer_output == guides.open(resource_id)["text"]


@pytest.mark.parametrize("question", [
    "How many assets are there?",
    "Explain read-only inventory capabilities and give warehouse-a stock totals.",
    "什么是当前运行证据，并给出库存数量？",
    "guide:overview and stock.summary",
    "guide:../policy/system-policy.md",
    "",
])
def test_no_reference_business_or_mixed_request_remains_limited(question):
    from inventory_domain.answer_admission import InventoryAnswerAdmissionPolicyFactory
    from inventory_domain.guide import InventoryGuideProvider

    decision = InventoryAnswerAdmissionPolicyFactory(InventoryGuideProvider())(object()).admit(
        AnswerAdmissionInput(question, "There are 9000 assets.", (), ())
    )
    assert (decision.mode, decision.assurance) == ("limited", "limited")
    assert "9000" not in decision.answer_output


def test_authority_backed_admission_claims_only_lineage():
    from inventory_domain.answer_admission import InventoryAnswerAdmissionPolicyFactory
    from inventory_domain.guide import InventoryGuideProvider

    request = AnswerAdmissionInput("stock?", "reader text", ("inventory-result:sha256:" + "a" * 64,), ())
    decision = InventoryAnswerAdmissionPolicyFactory(InventoryGuideProvider())(object()).admit(request)
    assert (decision.mode, decision.assurance, decision.answer_output) == ("authority_backed", "lineage_verified", "reader text")


@pytest.mark.parametrize("category,results,evidence,valid", [
    ("asset", ("inventory-result:sha256:" + "a" * 64,), (), True),
    ("stock", (), ("inventory-evidence:sha256:" + "b" * 64,), True),
    ("evidence", (), ("inventory-evidence:sha256:" + "b" * 64,), True),
    ("offline_information", (), (), True),
    ("asset", (), (), False),
    ("stock", ("result:sha256:" + "a" * 64,), (), False),
    ("evidence", ("inventory-result:sha256:" + "a" * 64,), (), False),
    ("offline_information", ("inventory-result:sha256:" + "a" * 64,), (), False),
    ("voltage", ("inventory-result:sha256:" + "a" * 64,), (), False),
])
def test_claim_policy_requires_inventory_reference_kinds(category, results, evidence, valid):
    from inventory_domain.answer_policy import InventoryAnswerEvidencePolicy

    claim = AnswerClaim(statement="test", category=category, result_refs=results, evidence_refs=evidence)
    if valid:
        InventoryAnswerEvidencePolicy().validate_claim(claim)
    else:
        with pytest.raises(ValueError):
            InventoryAnswerEvidencePolicy().validate_claim(claim)


def test_submission_policy_validates_kinds_without_binding_name_shortcut():
    from inventory_domain.answer_policy import InventoryAnswerEvidencePolicy

    policy = InventoryAnswerEvidencePolicy()
    submission = AnswerSubmission(
        submission_id="one", answer_output="reader text",
        result_refs=("inventory-result:sha256:" + "a" * 64,), claim_evidence_refs=(),
        claims=(), referenced_bindings=("another_inventory_binding",),
    )
    policy.validate_submission(submission)
    with pytest.raises(ValueError):
        policy.validate_submission(submission.model_copy(update={"result_refs": ("inventory-evidence:sha256:" + "a" * 64,)}))
