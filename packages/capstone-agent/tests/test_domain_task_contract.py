import pytest
from capability_agent.domain.task import ResolvedTaskGoal, TaskConclusion


@pytest.mark.parametrize("payload", ['{"a":NaN}', '{"a":1,"a":2}', '[' + '0' + ']', '{"a":' * 12 + '0' + '}' * 12])
def test_resolution_rejects_nonfinite_duplicate_and_deep_documents(payload):
    with pytest.raises(ValueError):
        ResolvedTaskGoal("g", "ready", payload)


def test_resolution_requires_actual_execution_boolean():
    with pytest.raises(ValueError):
        ResolvedTaskGoal("g", "ready", "{}", execution_required=1)


def test_conclusion_detaches_references_and_rejects_bad_fields():
    refs = ["result:sha256:" + "a" * 64]
    conclusion = TaskConclusion("g", "supported", "Converged.", refs)
    refs.clear()
    assert len(conclusion.result_refs) == 1
    with pytest.raises(ValueError):
        TaskConclusion("g", "supported", 12)
    with pytest.raises(ValueError):
        TaskConclusion("g", "supported", "answer", ["x" * 513])


def test_conclusion_round_trip_has_no_mutable_reference_alias():
    conclusion = TaskConclusion("g", "partial", "One requested case is missing.", ["result:sha256:" + "a" * 64])
    document = conclusion.to_document()
    assert TaskConclusion.from_document(document) == conclusion
    document["result_refs"].clear()
    assert len(conclusion.result_refs) == 1


def test_general_response_cannot_claim_authority_evidence_or_context():
    with pytest.raises(ValueError, match="general response"):
        TaskConclusion("g", "general", "A poem.", result_refs=("result:abc",))
    with pytest.raises(ValueError, match="general response"):
        TaskConclusion("g", "general", "A poem.", context_ref="context:abc")


def test_uncertified_goal_cannot_claim_authority_coverage():
    with pytest.raises(ValueError, match="uncertified goal"):
        TaskConclusion("g", "uncertified", "Existing query response.", evidence_refs=("evidence:abc",))
