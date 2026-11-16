"""Model proposals carry no execution identity or completion authority."""
from copy import deepcopy
from datetime import datetime, timedelta
from datetime import timezone
from dataclasses import replace
import json

from .goal_mode import parse_goal_mode


def published_goal_refs(events, attempt_id):
    refs = set()
    for event in events:
        if event.get('attempt_id') != attempt_id or event.get('event_type') != 'native_artifact_published':
            continue
        artifact = event.get('payload', {}).get('artifact', {})
        for key in ('artifact_id', 'file_name'):
            value = artifact.get(key)
            if isinstance(value, str) and value.strip():
                refs.add(value)
    return tuple(sorted(refs))


def decode_goal_response(text: str) -> tuple[str, dict]:
    """Decode the explicit goal-only response protocol, never ordinary prose."""
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate goal response field')
            result[key] = value
        return result
    value = json.loads(text, object_pairs_hook=unique_object)
    if (not isinstance(value, dict) or set(value) != {'schema', 'answer', 'progress'}
            or value['schema'] != 'capstone-goal-response/1'
            or not isinstance(value['answer'], str) or not value['answer'].strip()):
        raise ValueError('invalid goal response envelope')
    return value['answer'], parse_goal_proposal(value['progress'])


def goal_response_instruction(instruction: str) -> str:
    return (instruction + '\n\nGoal mode response contract: return exactly one JSON object with '
        'schema="capstone-goal-response/1", answer (your reader-facing delivery), and progress. '
        'progress has schema="capstone-work-goal-proposal/1", disposition '
        '(continue, wait, complete), summary, next_instruction (nonempty only for continue; '
        'otherwise null), waiting_reason (nonempty only for wait; otherwise null), '
        'product_refs (array of saved product references; use [] when no references are needed). '
        'Use continue when more useful work remains, wait when input is missing, and complete '
        'only when the objective has been delivered. Save useful products before responding. '
        'Do not add markdown fences or execution identity fields.')


def prompt_goal_runtime(runtime, instruction, *, on_event, correlation_id, on_heartbeat):
    enable = getattr(runtime, 'enable_goal_response', None)
    if callable(enable):
        enable()
    response = runtime.prompt(goal_response_instruction(instruction), on_event=on_event,
        correlation_id=correlation_id, on_heartbeat=on_heartbeat)
    answer, progress = decode_goal_response(response)
    on_event({'event_type': 'goal_progress_proposed', 'payload': progress})
    return answer


class GoalProposalCapture:
    """Capture one explicit progress proposal per Attempt."""

    def __init__(self):
        self._proposal = None

    @property
    def proposal(self):
        return deepcopy(self._proposal)

    def observe(self, event) -> bool:
        if event.get('event_type') != 'goal_progress_proposed':
            return False
        if self._proposal is not None:
            raise ValueError('duplicate goal progress proposal')
        self._proposal = parse_goal_proposal(event.get('payload'))
        return True


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


def apply_terminal_goal_proposal(snapshot, context, attempt_id, proposal, *,
                                 saved_product_refs, delivery_saved):
    """Prepare Work goal state for the caller's terminal transaction."""
    works = deepcopy(list(snapshot.works))
    work = next(item for item in works if item['work_id'] == context.binding.work_id)
    goal = work['goal_mode']
    progress = parse_goal_proposal(proposal)
    settled = settle_goal_proposal(goal, progress, objective_revision=context.goal_revision,
        generation=goal['generation'], attempt_id=attempt_id, now=datetime.now(timezone.utc),
        saved_product_refs=saved_product_refs, delivery_saved=delivery_saved)
    work['goal_mode'] = settled
    work.pop('goal_continuation', None)
    if settled['state'] == 'ready':
        work['goal_continuation'] = {'predecessor_attempt_id': attempt_id,
            'generation': settled['generation'], 'next_instruction': progress['next_instruction']}
    return replace(snapshot, works=tuple(works))
