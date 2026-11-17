"""Public Agent delegation service. Control never writes execution ledger rows."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import json
import re

from .thread_protocol import ThreadSnapshot, RunSnapshot
from .thread_service import ThreadNotFound
from .workspace_scope import workspace_name as normalize_workspace_name

REGISTERED_AGENTS = frozenset({'capstone'})


class DelegationConflict(ValueError):
    pass


class DelegationRevoked(ValueError):
    pass


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _request(value):
    fields = {'schema', 'delegation_id', 'operation_id', 'goal_id', 'goal_revision',
              'task_id', 'task_revision', 'generation', 'agent_id', 'binding', 'requested_control',
              'objective', 'delivery_requirements', 'mode', 'max_attempts', 'deadline_at', 'context_products'}
    v2 = isinstance(value, dict) and value.get('schema') == 'capstone-agent-delegation/2'
    if v2:
        fields |= {'equipment', 'restrictions', 'mission_origin'}
    if (not isinstance(value, dict) or not fields <= set(value)
            or set(value) - fields - {'control_revision', 'required_products'}
            or value['schema'] not in {'capstone-agent-delegation/1', 'capstone-agent-delegation/2'}):
        raise ValueError('invalid Agent delegation contract')
    if v2:
        from capstone_control.mission import references
        from .mission_origin import checked_origin
        references(value['equipment'])
        references(value['restrictions'])
        checked_origin(value['mission_origin'])
    for key in ['delegation_id', 'operation_id', 'goal_id', 'task_id', 'agent_id']:
        if not isinstance(value[key], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}', value[key]):
            raise ValueError('invalid delegation identity')
    for key in ['goal_revision', 'task_revision', 'generation', 'max_attempts']:
        if type(value[key]) is not int or value[key] < 1:
            raise ValueError('invalid delegation version or budget')
    if (value['agent_id'] not in REGISTERED_AGENTS or not isinstance(value['mode'], str) or value['mode'] not in {'single', 'goal'}
            or value['mode'] == 'single' and value['max_attempts'] != 1):
        raise ValueError('unregistered Agent or execution mode')
    if not isinstance(value['objective'], str) or not value['objective'].strip() or len(value['objective']) > 16384:
        raise ValueError('invalid delegation objective')
    if (not isinstance(value['delivery_requirements'], list) or not value['delivery_requirements']
            or len(value['delivery_requirements']) > 64
            or any(not isinstance(item, str) or not item.strip() or len(item) > 16384 for item in value['delivery_requirements'])):
        raise ValueError('invalid delivery requirements')
    if not isinstance(value['deadline_at'], str):
        raise ValueError('explicit UTC deadline required')
    deadline = datetime.fromisoformat(value['deadline_at'])
    if deadline.utcoffset() != timedelta(0):
        raise ValueError('explicit UTC deadline required')
    if not isinstance(value['context_products'], list) or len(value['context_products']) > 64:
        raise ValueError('invalid delegation context')
    # Binding and control are server state, not part of the immutable request.
    return deepcopy({key: item for key, item in value.items() if key not in {'binding', 'requested_control', 'control_revision'}})


class AgentDelegations:
    def __init__(self, threads, registry, *, wake=None):
        self.threads, self.registry, self.wake = threads, registry, wake

    def _reserve(self, workspace, delegation):
        workspace = normalize_workspace_name(workspace)
        request = _request(delegation)
        digest = _digest(request)
        def reserve(current):
            if current is None:
                token = _digest([workspace, request['operation_id']])[:32]
                current = {'request': request, 'digest': digest, 'thread_id': 'thr_' + token,
                           'binding': None, 'control': None, 'control_receipts': {}}
            elif current['digest'] != digest:
                raise DelegationConflict('delegation operation content conflict')
            return current, current
        return self.registry.transact(workspace, request['operation_id'], reserve)

    def _command(self, thread, work, kind, name, payload=None):
        token = _digest([thread, name])[:32]
        command = {'schema': 'capstone-command/2', 'command_id': 'cmd_' + token,
            'idempotency_key': 'delegation_' + token, 'thread_id': thread, 'kind': kind,
            'target': {'kind': 'work', 'id': 'new' if work is None else work['work_id'],
                       'expected_revision': 0 if work is None else work['revision']},
            'payload': {} if payload is None else payload}
        submit = getattr(self.threads, 'submit_goal_continuation', self.threads.submit_command)
        receipt = submit(command)
        if receipt is None or receipt.status != 'accepted':
            raise DelegationConflict('Agent command admission unavailable')
        return receipt

    def delegate(self, workspace, delegation):
        workspace = normalize_workspace_name(workspace)
        self._reserve(workspace, delegation)
        def admit(current):
            if current['control'] is not None:
                raise DelegationRevoked('delegation was revoked before admission')
            if current['binding'] is not None:
                return current, current['binding']
            request, thread = current['request'], current['thread_id']
            selection = None
            equipment_binding_revision = None
            if request['schema'] == 'capstone-agent-delegation/2':
                from .mission_equipment import resolve
                selection = resolve(self.threads, workspace, request['mission_origin'],
                    request['equipment'], request['restrictions'])
                from .mission_equipment import registry_revision
                equipment_binding_revision = registry_revision(self.threads._native_binding)
            if datetime.fromisoformat(request['deadline_at']) <= datetime.now(timezone.utc):
                raise DelegationRevoked('delegation deadline expired')
            try:
                self.threads.require_workspace(thread, workspace)
            except ThreadNotFound:
                try:
                    self.threads.create_thread(ThreadSnapshot(thread, RunSnapshot('run_' + thread[4:], 'open'),
                        None, None, None, 0, 0, minimum_protocol_version=2,
                        session_type='enterprise-research'), workspace_name=workspace)
                except ValueError:
                    self.threads.require_workspace(thread, workspace)
            snapshot = self.threads.snapshot(thread)
            if not snapshot.works:
                text = request['objective'] + '\n\n交付要求：\n' + '\n'.join(request['delivery_requirements'])
                if request.get('required_products'):
                    text += '\n必须保存的成果文件：' + json.dumps(request['required_products'], ensure_ascii=False)
                self._command(thread, None, 'work_message', 'create-work', {'text': text})
            work = self.threads.snapshot(thread).to_document()['works'][0]
            if selection is not None:
                from .mission_equipment import bind_work
                bind_work(self.threads, workspace, thread, work['work_id'], selection,
                    binding_revision=equipment_binding_revision)
                work = self.threads.snapshot(thread).to_document()['works'][0]
            if request['context_products']:
                from .delegation_resources import grant_resources
                grant_resources(self.threads, workspace, thread, work['work_id'],
                                request['delegation_id'], request['context_products'])
            if work['latest_attempt_id'] is None and work['start_available']:
                if request['mode'] == 'goal':
                    self._command(thread, work, 'start_goal', 'start',
                        {'objective': work['goal'], 'max_attempts': request['max_attempts'],
                         'deadline_at': request['deadline_at']})
                else:
                    self._command(thread, work, 'start_work', 'start')
            binding = {'thread_id': thread, 'work_id': work['work_id']}
            current['binding'] = binding
            admitted = self.threads.snapshot(thread).works[0]
            current['work_goal_revision'] = admitted['goal_revision']
            current['work_goal_digest'] = _digest(admitted['goal'])
            return current, binding
        binding = self.registry.transact(workspace, delegation['operation_id'], admit)
        if self.wake is not None:
            self.wake(binding['thread_id'])
        return binding

    def _bound(self, workspace, delegation):
        current = self.registry.read(workspace, delegation['operation_id'])
        if current['digest'] != _digest(_request(delegation)):
            raise DelegationConflict('delegation operation content conflict')
        binding = current['binding']
        if binding is None or delegation['binding'] != binding:
            raise DelegationConflict('delegation execution binding mismatch')
        self.threads.require_workspace(binding['thread_id'], workspace)
        return current, binding

    def observe(self, workspace, delegation):
        workspace = normalize_workspace_name(workspace)
        current, binding = self._bound(workspace, delegation)
        snapshot = self.threads.snapshot(binding['thread_id'])
        sequence = snapshot.last_event_seq + len(current['control_receipts'])
        work = next(w for w in snapshot.works if w['work_id'] == binding['work_id'])
        active = snapshot.current_attempt is not None and snapshot.current_attempt.attempt_id == work['latest_attempt_id']
        if current['control'] is not None and not active:
            return {'sequence': sequence,
                    'state': 'cancelled' if current['control'] == 'cancel' else 'paused',
                    'summary': 'execution stopped', 'delivery': None}
        if (work['goal_revision'] != current.get('work_goal_revision') or
                _digest(work['goal']) != current.get('work_goal_digest')):
            return {'sequence': sequence, 'state': 'unknown',
                    'summary': '委托目标已在执行侧修改，请在长期目标中核对。', 'delivery': None}
        status = work.get('goal_mode', {}).get('state', work['status'])
        state = {'ready': 'waiting', 'queued': 'running', 'blocked': 'waiting',
                 'interrupted': 'unknown'}.get(status, status)
        delivery = None
        if state == 'completed':
            after, artifacts, terminal = 0, {}, None
            for _ in range(128):
                page = self.threads.read_attempt_records(binding['thread_id'], work['latest_attempt_id'], after=after, limit=128)
                for event in page['events']:
                    if event['event_type'] == 'native_artifact_published':
                        item = event['payload']['artifact']
                        if item['work_id'] == binding['work_id'] and item.get('source_status') == 'completed':
                            artifacts[item['file_name']] = item
                    if event['event_type'] == 'attempt_completed' and str(event['payload'].get('answer', '')).strip():
                        terminal = event['event_id']
                if not page['has_more']:
                    break
                if page['next_after'] <= after:
                    raise ValueError('Agent observation cursor did not advance')
                after = page['next_after']
            else:
                raise ValueError('Agent observation exceeds bounded page budget')
            if terminal is None:
                raise ValueError('completed Work has no persisted answer')
            delivery = {'answer_ref': terminal, 'products': list(artifacts.values()), 'status': 'completed'}
        return {'sequence': sequence, 'state': state,
                'summary': work.get('goal_mode', {}).get('reason') or work.get('blocked_reason') or state,
                'delivery': delivery}

    def control(self, workspace, delegation, kind, operation_id):
        workspace = normalize_workspace_name(workspace)
        if not isinstance(kind, str) or kind not in {'cancel', 'pause', 'resume'}:
            raise ValueError('unsupported delegation control')
        if not isinstance(operation_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}', operation_id):
            raise ValueError('invalid control operation identity')
        self._reserve(workspace, delegation)
        def revoke(current):
            old = current['control_receipts'].get(operation_id)
            if old is not None:
                if old != kind:
                    raise DelegationConflict('control operation content conflict')
                return current, current
            if kind == 'resume' and (current['control'] == 'cancel' or current['binding'] is None
                                     or current['request']['mode'] != 'goal'):
                raise DelegationRevoked('delegation cannot resume')
            current['control'] = None if kind == 'resume' else kind
            current['control_receipts'][operation_id] = kind
            binding = current['binding']
            if binding is not None:
                snapshot = self.threads.snapshot(binding['thread_id'])
                work = next(w for w in snapshot.works if w['work_id'] == binding['work_id'])
                goal = work.get('goal_mode')
                if kind == 'resume':
                    if goal is None or goal['state'] not in {'paused', 'waiting', 'running', 'ready'}:
                        raise DelegationRevoked('Agent goal cannot resume')
                    if (goal['state'] in {'paused', 'waiting'} and
                            goal['attempts_admitted'] < goal['max_attempts'] and
                            datetime.fromisoformat(goal['deadline_at']) > datetime.now(timezone.utc)):
                        self._command(binding['thread_id'], work, 'resume_goal', operation_id)
                elif goal and goal['state'] not in {'completed', 'cancelled', 'failed'}:
                    self._command(binding['thread_id'], work, kind + '_goal', operation_id)
                elif (snapshot.current_attempt is not None and
                      snapshot.current_attempt.attempt_id == work['latest_attempt_id'] and not work.get('cancel_requested')):
                    self._command(binding['thread_id'], work, 'cancel_work', operation_id)
            return current, current
        current = self.registry.transact(workspace, delegation['operation_id'], revoke)
        if kind == 'resume' and self.wake is not None:
            self.wake(current['binding']['thread_id'])
        if current['binding'] is None:
            return {'sequence': 1, 'state': 'cancelled' if kind == 'cancel' else 'paused',
                    'summary': 'revoked before admission', 'delivery': None}
        return self.observe(workspace, {**delegation, 'binding': current['binding']})
