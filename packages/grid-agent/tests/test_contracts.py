import pytest
from pydantic import ValidationError

from grid_agent.contracts import AnswerEnvelope, AttemptStatus, RunRequest


def test_answer_envelope_has_exact_public_shape() -> None:
    envelope = AnswerEnvelope(question_id="q-1", answer_output="ok")

    assert envelope.model_dump() == {"question_id": "q-1", "answer_output": "ok"}


def test_plain_question_gets_id() -> None:
    request = RunRequest.from_text("  run AC power flow  ")

    assert request.question_id.startswith("q-")
    assert request.question == "run AC power flow"
    assert AttemptStatus.EXECUTION_FAILED.value == "execution_failed"


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
def test_run_request_rejects_question_ids_that_are_not_safe_basenames(
    question_id: str,
) -> None:
    with pytest.raises(ValidationError):
        RunRequest(question_id=question_id, question="question")


@pytest.mark.parametrize("question_id", ("q-1", "GRID_7", "turn.2026-08-28"))
def test_run_request_accepts_portable_question_ids(question_id: str) -> None:
    assert RunRequest(question_id=question_id, question="question").question_id == question_id
