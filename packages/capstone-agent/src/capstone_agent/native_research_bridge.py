"""Transport the existing research channel. The mirror owns no research ledger."""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
from threading import Event, RLock
from uuid import uuid4
from .application_capacity import current_capacity, CapacityExceeded

SCHEMA = 'capstone-research-bridge/1'
RESEARCH_TOOLS = ('agent_research_read', 'agent_research_update', 'agent_research_depth', 'agent_task_progress')
LEGACY_CYCLE_CONTROL_TOOLS = ('agent_research_cycle',)
SPLIT_CYCLE_CONTROL_TOOLS = ('agent_research_plan', 'agent_research_record', 'agent_research_assess')
CYCLE_CONTROL_TOOLS = (*LEGACY_CYCLE_CONTROL_TOOLS, *SPLIT_CYCLE_CONTROL_TOOLS)
GRAPH_CONTROL_TOOLS = ('agent_research_plan', 'agent_research_start', 'agent_research_record',
    'agent_research_assess', 'agent_research_revise', 'agent_research_resolve',
    'agent_research_inspect', 'agent_research_finish')
# Preserve the existing export for frozen legacy requests. Publication supports
# both interfaces; admission selects exactly one from the accepted profile.
ENTERPRISE_RESEARCH_TOOLS = (*RESEARCH_TOOLS, *LEGACY_CYCLE_CONTROL_TOOLS, 'agent_delegate')
ALL_ENTERPRISE_RESEARCH_TOOLS = tuple(dict.fromkeys((*RESEARCH_TOOLS, *CYCLE_CONTROL_TOOLS, *GRAPH_CONTROL_TOOLS, 'agent_delegate')))


def research_tools_for_profile(profile_id: str, version: str) -> tuple[str, ...]:
    if profile_id != 'enterprise-research':
        return ()
    if version in {'1.10.0', '1.11.0', '1.12.0', '1.13.0', '1.14.0', '1.15.0', '1.16.0', '1.17.0', '1.18.0', '1.19.0'}:
        return (*(name for name in RESEARCH_TOOLS if name != 'agent_research_update'), *GRAPH_CONTROL_TOOLS)
    if version == '1.1.0':
        return ENTERPRISE_RESEARCH_TOOLS
    if version in {'1.2.0', '1.3.0', '1.4.0', '1.5.0', '1.6.0', '1.7.0', '1.8.0', '1.9.0'}:
        return (*RESEARCH_TOOLS, *SPLIT_CYCLE_CONTROL_TOOLS, 'agent_delegate')
    return ()


_IDENTITY = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z')
_IDENTITIES = ('run_id', 'turn_id', 'attempt_id', 'research_id')


class _BridgeLimits(dict):
    """Numeric limits retain their immutable task's diagnostic mode."""
    def __init__(self, values, mode):
        super().__init__(values)
        self.mode = mode


def _limits(binding=None):
    mode = (binding or {}).get('runtime_limit_mode', current_capacity().mode)
    if mode not in ('normal', 'debug'):
        raise ValueError('research runtime limit mode is invalid')
    values = _BridgeLimits(current_capacity().values, mode)
    selected=(binding or {}).get('runtime_limits',{})
    if not isinstance(selected,dict) or any(not isinstance(key,str) or type(value) is not int
            or value < (0 if key=='provider_stream_bytes' else 1) or value > 2**53-1 for key,value in selected.items()):
        raise ValueError('research runtime_limits are invalid')
    values.update(selected)
    return values


def _check(limits, dimension, actual):
    if actual > limits[dimension]:
        raise CapacityExceeded(dimension,actual,limits[dimension],'research_bridge', mode=limits.mode)


def read_json(path, *, maximum=None):
    return json.loads(read_text(path,maximum=maximum))


