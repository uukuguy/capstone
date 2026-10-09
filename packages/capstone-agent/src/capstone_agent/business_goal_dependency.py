"""Trusted, current-Attempt business dependencies for prepared business goals."""
from dataclasses import dataclass, field
import json
from typing import TYPE_CHECKING

from .harness import AdmittedAttemptAnswer

if TYPE_CHECKING:
    from .thread_service import AttemptClaim


@dataclass(frozen=True, slots=True, init=False)
class AdmittedBusinessGoalDependency:
    """An application-issued receipt of an already admitted business goal."""

    _document_json: str = field(repr=False)

    def __init__(self, attempt_id: str, goal_id: str, model_context_id: str,
                 capability_refs: tuple[str, ...], admission: AdmittedAttemptAnswer,
                 tool_events: tuple[dict, ...]):
        if (not isinstance(admission, AdmittedAttemptAnswer) or
            not (admission.mode == 'authority_backed' or
                 (admission.mode == 'offline_information' and
                  admission.assurance == 'deterministic_information' and
                  'current_model_observation_verified' in admission.diagnostic_codes))):
            raise ValueError('business dependency requires professional admission')
        if any(not isinstance(value, str) or not value or len(value) > 256
               for value in (attempt_id, goal_id, model_context_id, *capability_refs)):
            raise ValueError('business dependency identity is invalid')
        if not capability_refs or len(set(capability_refs)) != len(capability_refs) or len(tool_events) > 128:
            raise ValueError('business dependency resource bounds are invalid')
        events = []
        fields = {'tool_name', 'tool_call_id', 'ok', 'capability', 'binding_id',
                  'capability_id', 'projector_id', 'result_kind', 'context_ref',
                  'model_ref', 'model_id', 'model_revision'}
        for event in tool_events:
            receipt = {key: value for key, value in event.items() if key in fields}
            for key in ('result_refs', 'evidence_refs'):
                admitted = getattr(admission, key)
                receipt[key] = [ref for ref in event.get(key, ()) if ref in admitted]
            events.append(receipt)
        document = {'schema': 'capstone-business-goal-dependency/1',
            'attempt_id': attempt_id, 'goal_id': goal_id, 'model_context_id': model_context_id,
            'capability_refs': list(capability_refs), 'answer': admission.answer,
            'admission': {'mode': admission.mode, 'assurance': admission.assurance,
                'result_refs': list(admission.result_refs), 'evidence_refs': list(admission.evidence_refs),
                'diagnostic_codes': list(admission.diagnostic_codes)},
            'result_projections': [dict(item) for item in admission.result_projections],
            'tool_receipts': events}
        serialized = json.dumps(document, ensure_ascii=False, allow_nan=False, sort_keys=True)
        if len(serialized.encode()) > 256 * 1024:
            raise ValueError('business dependency exceeds byte bounds')
        object.__setattr__(self, '_document_json', serialized)

    def to_document(self) -> dict:
        return json.loads(self._document_json)


def business_dependencies_for_claim(claim: 'AttemptClaim') -> list[dict]:
    """Admit only resolved source goals in the current model/profile scope."""
    plan = claim.turn_plan
    resources = {} if plan is None else getattr(plan, 'intent_resources', None) or {}
    values = resources.get('business_goal_dependencies', ())
    if not isinstance(values, tuple) or len(values) > 16:
        raise ValueError('typed business dependencies are invalid')
    if not values:
        return []
    if plan is None or plan.intent_decision is None:
        raise ValueError('business dependency has no validated target goal')
    targets = plan.intent_decision.to_document()['goals']
    target_refs = {ref for goal in targets for ref in goal['capability_refs']}
    resolved = resources.get('resolved_goal_dependencies', ())
    result, seen = [], set()
    for value in values:
        if not isinstance(value, AdmittedBusinessGoalDependency):
            raise ValueError('typed business dependency is required')
        document = value.to_document()
        if (document['attempt_id'] != claim.attempt.attempt_id or
            document['model_context_id'] != claim.model_context_id or
            document['goal_id'] not in resolved or document['goal_id'] in seen or
            not set(document['capability_refs']).issubset(target_refs)):
            raise ValueError('business dependency is outside the current authorized scope')
        seen.add(document['goal_id'])
        result.append(document)
    return result
