"""Bounded model-reference state, reduced only after authority admission."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from capability_agent.domain.projection import DomainStateDelta


MODEL_STATE_SCHEMA = "pypsa-network-modeling-state/1.0"
_REF = re.compile(r"^pypsa-(model|result|evidence):sha256:[a-f0-9]{64}$")


def require_reference(reference: object, kind: str) -> str:
    if not isinstance(reference, str) or not _REF.fullmatch(reference) or not reference.startswith(f"pypsa-{kind}:"):
        raise ValueError(f"PyPSA {kind} reference is invalid")
    return reference


def _state(value: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("PyPSA model state must be a mapping")
    if not value:
        return {"active_model_ref": None, "results": {}}
    if set(value) != {"active_model_ref", "results"}:
        raise ValueError("PyPSA model state fields are invalid")
    active = value["active_model_ref"]
    if active is not None:
        require_reference(active, "model")
    raw_results = value["results"]
    if not isinstance(raw_results, Mapping):
        raise ValueError("PyPSA model results must be a mapping")
    results: dict[str, object] = {}
    for ref, raw in raw_results.items():
        require_reference(ref, "result")
        if not isinstance(raw, Mapping) or set(raw) != {"model_ref", "evidence_refs"}:
            raise ValueError("PyPSA model result state is invalid")
        model_ref = require_reference(raw["model_ref"], "model")
        evidence_refs = raw["evidence_refs"]
        if not isinstance(evidence_refs, (tuple, list)) or not evidence_refs:
            raise ValueError("PyPSA model result evidence is invalid")
        results[ref] = {
            "model_ref": model_ref,
            "evidence_refs": [require_reference(item, "evidence") for item in evidence_refs],
        }
    if active is not None and not any(item["model_ref"] == active for item in results.values()):
        raise ValueError("active PyPSA model has no admitted result")
    return {"active_model_ref": active, "results": results}


@dataclass(frozen=True, slots=True)
class ModelContext:
    binding_id: str
    state: dict[str, object]
    admitted_refs: tuple[str, ...]

    def model_dump(self, *, mode: str = "python") -> dict[str, object]:
        del mode
        return {
            "binding_id": self.binding_id, "state": _state(self.state),
            "admitted_refs": list(self.admitted_refs),
        }


class ModelStateAdapter:
    schema_id = MODEL_STATE_SCHEMA

    def validate(self, *, binding_id: str, state: Mapping[str, object]) -> None:
        if not binding_id:
            raise ValueError("PyPSA model binding is empty")
        _state(state)

    def merge(
        self, *, binding_id: str, state: Mapping[str, object], delta: DomainStateDelta
    ) -> Mapping[str, object]:
        self.validate(binding_id=binding_id, state=state)
        change = delta.model_dump(mode="python")
        if set(change) != {"model_ref", "result_ref", "evidence_refs"}:
            raise ValueError("PyPSA model state delta is invalid")
        model_ref = require_reference(change["model_ref"], "model")
        result_ref = require_reference(change["result_ref"], "result")
        evidence_refs = change["evidence_refs"]
        if not isinstance(evidence_refs, (list, tuple)) or not evidence_refs:
            raise ValueError("PyPSA model state delta has no evidence")
        record = {
            "model_ref": model_ref,
            "evidence_refs": [require_reference(item, "evidence") for item in evidence_refs],
        }
        updated = _state(state)
        results = updated["results"]
        if result_ref in results and results[result_ref] != record:
            raise ValueError("PyPSA model result state conflicts with earlier authority data")
        results[result_ref] = record
        updated["active_model_ref"] = model_ref
        return _state(updated)

    def build_context(
        self, *, binding_id: str, state: Mapping[str, object]
    ) -> ModelContext:
        parsed = _state(state)
        refs: set[str] = set()
        if parsed["active_model_ref"] is not None:
            refs.add(parsed["active_model_ref"])
        for result_ref, record in parsed["results"].items():
            refs.add(result_ref)
            refs.add(record["model_ref"])
            refs.update(record["evidence_refs"])
        return ModelContext(binding_id, parsed, tuple(sorted(refs)))
