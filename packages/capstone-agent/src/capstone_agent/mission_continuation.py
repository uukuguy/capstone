"""Admit finite Control review intents through the existing native Attempt ledger."""
from copy import deepcopy
from hashlib import sha256
import json
import logging

from psycopg.types.json import Jsonb
from psycopg import Error as DatabaseError

from .application_capacity import limits
from .thread_protocol import ThreadProtocolError, _identifier

SCHEMA = 'capstone-mission-review-intent/1'
TERMINAL = {'completed', 'failed', 'cancelled', 'interrupted'}


class MissionReviewBlocked(ThreadProtocolError):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def review_cancel_requested(service, claim):
    review = (claim.submission or {}).get('_mission_review')
    if not review:
        return False
    host = getattr(service, 'control_host', None)
    if host is None:
        return True
    try:
        mission = host.service.read_mission(claim.workspace_name, review['mission_id'])
    except KeyError:
        return True
    return mission['state'] in {'paused', 'pausing', 'cancelled', 'cancelling', 'accepted'}


def _identity(intent):
    if (not isinstance(intent, dict) or intent.get('schema') != SCHEMA
            or not {'workspace', 'mission_id', 'review_id', 'origin', 'boundary'} <= intent.keys()):
        raise ThreadProtocolError('invalid Mission review source')
    for key in ('mission_id', 'review_id'):
        _identifier(intent[key], name='mission_review.' + key)
    from .mission_origin import checked_origin
    checked_origin(intent['origin'])
    token = sha256(json.dumps([intent['workspace'], intent['mission_id'], intent['review_id']],
        separators=(',', ':')).encode()).hexdigest()[:32]
    return 'attempt_mission_' + token, 'turn_mission_' + token


def review_instruction(intent):
    source = {'schema': SCHEMA, 'mission_id': intent['mission_id'], 'review_id': intent['review_id'],
              'boundary_digest': intent['boundary']['digest'], 'plan_revision': intent['boundary']['plan_revision']}
    return ('Review the admitted Mission boundary with the registered Mission tools. '
            'Update the plan, wait for required input, or conclude the plan based on its actual state. '
            'This is an application continuation, not a new user message.\n' +
            json.dumps(source, ensure_ascii=False, sort_keys=True))


def _check_source(service, snapshot, intent):
    from .mission_origin import _require_association
    from .thread_service import _validate_bounded_json
    _validate_bounded_json(intent, name='mission_review.intent', maximum=limits.control_document_bytes)
    host = getattr(service, 'control_host', None)
    if host is None:
        raise ThreadProtocolError('Mission Control is unavailable')
    saved = host.service.read_mission_review(intent['workspace'], intent['mission_id'], intent['review_id'])
    if saved != intent:
        raise ThreadProtocolError('Mission review source does not match its reserved intent')
    _require_association(snapshot, intent['mission_id'], intent['origin'])


def _select_work(snapshot, intent):
    origin = intent['origin']
    candidates = [work for work in snapshot.works if work.get('conversation_mode')
                  and ('work_id' not in origin or work['work_id'] == origin['work_id'])]
    if len(candidates) != 1:
        raise MissionReviewBlocked('organizer_work_unavailable' if not candidates else 'organizer_work_ambiguous')
    return candidates[0]


def _submission(service, prior, intent, grants):
    from .mission_equipment import origin_binding, registry_revision
    source = deepcopy(prior or {})
    mission = source.get('_mission')
    if (not isinstance(mission, dict) or mission.get('mission_id') != intent['mission_id']
            or mission.get('origin') != intent['origin'] or not source.get('_native_execution')):
        raise ThreadProtocolError('Mission review needs an admitted origin conversation grant')
    current, _ = origin_binding(service, intent['workspace'], intent['origin'])
    accepted = source['_native_execution']
    if registry_revision(current) != registry_revision(accepted):
        raise ThreadProtocolError('Mission review source or registered grants changed; a new user instruction is required')
    previous_review = source.get('_mission_review', {})
    removed = {grant['resource']['resource_id'] for grant in source.get('_delegation_resources', [])
               if grant['delegation_id'] == previous_review.get('review_id')}
    inherited = [grant for grant in source.get('_delegation_resources', [])
                 if grant['resource']['resource_id'] not in removed]
    manifests = [manifest for manifest in source.get('_resource_manifests', [])
                 if manifest['resource_id'] not in removed]
    if inherited or grants:
        source['_delegation_resources'] = inherited + deepcopy(grants)
    else:
        source.pop('_delegation_resources', None)
    if manifests or grants:
        source['_resource_manifests'] = manifests + [deepcopy(grant['resource']) for grant in grants]
    else:
        source.pop('_resource_manifests', None)
    source['_mission_review'] = deepcopy(intent)
    source['input'] = {'kind': 'text', 'text': review_instruction(intent)}
    # Selected methods remain registered grants; a prior skill invocation is
    # not a mandatory first action for a new application continuation.
    return source


