import re
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class AttemptStatus(StrEnum):
    ANSWERED_WITH_EVIDENCE = "answered_with_evidence"
    ANSWERED_FROM_GENERAL_KNOWLEDGE = "answered_from_general_knowledge"
    NEEDS_CLARIFICATION = "needs_clarification"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    EXECUTION_FAILED = "execution_failed"


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(min_length=1, max_length=128)
    question: str = Field(min_length=1)

    @field_validator("question_id")
    @classmethod
    def _validate_question_id(cls, value: str) -> str:
        return validate_question_id(value)

    @classmethod
    def from_text(cls, question: str) -> "RunRequest":
        return cls(question_id=f"q-{uuid4().hex}", question=question.strip())


class AnswerEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    answer_output: str
