"""Compatibility imports for the pandapower answer-reference policy."""

from pandapower_domain.answer_policy import (
    GridAnswerReferencePolicy,
    PandapowerAnswerEvidencePolicy,
    PandapowerAnswerPolicy,
    PandapowerReferenceVerifier,
)

GridReferenceVerifier = PandapowerReferenceVerifier

__all__ = [
    "GridAnswerReferencePolicy",
    "GridReferenceVerifier",
    "PandapowerAnswerEvidencePolicy",
    "PandapowerAnswerPolicy",
]