def read_text(path, *, maximum=None,dimension='research_response_bytes'):
    maximum=current_capacity().values['research_response_bytes'] if maximum is None else maximum
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError('research transport file is invalid')
        if before.st_size > maximum:
            raise CapacityExceeded(dimension,before.st_size,maximum,'research_read', mode=current_capacity().mode)
        with os.fdopen(descriptor, 'r', encoding='utf-8', closefd=False) as source:
            text = source.read(maximum + 1)
        after, named = os.fstat(descriptor), os.stat(path, follow_symlinks=False)
        identity = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns, item.st_ctime_ns)
        if len(text.encode()) > maximum:
            raise CapacityExceeded(dimension,len(text.encode()),maximum,'research_read', mode=current_capacity().mode)
        if identity(before) != identity(after) or identity(after) != identity(named):
            raise ValueError('research transport file changed')
        return text
    finally:
        os.close(descriptor)


def write_text(path, text, *, maximum=None,dimension='research_response_bytes'):
    maximum=current_capacity().values['research_response_bytes'] if maximum is None else maximum
    if len(text.encode()) > maximum:
        raise CapacityExceeded(dimension,len(text.encode()),maximum,'research_write', mode=current_capacity().mode)
    temporary = path.with_name('.' + uuid4().hex + '.tmp')
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o640)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as target:
            target.write(text)
            target.flush()
            os.fsync(target.fileno())
        # Preserve the private task group when a view/receipt is replaced.
        group = path.parent.stat().st_gid
        if os.geteuid() == 0:
            os.chown(temporary, 0, group)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_json(path, document, *, maximum=None):
    write_text(path, json.dumps(document, ensure_ascii=False, sort_keys=True, allow_nan=False) + '\n',maximum=maximum)


def checked_binding(value):
    # These schemas come from the accepted host application, never tool args.
    value = json.loads(json.dumps(value))
    if (not isinstance(value, dict) or set(value)-{'runtime_limits', 'runtime_limit_mode', 'cycle_owner', 'graph_schema', 'graph_work_edition'} != {
            'schema_version', *_IDENTITIES, 'read_tool_schema', 'update_tool_schema',
            'depth_tool_schema', 'progress_tool_schema'}
            or value['schema_version'] != 'capability-research-channel/1.0'
            or any(not isinstance(value[key], str) or not _IDENTITY.fullmatch(value[key]) for key in _IDENTITIES)
            or any(not isinstance(value[key], dict) or value[key].get('additionalProperties') is not False
                   for key in ('read_tool_schema', 'update_tool_schema', 'depth_tool_schema', 'progress_tool_schema'))):
        raise ValueError('research transport binding is invalid')
    if 'graph_schema' in value and value['graph_schema'] != 'capstone-enterprise-graph/2':
        raise ValueError('research graph publication is invalid')
    if 'graph_work_edition' in value and (value['graph_work_edition'] != 'capstone-graph-work/1' or value.get('graph_schema') != 'capstone-enterprise-graph/2'):
        raise ValueError('research graph work edition is invalid')
    if 'cycle_owner' in value:
        owner = value['cycle_owner']
        if (not isinstance(owner, dict) or set(owner) != {'thread_id', 'work_id', 'research_id', 'goal_revision'}
                or any(not isinstance(owner[key], str) or not _IDENTITY.fullmatch(owner[key])
                       for key in ('thread_id', 'work_id', 'research_id'))
                or owner['research_id'] != value['research_id']
                or type(owner['goal_revision']) is not int or not 1 <= owner['goal_revision'] <= 2**53 - 1):
            raise ValueError('research cycle owner is invalid')
    _check(_limits(value),'control_document_bytes',len(json.dumps(value).encode()))
    return value


def checked_view(value, binding):
    value = json.loads(json.dumps(value))
    if (not isinstance(value, dict) or set(value) != {'schema_version', *_IDENTITIES, 'research_revision', 'state'}
            or value['schema_version'] != 'capability-research-view/1.0'
            or any(value[key] != binding[key] for key in _IDENTITIES)
            or type(value['research_revision']) is not int or value['research_revision'] < 0
            or (value['state'] is None and value['research_revision'] != 0)
            or (value['state'] is not None and (not isinstance(value['state'], dict)
                or value['state'].get('research_id') != binding['research_id']
                or value['state'].get('revision') != value['research_revision']))):
        raise ValueError('research transport view is invalid')
    _check(_limits(binding),'research_response_bytes',len(json.dumps(value).encode()))
    return value


