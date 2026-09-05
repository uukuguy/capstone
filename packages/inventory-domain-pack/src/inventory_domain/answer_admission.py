"""Lineage admission and whole-request, resource-grounded informational answers."""

from capability_agent.domain.answer_admission import AnswerAdmissionDecision, AnswerAdmissionInput
from capability_agent.domain.authority import ArtifactAuthority
from capability_agent.tools.guide import GuideNotFound

from inventory_domain.guide import InventoryGuideProvider

_CONCEPTS = {
    "read-only inventory capabilities": "capability-map",
    "只读库存能力": "capability-map",
    "current-run evidence": "evidence-and-recovery",
    "当前运行证据": "evidence-and-recovery",
    "recovery after missing context": "evidence-and-recovery",
    "缺失上下文后的恢复": "evidence-and-recovery",
}


def _information_resource(question: str) -> str | None:
    if len(question) > 2048:
        return None
    normalized = " ".join(question.strip().casefold().split())
    if normalized.startswith("guide:"):
        return normalized.removeprefix("guide:").strip()
    normalized = normalized.rstrip("?.!。？！")
    for prefix in ("what is ", "explain ", "什么是", "解释"):
        if normalized.startswith(prefix):
            return _CONCEPTS.get(normalized.removeprefix(prefix).strip())
    return None


class InventoryAnswerAdmissionPolicy:
    def __init__(self, authority: ArtifactAuthority, guides: InventoryGuideProvider) -> None:
        # Retain the current-run binding, without re-verifying already admitted
        # references or making authority calls for offline information.
        self._authority = authority
        self._guides = guides

    def admit(self, request: AnswerAdmissionInput) -> AnswerAdmissionDecision:
        if request.result_refs or request.evidence_refs:
            return AnswerAdmissionDecision(
                "authority_backed", "lineage_verified", request.answer_output,
                ("current_run_lineage_verified",),
            )
        resource_id = _information_resource(request.question)
        if resource_id is not None:
            try:
                document = self._guides.open(resource_id)
            except GuideNotFound:
                pass
            else:
                text = document["text"]
                if not isinstance(text, str):
                    raise ValueError("inventory guide text is invalid")
                return AnswerAdmissionDecision(
                    "offline_information", "deterministic_information", text,
                    ("packaged_guide_information",),
                )
        return AnswerAdmissionDecision(
            "limited", "limited",
            "Execution limitation: current-run inventory authority references or "
            "a supported packaged information request are required.",
            ("no_current_run_result",),
        )


class InventoryAnswerAdmissionPolicyFactory:
    def __init__(self, guides: InventoryGuideProvider) -> None:
        self._guides = guides

    def __call__(self, authority: ArtifactAuthority) -> InventoryAnswerAdmissionPolicy:
        return InventoryAnswerAdmissionPolicy(authority, self._guides)
