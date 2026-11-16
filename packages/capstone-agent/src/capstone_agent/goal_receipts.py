"""Model proposals carry no execution identity or completion authority."""
from copy import deepcopy
from datetime import datetime, timedelta

from .goal_mode import parse_goal_mode


def parse_goal_proposal(value: object) -> dict:
    fields = {'schema', 'disposition', 'summary', 'next_instruction', 'waiting_reason', 'product_refs'}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError('invalid goal proposal fields')
    if value['schema'] != 'capstone-work-goal-proposal/1':
        raise ValueError('unsupported goal proposal schema')
    disposition = value['disposition']
    if not isinstance(disposition, str) or disposition not in {'continue', 'wait', 'complete'}:
        raise ValueError('invalid goal disposition')
    for name in ('summary', 'next_instruction', 'waiting_reason'):
        text = value[name]
        if text is not None and (not isinstance(text, str) or not text.strip() or len(text) > 8192):
            raise ValueError('invalid goal proposal text')
    if value['summary'] is None:
        raise ValueError('goal proposal summary is required')
    if disposition == 'continue' and value['next_instruction'] is None:
        raise ValueError('continuation instruction is required')
    if disposition != 'continue' and value['next_instruction'] is not None:
        raise ValueError('unexpected continuation instruction')
    if (disposition == 'wait') != (value['waiting_reason'] is not None):
        raise ValueError('waiting reason does not match disposition')
    refs = value['product_refs']
    if (not isinstance(refs, list) or len(refs) > 64
            or any(not isinstance(ref, str) or not ref.strip() or len(ref) > 2048 for ref in refs)
            or len(set(refs)) != len(refs)):
        raise ValueError('invalid goal product references')
    return deepcopy(value)


def settle_goal_proposal(value: object, proposal: object, *, objective_revision: int,
                         generation: int, attempt_id: str, now: datetime,
                         saved_product_refs: tuple[str, ...], delivery_saved: bool) -> dict:
    """Qualify a proposal against host facts; callers persist the result atomically."""
    goal = parse_goal_mode(value)
    progress = parse_goal_proposal(proposal)
    if (type(objective_revision) is not int or type(generation) is not int
            or objective_revision != goal['objective_revision'] or generation != goal['generation']):
        raise ValueError('stale goal execution identity')
    if goal['state'] != 'running' or goal['attempts_admitted'] < 1:
        raise ValueError('goal has no active execution')
    if not isinstance(attempt_id, str) or not attempt_id.strip() or len(attempt_id) > 512:
        raise ValueError('invalid goal attempt identity')
    if goal['last_settled_attempt_id'] == attempt_id:
        raise ValueError('goal attempt already settled')
    if now.utcoffset() != timedelta(0):
        raise ValueError('goal boundary clock must be UTC')
    if not set(progress['product_refs']) <= set(saved_product_refs):
        raise ValueError('goal references unsaved products')
    goal['last_settled_attempt_id'] = attempt_id
    if progress['disposition'] == 'complete':
        if delivery_saved is not True:
            raise ValueError('goal delivery is not saved')
        goal.update(state='completed', reason=None)
    elif progress['disposition'] == 'wait':
        goal.update(state='waiting', reason=progress['waiting_reason'][:512])
    elif goal['attempts_admitted'] >= goal['max_attempts']:
        goal.update(state='paused', reason='attempt_budget_exhausted')
    elif datetime.fromisoformat(goal['deadline_at']) <= now:
        goal.update(state='paused', reason='deadline_elapsed')
    else:
        goal.update(state='ready', reason=None)
    return parse_goal_mode(goal)