def checked_graph_progress(value, *, binding, task_id, attempt_id, view):
    """Admit an exact public graph from its own confirmed host checkpoint."""
    value = json.loads(json.dumps(value, allow_nan=False))
    binding = checked_binding(binding)
    owner = binding.get('cycle_owner')
    required = {'type', 'owner', 'attempt_id', 'task_id', 'checkpoint', 'graph', 'events'}
    if (binding.get('graph_schema') != 'capstone-enterprise-graph/2' or owner is None
            or not isinstance(value, dict) or set(value) - {'action_id', 'control'} != required
            or value['type'] != 'enterprise_graph_progress' or value['owner'] != owner
            or value['task_id'] != task_id or value['attempt_id'] != attempt_id
            or attempt_id != binding['attempt_id'] or not isinstance(value['graph'], dict)
            or value['graph'].get('schema') != binding['graph_schema']
            or not isinstance(value['events'], list)
            or 'action_id' in value and not isinstance(value['action_id'], str)):
        raise ValueError('research graph progress identity is invalid')
    control = value.get('control')
    if control is not None and (not isinstance(control, dict) or set(control) != {'tool_call_id', 'tool_name'}
            or not isinstance(control['tool_call_id'], str) or not control['tool_call_id']
            or len(control['tool_call_id']) > 128 or control['tool_name'] not in GRAPH_CONTROL_TOOLS):
        raise ValueError('research graph control identity is invalid')
    checkpoint = value['checkpoint']
    if (not isinstance(checkpoint, dict) or set(checkpoint) != {'ref', 'revision'}
            or not isinstance(checkpoint['ref'], str) or type(checkpoint['revision']) is not int
            or checkpoint['revision'] < 1 or not isinstance(view, dict)
            or type(view.get('research_revision')) is not int
            or checkpoint['revision'] > view['research_revision']):
        raise ValueError('research graph checkpoint revision is invalid')
    _check(_limits(binding), 'event_bytes', len(json.dumps(value, ensure_ascii=False).encode()))
    notes = view.get('state', {}).get('notes', []) if isinstance(view.get('state'), dict) else []
    note = next((item for item in notes if isinstance(item, dict)
                 and item.get('note_id') == checkpoint['ref']), None)
    if note is None or not isinstance(note.get('text'), str):
        raise ValueError('research graph checkpoint is not committed')
    saved = json.loads(note['text'])
    snapshot = saved.get('snapshot') if isinstance(saved, dict) else None
    if (not isinstance(saved, dict) or saved.get('schema') != 'capstone-enterprise-graph-checkpoint/1'
            or saved.get('runId') != task_id or not isinstance(saved.get('command_id'), str)
            or type(saved.get('committed_revision')) is not int
            or saved.get('committed_revision') != checkpoint['revision']
            or not isinstance(snapshot, dict) or snapshot.get('schema') != binding['graph_schema']
            or snapshot.get('owner') != owner
            or snapshot.get('work_edition') != binding.get('graph_work_edition')
            or snapshot.get('attempt_id') != attempt_id):
        raise ValueError('research graph checkpoint owner or revision is invalid')
    expected = ('runtime.checkpoint.' + sha256(task_id.encode()).hexdigest()[:20] + '.'
                + sha256(('call:' + saved['command_id']).encode()).hexdigest()[:24])
    public = {key: item for key, item in value.items() if key != 'checkpoint'}
    if checkpoint['ref'] != expected or public != saved.get('public_progress'):
        raise ValueError('research graph progress is not committed')
    if control is not None and (control['tool_call_id'] != saved['command_id']
            or not any(command.get('id') == control['tool_call_id']
                and 'agent_research_' + str(command.get('operation')) == control['tool_name']
                for command in saved.get('commands', []))):
        raise ValueError('research graph control is not committed')
    return value


