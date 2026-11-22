"""Pure instruction transitions; callers own durable transactions and lease checks."""
from copy import deepcopy


def supported(binding):
    capability = (binding or {}).get('capability', {})
    return ('capstone-native-instruction/1' in capability.get('instruction_schemas', ())
            and 'capstone-execution-authority/1' in capability.get('execution_authority_schemas', ())
            and type(capability.get('instruction_limit')) is int and capability['instruction_limit'] > 0)


def enqueue_rejection(binding, snapshot, work_id):
    if not supported(binding):
        return 'instruction_queue_unavailable'
    attempt = snapshot.current_attempt
    work = next((item for item in snapshot.works if item['work_id'] == work_id), None)
    if attempt is None or work is None:
        return None
    # Count withdrawn entries too. A single accepted attempt never exceeds
    # the host's frozen idempotency ledger capacity.
    entries = [item for item in work.get('instruction_queue', []) if item['attempt_id'] == attempt.attempt_id]
    count = sum(item.get('mode') != 'after_attempt' for item in entries)
    return 'instruction_queue_capacity_reached' if count >= binding['capability']['instruction_limit'] else None


def can_defer(snapshot, command, rejection):
    if (rejection not in (None, 'instruction_queue_capacity_reached') or 'mode' in command['payload']
            or snapshot.active_model_context is not None):
        return False
    return any(work['work_id'] == command['target']['id'] and work.get('conversation_mode')
               and 'goal_mode' not in work
               and (rejection == 'instruction_queue_capacity_reached' or command['payload'].get('attachment_refs')
                    or any(item.get('mode') == 'after_attempt' and item['state'] == 'pending'
                           for item in work.get('instruction_queue', ())))
               for work in snapshot.works)


def freeze_queue_attachments(service, thread_id, refs, *, connection=None):
    from .application_capacity import limits
    from .resource_manifest import checked_resource
    from .thread_resources import ResourceUploads

    if (not isinstance(refs, list) or len(refs) > limits.context_references
            or any(not isinstance(ref, str) for ref in refs) or len(set(refs)) != len(refs)):
        raise ValueError('invalid queued attachments')
    if not refs:
        return []
    states = ResourceUploads(service, service._material_objects).resource_states(thread_id, connection)
    complete = {item['resource']['resource_id']: item['resource'] for item in states if item['state'] == 'complete'}
    if not set(refs) <= complete.keys():
        raise ValueError('queued attachment is unavailable')
    return [checked_resource(dict(complete[ref])) for ref in refs]


def queued_attachment_pinned(service, snapshot, resource, connection):
    pending_ids = {(work['work_id'], item['id']) for work in snapshot.works
                   for item in work.get('instruction_queue', ())
                   if item['state'] == 'pending' and item.get('mode') == 'after_attempt'}
    if not pending_ids:
        return False
    if connection is None:
        manifests = (item for key in pending_ids for item in service._queued_attachments.get(key, ()))
        return any((item['resource_id'], item['version']) == (resource['resource_id'], resource['version'])
                   for item in manifests)
    from psycopg.types.json import Jsonb

    return connection.execute("""SELECT 1 FROM capstone_queued_attachments
        WHERE thread_id=%s AND command_id=ANY(%s) AND manifests @> %s LIMIT 1""",
        (snapshot.thread_id, [command for _, command in pending_ids],
         Jsonb([{'resource_id': resource['resource_id'], 'version': resource['version']}]))).fetchone() is not None


def submit(queue, identity, text, attempt_id, *, mode=None):
    if any(not isinstance(value, str) or not value.strip()
           for value in (identity, text, attempt_id)):
        raise ValueError('Instruction identity, text and attempt are required')
    previous = next((item for item in queue if item['id'] == identity), None)
    if previous is not None:
        if previous['text'] != text or previous['attempt_id'] != attempt_id or previous.get('mode') != mode:
            raise ValueError('Instruction identity was reused with different content')
        return deepcopy(queue)
    result = deepcopy(queue)
    result.append(dict(id=identity, text=text, attempt_id=attempt_id,
                       sequence=max((item['sequence'] for item in queue), default=0) + 1,
                       state='pending', **({'mode': mode} if mode else {})))
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
                 if item['attempt_id'] == attempt_id and item['state'] == 'pending'
                 and item.get('mode') != 'after_attempt'), None)
    if item is None:
        return result, None
    # Lease secrets remain execution-owner state, never public Work projections.
    item.update(state='admitted')
    return result, deepcopy(item)


