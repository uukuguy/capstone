from __future__ import annotations

import pytest

from pandapower_domain.output import PandapowerOutputContract


def test_output_contract_emits_only_validated_pandapower_payload() -> None:
    report_ref = "artifact:sha256:" + "b" * 64
    contract = PandapowerOutputContract(allowed_references=(report_ref,))
    payload = contract.build(
        binding_id="grid",
        context={
            "input": {"instruction_count": 2},
            "report_artifact_ref": report_ref,
        },
        committed_answers=(
            {"status": "success", "answer_ref": "artifact:sha256:" + "a" * 64},
            {"status": "failed", "answer_ref": None},
        ),
    )

    contract.validate(payload)
    assert payload == {
        "mode": "continuous-static-analysis",
        "instruction_count": 2,
        "completed_count": 1,
        "failed_count": 1,
        "report_artifact_ref": report_ref,
    }
    assert "core" not in payload and "domains" not in payload


@pytest.mark.parametrize(
    "payload",
    [
        {"mode": "continuous-static-analysis", "instruction_count": 1},
        {"core": {}, "mode": "continuous-static-analysis"},
        {"mode": "continuous-static-analysis", "report_artifact_ref": "foreign"},
    ],
)
def test_output_contract_rejects_framework_fields_missing_fields_or_foreign_refs(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        PandapowerOutputContract().validate(payload)


def test_output_contract_requires_an_admitted_current_run_report_reference() -> None:
    report_ref = "artifact:sha256:" + "b" * 64
    contract = PandapowerOutputContract(allowed_references=(report_ref,))
    context = {
        "input": {"instruction_count": 2},
        "report_artifact_ref": report_ref,
    }
    answers = ({"status": "success"}, {"status": "failed"})

    payload = contract.build(
        binding_id="grid",
        context=context,
        committed_answers=answers,
    )

    assert payload["report_artifact_ref"] == report_ref
    with pytest.raises(ValueError, match="report reference"):
        contract.validate({
            **payload,
            "report_artifact_ref": "artifact:sha256:" + "c" * 64,
        })

    with pytest.raises(ValueError, match="admission"):
        PandapowerOutputContract().validate(payload)


@pytest.mark.parametrize(
    "context",
    [
        {"input": {"instruction_count": 1}},
        {
            "input": {"instruction_count": 1},
            "report_artifact_ref": None,
            "state": {"report_artifact_ref": "artifact:sha256:" + "c" * 64},
        },
    ],
)
def test_output_contract_allows_an_absent_or_explicitly_null_report_reference(
    context: dict[str, object],
) -> None:
    contract = PandapowerOutputContract()
    payload = contract.build(
        binding_id="grid",
        context=context,
        committed_answers=({"status": "success"},),
    )

    contract.validate(payload)
    assert payload["report_artifact_ref"] is None


@pytest.mark.parametrize(
    "report_ref",
    [7, "not-an-artifact-reference", "artifact:sha256:" + "c" * 64],
)
def test_output_contract_rejects_malformed_or_unadmitted_context_report_references(
    report_ref: object,
) -> None:
    admitted_ref = "artifact:sha256:" + "b" * 64
    contract = PandapowerOutputContract(allowed_references=(admitted_ref,))

    with pytest.raises(ValueError, match="report reference"):
        contract.build(
            binding_id="grid",
            context={
                "input": {"instruction_count": 1},
                "report_artifact_ref": report_ref,
            },
            committed_answers=({"status": "success"},),
        )


def test_output_contract_rejects_a_foreign_context_binding() -> None:
    report_ref = "artifact:sha256:" + "b" * 64
    contract = PandapowerOutputContract(allowed_references=(report_ref,))

    with pytest.raises(ValueError, match="binding"):
        contract.build(
            binding_id="grid",
            context={
                "binding_id": "inventory",
                "report_artifact_ref": report_ref,
            },
            committed_answers=(),
        )


def test_output_contract_counts_uncompleted_instructions_as_failed() -> None:
    report_ref = "artifact:sha256:" + "b" * 64
    payload = PandapowerOutputContract(
        allowed_references=(report_ref,)
    ).build(
        binding_id="grid",
        context={
            "input": {"instruction_count": 2},
            "report_artifact_ref": report_ref,
        },
        committed_answers=({"status": "success"},),
    )

    assert payload["instruction_count"] == 2
    assert payload["completed_count"] == 1
    assert payload["failed_count"] == 1
