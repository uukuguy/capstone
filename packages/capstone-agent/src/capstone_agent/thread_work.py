"""Work admission at the application boundary, using the Thread ledger."""
from copy import deepcopy
from dataclasses import replace
import json
import secrets

from .enterprise_context import TaskContext, WorkBinding
from .thread_protocol import ThreadProtocolError, ThreadSnapshot
from .session_title import SessionTitle


WORK_STATUSES = {'ready', 'queued', 'running', 'completed', 'failed', 'cancelled', 'interrupted', 'blocked'}


def execution_model(snapshot):
    """Preview the same pending resource choice that legacy message admission activates."""
    return snapshot.pending_model_switch or snapshot.active_model_context


def start_unavailable_reason(snapshot):
    if snapshot.run.state != 'open':
        return 'run_not_open'
    if snapshot.current_attempt is not None:
        return 'attempt_in_progress'
    model = execution_model(snapshot)
    if model is None and snapshot.native_execution is not None:
        return None
    if snapshot.runtime_mode != 'capstone' or model is None:
        return 'execution_unavailable'
    profiles = (model.enabled_profiles if snapshot.pending_model_switch is not None or snapshot.pending_selection is None
                else snapshot.pending_selection.enabled_profiles)
    if not profiles:
        return 'capability_required'
    from .thread_service import _application_case_active, _application_context_lock
    return _application_context_lock(snapshot) or ('case_execution_active' if _application_case_active(snapshot) else None)


def project_work(snapshot, work):
    reason = start_unavailable_reason(snapshot)
    from .request_intent import MAX_TEXT
    if reason is None and len(work_instruction(work)) > MAX_TEXT:
        reason = 'work_input_too_large'
    if work['status'] in {'queued', 'running'}:
        reason = 'attempt_in_progress'
    return {**deepcopy(work), 'latest_attempt_id': work.get('latest_attempt_id'),
            'consumed_message_count': work.get('consumed_message_count', 0),
            'cancel_requested': work.get('cancel_requested', False),
            'start_available': reason is None, 'start_unavailable_reason': reason}


def transition_work(snapshot, task_context, attempt_id, status):
    """Apply an Attempt boundary only to its exact, host-frozen Work."""
    if task_context is None:
        return snapshot, None
    works = deepcopy(list(snapshot.works))
    work = next((item for item in works if item['work_id'] == task_context.binding.work_id), None)
    if (work is None or work['task_context'] != task_context.to_document()
            or (work.get('latest_attempt_id') is not None and work['latest_attempt_id'] != attempt_id)):
        raise ThreadProtocolError('attempt Work snapshot is inconsistent')
    work['revision'] += 1
    work['status'] = status
    work['blocked_reason'] = None
    work['latest_attempt_id'] = attempt_id
    if status == 'completed':
        if work.get('conversation_mode'):
            # Full transcript is in the same event/Attempt ledger. Keep only
            # unconsumed input here so a normal conversation has no turn cap.
            work['messages'] = []
            work['consumed_message_count'] = 0
        else:
            work['consumed_message_count'] = len(work['messages'])
    if status in {'completed', 'failed', 'cancelled', 'interrupted'}:
        work['cancel_requested'] = False
    return replace(snapshot, works=tuple(works)), work


def work_event_payload(snapshot, task_context, attempt_id, status):
    updated, work = transition_work(snapshot, task_context, attempt_id, status)
    return updated, ({} if work is None else {'work_id': work['work_id'], 'work': project_work(updated, work)})


def create_attempt(snapshot, work, *, turn_id=None):
    """Adapt one explicit Work start to the existing accepted Attempt contract."""
    from .thread_protocol import AttemptSnapshot
    token = secrets.token_hex(8)
    model = snapshot.active_model_context
    context = replace(TaskContext.from_document(work['task_context']),
                      model_contexts=() if model is None else (model,))
    work['task_context'] = context.to_document()
    attempt = AttemptSnapshot(turn_id or 'turn_' + token, 'attempt_' + token, 'accepted',
                              None if model is None else model.id, snapshot.runtime_mode)
    instruction = work_instruction(work)
    work['latest_attempt_id'] = attempt.attempt_id
    return replace(snapshot, current_attempt=attempt), attempt, context, instruction