def checked_cycle_progress(value, *, binding, task_id, attempt_id, view):
    """Project only progress present in this owner's host-committed checkpoint."""
    value = json.loads(json.dumps(value, allow_nan=False))
    binding = checked_binding(binding)
    owner = binding.get('cycle_owner')
    if isinstance(value, dict) and 'owner' in value:
        checked_binding({**binding, 'cycle_owner': value['owner']})
    if (owner is None or not isinstance(value, dict) or set(value) != {
            'type', 'owner', 'attempt_id', 'action_id', 'checkpoint', 'progress'}
            or value['type'] != 'enterprise_cycle_progress' or value['owner'] != owner
            or value['attempt_id'] != attempt_id or attempt_id != binding['attempt_id']
            or not isinstance(value['action_id'], str) or not re.fullmatch(r'cycle-[a-f0-9]{64}', value['action_id'])):
        raise ValueError('research cycle progress identity is invalid')
    checkpoint, progress = value['checkpoint'], value['progress']
    if (not isinstance(checkpoint, dict) or set(checkpoint) != {'ref', 'revision'}
            or not isinstance(checkpoint['ref'], str)
            or type(checkpoint['revision']) is not int or checkpoint['revision'] < 1
            or not isinstance(view, dict) or type(view.get('research_revision')) is not int
            or checkpoint['revision'] > view['research_revision']
            or not isinstance(progress, dict) or set(progress) - {
                'outcome', 'questions', 'expected_outputs', 'derived_from', 'result_summary', 'next_action_reason'}
                != {'step_id', 'phase', 'text'}
            or not isinstance(progress['step_id'], str) or not _IDENTITY.fullmatch(progress['step_id'])
            or progress['phase'] not in {'started', 'updated', 'settled'}
            or not isinstance(progress['text'], str) or not progress['text'].strip()
            or 'outcome' in progress and progress['outcome'] not in {'met', 'partial', 'failed', 'limited'}):
        raise ValueError('research cycle progress is invalid')
    selected = _limits(binding)
    _check(selected, 'research_progress_chars', len(progress['text']))
    for field, dimension in (('questions', 'research_question_count'),
                             ('expected_outputs', 'context_references'), ('derived_from', 'context_references')):
        if field not in progress:
            continue
        values = progress[field]
        if not isinstance(values, list) or any(not isinstance(item, str) or not item.strip() for item in values):
            raise ValueError('research cycle progress metadata is invalid')
        _check(selected, dimension, len(values))
        for item in values:
            _check(selected, 'research_text_chars', len(item))
    for field in ('result_summary', 'next_action_reason'):
        if field in progress:
            if not isinstance(progress[field], str) or not progress[field].strip():
                raise ValueError('research cycle progress metadata is invalid')
            _check(selected, 'research_summary_chars', len(progress[field]))
    _check(selected, 'event_bytes', len(json.dumps(value, ensure_ascii=False).encode()))
    saved = _committed_cycle_checkpoint(checkpoint, owner=owner, task_id=task_id, attempt_id=attempt_id, view=view)
    call = saved['cycleCall']
    if (not isinstance(call.get('progress'), list)
            or {'action_id': value['action_id'], 'progress': progress} not in call['progress']):
        raise ValueError('research cycle progress is not committed')
    return value


