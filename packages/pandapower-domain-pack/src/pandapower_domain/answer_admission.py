"""Pandapower answer-admission policy with resource-grounded offline guidance."""

from __future__ import annotations

from pathlib import Path
from hashlib import sha256
import stat

from capability_agent.domain.answer_admission import (
    AnswerAdmissionDecision,
    AnswerAdmissionInput,
)
from capability_agent.tools.guide import GuideIndex, GuideNotFound


class PandapowerAnswerAdmissionPolicy:
    """Admit lineage, or render an explicitly selected packaged guide.

    Offline information is intentionally selected by the reader's stable
    ``guide:<relative-resource>`` request, not inferred from model prose or
    grid-looking words.  This keeps arbitrary no-reference business answers
    in the limited path.
    """

    def __init__(self, authority: object | None = None, guide_root: Path | None = None) -> None:
        self._authority = authority
        self._guides = _trusted_guides(guide_root) if guide_root is not None else {}

    def admit(self, request: AnswerAdmissionInput) -> AnswerAdmissionDecision:
        if request.result_refs or request.evidence_refs:
            return AnswerAdmissionDecision(
                mode="authority_backed",
                assurance="lineage_verified",
                answer_output=request.answer_output,
                diagnostic_codes=("current_run_lineage_verified",),
            )
        offline = self._offline_answer(request.question)
        if offline is not None:
            return AnswerAdmissionDecision(
                mode="offline_information",
                assurance="deterministic_information",
                answer_output=offline,
                diagnostic_codes=("packaged_guide_information",),
            )
        return AnswerAdmissionDecision(
            mode="limited",
            assurance="limited",
            answer_output=(
                "execution limitation: a current-run authority reference or an "
                "explicit published guide ID is required before this answer can be accepted."
            ),
            diagnostic_codes=("no_current_run_result",),
        )

    def _offline_answer(self, question: str) -> str | None:
        prefix = "guide:"
        resource_id = question.removeprefix(prefix).strip() if question.startswith(prefix) else _concept_resource_id(question)
        return self._guides.get(resource_id)


class PandapowerAnswerAdmissionPolicyFactory:
    """Bind each admission policy to the controller's current-run authority."""

    def __init__(self, guide_root: Path) -> None:
        self._guide_root = guide_root

    def __call__(self, authority: object) -> PandapowerAnswerAdmissionPolicy:
        return PandapowerAnswerAdmissionPolicy(authority, self._guide_root)


_CONCEPTS = {
    "ac power flow": "ac-powerflow",
    "交流潮流": "ac-powerflow",
    "n-1 contingency": "contingency-analysis",
    "n-1 静态安全校核": "contingency-analysis",
    "topology analysis": "topology-analysis",
    "拓扑分析": "topology-analysis",
    "network elements": "network-elements",
    "网络元件": "network-elements",
    "result query": "result-query",
    "结果查询": "result-query",
}


def _concept_resource_id(question: str) -> str:
    normalized = " ".join(question.strip().casefold().split())
    for prefix in ("what is ", "explain ", "什么是", "解释"):
        if normalized.startswith(prefix):
            return _CONCEPTS.get(normalized.removeprefix(prefix).strip(), "")
    return ""


def _trusted_guides(guide_root: Path) -> dict[str, str]:
    index = GuideIndex.load(guide_root)
    trusted: dict[str, str] = {}
    for resource_id in ("ac-powerflow", "contingency-analysis", "topology-analysis", "network-elements", "result-query"):
        try:
            document = index.open(resource_id)
            metadata = document.path.lstat()
        except (GuideNotFound, OSError):
            continue
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            continue
        text = document.text.strip()
        if text and sha256(text.encode("utf-8")).hexdigest():
            trusted[resource_id] = text
    return trusted


__all__ = [
    "PandapowerAnswerAdmissionPolicy",
    "PandapowerAnswerAdmissionPolicyFactory",
]
