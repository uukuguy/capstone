from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from capability_agent.trajectory.answers import (
    AnswerClaim,
    NeutralAnswerReferencePolicy,
    validate_submission,
)


RESULT_REF = "result:sha256:" + "a" * 64
EVIDENCE_REF = "evidence:sha256:" + "b" * 64


class RecordingVerifier:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def verify(self, reference: str, group: str) -> object:
        self.calls.append((reference, group))
        return object()


class InventoryVerifier:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def verify(self, reference: str, group: str) -> object:
        self.calls.append((reference, group))
        return object()


def submission_draft(**overrides: Any) -> dict[str, Any]:
    draft: dict[str, Any] = {
        "submission_id": "submission-1",
        "answer_output": "Line 11 reaches 132.51 percent loading.",
        "result_refs": [RESULT_REF],
        "claim_evidence_refs": [EVIDENCE_REF],
        "claims": [
            {
                "statement": "Line 11 reaches 132.51 percent loading",
                "category": "numerical_result",
                "result_refs": [RESULT_REF],
                "evidence_refs": [EVIDENCE_REF],
            }
        ],
    }
    draft.update(overrides)
    return draft


def test_neutral_reference_policy_accepts_inventory_claims_and_references() -> None:
    verifier = InventoryVerifier()
    asset_ref = "asset:sha256:" + "a" * 64
    fact_ref = "fact:sha256:" + "b" * 64

    submission = validate_submission(
        {
            "submission_id": "inventory-submission",
            "answer_output": "Asset 1 is available.",
            "result_refs": [asset_ref],
            "claim_evidence_refs": [fact_ref],
            "claims": [
                {
                    "statement": "Asset 1 is available",
                    "category": "inventory_observation",
                    "result_refs": [asset_ref],
                    "evidence_refs": [fact_ref],
                }
            ],
        },
        verifier,
        {asset_ref, fact_ref},
        reference_policy=NeutralAnswerReferencePolicy(),
    )

    assert submission.submission_id == "inventory-submission"
    assert verifier.calls == [(asset_ref, "result_refs"), (fact_ref, "claim_evidence_refs")]


def test_validate_submission_verifies_declared_claim_lineage() -> None:
    verifier = RecordingVerifier()

    submission = validate_submission(
        submission_draft(), verifier, {RESULT_REF, EVIDENCE_REF}
    )

    assert submission.submission_id == "submission-1"
    assert verifier.calls == [
        (RESULT_REF, "result_refs"),
        (EVIDENCE_REF, "claim_evidence_refs"),
    ]


def test_neutral_claim_category_and_lineage_are_policy_defined() -> None:
    verifier = RecordingVerifier()

    submission = validate_submission(
        submission_draft(
            answer_output="An opaque inventory observation.",
            result_refs=[],
            claim_evidence_refs=[],
            claims=[
                {
                    "statement": "An opaque inventory observation",
                    "category": "inventory_observation",
                    "result_refs": [],
                    "evidence_refs": [],
                }
            ],
        ),
        verifier,
        set(),
    )

    assert submission.claims[0].category == "inventory_observation"
    assert verifier.calls == []


def test_neutral_policy_rejects_empty_reference_identifiers() -> None:
    claim = AnswerClaim(
        statement="An inventory observation",
        category="inventory_observation",
        result_refs=("",),
    )

    with pytest.raises(ValueError, match="empty identifiers"):
        NeutralAnswerReferencePolicy().validate_claim(claim)


def test_offline_information_claim_is_accepted_without_run_evidence() -> None:
    verifier = RecordingVerifier()

    submission = validate_submission(
        submission_draft(
            answer_output="General power-system information.",
            result_refs=[],
            claim_evidence_refs=[],
            claims=[
                {
                    "statement": "General power-system information",
                    "category": "offline_information",
                    "result_refs": [],
                    "evidence_refs": [],
                }
            ],
        ),
        verifier,
        set(),
    )

    assert submission.claims[0].category == "offline_information"
    assert verifier.calls == []


def test_claim_refs_must_be_declared_at_answer_level() -> None:
    with pytest.raises(ValueError, match="answer-level result_refs"):
        validate_submission(
            submission_draft(result_refs=[]),
            RecordingVerifier(),
            {RESULT_REF, EVIDENCE_REF},
        )

    with pytest.raises(ValueError, match="answer-level claim_evidence_refs"):
        validate_submission(
            submission_draft(claim_evidence_refs=[]),
            RecordingVerifier(),
            {RESULT_REF, EVIDENCE_REF},
        )


def test_claim_refs_must_be_controller_known() -> None:
    with pytest.raises(ValueError, match="not available to this submission"):
        validate_submission(
            submission_draft(), RecordingVerifier(), {RESULT_REF}
        )


def test_submission_accepts_opaque_reference_names() -> None:
    verifier = RecordingVerifier()
    submission = validate_submission(
        submission_draft(
            result_refs=[EVIDENCE_REF],
            claims=[
                {
                    "statement": "An opaque observation",
                    "category": "inventory_observation",
                    "result_refs": [EVIDENCE_REF],
                    "evidence_refs": [EVIDENCE_REF],
                }
            ],
        ),
        verifier,
        {EVIDENCE_REF},
    )

    assert submission.result_refs == (EVIDENCE_REF,)
    assert verifier.calls == [(EVIDENCE_REF, "result_refs"), (EVIDENCE_REF, "claim_evidence_refs")]


def test_claim_and_submission_bounds_are_closed() -> None:
    with pytest.raises(ValidationError, match="at most 1000 characters"):
        AnswerClaim(
            statement="x" * 1001,
            category="inventory_observation",
        )

    with pytest.raises(ValidationError, match="at most 20 items"):
        AnswerClaim(
            statement="bounded refs",
            category="inventory_observation",
            result_refs=tuple(
                f"result:sha256:{index:064x}" for index in range(21)
            ),
        )

    with pytest.raises(ValidationError, match="at most 50 items"):
        validate_submission(
            submission_draft(
                result_refs=[],
                claim_evidence_refs=[],
                claims=[
                    {
                        "statement": f"offline {index}",
                        "category": "inventory_observation",
                        "result_refs": [],
                        "evidence_refs": [],
                    }
                    for index in range(51)
                ],
            ),
            RecordingVerifier(),
            set(),
        )
