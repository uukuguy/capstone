"""Domain claim semantics; the Kernel separately verifies current-run ownership."""

from capability_agent.trajectory.answers import AnswerClaim, AnswerSubmission

from inventory_domain.state import validate_inventory_reference


class InventoryAnswerEvidencePolicy:
    categories = frozenset({"asset", "stock", "evidence", "offline_information"})

    def validate_claim(self, claim: AnswerClaim) -> None:
        if claim.category not in self.categories:
            raise ValueError("inventory claim category is unsupported")
        for reference in claim.result_refs:
            validate_inventory_reference(reference, "result")
        for reference in claim.evidence_refs:
            validate_inventory_reference(reference, "evidence")
        lineage = bool(claim.result_refs or claim.evidence_refs)
        if claim.category == "offline_information":
            if lineage:
                raise ValueError("offline information cannot have authority references")
        elif not lineage or (claim.category == "evidence" and not claim.evidence_refs):
            raise ValueError("inventory claim requires authority lineage")

    def validate_submission(self, submission: AnswerSubmission) -> None:
        for reference in submission.result_refs:
            validate_inventory_reference(reference, "result")
        for reference in submission.claim_evidence_refs:
            validate_inventory_reference(reference, "evidence")
