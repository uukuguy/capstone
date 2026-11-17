"""Pure instruction transitions; callers own durable transactions and lease checks."""
from copy import deepcopy


def submit(queue, identity, text, attempt_id):
    if any(not isinstance(value, str) or not value.strip()
           for value in (identity, text, attempt_id)):
        raise ValueError('Instruction identity, text and attempt are required')
    previous = next((item for item in queue if item['id'] == identity), None)
    if previous is not None:
        if previous['text'] != text or previous['attempt_id'] != attempt_id:
            raise ValueError('Instruction identity was reused with different content')
        return deepcopy(queue)
    result = deepcopy(queue)
    result.append(dict(id=identity, text=text, attempt_id=attempt_id,
                       sequence=max((item['sequence'] for item in queue), default=0) + 1,
                       state='pending'))
    return result


def withdraw(queue, identity):
    result = deepcopy(queue)
    item = next((item for item in result if item['id'] == identity), None)
    if item is None:
        raise ValueError('Instruction not found')
    if item['state'] in {'admitted', 'delivering', 'delivery_unknown'}:
        raise ValueError('Instruction already in execution')
    item['state'] = 'withdrawn'
    return result


def admit(queue, attempt_id, lease_token, *, stopped=False):
    if not isinstance(lease_token, str) or not lease_token:
        raise ValueError('A checked execution lease is required')
    result = deepcopy(queue)
    if stopped:
        return result, None
    item = next((item for item in result
                 if item['attempt_id'] == attempt_id and item['state'] == 'pending'), None)
    if item is None:
        return result, None
    # Lease secrets remain execution-owner state, never public Work projections.
    item.update(state='admitted')
    return result, deepcopy(item)


def pending(queue, attempt_id):
    return tuple(deepcopy(item) for item in sorted(queue, key=lambda item: item['sequence'])
                 if item['attempt_id'] == attempt_id and item['state'] == 'pending')


def reserve(queue, attempt_id, identity):
    """Fence withdrawal before transport. Delivery is not context admission."""
    existing = next((item for item in queue if item['id'] == identity
                     and item['attempt_id'] == attempt_id), None)
    if existing is not None and existing['state'] in {'delivering', 'admitted'}:
        return deepcopy(queue), deepcopy(existing), False
    waiting = pending(queue, attempt_id)
    if not waiting or waiting[0]['id'] != identity:
        return deepcopy(queue), None, False
    result = deepcopy(queue)
    item = next(item for item in result if item['id'] == identity)
    item['state'] = 'delivering'
    return result, deepcopy(item), True


def acknowledge(queue, attempt_id, identity):
    result = deepcopy(queue)
    item = next((item for item in result if item['id'] == identity
                 and item['attempt_id'] == attempt_id), None)
    if item is None or item['state'] not in {'delivering', 'admitted'}:
        return result, None, False
    changed = item['state'] != 'admitted'
    item['state'] = 'admitted'
    return result, deepcopy(item), changed


def access(service, claim, operation, identity=None):
    """Serialize queue changes with command, stop and terminal transactions."""
    from dataclasses import replace
    from psycopg.types.json import Jsonb
    from .thread_service import ThreadExecutionError

    def change(snapshot, stopped):
        work = next((item for item in snapshot.works
                     if item.get('latest_attempt_id') == claim.attempt.attempt_id), None)
        if work is None or (operation != 'acknowledge' and (stopped or work.get('cancel_requested'))):
            return snapshot, None, None
        queue = work.get('instruction_queue', [])
        if operation == 'peek':
            return snapshot, pending(queue, claim.attempt.attempt_id), None
        updated, item, changed = (reserve if operation == 'reserve' else acknowledge)(
            queue, claim.attempt.attempt_id, identity)
        if not changed:
            return snapshot, item, None
        works = deepcopy(list(snapshot.works))
        saved = next(item for item in works if item['work_id'] == work['work_id'])
        saved['instruction_queue'] = updated
        saved['revision'] += 1
        payload = dict(work_id=work['work_id'], instruction_id=item['id'],
                       sequence=item['sequence'], state=item['state'])
        return replace(snapshot, works=tuple(works)), item, payload

    event_type = 'instruction_delivery_started' if operation == 'reserve' else 'instruction_admitted'
    if hasattr(service, '_lock'):
        with service._lock:
            record = service._require_claim(claim)
            if record['attempt'].phase != 'running':
                raise ThreadExecutionError('attempt is not running')
            updated, item, payload = change(service._snapshot, claim.attempt.attempt_id in service._cancel_requests)
            if payload is not None:
                event = service._append_event(event_type=event_type, attempt=record['attempt'],
                                              payload=payload, context=record.get('model_context'))
                service._snapshot = replace(updated, last_event_seq=event.event_seq)
            return () if operation == 'peek' and item is None else item
    with service._connect() as connection:
        # Commands also lock the Thread. Read the lease without taking a
        # second row lock: terminal writers may already hold the Attempt.
        thread = connection.execute('SELECT * FROM capstone_threads WHERE thread_id=%s FOR UPDATE',
                                    (claim.thread_id,)).fetchone()
        attempt = connection.execute("""SELECT * FROM capstone_thread_attempts
            WHERE attempt_id=%s AND thread_id=%s AND lease_token=%s AND phase='running'
            AND lease_deadline > clock_timestamp()""",
            (claim.attempt.attempt_id, claim.thread_id, claim.lease_token)).fetchone()
        if attempt is None:
            raise ThreadExecutionError('attempt lease is unavailable')
        snapshot = service._snapshot_from_row(thread)
        if snapshot.current_attempt is None or snapshot.current_attempt.attempt_id != claim.attempt.attempt_id:
            raise ThreadExecutionError('attempt snapshot is inconsistent')
        stopped = connection.execute("""SELECT 1 FROM capstone_thread_events
            WHERE thread_id=%s AND attempt_id=%s AND event_type='attempt_cancel_requested' LIMIT 1""",
            (claim.thread_id, claim.attempt.attempt_id)).fetchone() is not None
        updated, item, payload = change(snapshot, stopped)
        if payload is not None:
            event = service._make_attempt_event(thread, snapshot.current_attempt,
                event_seq=thread['last_event_seq'] + 1, event_type=event_type,
                payload=payload, context=claim.model_context)
            service._insert_event(connection, event)
            connection.execute('UPDATE capstone_threads SET works=%s,last_event_seq=%s WHERE thread_id=%s',
                               (Jsonb(list(updated.works)), event.event_seq, claim.thread_id))
        return () if operation == 'peek' and item is None else item
