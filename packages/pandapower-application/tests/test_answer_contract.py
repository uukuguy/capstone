import pytest

from pandapower_application.answer_contract import AnswerEnvelope, validate_question_id


def test_answer_envelope_has_exact_public_shape() -> None:
    envelope = AnswerEnvelope(question_id="q-1", answer_output="ok")

    assert envelope.model_dump() == {"question_id": "q-1", "answer_output": "ok"}


@pytest.mark.parametrize(
    "question_id",
    (
        "/tmp/escape",
        "../escape",
        ".",
        "..",
        ".hidden",
        "nested/name",
        r"nested\name",
        "encoded%2fname",
        "encoded%5Cname",
        "trailing.",
        "q-" + ("a" * 127),
    ),
)
def test_validator_rejects_question_ids_that_are_not_safe_basenames(
    question_id: str,
) -> None:
    with pytest.raises(ValueError):
        validate_question_id(question_id)


@pytest.mark.parametrize("question_id", ("q-1", "GRID_7", "turn.2026-08-28"))
def test_validator_accepts_portable_question_ids(question_id: str) -> None:
    assert validate_question_id(question_id) == question_id
