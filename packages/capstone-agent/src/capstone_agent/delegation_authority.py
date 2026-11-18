"""Resolve Mission dependencies against the producing execution ledger."""
from copy import deepcopy

from capstone_control.contracts import authority_source

from .structural_context import checked_authority_references, checked_structural_context

GRANT_EVENT = 'delegation_authority_sources_granted'


def frozen_authority_sources(service, thread_id, work_id, connection=None):
    if connection is None:
        rows = [event.payload for event in service._events
                if event.thread_id == thread_id and event.event_type == GRANT_EVENT
                and event.payload['work_id'] == work_id]
    else:
        rows = [row['payload'] for row in connection.execute("""SELECT payload FROM capstone_thread_events
            WHERE thread_id=%s AND event_type=%s AND payload->>'work_id'=%s LIMIT 2""",
            (thread_id, GRANT_EVENT, work_id))]
    if len(rows) > 1:
        raise ValueError('conflicting delegation authority grants')
    return deepcopy(rows[0]) if rows else None


def grant_authority_sources(service, workspace, thread_id, work_id, delegation_id, sources, origin):
    from .thread_materials import _mutate, _write_event

    service.require_workspace(thread_id, workspace)
    resolve_authority_inputs(service, workspace, sources)
    catalog = origin_catalog(service, workspace, origin)
    if not sources and catalog is None:
        return
    grant = {'workspace': workspace, 'work_id': work_id, 'delegation_id': delegation_id,
             'sources': sources, 'catalog': catalog}

    def save(snapshot, connection):
        if not any(work['work_id'] == work_id for work in snapshot.works):
            raise ValueError('delegation authority consumer Work is unavailable')
        previous = frozen_authority_sources(service, thread_id, work_id, connection)
        if previous is not None and any(previous[key] != grant[key]
                                        for key in ('workspace', 'work_id', 'delegation_id', 'sources')):
            raise ValueError('delegation authority grant changed')
        if previous is None:
            _write_event(service, snapshot, GRANT_EVENT, grant, connection)

    _mutate(service, thread_id, save)


def origin_catalog(service, workspace, origin):
    thread_id = origin['thread_id']
    service.require_workspace(thread_id, workspace)
    snapshot = service.snapshot(thread_id)
    works = [work for work in snapshot.works if work.get('conversation_mode')
             and work['work_id'] == origin.get('work_id', work['work_id'])]
    if len(works) != 1 or not works[0].get('latest_attempt_id'):
        return None
    attempt_id = works[0]['latest_attempt_id']
    if hasattr(service, '_lock'):
        with service._lock:
            submission = service._attempts.get(attempt_id, {}).get('submission')
    else:
        with service._connect() as connection:
            row = connection.execute("""SELECT submission_snapshot FROM capstone_thread_attempts
                WHERE thread_id=%s AND attempt_id=%s""", (thread_id, attempt_id)).fetchone()
            submission = row['submission_snapshot'] if row else None
    return deepcopy((submission or {}).get('_application_catalog'))


def resolve_authority_inputs(service, workspace, sources):
    if not isinstance(sources, list) or len(sources) > 64:
        raise ValueError('invalid delegation authority sources')
    inputs = []
    for source in sources:
        authority_source(source)
        thread_id, attempt_id = source['thread_id'], source['attempt_id']
        service.require_workspace(thread_id, workspace)
        if hasattr(service, '_lock'):
            with service._lock:
                record = service._attempts.get(attempt_id) or {}
                context = record.get('task_context')
                event = next((event.to_document() for event in service._events
                    if event.thread_id == thread_id and event.attempt_id == attempt_id
                    and event.event_id == source['answer_ref']
                    and event.event_type == 'attempt_completed'), None)
                if context is None or context.binding.work_id != source['work_id'] or event is None:
                    raise ValueError('delegation authority source is unavailable')
                payload = event['payload']
                plan = deepcopy(record.get('intent_input_snapshot'))
        else:
            with service._connect() as connection:
                row = connection.execute("""SELECT e.payload, a.intent_input_snapshot
                    FROM capstone_thread_events e JOIN capstone_thread_attempts a
                    ON a.thread_id=e.thread_id AND a.attempt_id=e.attempt_id AND a.run_id=e.run_id
                    WHERE e.thread_id=%s AND e.attempt_id=%s AND e.event_id=%s
                    AND e.event_type='attempt_completed' AND a.phase='completed'
                    AND a.task_context_snapshot->'binding'->>'work_id'=%s""",
                    (thread_id, attempt_id, source['answer_ref'], source['work_id'])).fetchone()
                if row is None:
                    raise ValueError('delegation authority source is unavailable')
                payload, plan = row['payload'], row['intent_input_snapshot']
        structural = checked_structural_context((plan or {}).get('resources', {}).get('structural_context'))
        selector = ({'model': structural['model']} if structural['model'] is not None
                    else {'work_scope': structural['work_scope']} if 'work_scope' in structural else None)
        if selector is None:
            raise ValueError('delegation authority source has no frozen owner')
        receipts = [checked_authority_references(item) for item in payload.get('authority_references', ())]
        if not receipts or any(not set(receipt['result_refs']).issubset(payload.get('result_refs', ()))
                or not set(receipt['evidence_refs']).issubset(payload.get('evidence_refs', ()))
                for receipt in receipts):
            raise ValueError('delegation authority source is outside terminal admission')
        for receipt in receipts:
            owner = next((item['owner'] for item in structural.get('authority_inputs', ())
                if item['authority_id'] == receipt['authority_id']
                and set(receipt['result_refs']).issubset(item['result_refs'])
                and set(receipt['evidence_refs']).issubset(item['evidence_refs'])), selector)
            inputs.append({'owner': owner, **receipt})
    if len(inputs) > 64:
        raise ValueError('delegation authority inputs exceed bounds')
    return inputs
