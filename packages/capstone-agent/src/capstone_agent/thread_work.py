"""Work admission at the application boundary, using the Thread ledger."""
from copy import deepcopy
from dataclasses import replace
import json
import secrets

from .enterprise_context import TaskContext, WorkBinding
from .thread_protocol import ThreadProtocolError, ThreadSnapshot


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
            or target['kind'] != 'work' or type(target['expected_revision']) is not int
            or target['expected_revision'] < 0):
        raise ThreadProtocolError('invalid Work target')
    _identifier(target['id'], name='target.id')
    if not isinstance(command['kind'], str) or not isinstance(command['payload'], dict):
        raise ThreadProtocolError('invalid Work command')
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
    if snapshot.current_attempt is not None:
        return snapshot, 'attempt_in_progress', None
    from .thread_service import _application_case_active, _application_context_lock
    if (context_lock := _application_context_lock(snapshot)) is not None:
        return snapshot, context_lock, None
    if _application_case_active(snapshot):
        return snapshot, 'case_execution_active', None
    if command['kind'] not in {'work_message', 'revise_goal'}:
        return snapshot, 'execution_unavailable', None
    payload = command['payload']
    if set(payload) != {'text'} or not isinstance(payload['text'], str) or not payload['text'].strip():
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
        work = {'work_id': work_id, 'goal': payload['text'], 'goal_revision': 1, 'revision': 1,
                'status': 'blocked', 'blocked_reason': 'execution_unavailable',
                'task_context': context.to_document(), 'messages': [payload['text']]}
        works.append(work)
    else:
        if work is None:
            return snapshot, 'work_not_found', None
        if work['revision'] != target['expected_revision']:
            return snapshot, 'revision_conflict', None
        if len(work['messages']) >= 128:
            return snapshot, 'work_limit_reached', None
        work['revision'] += 1
        work['messages'].append(payload['text'])
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
    return {**document, 'schema': 'capstone-thread-snapshot/2', 'minimum_protocol_version': 2,
            'selected_model_context_id': None if snapshot.active_model_context is None else snapshot.active_model_context.id,
            'task_context': None if not snapshot.works else deepcopy(snapshot.works[-1]['task_context']),
            'works': deepcopy(list(snapshot.works))}


def parse_snapshot(document):
    extra = {'minimum_protocol_version', 'selected_model_context_id', 'task_context', 'works'}
    base = {key: value for key, value in document.items() if key not in extra}
    context = base.get('active_model_context')
    if (not extra <= set(document) or document.get('minimum_protocol_version') != 2
            or not isinstance(document.get('works'), list) or len(document['works']) > 64):
        raise ThreadProtocolError('invalid Work snapshot')
    # Validate all common fields with the existing strict parser. No substitute
    # model is created for the model-free representation.
    if context is None:
        from .thread_protocol import RunSnapshot, _identifier, _sequence
        allowed = {'schema', 'runtime_mode', 'thread_id', 'run', 'active_model_context', 'active_grid_page_id',
                   'current_attempt', 'last_event_seq', 'base_event_seq', 'application_state'}
        required = allowed - {'runtime_mode', 'application_state'}
        if (set(base) - allowed or not required <= set(base)
                or base.get('active_grid_page_id') is not None or base.get('current_attempt') is not None):
            raise ThreadProtocolError('invalid model-free snapshot')
        snapshot = ThreadSnapshot(_identifier(base['thread_id'], name='thread_id'), RunSnapshot.from_document(base['run']),
                                  None, None, None, _sequence(base['last_event_seq'], name='last_event_seq'),
                                  _sequence(base['base_event_seq'], name='base_event_seq'),
                                  application_state=base.get('application_state'), runtime_mode=base.get('runtime_mode', 'capstone'),
                                  minimum_protocol_version=2)
    else:
        base['schema'] = 'capstone-thread-snapshot/1'
        snapshot = ThreadSnapshot.from_document(base)
    identities = set()
    for work in document['works']:
        fields = {'work_id', 'goal', 'goal_revision', 'revision', 'status', 'blocked_reason', 'task_context', 'messages'}
        if (not isinstance(work, dict) or set(work) != fields or not isinstance(work['goal'], str)
                or not work['goal'].strip() or type(work['revision']) is not int or work['revision'] < 1
                or type(work['goal_revision']) is not int or not 1 <= work['goal_revision'] <= work['revision']
                or work['status'] != 'blocked' or work['blocked_reason'] != 'execution_unavailable'
                or not isinstance(work['messages'], list) or not 1 <= len(work['messages']) <= 128
                or any(not isinstance(message, str) or not message.strip() for message in work['messages'])):
            raise ThreadProtocolError('invalid Work state')
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
    return replace(snapshot, minimum_protocol_version=2, works=tuple(deepcopy(document['works'])))
