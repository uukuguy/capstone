"""Application-owned Mission origin checks and durable Thread references."""
from copy import deepcopy
from dataclasses import replace

from psycopg.types.json import Jsonb

from .thread_protocol import ThreadProtocolError, _identifier
from .workspace_scope import workspace_name


def checked_origin(origin):
    if (not isinstance(origin, dict) or 'thread_id' not in origin
            or set(origin) - {'thread_id', 'work_id'}):
        raise ThreadProtocolError('Mission origin must name a Thread and optional Work')
    return {key: _identifier(value, name='mission.origin.' + key) for key, value in origin.items()}


def _check(snapshot, archived, origin, claim):
    from .thread_service import ThreadExecutionError
    if archived or snapshot.run.state != 'open':
        raise ThreadProtocolError('Mission origin Thread is unavailable')
    if 'work_id' in origin and not any(work['work_id'] == origin['work_id'] for work in snapshot.works):
        raise ThreadProtocolError('Mission origin Work is unavailable')
    if claim is not None:
        current = snapshot.current_attempt
        if (claim.thread_id != origin['thread_id'] or current is None
                or current.attempt_id != claim.attempt.attempt_id
                or current.phase != 'running' or claim.task_context is None
                or ('work_id' in origin and claim.task_context.binding.work_id != origin['work_id'])):
            raise ThreadExecutionError('Mission execution origin does not match the active claim')


def _reference(snapshot, mission_id, origin):
    ref = {'mission_id': mission_id, **({'work_id': origin['work_id']} if 'work_id' in origin else {})}
    previous = next((item for item in snapshot.mission_refs if item['mission_id'] == mission_id), None)
    if previous is not None:
        if previous != ref:
            raise ThreadProtocolError('Mission origin reference conflicts')
        return snapshot, False
    return replace(snapshot, mission_refs=(*snapshot.mission_refs, ref)), True


def access(service, workspace, origin, *, mission_id=None, claim=None, operation=None):
    """The Thread is the authorization source; caller metadata cannot grant access."""
    from .thread_service import ThreadExecutionError, ThreadNotFound
    origin, workspace = checked_origin(origin), workspace_name(workspace)
    if mission_id is not None:
        _identifier(mission_id, name='mission_id')
    if claim is not None and claim.workspace_name != workspace:
        raise ThreadExecutionError('Mission claim workspace does not match')
    if hasattr(service, '_lock'):
        with service._lock:
            service.require_workspace(origin['thread_id'], workspace)
            if claim is not None:
                service._require_claim(claim)
            snapshot = service._snapshot
            _check(snapshot, service._archived, origin, claim)
            if operation is not None:
                return operation()
            if mission_id is not None:
                updated, changed = _reference(snapshot, mission_id, origin)
                if changed:
                    event = service._append_control_event(event_type='mission_associated',
                        payload={'mission_id': mission_id, 'origin': origin})
                    service._snapshot = replace(updated, last_event_seq=event.event_seq)
            return deepcopy(origin)
    with service._connect() as connection:
        row = connection.execute('SELECT * FROM capstone_threads WHERE thread_id=%s AND workspace_name=%s FOR UPDATE',
            (origin['thread_id'], workspace)).fetchone()
        if row is None:
            raise ThreadNotFound(origin['thread_id'])
        snapshot = service._snapshot_from_row(row)
        if claim is not None:
            leased = connection.execute("""SELECT 1 FROM capstone_thread_attempts
                WHERE thread_id=%s AND attempt_id=%s AND lease_token=%s
                AND phase='running' AND lease_deadline > clock_timestamp()""",
                (claim.thread_id, claim.attempt.attempt_id, claim.lease_token)).fetchone()
            if leased is None:
                raise ThreadExecutionError('attempt lease is unavailable')
        _check(snapshot, row['archived'], origin, claim)
        if operation is not None:
            return operation()
        if mission_id is not None:
            updated, changed = _reference(snapshot, mission_id, origin)
            if changed:
                event = service._make_control_event(row, snapshot.active_model_context,
                    event_seq=row['last_event_seq'] + 1, event_type='mission_associated',
                    payload={'mission_id': mission_id, 'origin': origin})
                service._insert_event(connection, event)
                connection.execute('UPDATE capstone_threads SET mission_refs=%s,last_event_seq=%s WHERE thread_id=%s',
                    (Jsonb([dict(ref) for ref in updated.mission_refs]), event.event_seq, origin['thread_id']))
        return deepcopy(origin)


def bind_submission(snapshot, work_id, submission):
    """Freeze the latest explicit Mission association for this Work or Thread."""
    reference = next((ref for ref in reversed(snapshot.mission_refs)
                      if ref.get('work_id', work_id) == work_id), None)
    if reference is None:
        return submission
    origin = {'thread_id': snapshot.thread_id}
    if 'work_id' in reference:
        origin['work_id'] = reference['work_id']
    return {**(submission or {}), '_mission': {'schema': 'capstone-native-mission/1',
        'mission_id': reference['mission_id'], 'origin': origin}}
