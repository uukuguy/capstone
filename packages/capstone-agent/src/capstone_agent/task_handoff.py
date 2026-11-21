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


def lock_takeover_source(connection, workspace, value):
    """Lock the selected live Instruction within its workspace for a transfer."""
    selection = parse_task_handoff(value)
    if 'mission_id' in selection:
        raise ThreadProtocolError('Instruction takeover cannot select a Mission')
    return connection.execute("""
        SELECT a.attempt_id, a.turn_id, a.phase, a.takeover_target_thread_id, t.last_event_seq
        FROM capstone_threads t JOIN capstone_thread_attempts a
          ON a.thread_id=t.thread_id AND a.run_id=t.run_id
        CROSS JOIN LATERAL jsonb_array_elements(t.works) AS item(work)
        WHERE t.thread_id=%s AND t.workspace_name=%s AND t.run_state='open' AND NOT t.archived
          AND a.attempt_id=%s AND a.phase IN ('accepted', 'running', 'waiting')
          AND t.current_attempt->>'attempt_id'=a.attempt_id
          AND a.task_context_snapshot->'binding'->>'work_id'=%s
          AND item.work->>'work_id'=%s AND item.work->>'revision'=%s
          AND item.work->>'latest_attempt_id'=a.attempt_id
          AND item.work->'conversation_mode'='true'::jsonb
          AND NOT (item.work ? 'goal_mode')
          AND item.work->'cancel_requested' IS DISTINCT FROM 'true'::jsonb
        FOR UPDATE OF a, t SKIP LOCKED
    """, (selection['thread_id'], workspace, selection['revision_ref'],
          selection['work_id'], selection['work_id'], str(selection['work_revision']))).fetchone()


def reserve_instruction_takeover(connection, workspace, target_thread_id, value):
    """Reserve one destination while keeping the source worker's lease intact."""
    selection = parse_task_handoff(value)
    if selection['thread_id'] == target_thread_id:
        return False
    target = connection.execute("""
        SELECT 1 FROM capstone_threads
        WHERE thread_id=%s AND workspace_name=%s AND run_state='open'
          AND NOT archived AND current_attempt IS NULL
        FOR UPDATE SKIP LOCKED
    """, (target_thread_id, workspace)).fetchone()
    if target is None:
        return False
    source = lock_takeover_source(connection, workspace, selection)
    if source is None:
        return False
    return connection.execute("""
        UPDATE capstone_thread_attempts SET takeover_target_thread_id=%s
        WHERE attempt_id=%s
          AND (takeover_target_thread_id IS NULL OR takeover_target_thread_id=%s)
        RETURNING attempt_id
    """, (target_thread_id, source['attempt_id'], target_thread_id)).fetchone() is not None


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
    unconfirmed = []
    if state['execution']['phase'] != 'completed':
        unconfirmed = connection.execute("""
            SELECT task_id, tool_call_id, tool_name FROM (
                SELECT DISTINCT ON (payload->>'task_id', payload->>'tool_call_id')
                    payload->>'task_id' AS task_id, payload->>'tool_call_id' AS tool_call_id,
                    payload->>'tool_name' AS tool_name, payload->>'native_type' AS native_type
                FROM capstone_thread_events
                WHERE thread_id=%s AND attempt_id=%s AND event_seq <= %s
                  AND visibility='public' AND event_type='runtime_event'
                  AND payload->>'native_type' IN ('tool_execution_start', 'tool_execution_end')
                  AND payload->>'task_id' <> '' AND payload->>'tool_call_id' <> ''
                  AND payload->>'tool_name' <> ''
                ORDER BY payload->>'task_id', payload->>'tool_call_id', event_seq DESC
            ) AS latest
            WHERE native_type='tool_execution_start'
            ORDER BY task_id, tool_call_id LIMIT 65
        """, (selection['thread_id'], selection['revision_ref'], source['last_event_seq'])).fetchall()
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
            **({'unconfirmed_native_calls': unconfirmed[:64],
                'unconfirmed_native_calls_truncated': len(unconfirmed) > 64} if unconfirmed else {}),
            'through_event_seq': source['last_event_seq'], 'state': task_state, 'decision': deepcopy(work.get('task_decision'))}