def work_instruction(work):
    """Keep every unconsumed supplement; completed rounds use bounded history."""
    pending = work['messages'][work.get('consumed_message_count', 0):]
    if work.get('conversation_mode'):
        return '\n\n'.join(pending)
    if pending and pending[0] == work['goal']:
        pending = pending[1:]
    return work['goal'] if not pending else work['goal'] + '\n\nAdditional messages:\n' + json.dumps(pending, ensure_ascii=False)


def parse_command(command):
    fields = {'schema', 'command_id', 'idempotency_key', 'thread_id', 'run_id', 'kind', 'payload', 'target'}
    if set(command) - fields or not fields - {'run_id'} <= set(command):
        raise ThreadProtocolError('invalid Work command fields')
    from .thread_service import _identifier, _canonical, _MAX_COMMAND_BYTES, _validate_json
    for key in ('command_id', 'idempotency_key', 'thread_id'):
        _identifier(command[key], name=key)
    if command.get('run_id') is not None:
        _identifier(command['run_id'], name='run_id')
    target = command['target']
    if (not isinstance(target, dict) or set(target) != {'kind', 'id', 'expected_revision'}
            or target['kind'] != ('session_title' if command['kind'] == 'rename_session' else 'work') or type(target['expected_revision']) is not int
            or target['expected_revision'] < 0):
        raise ThreadProtocolError('invalid Work target')
    _identifier(target['id'], name='target.id')
    if not isinstance(command['kind'], str) or not isinstance(command['payload'], dict):
        raise ThreadProtocolError('invalid Work command')
    if command['kind'] == 'send_message' and (set(command['payload']) - {
            'text', 'input', 'context_selection', 'resource_profile', 'enabled_profiles', 'source_attempt_id'}):
        raise ThreadProtocolError('invalid message input fields')
    _validate_json(command['payload'], name='command.payload')
    if len(_canonical(command).encode()) > _MAX_COMMAND_BYTES:
        raise ThreadProtocolError('command is too large')
    return {**deepcopy(command), 'run_id': command.get('run_id')}


