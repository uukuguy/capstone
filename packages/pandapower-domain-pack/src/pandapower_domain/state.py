"""Pandapower state schema, reducer, and generic state adapter.

Legacy analysis lifecycle helpers remain here for the v1.0.1 compatibility
entrypoint.  The generic application consumes only the adapter contract and
opaque JSON state.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from pydantic import ValidationError

from capability_agent.domain.projection import (
    DomainStateDelta as KernelDomainStateDelta,
)
from pandapower_domain.models import (
    ActiveTurn,
    AnalysisContext,
    BaselineRecord,
    ContextEventDraft,
    DomainState,
    DomainStateDelta,
    DiagnosticRecord,
    EvidenceRecord,
    InputRecord,
    LimitationRecord,
    ObservationRecord,
    ResultRecord,
    RuntimeRecord,
    TurnRecord,
    VerifiedFact,
)


class ContextTransitionError(RuntimeError):
    """Raised when an analysis context event violates reducer invariants."""


_TERMINAL_STATUSES = {"completed", "failed"}
_SIMULATOR_PROVENANCE = {"simulator", "gridctl"}


def canonical_state_hash(state: AnalysisContext) -> str:
    payload = state.model_dump(mode="json")
    payload.pop("state_hash", None)
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


def initial_context(
    analysis_id: str,
    input_payload: dict[str, Any],
    runtime_payload: dict[str, Any],
) -> AnalysisContext:
    runtime = RuntimeRecord.model_validate(runtime_payload)
    state = AnalysisContext(
        analysis_id=analysis_id,
        revision=0,
        state_hash="",
        status="initializing",
        input=InputRecord.model_validate(input_payload),
        runtime=runtime,
        domain_state=DomainState(capabilities={item.id: item for item in runtime.capability_families}),
    )
    return state.model_copy(update={"state_hash": canonical_state_hash(state)})


def reduce_context(state: AnalysisContext, draft: ContextEventDraft) -> AnalysisContext:
    if state.status in _TERMINAL_STATUSES:
        raise ContextTransitionError("terminal analysis context cannot be mutated")

    try:
        next_state = _apply_transition(state, draft)
    except ValidationError as exc:
        raise ContextTransitionError(str(exc)) from exc

    if next_state is state:
        next_state = state.model_copy()
    next_state = next_state.model_copy(update={"revision": state.revision + 1})
    return next_state.model_copy(update={"state_hash": canonical_state_hash(next_state)})


def _apply_transition(state: AnalysisContext, draft: ContextEventDraft) -> AnalysisContext:
    if draft.event_type == "analysis.started":
        return state.model_copy(update={"status": "running"})
    if draft.event_type == "turn.started":
        return _start_turn(state, draft)
    if draft.event_type == "simulator.context.opened":
        return _open_simulator_context(state, draft)
    if draft.event_type == "tool.observation.recorded":
        return _record_observation(state, draft)
    if draft.event_type == "result.registered":
        return _register_result(state, draft)
    if draft.event_type == "evidence.registered":
        return _register_evidence(state, draft)
    if draft.event_type == "fact.verified":
        return _record_verified_fact(state, draft)
    if draft.event_type == "domain.state.projected":
        return _project_domain_state(state, draft)
    if draft.event_type == "tool.failed":
        return _record_diagnostic(state, draft)
    if draft.event_type == "answer.submitted":
        return _record_answer_submission(state, draft)
    if draft.event_type == "audit.diagnostic.recorded":
        return _record_diagnostic(state, draft)
    if draft.event_type == "limitation.recorded":
        return _record_limitation(state, draft)
    if draft.event_type == "limitation.resolved":
        return _resolve_limitation(state, draft)
    if draft.event_type == "turn.completed":
        return _complete_turn(state, draft)
    if draft.event_type == "analysis.completed":
        return _complete_analysis(state, "completed")
    if draft.event_type == "analysis.failed":
        return _complete_analysis(state, "failed")
    raise ContextTransitionError(f"unsupported event type: {draft.event_type}")


def _start_turn(state: AnalysisContext, draft: ContextEventDraft) -> AnalysisContext:
    if state.current_turn is not None:
        raise ContextTransitionError("active turn already exists")
    if draft.turn_id is None:
        raise ContextTransitionError("turn.started requires turn_id")
    if any(turn.turn_id == draft.turn_id for turn in state.turns):
        raise ContextTransitionError("turn_id was already completed")
    payload = dict(draft.payload)
    payload["turn_id"] = draft.turn_id
    turn = ActiveTurn.model_validate(payload)
    return state.model_copy(update={"status": "running", "current_turn": turn})


def _open_simulator_context(state: AnalysisContext, draft: ContextEventDraft) -> AnalysisContext:
    _require_active_turn(state, draft)
    baseline = BaselineRecord.model_validate(draft.payload)
    baselines = _upsert_record(
        state.baselines,
        key=baseline.context_ref,
        value=baseline,
        duplicate_message=f"baseline {baseline.context_ref} already exists with different content",
    )
    return state.model_copy(update={"baselines": baselines, "active_context_ref": baseline.context_ref})


def _record_observation(state: AnalysisContext, draft: ContextEventDraft) -> AnalysisContext:
    turn = _require_active_turn(state, draft)
    capability = _require_capability(draft)
    payload = dict(draft.payload)
    payload["turn_id"] = turn.turn_id
    payload["capability"] = capability
    observation = ObservationRecord.model_validate(payload)
    _require_known_refs(state, observation.consumed_refs, allow_unregistered_context_refs=True)
    if capability == "result.branches.rank" and observation.summary.get("ok") is not False:
        _validate_ranking_observation(state, observation)
    observations = _upsert_record(
        state.observations,
        key=observation.observation_ref,
        value=observation,
        duplicate_message=f"observation {observation.observation_ref} already exists with different content",
    )
    current_turn = _merge_turn_refs(turn, consumed_refs=observation.consumed_refs, produced_refs=observation.produced_refs)
    return state.model_copy(update={"observations": observations, "current_turn": current_turn})


def _record_answer_submission(state: AnalysisContext, draft: ContextEventDraft) -> AnalysisContext:
    turn = _require_active_turn(state, draft)
    payload = draft.payload
    if payload.get("turn_id") != turn.turn_id:
        raise ContextTransitionError("answer.submitted must bind to active turn")
    for key in ("answer_path", "answer_sha256", "answer_draft_path"):
        if not isinstance(payload.get(key), str) or not payload[key]:
            raise ContextTransitionError(f"answer.submitted requires {key}")
    result_refs = payload.get("result_refs", [])
    claimed_refs = payload.get("claim_evidence_refs", [])
    if not isinstance(result_refs, list) or not all(isinstance(item, str) for item in result_refs):
        raise ContextTransitionError("answer.submitted result_refs must be strings")
    if not isinstance(claimed_refs, list) or not all(isinstance(item, str) for item in claimed_refs):
        raise ContextTransitionError("answer.submitted claim_evidence_refs must be strings")
    # Submission is accepted independently of audit findings; unknown claim
    # references are recorded by the subsequent diagnostic events.  Known
    # references are dependency edges of this answer, not newly produced
    # artifacts, and must survive into the finalized turn/report.
    known_refs = set(state.baselines) | set(state.results) | set(state.evidence)
    consumed_refs = [
        reference
        for reference in (*result_refs, *claimed_refs)
        if reference in known_refs
    ]
    current_turn = _merge_turn_refs(turn, consumed_refs=consumed_refs)
    return state.model_copy(update={"current_turn": current_turn})


def _register_result(state: AnalysisContext, draft: ContextEventDraft) -> AnalysisContext:
    turn = _require_active_turn(state, draft)
    capability = _require_capability(draft)
    if state.active_context_ref is None:
        raise ContextTransitionError("result requires a registered baseline")
    baseline = state.baselines[state.active_context_ref]
    payload = dict(draft.payload)
    payload["turn_id"] = turn.turn_id
    payload["capability"] = capability
    result = ResultRecord.model_validate(payload)
    if result.revision_ref != baseline.revision_ref:
        raise ContextTransitionError("result revision_ref does not match registered baseline")
    results = _upsert_record(
        state.results,
        key=result.result_ref,
        value=result,
        duplicate_message=f"result {result.result_ref} already exists with different content",
    )
    current_turn = _merge_turn_refs(turn, produced_refs=[result.result_ref])
    return state.model_copy(update={"results": results, "current_turn": current_turn})


def _register_evidence(state: AnalysisContext, draft: ContextEventDraft) -> AnalysisContext:
    payload = dict(draft.payload)
    evidence = EvidenceRecord.model_validate(payload)
    _require_known_refs(state, evidence.refs)
    evidence_by_ref = _upsert_record(
        state.evidence,
        key=evidence.evidence_ref,
        value=evidence,
        duplicate_message=f"evidence {evidence.evidence_ref} already exists with different content",
    )
    current_turn = state.current_turn
    if current_turn is not None and draft.turn_id == current_turn.turn_id:
        current_turn = _merge_turn_refs(current_turn, produced_refs=[evidence.evidence_ref])
    return state.model_copy(update={"evidence": evidence_by_ref, "current_turn": current_turn})


def _record_verified_fact(state: AnalysisContext, draft: ContextEventDraft) -> AnalysisContext:
    payload = dict(draft.payload)
    authored_by = payload.pop("authored_by", None)
    if authored_by not in _SIMULATOR_PROVENANCE:
        raise ContextTransitionError("fact.verified requires explicit simulator/gridctl provenance")
    capability = _require_capability(draft)
    payload["verifier_capability"] = capability
    fact = VerifiedFact.model_validate(payload)
    if not fact.evidence_refs:
        raise ContextTransitionError("verified facts must come from simulator evidence")
    _require_simulator_evidence_refs(state, fact.evidence_refs)
    facts = _upsert_record(
        state.verified_facts,
        key=fact.fact_ref,
        value=fact,
        duplicate_message=f"verified fact {fact.fact_ref} already exists with different content",
    )
    return state.model_copy(update={"verified_facts": facts})


def _project_domain_state(state: AnalysisContext, draft: ContextEventDraft) -> AnalysisContext:
    turn = _require_active_turn(state, draft)
    capability = _require_capability(draft)
    delta = DomainStateDelta.model_validate(draft.payload)
    domain = state.domain_state

    model = domain.model
    if delta.model is not None:
        _require_baseline_revision(state, delta.model.context_ref, delta.model.revision_ref, label="model")
        model = delta.model

    operating_state = domain.operating_state
    if delta.operating_state is not None:
        _require_domain_producer(delta.operating_state, capability, turn.turn_id)
        _require_baseline_revision(
            state,
            delta.operating_state.context_ref,
            delta.operating_state.revision_ref,
            label="operating state",
        )
        operating_state = delta.operating_state

    constraints = domain.constraints
    for constraint in delta.constraints:
        _require_domain_producer(constraint, capability, turn.turn_id)
        _require_baseline_revision(state, constraint.context_ref, constraint.revision_ref, label="constraint")
        constraints = _upsert_record(
            constraints,
            key=constraint.constraint_ref,
            value=constraint,
            duplicate_message=f"constraint {constraint.constraint_ref} already exists with different content",
        )

    scenarios = domain.scenarios
    for scenario in delta.scenarios:
        _require_domain_producer(scenario, capability, turn.turn_id)
        _require_baseline_revision(state, scenario.context_ref, scenario.revision_ref, label="scenario")
        scenarios = _upsert_record(
            scenarios,
            key=scenario.scenario_ref,
            value=scenario,
            duplicate_message=f"scenario {scenario.scenario_ref} already exists with different content",
        )

    calculations = domain.calculations
    for calculation in delta.calculations:
        _require_domain_producer(calculation, capability, turn.turn_id)
        _require_baseline_revision(state, calculation.context_ref, calculation.revision_ref, label="calculation")
        registered = state.results.get(calculation.result_ref)
        if registered is None:
            raise ContextTransitionError(f"calculation references unregistered result: {calculation.result_ref}")
        if registered.revision_ref != calculation.revision_ref:
            raise ContextTransitionError("calculation revision does not match registered result")
        calculations = _upsert_record(
            calculations,
            key=calculation.result_ref,
            value=calculation,
            duplicate_message=f"calculation {calculation.result_ref} already exists with different content",
        )

    capabilities = domain.capabilities
    for item in delta.capabilities:
        capabilities = _upsert_record(
            capabilities,
            key=item.id,
            value=item,
            duplicate_message=f"capability {item.id} already exists with different content",
        )

    artifacts = domain.artifacts
    for artifact in delta.artifacts:
        _require_domain_producer(artifact, capability, turn.turn_id)
        if artifact.context_ref is not None and artifact.revision_ref is not None:
            _require_baseline_revision(state, artifact.context_ref, artifact.revision_ref, label="artifact")
        artifacts = _upsert_record(
            artifacts,
            key=artifact.artifact_ref,
            value=artifact,
            duplicate_message=f"artifact {artifact.artifact_ref} already exists with different content",
        )

    return state.model_copy(
        update={
            "domain_state": domain.model_copy(
                update={
                    "model": model,
                    "operating_state": operating_state,
                    "constraints": constraints,
                    "scenarios": scenarios,
                    "calculations": calculations,
                    "capabilities": capabilities,
                    "artifacts": artifacts,
                }
            )
        }
    )


def _record_diagnostic(state: AnalysisContext, draft: ContextEventDraft) -> AnalysisContext:
    payload = dict(draft.payload)
    message = payload.pop("message", draft.event_type)
    diagnostic = DiagnosticRecord(
        event_type=draft.event_type,
        turn_id=draft.turn_id,
        capability=draft.capability,
        message=message,
        details=payload,
    )
    return state.model_copy(update={"diagnostics": [*state.diagnostics, diagnostic]})


def _record_limitation(state: AnalysisContext, draft: ContextEventDraft) -> AnalysisContext:
    payload = dict(draft.payload)
    payload.setdefault("turn_id", draft.turn_id)
    limitation = LimitationRecord.model_validate(payload)
    limitations = _upsert_record(
        {item.limitation_ref: item for item in state.unresolved_limitations},
        key=limitation.limitation_ref,
        value=limitation,
        duplicate_message=f"limitation {limitation.limitation_ref} already exists with different content",
    )
    return state.model_copy(update={"unresolved_limitations": list(limitations.values())})


def _resolve_limitation(state: AnalysisContext, draft: ContextEventDraft) -> AnalysisContext:
    limitation_ref = draft.payload.get("limitation_ref")
    if not isinstance(limitation_ref, str):
        raise ContextTransitionError("limitation.resolved requires limitation_ref")
    unresolved = [item for item in state.unresolved_limitations if item.limitation_ref != limitation_ref]
    if len(unresolved) == len(state.unresolved_limitations):
        raise ContextTransitionError(f"unknown limitation: {limitation_ref}")
    return state.model_copy(update={"unresolved_limitations": unresolved})


def _complete_turn(state: AnalysisContext, draft: ContextEventDraft) -> AnalysisContext:
    turn = _require_active_turn(state, draft)
    if any(completed_turn.turn_id == turn.turn_id for completed_turn in state.turns):
        raise ContextTransitionError("turn_id was already completed")
    payload = dict(draft.payload)
    consumed_refs = _dedupe([*turn.consumed_refs, *payload.pop("consumed_refs", [])])
    produced_refs = _dedupe([*turn.produced_refs, *payload.pop("produced_refs", [])])
    _require_known_refs(state, consumed_refs)
    turn_record = TurnRecord(
        turn_id=turn.turn_id,
        ordinal=turn.ordinal,
        instruction=turn.instruction,
        instruction_sha256=turn.instruction_sha256,
        nonce_sha256=turn.nonce_sha256,
        consumed_refs=consumed_refs,
        produced_refs=produced_refs,
        **payload,
    )
    return state.model_copy(update={"current_turn": None, "turns": [*state.turns, turn_record]})


def _complete_analysis(state: AnalysisContext, status: str) -> AnalysisContext:
    if state.current_turn is not None:
        raise ContextTransitionError("cannot complete analysis with an active turn")
    return state.model_copy(update={"status": status})


def _require_active_turn(state: AnalysisContext, draft: ContextEventDraft) -> ActiveTurn:
    if state.current_turn is None:
        raise ContextTransitionError("event requires an active turn")
    if draft.turn_id != state.current_turn.turn_id:
        raise ContextTransitionError("event turn_id does not match active turn")
    return state.current_turn


def _optional_matching_turn(state: AnalysisContext, draft: ContextEventDraft) -> ActiveTurn | None:
    if state.current_turn is None:
        return None
    if draft.turn_id != state.current_turn.turn_id:
        raise ContextTransitionError("event turn_id does not match active turn")
    return state.current_turn


def _require_capability(draft: ContextEventDraft) -> str:
    if not draft.capability:
        raise ContextTransitionError(f"{draft.event_type} requires capability")
    return draft.capability


def _require_known_refs(
    state: AnalysisContext,
    refs: list[str],
    *,
    allow_unregistered_context_refs: bool = False,
) -> None:
    known_refs = set(state.baselines) | set(state.results) | set(state.evidence) | set(state.verified_facts)
    if state.active_context_ref is not None:
        known_refs.add(state.active_context_ref)
    unknown = [
        ref
        for ref in refs
        if ref not in known_refs and not (allow_unregistered_context_refs and ref.startswith("context:sha256:"))
    ]
    if unknown:
        raise ContextTransitionError(f"unknown referenced context artifact: {unknown[0]}")


def _require_simulator_evidence_refs(state: AnalysisContext, refs: list[str]) -> None:
    unknown = [ref for ref in refs if ref not in state.evidence]
    if unknown:
        raise ContextTransitionError(f"verified fact references unknown simulator evidence: {unknown[0]}")
    unsupported = [ref for ref in refs if not _has_simulator_provenance(state.evidence[ref])]
    if unsupported:
        raise ContextTransitionError(f"evidence provenance is not simulator/gridctl: {unsupported[0]}")


def _has_simulator_provenance(evidence: EvidenceRecord) -> bool:
    summary_provenance = evidence.summary.get("provenance")
    return evidence.kind in _SIMULATOR_PROVENANCE or summary_provenance in _SIMULATOR_PROVENANCE


def _validate_ranking_observation(state: AnalysisContext, observation: ObservationRecord) -> None:
    if observation.produced_refs:
        raise ContextTransitionError("result.branches.rank observations must not produce refs")
    if not any(ref in state.results for ref in observation.consumed_refs):
        raise ContextTransitionError("result.branches.rank must consume a preexisting result ref")


def _require_baseline_revision(
    state: AnalysisContext,
    context_ref: str,
    revision_ref: str,
    *,
    label: str,
) -> None:
    baseline = state.baselines.get(context_ref)
    if baseline is None:
        raise ContextTransitionError(f"{label} references unknown model context")
    if baseline.revision_ref != revision_ref:
        raise ContextTransitionError(f"{label} revision does not match registered baseline")


def _require_domain_producer(record: Any, capability: str, turn_id: str) -> None:
    if record.producer_capability != capability:
        raise ContextTransitionError("domain state producer capability does not match event")
    if record.producer_turn_id != turn_id:
        raise ContextTransitionError("domain state producer turn does not match event")


def _merge_turn_refs(
    turn: ActiveTurn,
    *,
    consumed_refs: list[str] | None = None,
    produced_refs: list[str] | None = None,
) -> ActiveTurn:
    return turn.model_copy(
        update={
            "consumed_refs": _dedupe([*turn.consumed_refs, *(consumed_refs or [])]),
            "produced_refs": _dedupe([*turn.produced_refs, *(produced_refs or [])]),
        }
    )


def _upsert_record[T](
    records: dict[str, T],
    *,
    key: str,
    value: T,
    duplicate_message: str,
) -> dict[str, T]:
    existing = records.get(key)
    if existing is not None:
        if existing != value:
            raise ContextTransitionError(duplicate_message)
        return records
    return {**records, key: value}


def _dedupe(refs: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for ref in refs:
        if ref not in seen:
            seen.add(ref)
            deduped.append(ref)
    return deduped


PANDAPOWER_STATE_SCHEMA = "pandapower-static-analysis-state/1.0"
_STATE_SCHEMA_KEY = "state_schema"
_STATE_REVISION_KEY = "state_revision"


class PandapowerStateAdapter:
    """Validate and merge one binding's pandapower state namespace."""

    schema_id = PANDAPOWER_STATE_SCHEMA

    def validate(self, *, binding_id: str, state: Mapping[str, object]) -> None:
        if not isinstance(binding_id, str) or not binding_id:
            raise ValueError("binding_id is required")
        if not isinstance(state, Mapping):
            raise ValueError("pandapower state must be an object")
        schema = state.get(_STATE_SCHEMA_KEY)
        if schema is not None and schema != self.schema_id:
            raise ValueError("pandapower state schema does not match")
        revision = state.get(_STATE_REVISION_KEY)
        if revision is not None and (
            type(revision) is not int or revision < 0
        ):
            raise ValueError("pandapower state revision is invalid")
        self._validate_ownership(state, binding_id=binding_id)
        body = {
            key: value
            for key, value in state.items()
            if key not in {_STATE_SCHEMA_KEY, _STATE_REVISION_KEY}
        }
        try:
            DomainState.model_validate(body)
        except Exception as exc:
            raise ValueError("pandapower state is invalid") from exc
        self._validate_references(body)

    def merge(
        self,
        *,
        binding_id: str,
        state: Mapping[str, object],
        delta: KernelDomainStateDelta,
    ) -> Mapping[str, object]:
        self.validate(binding_id=binding_id, state=state)
        body = {
            key: value
            for key, value in state.items()
            if key not in {_STATE_SCHEMA_KEY, _STATE_REVISION_KEY}
        }
        current = DomainState.model_validate(body)
        try:
            domain_delta = DomainStateDelta.model_validate(
                delta.model_dump(mode="python")
            )
        except Exception as exc:
            raise ValueError("pandapower state delta is invalid") from exc
        updated = self._merge_delta(current, domain_delta)
        previous_revision = state.get(_STATE_REVISION_KEY, 0)
        assert type(previous_revision) is int
        merged: dict[str, object] = {
            _STATE_SCHEMA_KEY: self.schema_id,
            _STATE_REVISION_KEY: previous_revision + 1,
            **updated.model_dump(mode="json"),
        }
        self.validate(binding_id=binding_id, state=merged)
        return merged

    def build_context(
        self, *, binding_id: str, state: Mapping[str, object]
    ) -> PandapowerDomainContext:
        self.validate(binding_id=binding_id, state=state)
        return PandapowerDomainContext(
            binding_id=binding_id,
            state=dict(state),
        )

    @staticmethod
    def _merge_delta(current: DomainState, delta: DomainStateDelta) -> DomainState:
        values = current.model_dump(mode="python")
        if delta.model is not None:
            values["model"] = delta.model.model_dump(mode="python")
        if delta.operating_state is not None:
            values["operating_state"] = delta.operating_state.model_dump(mode="python")
        for field in (
            "constraints",
            "scenarios",
            "calculations",
            "capabilities",
            "artifacts",
        ):
            records = dict(values[field] or {})
            for item in getattr(delta, field):
                key = _record_key(field, item)
                existing = records.get(key)
                dumped = item.model_dump(mode="python")
                if (
                    field == "scenarios"
                    and isinstance(existing, Mapping)
                    and _same_scenario_content(existing, dumped)
                ):
                    continue
                if existing is not None and existing != dumped:
                    raise ValueError(f"pandapower state record collision: {key}")
                records[key] = dumped
            values[field] = records
        return DomainState.model_validate(values)

    @classmethod
    def _validate_ownership(cls, value: object, *, binding_id: str) -> None:
        if isinstance(value, Mapping):
            for key, nested in value.items():
                if not isinstance(key, str):
                    raise ValueError("pandapower state keys must be strings")
                normalized = key.casefold().replace("-", "_")
                if normalized in {
                    "binding_id",
                    "owner_binding_id",
                    "source_binding_id",
                    "target_binding_id",
                } and (type(nested) is not str or nested != binding_id):
                    raise ValueError("pandapower state has foreign binding ownership")
                if normalized.endswith("_binding_id") and (
                    type(nested) is not str or nested != binding_id
                ):
                    raise ValueError("pandapower state has foreign binding ownership")
                if normalized.endswith("_binding_ids") or normalized in {
                    "binding_ids",
                    "owner_binding_ids",
                    "source_binding_ids",
                    "target_binding_ids",
                }:
                    if not isinstance(nested, (list, tuple)) or any(
                        type(owner) is not str or owner != binding_id
                        for owner in nested
                    ):
                        raise ValueError("pandapower state has foreign binding ownership")
                cls._validate_ownership(nested, binding_id=binding_id)
            return
        if isinstance(value, (list, tuple)):
            for nested in value:
                cls._validate_ownership(nested, binding_id=binding_id)
            return
        if isinstance(value, str):
            foreign = (
                value.startswith("inventory:")
                or value.startswith("binding=inventory:")
                or "/inventory/" in value
            )
            if foreign and binding_id != "inventory":
                raise ValueError("pandapower state has foreign binding ownership")

    @staticmethod
    def _validate_references(value: object) -> None:
        if isinstance(value, Mapping):
            for key, nested in value.items():
                if key in {"context_ref", "revision_ref"} and nested is not None:
                    if not isinstance(nested, str) or not nested:
                        raise ValueError("pandapower state reference is invalid")
                PandapowerStateAdapter._validate_references(nested)
        elif isinstance(value, (list, tuple)):
            for nested in value:
                PandapowerStateAdapter._validate_references(nested)


