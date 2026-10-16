"""Source-bound execution needs, separate from model-written intent diagnostics."""

from .request_intent import IntentDecision, IntentRequest


def execution_plan_for(request: IntentRequest, decision: IntentDecision) -> dict:
    """Project validated task structure without forwarding diagnostic prose.

    Readiness is not permission. The application still prepares authorized
    resources, and Domain Packs still admit current-run results and evidence.
    """
    source = request.to_document()
    checked = IntentDecision.from_document(decision.to_document(), request)
    document = checked.to_document()
    ready = {goal['goal_id'] for goal in checked.execution_goals}
    prior: list[str] = []
    goals: list[dict] = []
    for goal in document['goals']:
        dependencies = goal.get('depends_on', list(prior))
        blockers: list[dict] = []
        if checked.needs_clarification:
            blockers.append({'kind': 'clarification_required'})
        if goal['missing_requirements']:
            blockers.append({'kind': 'unresolved_requirement'})
        unavailable = [identity for identity in dependencies if identity not in ready]
        if unavailable:
            blockers.append({'kind': 'dependency_not_ready', 'goal_ids': unavailable})
        goals.append({
            'goal_id': goal['goal_id'], 'operation': goal['operation'],
            'instruction_excerpt': goal.get('instruction_excerpt', source['instruction']),
            'message_refs': goal['message_refs'], 'object_refs': goal['object_refs'],
            'capability_refs': goal['capability_refs'], 'depends_on': dependencies,
            'status': 'ready' if goal['goal_id'] in ready else 'blocked', 'blockers': blockers,
        })
        prior.append(goal['goal_id'])
    return {'schema': 'capstone-execution-plan/1', 'attempt_id': source['attempt_id'],
            'history_cutoff': source['history_cutoff'], 'relationship': document['relationship'],
            'goals': goals, 'executable_goal_ids': [goal['goal_id'] for goal in checked.execution_goals]}