def _committed_cycle_checkpoint(checkpoint, *, owner, task_id, attempt_id, view):
    if (not isinstance(checkpoint, dict) or set(checkpoint) != {'ref', 'revision'}
            or not isinstance(checkpoint['ref'], str)
            or type(checkpoint['revision']) is not int or checkpoint['revision'] < 1
            or not isinstance(view, dict) or type(view.get('research_revision')) is not int
            or checkpoint['revision'] > view['research_revision']):
        raise ValueError('research cycle checkpoint revision is invalid')
    state = view.get('state')
    notes = state.get('notes', []) if isinstance(state, dict) else []
    note = next((item for item in notes if isinstance(item, dict) and item.get('note_id') == checkpoint['ref']), None)
    if note is None or not isinstance(note.get('text'), str):
        raise ValueError('research cycle checkpoint is not committed')
    saved = json.loads(note['text'])
    if not isinstance(saved, dict):
        raise ValueError('research cycle checkpoint is invalid')
    snapshot, call = saved.get('snapshot'), saved.get('cycleCall')
    if (saved.get('schema') not in {'capstone-enterprise-cycle-checkpoint/1', 'capstone-enterprise-cycle-checkpoint/2'} or saved.get('runId') != task_id
            or not isinstance(snapshot, dict) or snapshot.get('owner') != owner or snapshot.get('attempt_id') != attempt_id
            or not isinstance(call, dict) or not isinstance(call.get('id'), str)):
        raise ValueError('research cycle checkpoint owner is invalid')
    expected_ref = ('runtime.checkpoint.' + sha256(task_id.encode()).hexdigest()[:20] + '.'
                    + sha256(('call:' + call['id']).encode()).hexdigest()[:24])
    if checkpoint['ref'] != expected_ref:
        raise ValueError('research cycle checkpoint reference is invalid')
    return saved