def apply_work(snapshot, command, *, archived=False):
    """Return a new snapshot and rejection; never queue an unsupported executor."""
    if archived:
        return snapshot, 'thread_archived', None
    if snapshot.run.state != 'open':
        return snapshot, 'run_not_open', None
    if command['run_id'] is not None and command['run_id'] != snapshot.run.run_id:
        return snapshot, 'run_mismatch', None
    if snapshot.current_attempt is not None and command['kind'] != 'cancel_work':
        return snapshot, 'attempt_in_progress', None
    from .thread_service import _application_case_active, _application_context_lock
    if (context_lock := _application_context_lock(snapshot)) is not None:
        return snapshot, context_lock, None
    if _application_case_active(snapshot):
        return snapshot, 'case_execution_active', None
    if command['kind'] == 'send_message':
        if command['target']['id'] == 'new' and any(work.get('conversation_mode') for work in snapshot.works):
            return snapshot, 'conversation_work_exists', None
        saved, rejection, work = apply_work(snapshot, {**command, 'kind': 'work_message',
            'payload': {'text': command['payload'].get('text')}}, archived=archived)
        if rejection is not None:
            return snapshot, rejection, None
        assert work is not None
        work['conversation_mode'] = True
        reason = start_unavailable_reason(saved)
        if reason is not None:
            return snapshot, reason, None
        from .request_intent import MAX_TEXT
        if len(work_instruction(work)) > MAX_TEXT:
            return snapshot, 'work_input_too_large', None
        work['status'], work['blocked_reason'] = 'queued', None
        work['cancel_requested'] = False
        work['task_context'] = replace(TaskContext.from_document(work['task_context']),
            snapshot_id='task_' + secrets.token_hex(10)).to_document()
        return saved, None, work
    if command['kind'] not in {'work_message', 'revise_goal', 'start_work', 'cancel_work'}:
        return snapshot, 'execution_unavailable', None
    payload = command['payload']
    if command['kind'] in {'start_work', 'cancel_work'}:
        if payload:
            raise ThreadProtocolError('Work control payload must be empty')
    elif set(payload) != {'text'} or not isinstance(payload['text'], str) or not payload['text'].strip():
        raise ThreadProtocolError('Work text is required')
    target = command['target']
    works = deepcopy(list(snapshot.works))
    work = next((item for item in works if item['work_id'] == target['id']), None)
    if target['id'] == 'new':
        if len(works) >= 64:
            return snapshot, 'work_limit_reached', None
        if command['kind'] != 'work_message' or target['expected_revision'] != 0:
            return snapshot, 'revision_conflict', None
        work_id = 'work_' + secrets.token_hex(10)
        context = TaskContext(WorkBinding(snapshot.thread_id, work_id, 'research-' + secrets.token_hex(10)),
                              1, 'task_' + secrets.token_hex(10),
                              () if snapshot.active_model_context is None else (snapshot.active_model_context,))
        reason = start_unavailable_reason(snapshot)
        work = {'work_id': work_id, 'goal': payload['text'], 'goal_revision': 1, 'revision': 1,
                'status': 'ready' if reason is None else 'blocked', 'blocked_reason': reason,
                'latest_attempt_id': None,
                'consumed_message_count': 0,
                'cancel_requested': False,
                'task_context': context.to_document(), 'messages': [payload['text']]}
        works.append(work)
    else:
        if work is None:
            return snapshot, 'work_not_found', None
        if work['revision'] != target['expected_revision']:
            return snapshot, 'revision_conflict', None
        if command['kind'] == 'cancel_work':
            current = snapshot.current_attempt
            if current is None or work.get('latest_attempt_id') != current.attempt_id:
                return snapshot, 'attempt_target_mismatch', None
            if work.get('cancel_requested', False):
                return snapshot, 'cancel_already_requested', None
            work['revision'] += 1
            work['cancel_requested'] = True
            return replace(snapshot, works=tuple(works)), None, work
        if command['kind'] == 'start_work':
            reason = start_unavailable_reason(snapshot)
            if reason is not None:
                return snapshot, reason, None
            from .request_intent import MAX_TEXT
            if len(work_instruction(work)) > MAX_TEXT:
                return snapshot, 'work_input_too_large', None
            previous = TaskContext.from_document(work['task_context'])
            context = TaskContext(previous.binding, work['goal_revision'], 'task_' + secrets.token_hex(10),
                                  () if snapshot.active_model_context is None else (snapshot.active_model_context,), previous.resource_refs)
            work['task_context'] = context.to_document()
            work['revision'] += 1
            work['status'] = 'queued'
            work['blocked_reason'] = None
            work['latest_attempt_id'] = None
            work['cancel_requested'] = False
            return replace(snapshot, works=tuple(works)), None, work
        if len(work['messages']) >= 128:
            return snapshot, 'work_limit_reached', None
        work['revision'] += 1
        work['messages'].append(payload['text'])
        reason = start_unavailable_reason(snapshot)
        work['status'] = 'ready' if reason is None else 'blocked'
        work['blocked_reason'] = reason
        if command['kind'] == 'revise_goal' and work['goal'] != payload['text']:
            work['goal'] = payload['text']
            work['goal_revision'] += 1
            context = TaskContext.from_document(work['task_context'])
            work['task_context'] = replace(context, goal_revision=work['goal_revision'],
                                           snapshot_id='task_' + secrets.token_hex(10)).to_document()
    if len(json.dumps(works, ensure_ascii=False).encode()) > 256 * 1024:
        return snapshot, 'work_limit_reached', None
    return replace(snapshot, minimum_protocol_version=2, works=tuple(works)), None, work


def snapshot_document(snapshot, document):
    current = document['current_attempt']
    if current is not None:
        current = {**current, 'work_id': next((work['work_id'] for work in snapshot.works
            if work.get('latest_attempt_id') == current['attempt_id']), None)}
    return {**document, 'current_attempt': current, 'schema': 'capstone-thread-snapshot/2', 'minimum_protocol_version': 2,
            'selected_model_context_id': None if snapshot.active_model_context is None else snapshot.active_model_context.id,
            'task_context': None if not snapshot.works else deepcopy(snapshot.works[-1]['task_context']),
            'works': [project_work(snapshot, work) for work in snapshot.works]}


