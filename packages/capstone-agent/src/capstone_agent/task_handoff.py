"""Bind one cross-session continuation to an application-owned Work version."""
from copy import deepcopy

from .thread_protocol import ThreadProtocolError, _identifier


SELECTION_FIELDS = frozenset({'thread_id', 'work_id', 'work_revision', 'revision_ref'})
MISSION_FIELDS = frozenset({'mission_id', 'mission_revision'})


def parse_task_handoff(value):
    if (not isinstance(value, dict)
            or set(value) not in (SELECTION_FIELDS, SELECTION_FIELDS | MISSION_FIELDS)
            or type(value['work_revision']) is not int or value['work_revision'] < 1):
        raise ThreadProtocolError('invalid task handoff')
    for field in ('thread_id', 'work_id', 'revision_ref'):
        _identifier(value[field], name=f'task_handoff.{field}')
    if 'mission_id' in value:
        _identifier(value['mission_id'], name='task_handoff.mission_id')
        if type(value['mission_revision']) is not int or value['mission_revision'] < 1:
            raise ThreadProtocolError('invalid Mission handoff revision')
    return dict(value)


def freeze_task_handoff(connection, target, value, *, control=None):
    selection = parse_task_handoff(value)
    if selection['thread_id'] == target['thread_id']:
        return None
    # Read the source as a single MVCC snapshot. The target already holds its
    # row lock. A second row lock would deadlock reciprocal handoffs.
    source = connection.execute(
        'SELECT works, mission_refs, last_event_seq FROM capstone_threads WHERE thread_id=%s AND workspace_name=%s',
        (selection['thread_id'], target['workspace_name']),
    ).fetchone()
    if source is None:
        return None
    work = next((item for item in source['works'] if item['work_id'] == selection['work_id']), None)
    if work is None or work['revision'] != selection['work_revision']:
        return None
    state = work.get('task_state')
    if not state or state['revision_ref'] != selection['revision_ref'] or work['status'] in {'queued', 'running'}:
        return None
    attempt = connection.execute(
        """SELECT 1 FROM capstone_thread_attempts WHERE thread_id=%s AND attempt_id=%s
           AND task_context_snapshot->'binding'->>'work_id'=%s
           AND phase IN ('completed', 'failed', 'cancelled', 'interrupted')""",
        (selection['thread_id'], selection['revision_ref'], selection['work_id']),
    ).fetchone()
    if attempt is None:
        return None
    from .thread_work import goal_task_workflow
    task_state = deepcopy(state)
    workflow = goal_task_workflow(work)
    if workflow is not None:
        task_state['workflow'] = {**workflow, 'objective': work['goal'],
                                  'plan': deepcopy(work.get('goal_plan', {}).get('plan'))}
    mission_state = None
    if 'mission_id' in selection:
        mission_id = selection['mission_id']
        association = next((ref for ref in source['mission_refs']
                            if ref['mission_id'] == mission_id
                            and ref.get('work_id', selection['work_id']) == selection['work_id']), None)
        if control is None or association is None:
            return None
        try:
            mission = control.read_mission(target['workspace_name'], mission_id)
        except KeyError:
            return None
        origin = {'thread_id': selection['thread_id']}
        if 'work_id' in association:
            origin['work_id'] = association['work_id']
        if mission['revision'] != selection['mission_revision'] or mission['origin'] != origin:
            return None
        mission_state = mission['task_state']
    return {**selection, **({'mission_state': mission_state} if mission_state is not None else {}),
            'through_event_seq': source['last_event_seq'], 'state': task_state, 'decision': deepcopy(work.get('task_decision'))}
