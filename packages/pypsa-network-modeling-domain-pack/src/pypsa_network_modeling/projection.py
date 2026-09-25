"""Projection of verified model references into the Pack's bounded state."""

from __future__ import annotations

from dataclasses import dataclass

from capability_agent.domain.projection import VerifiedInvocation

from pypsa_network_modeling.state import require_reference


@dataclass(frozen=True, slots=True)
class ModelStateDelta:
    model_ref: str
    result_ref: str
    evidence_refs: tuple[str, ...]

    def model_dump(self, *, mode: str = "python") -> dict[str, object]:
        del mode
        return {
            "model_ref": self.model_ref, "result_ref": self.result_ref,
            "evidence_refs": list(self.evidence_refs),
        }


class ModelProjector:
    projector_id = "pypsa-model-revision-v1"

    def project(self, invocation: VerifiedInvocation) -> ModelStateDelta:
        if invocation.projector_id != self.projector_id:
            raise ValueError("PyPSA model projector identity differs")
        result = invocation.result
        raw_evidence = result.get("evidence_refs")
        if not isinstance(raw_evidence, list) or not raw_evidence:
            raise ValueError("PyPSA model result has no evidence")
        return ModelStateDelta(
            require_reference(result.get("model_ref"), "model"),
            require_reference(result.get("result_ref"), "result"),
            tuple(require_reference(item, "evidence") for item in raw_evidence),
        )


class ModelProjectorRegistry:
    def __init__(self) -> None:
        self._projector = ModelProjector()

    def require(self, projector_id: str) -> ModelProjector:
        if projector_id != self._projector.projector_id:
            raise LookupError("unknown PyPSA model projector")
        return self._projector
