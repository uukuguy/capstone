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