@dataclass(frozen=True, slots=True)
class PandapowerDomainContext:
    """Detached domain context view passed to presentation and output providers."""

    binding_id: str
    state: Mapping[str, object]

    def model_dump(self, *, mode: str = "python") -> dict[str, object]:
        del mode
        return {
            "binding_id": self.binding_id,
            "state": _detach_json(self.state),
        }


def _record_key(field: str, item: object) -> str:
    if field == "constraints":
        return str(getattr(item, "constraint_ref"))
    if field == "scenarios":
        return str(getattr(item, "scenario_ref"))
    if field in {"calculations", "artifacts"}:
        return str(getattr(item, "result_ref", getattr(item, "artifact_ref", "")))
    if field == "capabilities":
        return str(getattr(item, "id"))
    raise ValueError(f"unsupported pandapower state field: {field}")


def _same_scenario_content(
    existing: Mapping[str, object], candidate: Mapping[str, object]
) -> bool:
    existing_content = dict(existing)
    candidate_content = dict(candidate)
    existing_content.pop("producer_turn_id", None)
    candidate_content.pop("producer_turn_id", None)
    return existing_content == candidate_content


def _detach_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _detach_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_detach_json(item) for item in value]
    if value is None or type(value) in {str, int, float, bool}:
        return value
    return None


__all__ = [
    "PANDAPOWER_STATE_SCHEMA",
    "PandapowerDomainContext",
    "PandapowerStateAdapter",
    "ContextTransitionError",
    "canonical_state_hash",
    "initial_context",
    "reduce_context",
]