def parse_snapshot(document):
    extra = {'minimum_protocol_version', 'selected_model_context_id', 'task_context', 'works'}
    base = {key: value for key, value in document.items() if key not in extra}
    context = base.get('active_model_context')
    current = base.get('current_attempt')
    if isinstance(current, dict):
        base['current_attempt'] = {key: value for key, value in current.items() if key != 'work_id'}
    if (not extra <= set(document) or document.get('minimum_protocol_version') != 2
            or not isinstance(document.get('works'), list) or len(document['works']) > 64):
        raise ThreadProtocolError('invalid Work snapshot')
    # Validate all common fields with the existing strict parser. No substitute
    # model is created for the model-free representation.
    if context is None:
        from .thread_protocol import RunSnapshot, _identifier, _sequence
        allowed = {'schema', 'runtime_mode', 'thread_id', 'run', 'active_model_context', 'active_grid_page_id',
                   'current_attempt', 'last_event_seq', 'base_event_seq', 'application_state', 'session_title'}
        required = allowed - {'runtime_mode', 'application_state', 'session_title'}
        if (set(base) - allowed or not required <= set(base)
                or base.get('active_grid_page_id') is not None):
            raise ThreadProtocolError('invalid model-free snapshot')
        from .thread_protocol import AttemptSnapshot
        snapshot = ThreadSnapshot(_identifier(base['thread_id'], name='thread_id'), RunSnapshot.from_document(base['run']),
                                  None, None, None if current is None else AttemptSnapshot.from_document(base['current_attempt']), _sequence(base['last_event_seq'], name='last_event_seq'),
                                  _sequence(base['base_event_seq'], name='base_event_seq'),
                                  application_state=base.get('application_state'), runtime_mode=base.get('runtime_mode', 'capstone'),
                                  minimum_protocol_version=2,
                                  session_title=None if base.get('session_title') is None else SessionTitle.from_document(base['session_title']))
    else:
        base['schema'] = 'capstone-thread-snapshot/1'
        snapshot = ThreadSnapshot.from_document(base)
    identities = set()
    for work in document['works']:
        fields = {'work_id', 'goal', 'goal_revision', 'revision', 'status', 'blocked_reason', 'task_context', 'messages'}
        optional = {'latest_attempt_id', 'start_available', 'start_unavailable_reason', 'consumed_message_count', 'cancel_requested', 'conversation_mode'}
        if (not isinstance(work, dict) or set(work) - fields - optional or not fields <= set(work) or not isinstance(work['goal'], str)
                or not work['goal'].strip() or type(work['revision']) is not int or work['revision'] < 1
                or type(work['goal_revision']) is not int or not 1 <= work['goal_revision'] <= work['revision']
                or work['status'] not in WORK_STATUSES
                or work['blocked_reason'] not in {None, 'execution_unavailable', 'capability_required', 'run_not_open'}
                or not isinstance(work['messages'], list) or not (0 if work.get('conversation_mode') else 1) <= len(work['messages']) <= 128
                or any(not isinstance(message, str) or not message.strip() for message in work['messages'])):
            raise ThreadProtocolError('invalid Work state')
        count = work.get('consumed_message_count', 0)
        if type(count) is not int or not 0 <= count <= len(work['messages']):
            raise ThreadProtocolError('invalid Work message cursor')
        if type(work.get('cancel_requested', False)) is not bool:
            raise ThreadProtocolError('invalid Work cancellation state')
        try:
            context = TaskContext.from_document(work['task_context'])
        except (ValueError, TypeError) as error:
            raise ThreadProtocolError('invalid Work task context') from error
        if (context.binding.thread_id != snapshot.thread_id or context.binding.work_id != work['work_id']
                or context.goal_revision != work['goal_revision'] or work['work_id'] in identities):
            raise ThreadProtocolError('invalid Work context identity')
        identities.add(work['work_id'])
    if (document['selected_model_context_id'] != (None if snapshot.active_model_context is None else snapshot.active_model_context.id)
            or document['task_context'] != (None if not document['works'] else document['works'][-1]['task_context'])
            or snapshot.base_event_seq > snapshot.last_event_seq
            or len(json.dumps(document['works'], ensure_ascii=False).encode()) > 256 * 1024):
        raise ThreadProtocolError('invalid Work snapshot identity or bounds')
    stored = tuple({key: deepcopy(value) for key, value in work.items()
                    if key not in {'start_available', 'start_unavailable_reason'}} for work in document['works'])
    return replace(snapshot, minimum_protocol_version=2, works=stored)
