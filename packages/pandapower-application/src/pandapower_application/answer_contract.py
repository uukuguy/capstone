import re

from pydantic import BaseModel, ConfigDict


_PORTABLE_QUESTION_ID = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,126}[A-Za-z0-9])?$"
)


def validate_question_id(value: str) -> str:
    """Require a bounded portable basename before it reaches filesystem code."""

    if _PORTABLE_QUESTION_ID.fullmatch(value) is None:
        raise ValueError(
            "question_id must be a safe portable basename of 1 to 128 characters"
        )
    return value


class AnswerEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    answer_output: str