def pending(queue, attempt_id):
    return tuple(deepcopy(item) for item in sorted(queue, key=lambda item: item['sequence'])
                 if item['attempt_id'] == attempt_id and item['state'] == 'pending' and 'mode' not in item)


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
        if operation == 'acknowledge':
            payload['text'] = item['text']
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
            WHERE attempt_id=%s AND thread_id=%s AND lease_token=%s AND phase='running'""",
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


def replacement_item(snapshot, attempt_id):
    """Choose an explicit interruption for the current Work."""
    for work in snapshot.works:
        if (work.get('latest_attempt_id') == attempt_id and work.get('conversation_mode')
                and not work.get('cancel_requested') and 'goal_mode' not in work):
            for item in work.get('instruction_queue', ()):
                if (item['attempt_id'] == attempt_id and item['state'] == 'pending'
                        and item.get('mode') == 'interrupt'):
                    return work['work_id'], item
    return None


def prepare_replacement(before, terminal, attempt_id, submission, *, phase=None, terminal_payload=None, queued_attachments=None,
                        organizer_active=False, recovered_work_id=None):
    """Admit a separate instruction using the source Attempt's frozen grants."""
    from dataclasses import replace
    from .thread_work import create_attempt, project_work
    from .enterprise_context import TaskContext
    import secrets

    selection = replacement_item(before, attempt_id) if recovered_work_id is None else None
    interrupt = selection is not None
    outcome = terminal_payload or {}
    settled_failure = (phase == 'failed' and terminal_payload is not None
                       and (outcome.get('outcome') or {}).get('execution_state') not in {'unknown', 'delivery_recovery_pending'}
                       and outcome.get('error_code') not in {
                           'native_execution_outcome_unknown', 'native_process_cleanup_unconfirmed',
                           'native_result_retention_expired'})
    if (selection is None and not organizer_active and (phase == 'completed' or settled_failure)
            and terminal.current_attempt is None):
        source = before.current_attempt
        if recovered_work_id is not None or (source is not None and source.attempt_id == attempt_id):
            for work in before.works:
                if recovered_work_id is not None and work['work_id'] != recovered_work_id:
                    continue
                if (work.get('latest_attempt_id') == attempt_id and work.get('conversation_mode')
                        and not work.get('cancel_requested') and 'goal_mode' not in work):
                    item = next((item for item in work.get('instruction_queue', ())
                                 if item['attempt_id'] == attempt_id and item['state'] == 'pending'
                                 and item.get('mode') != 'interrupt'), None)
                    if item is not None:
                        selection = (work['work_id'], item)
                        break
    if selection is None:
        return None
    work_id, selected = selection
    works = deepcopy(terminal.works)
    work = next(item for item in works if item['work_id'] == work_id)
    queued = next(item for item in work['instruction_queue'] if item['id'] == selected['id'])
    queued['state'] = 'admitted'
    work.update(status='queued', revision=work['revision'] + 1, messages=[queued['text']],
                consumed_message_count=0, cancel_requested=False)
    context = TaskContext.from_document(work['task_context'])
    work['task_context'] = replace(context, snapshot_id='task_' + secrets.token_hex(10)).to_document()
    snapshot, current, task_context, text = create_attempt(replace(terminal, works=works), work, bind_task_state=True)
    frozen = {**deepcopy(submission or {}), 'input': {'kind': 'text', 'text': text},
              '_instruction_command_id': queued['id']}
    frozen.pop('_task_handoff', None)
    attachments = queued_attachments(work_id, queued['id']) if queued_attachments is not None else []
    frozen['attachment_refs'] = [item['resource_id'] for item in attachments]
    if attachments:
        selected_ids = set(frozen['attachment_refs'])
        inherited = [item for item in frozen.get('_resource_manifests', ()) if item['resource_id'] not in selected_ids]
        frozen['_resource_manifests'] = [*inherited, *attachments]
    payload = {'command_id': queued['id'], 'kind': 'send_auto',
               'payload': {'text': text, 'source_attempt_id': attempt_id},
               **({'attachment_refs': frozen['attachment_refs'],
                   'attachment_versions': {item['resource_id']: item['version'] for item in attachments}}
                  if attachments else {}),
               **({'supersedes_attempt_id': attempt_id} if interrupt else {}), 'work_id': work_id,
               'work': project_work(snapshot, work)}
    return snapshot, current, task_context, frozen, payload
