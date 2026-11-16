"""Strict persisted Work goal state; parsing never grants execution authority."""
from datetime import datetime, timedelta

from .application_capacity import limits


GOAL_SCHEMA = 'capstone-work-goal/1'
GOAL_STATES = frozenset({'ready', 'running', 'waiting', 'paused', 'completed', 'failed', 'cancelled'})
_FIELDS = frozenset({'schema', 'objective', 'objective_revision', 'generation', 'state',
    'reason', 'max_attempts', 'attempts_admitted', 'deadline_at', 'last_settled_attempt_id'})


def parse_goal_mode(value: object) -> dict:
    """Read exact version-one state, including expired goals during recovery."""
    if not isinstance(value, dict) or set(value) != _FIELDS:
        raise ValueError('invalid goal state fields')
    if value['schema'] != GOAL_SCHEMA:
        raise ValueError('unsupported goal state schema')
    objective = value['objective']
    if (not isinstance(objective, str) or not objective.strip()
            or len(objective) > limits.input_text_chars):
        raise ValueError('invalid goal objective')
    for field in ('objective_revision', 'generation', 'max_attempts'):
        if type(value[field]) is not int or value[field] < 1:
            raise ValueError(f'invalid goal {field}')
    used = value['attempts_admitted']
    if type(used) is not int or not 0 <= used <= value['max_attempts']:
        raise ValueError('invalid goal consumed budget')
    state = value['state']
    if not isinstance(state, str) or state not in GOAL_STATES:
        raise ValueError('invalid goal lifecycle state')
    reason = value['reason']
    if reason is not None and (not isinstance(reason, str) or not reason.strip() or len(reason) > 512):
        raise ValueError('invalid goal reason')
    if state in {'paused', 'waiting', 'failed'} and reason is None:
        raise ValueError('goal lifecycle reason is required')
    deadline = value['deadline_at']
    if not isinstance(deadline, str) or 'T' not in deadline:
        raise ValueError('goal deadline must be a UTC instant')
    try:
        instant = datetime.fromisoformat(deadline)
    except ValueError as error:
        raise ValueError('invalid goal deadline') from error
    if instant.utcoffset() != timedelta(0):
        raise ValueError('goal deadline must be UTC')
    previous = value['last_settled_attempt_id']
    if previous is not None and (not isinstance(previous, str) or not previous.strip() or len(previous) > 512):
        raise ValueError('invalid goal settled attempt identity')
    # All accepted fields are immutable scalar values; callers own the mapping.
    return dict(value)


def control_goal(value: object, command: str, payload: dict, *, now: datetime) -> dict:
    """Validate control intent; the caller owns locking and executor cancellation."""
    goal = parse_goal_mode(value)
    if now.utcoffset() != timedelta(0):
        raise ValueError('goal control clock must be UTC')
    if goal['state'] in {'completed', 'cancelled', 'failed'}:
        raise ValueError('goal is terminal')
    if command == 'revise_goal_objective':
        if set(payload) != {'objective'}:
            raise ValueError('invalid objective revision payload')
        goal.update(objective=payload['objective'],
                    objective_revision=goal['objective_revision'] + 1,
                    generation=goal['generation'] + 1,
                    state='paused', reason='objective_revised')
    else:
        if payload:
            raise ValueError('goal control payload must be empty')
        if command == 'pause_goal':
            goal.update(state='paused', reason='user_pause')
        elif command == 'cancel_goal':
            goal.update(state='cancelled', reason='user_cancel')
        elif command == 'resume_goal':
            if goal['state'] not in {'paused', 'waiting'}:
                raise ValueError('goal cannot resume from current state')
            if goal['attempts_admitted'] >= goal['max_attempts']:
                raise ValueError('goal attempt budget exhausted')
            if datetime.fromisoformat(goal['deadline_at']) <= now:
                raise ValueError('goal deadline elapsed')
            goal.update(state='ready', reason=None)
        else:
            raise ValueError('unsupported goal control')
    return parse_goal_mode(goal)