def checked_branch_progress(value, *, binding, task_id, attempt_id, view, allow_delivery_review=False):
    """Child observations belong to an accepted parent action, not Authority."""
    value = json.loads(json.dumps(value, allow_nan=False))
    binding = checked_binding(binding)
    owner = binding.get('cycle_owner')
    if not isinstance(value, dict):
        raise ValueError('research branch progress is invalid')
    if 'owner' in value:
        checked_binding({**binding, 'cycle_owner': value['owner']})
    base = {'type', 'subordinate', 'owner', 'attempt_id', 'parent_action_id', 'parent_step_id',
            'parent_tool_call_id', 'child_id', 'title', 'questions', 'expected_outputs', 'checkpoint'}
    kind = value.get('type')
    required = base | ({'status', 'result_summary'} if kind == 'delegation_child_finished' else
                       {'activity', 'tool_name', 'tool_call_id'} if kind == 'delegation_child_tool' else
                       {'response_number', 'response_ms'} if kind == 'delegation_child_response' else set())
    optional = {'error'} if kind == 'delegation_child_finished' else {'is_error', 'args', 'result'} if kind == 'delegation_child_tool' else set()
    optional |= {'review_mode'}
    if (kind not in {'delegation_child_started', 'delegation_child_finished', 'delegation_child_tool', 'delegation_child_response'}
            or set(value) - optional != required or value.get('subordinate') is not True
            or owner is None or value['owner'] != owner or value['attempt_id'] != attempt_id
            or attempt_id != binding['attempt_id']
            or not isinstance(value['parent_action_id'], str) or not re.fullmatch(r'cycle-[a-f0-9]{64}', value['parent_action_id'])
            or any(not isinstance(value[key], str) or not value[key].strip()
                   for key in ('parent_step_id', 'parent_tool_call_id', 'child_id', 'title'))):
        raise ValueError('research branch identity is invalid')
    reviewing = value.get('review_mode') == 'delivery'
    if ('review_mode' in value and (not reviewing or allow_delivery_review is not True)
            or reviewing and kind == 'delegation_child_tool'):
        raise ValueError('research branch review mode is invalid')
    selected = _limits(binding)
    for key in ('parent_step_id', 'parent_tool_call_id', 'child_id', 'title'):
        _check(selected, 'research_progress_chars', len(value[key]))
    for key, dimension in (('questions', 'research_question_count'), ('expected_outputs', 'context_references')):
        values = value[key]
        if not isinstance(values, list) or not values or any(not isinstance(item, str) or not item.strip() for item in values):
            raise ValueError('research branch task metadata is invalid')
        _check(selected, dimension, len(values))
        for item in values:
            _check(selected, 'research_text_chars', len(item))
    saved = _committed_cycle_checkpoint(value['checkpoint'], owner=owner, task_id=task_id, attempt_id=attempt_id, view=view)
    pending = saved['snapshot'].get('pending_action')
    if (not isinstance(pending, dict) or pending.get('id') != value['parent_action_id']
            or pending.get('kind') not in ({'execute', 'assess'} if reviewing else {'execute'})
            or pending.get('objective_id') != value['parent_step_id']
            or not isinstance(pending.get('questions'), list)
            or any(question not in pending['questions'] for question in value['questions'])):
        raise ValueError('research branch does not belong to the committed parent action')
    if kind == 'delegation_child_response':
        if (type(value['response_number']) is not int or value['response_number'] < 1
                or type(value['response_ms']) is not int or value['response_ms'] < 0):
            raise ValueError('research branch response timing is invalid')
    elif kind == 'delegation_child_finished':
        if value['status'] not in {'completed', 'failed', 'cancelled'} or not isinstance(value['result_summary'], str):
            raise ValueError('research branch result is invalid')
        _check(selected, 'answer_bytes', len(value['result_summary'].encode()))
        if 'error' in value:
            error = value['error']
            if (not isinstance(error, dict) or set(error) - {'type'} != {'code', 'message'}
                    or any(not isinstance(item, str) or not item.strip() for item in error.values())):
                raise ValueError('research branch error is invalid')
            for item in error.values():
                _check(selected, 'research_summary_chars', len(item))
    elif kind == 'delegation_child_tool':
        if (value['activity'] not in {'start', 'end'}
                or any(not isinstance(value[key], str) or not value[key].strip() for key in ('tool_name', 'tool_call_id'))
                or 'is_error' in value and type(value['is_error']) is not bool):
            raise ValueError('research branch tool activity is invalid')
        for key in ('tool_name', 'tool_call_id'):
            _check(selected, 'research_progress_chars', len(value[key]))
    _check(selected, 'event_bytes', len(json.dumps(value, ensure_ascii=False).encode()))
    # Native frames are private. Publish only the existing bounded, redacted
    # activity projection, never arguments or raw child tool responses.
    from .progress import project_native_tool_activity, project_tool_failure
    if kind == 'delegation_child_tool':
        for key in ('args', 'result'):
            if key in value and not isinstance(value[key], dict):
                raise ValueError('research branch tool diagnostic is invalid')
        activity = project_native_tool_activity(value)
        value.pop('args', None)
        value.pop('result', None)
        if activity:
            value['tool_activity'] = activity
    elif kind == 'delegation_child_finished' and 'error' in value:
        value['error'] = {**value['error'], **project_tool_failure(value['error'])}
    return value