def _binding(intent, work_id, attempt_id):
    return {'thread_id': intent['origin']['thread_id'], 'work_id': work_id, 'attempt_id': attempt_id}


def _payload(intent, work, previous_id, snapshot):
    from .thread_work import project_work
    return {'command_id': 'cmd_' + intent['review_id'], 'mission_id': intent['mission_id'],
            'review_id': intent['review_id'], 'work_id': work['work_id'],
            'boundary': deepcopy(intent['boundary']), 'source_origin': deepcopy(intent['origin']),
            'source_attempt_id': previous_id, 'work': project_work(snapshot, work)}


def find_review(service, intent):
    attempt_id, _ = _identity(intent)
    thread_id = intent['origin']['thread_id']
    service.require_workspace(thread_id, intent['workspace'])
    if hasattr(service, '_lock'):
        with service._lock:
            record = service._attempts.get(attempt_id)
            if record is None:
                return None
            source = (record.get('submission') or {}).get('_mission_review')
            if source != intent:
                raise ThreadProtocolError('Mission review identity was reused with different source')
            return _binding(intent, record['task_context'].binding.work_id, attempt_id), record['attempt'].phase
    with service._connect() as connection:
        record = connection.execute("""SELECT phase,submission_snapshot,task_context_snapshot
            FROM capstone_thread_attempts WHERE thread_id=%s AND attempt_id=%s""",
            (thread_id, attempt_id)).fetchone()
        if record is None:
            return None
        if (record['submission_snapshot'] or {}).get('_mission_review') != intent:
            raise ThreadProtocolError('Mission review identity was reused with different source')
        return _binding(intent, record['task_context_snapshot']['binding']['work_id'], attempt_id), record['phase']


def _origin_ready(service, intent):
    service.require_workspace(intent['origin']['thread_id'], intent['workspace'])
    snapshot = service.snapshot(intent['origin']['thread_id'])
    if snapshot.current_attempt is not None:
        return False
    work = _select_work(snapshot, intent)
    return (snapshot.run.state == 'open' and snapshot.active_model_context is None
            and work['status'] == 'completed' and not work.get('cancel_requested')
            and snapshot.pending_model_switch is None and snapshot.pending_selection is None)


def release_unadmitted_review(service, intent):
    """Refund only after serialized proof that no exact Attempt was admitted."""
    host = getattr(service, 'control_host', None)
    if host is None or not hasattr(host.service, 'release_mission_review'):
        return False
    attempt_id, _ = _identity(intent)
    thread_id, workspace = intent['origin']['thread_id'], intent['workspace']
    def release():
        mission = host.service.read_mission(workspace, intent['mission_id'])
        if mission['state'] not in {'paused', 'pausing', 'cancelled', 'cancelling'}:
            return False
        host.service.release_mission_review(workspace, intent['mission_id'], intent['review_id'],
                                           'origin_paused_before_admission')
        return True
    if hasattr(service, '_lock'):
        with service._lock:
            service.require_workspace(thread_id, workspace)
            if attempt_id in service._attempts:
                return False
            return release()
    with service._connect() as connection:
        row = connection.execute('SELECT thread_id FROM capstone_threads WHERE thread_id=%s AND workspace_name=%s FOR UPDATE',
            (thread_id, workspace)).fetchone()
        if row is None:
            return False
        existing = connection.execute('SELECT 1 FROM capstone_thread_attempts WHERE thread_id=%s AND attempt_id=%s',
            (thread_id, attempt_id)).fetchone()
        if existing is not None:
            return False
        return release()


