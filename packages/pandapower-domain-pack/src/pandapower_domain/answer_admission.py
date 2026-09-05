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
    """Admit lineage, current-turn guide access, or explicit packaged guidance.

    Guide access preserves reader-facing prose without claiming its semantics
    or numerical assertions were verified. Failed authority execution cannot
    use that path to substitute guidance for missing current-run evidence.
    """

    def __init__(self, authority: object | None = None, guide_root: Path | None = None) -> None:
        self._authority = authority
        self._guides = _trusted_guides(guide_root) if guide_root is not None else {}
        self._guide_index = GuideIndex.load(guide_root) if guide_root is not None else None

    def admit(self, request: AnswerAdmissionInput) -> AnswerAdmissionDecision:
        if request.result_refs or request.evidence_refs:
            return AnswerAdmissionDecision(
                mode="authority_backed",
                assurance="lineage_verified",
                answer_output=request.answer_output,
                diagnostic_codes=("current_run_lineage_verified",),
            )
        if request.guide_reads and not request.authority_attempted:
            verified = self._verified_guide_reads(request.guide_reads)
            if verified:
                return AnswerAdmissionDecision(
                    mode="offline_information", assurance="guide_access_verified",
                    answer_output=request.answer_output,
                    diagnostic_codes=("published_guide_access_verified", "answer_semantics_not_verified"),
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
                "证据限制（execution limitation）：本回答未绑定本轮结果或已核验的指南访问。"
                "以下保留模型回答原文，其数值与语义未经核验，不应视为已验证的仿真结论。\n\n"
                + request.answer_output
            ),
            diagnostic_codes=("no_current_run_result",),
        )

    def _verified_guide_reads(self, reads: tuple[tuple[str, str], ...]) -> bool:
        if self._guide_index is None:
            return False
        try:
            return all(
                sha256(self._guide_index.open(resource_id).text.strip().encode()).hexdigest() == digest
                for resource_id, digest in reads
            )
        except (GuideNotFound, OSError, ValueError):
            return False

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
    normalized = " ".join(question.strip().casefold().rstrip("?.!。？！").split())
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
        if text:
            trusted[resource_id] = text
    return trusted


__all__ = [
    "PandapowerAnswerAdmissionPolicy",
    "PandapowerAnswerAdmissionPolicyFactory",
]