class ResearchMirror:
    """A task-private file mirror for the canonical tools; never mints revisions."""
    def __init__(self, root: Path, binding):
        self.root, self.binding = root, checked_binding(binding)
        self.limits=_limits(self.binding)
        root.mkdir(parents=True, mode=0o750, exist_ok=False)
        for name in ('requests', 'receipts'):
            (root / name).mkdir(mode=0o750)
        write_json(root / 'binding.json', self.binding,maximum=self.limits['control_document_bytes'])
        self.ready = Event()
        self._lock, self._owner, self._view = RLock(), None, None

    def _check_owner(self, owner):
        if not isinstance(owner, str) or not re.fullmatch(r'[a-f0-9]{64}', owner):
            raise ValueError('research transport owner is invalid')
        if self._owner is not None and owner != self._owner:
            raise RuntimeError('research transport owner conflict; do not repeat unknown work')

    def _publish_view(self, value):
        value = checked_view(value, self.binding)
        if self._view is not None:
            if value['research_revision'] < self._view['research_revision']:
                raise ValueError('research view revision regressed')
            if value['research_revision'] == self._view['research_revision'] and value != self._view:
                raise ValueError('research view changed without a revision')
        write_json(self.root / 'view.json', value,maximum=self.limits['research_response_bytes'])
        self._view = value

    def bootstrap(self, owner, document):
        with self._lock:
            self._check_owner(owner)
            if set(document) != {'binding', 'view'} or document['binding'] != self.binding:
                raise ValueError('research bootstrap identity changed')
            self._publish_view(document['view'])
            self._owner = owner
            self.ready.set()

    def pending(self, owner):
        with self._lock:
            self._check_owner(owner)
            if not self.ready.is_set():
                raise RuntimeError('research transport is not ready')
            result = []
            for path in sorted((self.root / 'requests').glob('*.json')):
                if not _IDENTITY.fullmatch(path.stem):
                    raise ValueError('research request identity is invalid')
                raw = read_text(path,maximum=self.limits['research_request_bytes'],dimension='research_request_bytes')
                _check(self.limits,'research_request_bytes',len(raw.encode()))
                receipt = self.root / 'receipts' / path.name
                if receipt.exists():
                    ack = read_json(receipt,maximum=self.limits['research_response_bytes'])
                    if ack['request_sha256'] != sha256(raw.encode()).hexdigest():
                        raise ValueError('research request changed after receipt')
                    if ack['status'] != 'not_confirmed':
                        continue
                item={'request_id':path.stem,'raw':raw}
                size=len(json.dumps([*result,item],ensure_ascii=False).encode())
                if size > self.limits['research_response_bytes'] and result:
                    break
                _check(self.limits,'research_response_bytes',size)
                result.append(item)
                if len(result) == self.limits['rpc_batch_requests']:
                    break
            return result

    def acknowledge(self, owner, document):
        with self._lock:
            self._check_owner(owner)
            if not self.ready.is_set() or set(document) != {'view', 'receipts'}:
                raise ValueError('research acknowledgement is invalid')
            _check(self.limits,'rpc_batch_requests',len(document['receipts']))
            for ack in document['receipts']:
                identity = ack.get('request_id')
                if not isinstance(identity, str) or not _IDENTITY.fullmatch(identity):
                    raise ValueError('research receipt identity is invalid')
                raw = read_text(self.root / 'requests' / (identity + '.json'),maximum=self.limits['research_request_bytes'],dimension='research_request_bytes')
                request = json.loads(raw)
                if (ack.get('schema_version') != 'capability-research-receipt/1.0'
                        or any(ack.get(key) != self.binding[key] for key in ('run_id', 'turn_id', 'attempt_id'))
                        or ack.get('request_sha256') != sha256(raw.encode()).hexdigest()
                        or ack.get('status') not in {'committed', 'rejected', 'not_confirmed'}):
                    raise ValueError('research receipt does not match the request')
                if ack['status'] == 'committed' and (ack.get('receipt', {}).get('research_id') != self.binding['research_id']
                        or ack['receipt'].get('request_id') != identity
                        or ack['receipt'].get('research_revision') != request.get('expected_revision', -2) + 1
                        or ack['receipt']['research_revision'] > document['view']['research_revision']):
                    raise ValueError('research committed receipt is invalid')
                existing = self.root / 'receipts' / (identity + '.json')
                if existing.exists() and read_json(existing).get('status') != 'not_confirmed' and read_json(existing) != ack:
                    raise ValueError('research receipt changed')
            # The tools must see committed state before they observe success.
            self._publish_view(document['view'])
            for ack in document['receipts']:
                write_json(self.root / 'receipts' / (ack['request_id'] + '.json'), ack,maximum=self.limits['research_response_bytes'])