def admit_review(service, intent):
    from .thread_service import _conversation_from_events, _conversation_from_postgres
    from .thread_work import prepare_mission_review
    attempt_id, turn_id = _identity(intent)
    existing = find_review(service, intent)
    if existing is not None:
        return existing[0]
    thread_id, workspace = intent['origin']['thread_id'], intent['workspace']
    # Cross-Thread resource validation runs outside the origin transaction.
    # Admission below rechecks the same immutable reserved intent before use.
    snapshot = service.snapshot(thread_id)
    service.require_workspace(thread_id, workspace)
    _check_source(service, snapshot, intent)
    selected = _select_work(snapshot, intent)
    if snapshot.current_attempt is not None:
        existing = find_review(service, intent)
        return None if existing is None else existing[0]
    if selected is None or selected.get('status') != 'completed' or selected.get('cancel_requested'):
        return None
    products = [deepcopy(product) for task in intent['boundary']['tasks']
                if task.get('state') in {'delivered', 'verified'}
                for product in (task.get('delivery') or {}).get('products', [])]
    products = list({(product['thread_id'], product['attempt_id'], product['artifact_id'], product['sha256']):
                     product for product in products}.values())
    grants = []
    if products:
        from .delegation_resources import grant_resources
        grants = grant_resources(service, workspace, thread_id, selected['work_id'],
            intent['review_id'], products, mission_review=True)
    if hasattr(service, '_lock'):
        with service._lock:
            service.require_workspace(thread_id, workspace)
            existing = find_review(service, intent)
            if existing is not None:
                return existing[0]
            snapshot = service._snapshot
            _check_source(service, snapshot, intent)
            work = _select_work(snapshot, intent)
            if service._archived or snapshot.run.state != 'open' or work is None:
                return None
            prepared = prepare_mission_review(snapshot, work['work_id'], attempt_id=attempt_id, turn_id=turn_id)
            if prepared is None:
                return None
            previous_id = work.get('latest_attempt_id')
            prior = service._attempts.get(previous_id, {})
            submission = _submission(service, prior.get('submission'), intent, grants)
            updated, saved, attempt, context = prepared
            relevant = {identity: record for identity, record in service._attempts.items()
                if record.get('task_context') is not None
                and record['task_context'].binding.work_id == work['work_id']}
            conversation = _conversation_from_events(service._events, relevant, thread_id, snapshot.last_event_seq)
            service._attempts[attempt_id] = {'attempt': attempt, 'kind': 'send_auto',
                'instruction': review_instruction(intent), 'lease_token': None, 'lease_deadline': None,
                'model_context': None, 'command_id': 'cmd_' + intent['review_id'], 'conversation_context': conversation,
                'submission': submission, 'source_attempt_id': previous_id, 'task_context': context}
            service._snapshot = updated
            event = service._append_event(event_type='mission_review_requested', attempt=attempt,
                                          payload=_payload(intent, saved, previous_id, updated))
            from dataclasses import replace
            service._snapshot = replace(updated, last_event_seq=event.event_seq)
            return _binding(intent, work['work_id'], attempt_id)
    with service._connect() as connection:
        row = connection.execute('SELECT * FROM capstone_threads WHERE thread_id=%s AND workspace_name=%s FOR UPDATE',
            (thread_id, workspace)).fetchone()
        if row is None:
            raise ThreadProtocolError('Mission review origin Thread is unavailable')
        # A concurrent drain may have committed while this drain waited.
        existing = connection.execute('SELECT submission_snapshot,task_context_snapshot FROM capstone_thread_attempts WHERE thread_id=%s AND attempt_id=%s',
            (thread_id, attempt_id)).fetchone()
        if existing is not None:
            if existing['submission_snapshot'].get('_mission_review') != intent:
                raise ThreadProtocolError('Mission review source conflicts')
            return _binding(intent, existing['task_context_snapshot']['binding']['work_id'], attempt_id)
        snapshot = service._snapshot_from_row(row)
        _check_source(service, snapshot, intent)
        work = _select_work(snapshot, intent)
        if row['archived'] or snapshot.run.state != 'open' or work is None:
            return None
        prepared = prepare_mission_review(snapshot, work['work_id'], attempt_id=attempt_id, turn_id=turn_id)
        if prepared is None:
            return None
        previous_id = work.get('latest_attempt_id')
        prior = connection.execute('SELECT submission_snapshot FROM capstone_thread_attempts WHERE thread_id=%s AND attempt_id=%s',
            (thread_id, previous_id)).fetchone()
        submission = _submission(service, None if prior is None else prior['submission_snapshot'], intent, grants)
        updated, saved, attempt, context = prepared
        conversation = _conversation_from_postgres(connection, thread_id, snapshot.last_event_seq, work_id=work['work_id'])
        connection.execute("""INSERT INTO capstone_thread_attempts
            (attempt_id,thread_id,run_id,turn_id,command_id,kind,instruction,model_context_id,
             selection_revision,model_context_snapshot,conversation_context_snapshot,task_context_snapshot,
             runtime_mode,submission_snapshot,phase)
            VALUES (%s,%s,%s,%s,%s,'send_auto',%s,NULL,NULL,NULL,%s,%s,%s,%s,'accepted')""",
            (attempt_id, thread_id, snapshot.run.run_id, turn_id, 'cmd_' + intent['review_id'],
             review_instruction(intent), Jsonb(conversation.to_document()), Jsonb(context.to_document()),
             snapshot.runtime_mode, Jsonb(submission)))
        event = service._make_attempt_event(row, attempt, event_seq=row['last_event_seq'] + 1,
            event_type='mission_review_requested', payload=_payload(intent, saved, previous_id, updated), context=None)
        service._insert_event(connection, event)
        connection.execute('UPDATE capstone_threads SET current_attempt=%s,works=%s,last_event_seq=%s WHERE thread_id=%s',
            (Jsonb(attempt.to_document()), Jsonb(list(updated.works)), event.event_seq, thread_id))
        return _binding(intent, work['work_id'], attempt_id)


