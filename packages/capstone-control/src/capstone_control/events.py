"""Bounded Control facts. No Agent ledger access or inferred execution events."""
from copy import deepcopy
from hashlib import sha256
import json


def task_state(goal, task):
    delegation = task.get('delegation') or {}
    return dict(task_id=task['task_id'], task_revision=task['revision'],
                objective_revision=delegation.get('goal_revision', goal['objective_revision']),
                generation=task['generation'], state=task['state'],
                delegation_id=delegation.get('delegation_id'),
                binding=deepcopy(delegation.get('binding')),
                requested_control=delegation.get('requested_control'),
                control_revision=delegation.get('control_revision'),
                delivery_revision=(task.get('delivery') or {}).get('revision'))


def build_event(before, after, metadata):
    if metadata is None or (before and before['revision'] == after['revision']):
        return None
    sequence = (before or {}).get('_event_sequence', 0) + 1
    identity = json.dumps([after['workspace'], after['goal_id'], sequence], separators=(',', ':'))
    old = {t['task_id']: task_state(before, t) for t in before['tasks']} if before else {}
    new = {t['task_id']: task_state(after, t) for t in after['tasks']}
    changes = [dict(task_id=key, before=old.get(key), after=new.get(key))
               for key in sorted(old.keys() | new.keys()) if old.get(key) != new.get(key)]
    previous_revision = (before or {}).get('_event_revision', 0)
    gap = (dict(from_revision=previous_revision + 1, through=before['revision'])
           if before and previous_revision != before['revision'] else None)
    complete = not before or (before.get('_event_history_complete', False) and gap is None)
    result = dict(schema='capstone-control-event/1', source='capstone-control',
                  event_id='control_event_' + sha256(identity.encode()).hexdigest()[:32],
                  workspace=after['workspace'], goal_id=after['goal_id'], sequence=sequence,
                  before={k: before[k] for k in ('revision', 'objective_revision', 'state', 'reason')} if before else None,
                  after={k: after[k] for k in ('revision', 'objective_revision', 'state', 'reason')},
                  task_changes=changes, history_complete=complete,
                  missing_goal_revisions={'from': gap['from_revision'], 'through': gap['through']} if gap else None,
                  **deepcopy(metadata))
    # Fail before either the aggregate or event is committed, including MemoryStore.
    json.dumps(result, allow_nan=False)
    after['_event_sequence'] = sequence
    after['_event_revision'] = after['revision']
    after['_event_history_complete'] = complete
    return result


def page_bounds(goal, after, limit, through):
    high = goal.get('_event_sequence', 0)
    through = high if through is None else through
    if (type(after) is not int or type(through) is not int or type(limit) is not int
            or not 1 <= limit <= 100 or not 0 <= after <= through <= high):
        raise ValueError('invalid Control event page boundary')
    return through


def event_page(workspace, goal_id, rows, first, last, after, limit, through):
    events = rows[:limit]
    return dict(schema='capstone-control-events/1', workspace=workspace, goal_id=goal_id,
                events=events, after_sequence=after, through_sequence=through,
                next_sequence=events[-1]['sequence'] if events else after,
                has_more=len(rows) > limit,
                history_complete=bool(last and last['history_complete']),
                first_recorded_goal_revision=first['after']['revision'] if first else None)