class WorkerResearchBridge:
    """Use the existing controller's validation, CAS, active guard and receipts."""
    def __init__(self, channel, *, owner_id, producer_binding=None, on_commit=lambda: None,
                 admit_sources=lambda refs: None):
        self.channel, self.owner_id = channel, owner_id
        self.binding = checked_binding(producer_binding or read_json(channel.root / 'binding.json'))
        self.limits=_limits(self.binding)
        self.on_commit = on_commit
        self.admit_sources = admit_sources

    def _project_identity(self, document):
        return {**document, **{key: self.binding[key] for key in _IDENTITIES if key in document}}

    def bootstrap(self):
        self.channel.publish_view()
        return {'binding': self.binding, 'view': self._project_identity(read_json(self.channel.view_path,maximum=self.limits['research_response_bytes']))}

    def process(self, requests):
        if not isinstance(requests, list):
            raise ValueError('research request batch exceeds bounds')
        _check(self.limits,'rpc_batch_requests',len(requests))
        paths = []
        for item in requests:
            identity, raw = item['request_id'], item['raw']
            if (not isinstance(identity, str) or not _IDENTITY.fullmatch(identity)
                    or not isinstance(raw, str)):
                raise ValueError('research request is invalid')
            _check(self.limits,'research_request_bytes',len(raw.encode()))
            path = self.channel.requests_path / (identity + '.json')
            if path.exists():
                if read_text(path,maximum=self.limits['research_request_bytes'],dimension='research_request_bytes') != raw:
                    raise ValueError('research request identity changed')
            else:
                write_text(path, raw,maximum=self.limits['research_request_bytes'],dimension='research_request_bytes')
            paths.append(identity)
        before = self.channel.controller.read()
        self.channel.drain(max_requests=self.limits['rpc_batch_requests'])
        after = self.channel.controller.read()
        if after is not None and (before is None or after.revision != before.revision):
            self.on_commit()
        return {'view': self._project_identity(read_json(self.channel.view_path,maximum=self.limits['research_response_bytes'])), 'receipts': [
            self._project_identity(read_json(self.channel.receipts_path / (identity + '.json'),maximum=self.limits['research_response_bytes'])) for identity in paths]}


class SourceReceiptCache:
    """Retain verified source receipts for current Work research, not a ledger.

    Only protected executor observations enter this cache. Model-provided refs
    and research judgments cannot add a source. Keep every receipt still used
    by committed state; discard unused prior-turn receipts at the next turn.
    """
    def __init__(self, path, owner, *, referenced=()):
        self.path, self.owner = path, dict(owner)
        self.records = {}
        if path.exists():
            document = read_json(path)
            if (set(document) != {'schema', 'owner', 'receipts'}
                    or document['schema'] != 'capstone-native-source-receipts/1'
                    or document['owner'] != self.owner or not isinstance(document['receipts'], list)):
                raise ValueError('native source receipt owner changed')
            for record in document['receipts']:
                self._validate(record)
                if record['source_ref'] in referenced:
                    self.records[record['source_ref']] = record

    @staticmethod
    def _validate(record):
        if (not isinstance(record, dict) or set(record) != {'task_id', 'parent_attempt_id', 'source_ref', 'observation_sha256'}
                or not isinstance(record['task_id'], str) or not isinstance(record['source_ref'], str)
                or not re.fullmatch(r'[a-f0-9]{64}', record['observation_sha256'])
                or not _IDENTITY.fullmatch(record['parent_attempt_id'])
                or not re.fullmatch(re.escape('native-observation:' + record['task_id'] + ':') + r'[a-f0-9]{64}', record['source_ref'])):
            raise ValueError('native source receipt identity is invalid')

    def accept(self, records):
        updated = dict(self.records)
        for record in records:
            self._validate(record)
            previous = updated.get(record['source_ref'])
            if previous is not None and previous != record:
                raise ValueError('native source identity changed observed content')
            updated[record['source_ref']] = record
        if updated == self.records and self.path.exists():
            return
        document = {'schema': 'capstone-native-source-receipts/1', 'owner': self.owner,
                    'receipts': list(updated.values())}
        write_json(self.path, document)
        self.records = updated