def drain_mission_reviews(service, limit=32, *, workspace=None):
    host = getattr(service, 'control_host', None)
    if host is None or not hasattr(host.service, 'pending_mission_reviews'):
        return 0
    admitted = 0
    for pending in host.service.pending_mission_reviews(workspace, limit=limit):
        workspace, mission_id, review_id = pending['workspace'], pending['mission_id'], pending['review_id']
        try:
            # Reconcile an admitted Attempt first, including an ambiguous ack.
            intent, existing = pending, find_review(service, pending)
            if existing is None:
                if release_unadmitted_review(service, pending):
                    continue
                if not _origin_ready(service, pending):
                    continue
                intent = host.service.reserve_mission_review(workspace, mission_id, review_id)
                if intent is None:
                    continue
                existing = find_review(service, intent)
            if existing is None:
                binding = service.submit_mission_review(intent)
                if binding is None:
                    continue
                admitted += 1
                existing = (binding, 'accepted')
            binding, phase = existing
            host.service.acknowledge_mission_review(workspace, mission_id, review_id, binding)
            if phase in TERMINAL:
                host.service.finish_mission_review(workspace, mission_id, review_id,
                    attempt_id=binding['attempt_id'], phase=phase)
        except MissionReviewBlocked as error:
            host.service.block_mission_review(workspace, mission_id, review_id, error.reason)
        except ThreadProtocolError:
            if (not release_unadmitted_review(service, pending)
                    and hasattr(host.service, 'block_mission_review')):
                host.service.block_mission_review(workspace, mission_id, review_id, 'origin_source_or_grants_unavailable')
        except (ValueError, KeyError, OSError, DatabaseError):
            release_unadmitted_review(service, pending)
            # Retain the exact reserved intent. No new model calls or retries
            # are created from a failed admission or ambiguous acknowledgement.
            logging.getLogger(__name__).warning('Mission review admission is incomplete; durable source retained')
    return admitted
