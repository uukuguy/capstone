"""Bind native activity to host-admitted graph leases without an active-step guess."""
from copy import deepcopy
import json
import math
import re

from .application_capacity import require_capacity

GRAPH_FRAME_TYPES = frozenset({'enterprise_graph_tool_binding', 'enterprise_graph_tool_failure',
    'enterprise_graph_child_started', 'enterprise_graph_child_tool',
    'enterprise_graph_child_response_started', 'enterprise_graph_child_response', 'enterprise_graph_child_finished'})


def _public_text(value, private_roots):
    roots = {'/var/lib/general-pi/tasks/.contexts', *private_roots}
    for root in sorted(roots, key=len, reverse=True):
        value = re.sub(re.escape(root.rstrip('/')) + r"(?:/[^\s\"'`<>]*)?", '[只读任务结果]', value)
    return value


def public_graph_activity(activity, private_roots=()):
    public = {}
    for key, value in activity.items():
        if key not in {'operation', 'output_excerpt', 'warning'} or not isinstance(value, str):
            continue
        # Binary output remains in the original observation, never a JSONB preview.
        # Preserve normal whitespace and existing ANSI display semantics.
        if key == 'output_excerpt' and re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1a\x1c-\x1f]', value):
            public[key] = '非文本工具输出，预览已省略。'
            continue
        value = _public_text(value, private_roots)
        if '\x00' in value:
            value = value.replace('\x00', r'\u0000')
            if len(value) > 240:
                value = value[:240] + '…'
        public[key] = value
    return public


def project_graph_tool_activity(event, private_roots=()):
    """Filter exact host handles before the existing bounded text projection."""
    from .progress import project_native_tool_activity
    arguments = event.get('args', {})
    result = event.get('result', {})
    safe = {**event, 'args': {key: _public_text(value, private_roots)
        for key, value in arguments.items() if key in {'command', 'path', 'file_path'} and isinstance(value, str)}
        if isinstance(arguments, dict) else {}}
    if isinstance(result, dict) and isinstance(result.get('content'), list):
        projected_result: dict = {'content': [{**block, 'text': _public_text(block['text'], private_roots)}
            for block in result['content'] if isinstance(block, dict) and block.get('type') == 'text'
            and isinstance(block.get('text'), str)]}
        details = result.get('details')
        if isinstance(details, dict) and isinstance(details.get('execution_notice'), dict):
            projected_result['details'] = {'execution_notice': details['execution_notice']}
        safe['result'] = projected_result
    return public_graph_activity(project_native_tool_activity(safe), private_roots)


class NativeGraphEvents:
    def __init__(self, *, owner, attempt_id, task_id, private_roots=()):
        self.identity = {'owner': deepcopy(owner), 'attempt_id': attempt_id, 'task_id': task_id}
        self.leases, self.calls, self.children, self.terminals = {}, {}, set(), {}
        self.failures = {}
        self.private_roots = tuple(private_roots)

    def admit_progress(self, progress):
        """HOST ONLY: caller has verified this exact persisted public checkpoint."""
        checkpoint = progress['checkpoint']
        for action in progress['graph']['actions']:
            if action.get('kind') != 'execute':
                continue
            node = next((node for node in progress['graph']['nodes'] if node['id'] == action['step_id']), None)
            if node is None or action.get('owner') != self.identity['owner'] or action.get('attempt_id') != self.identity['attempt_id']:
                raise ValueError('graph action owner is invalid')
            key = (checkpoint['ref'], checkpoint['revision'], action['id'])
            value = {'action': deepcopy(action), 'delegated': node.get('execution') == 'delegated'}
            if key in self.leases and self.leases[key] != value:
                raise ValueError('graph action lease changed')
            self.leases[key] = value

    def action_for_call(self, call_id, tool_name, *, required=True):
        binding = self.calls.get(call_id)
        if binding is None and not required:
            return None
        if binding is None or binding['tool_name'] != tool_name:
            raise ValueError('graph tool has no exact action binding')
        return binding['action_id']

    def admit(self, event):
        event = json.loads(json.dumps(event, allow_nan=False))
        require_capacity('event_bytes', len(json.dumps(event, ensure_ascii=False).encode()), 'graph_native_event')
        if not isinstance(event, dict) or event.get('type') not in GRAPH_FRAME_TYPES:
            raise ValueError('graph native event type is invalid')
        if any(event.get(key) != value for key, value in self.identity.items()):
            raise ValueError('graph native event owner is invalid')
        checkpoint = event.get('checkpoint')
        if (not isinstance(checkpoint, dict) or set(checkpoint) != {'ref', 'revision'}
                or not isinstance(checkpoint['ref'], str) or type(checkpoint['revision']) is not int):
            raise ValueError('graph native event checkpoint is invalid')
        key = (checkpoint['ref'], checkpoint['revision'], event.get('action_id'))
        lease = self.leases.get(key)
        if lease is None or event.get('step_id') != lease['action']['step_id']:
            raise ValueError('graph native event has no committed lease')
        base = {*self.identity, 'type', 'action_id', 'step_id', 'checkpoint'}
        kind = event['type']
        if kind == 'enterprise_graph_tool_binding':
            if set(event) != base | {'tool_call_id', 'tool_name'}:
                raise ValueError('graph tool binding is invalid')
            self._tool(event)
            previous = self.calls.get(event['tool_call_id'])
            if previous is not None and previous != event:
                raise ValueError('graph tool binding changed')
            self.calls[event['tool_call_id']] = deepcopy(event)
            return event
        if kind == 'enterprise_graph_tool_failure':
            if (set(event) != base | {'tool_call_id', 'tool_name', 'status'}
                    or event.get('status') not in {'failed', 'cancelled'}):
                raise ValueError('graph tool failure is invalid')
            self._tool(event)
            expected = {key: value for key, value in event.items() if key != 'status'}
            expected['type'] = 'enterprise_graph_tool_binding'
            if self.calls.get(event['tool_call_id']) != expected:
                raise ValueError('graph tool failure has no exact action binding')
            previous = self.failures.get(event['tool_call_id'])
            if previous is not None and previous != event['status']:
                raise ValueError('graph tool failure status changed')
            self.failures[event['tool_call_id']] = event['status']
            return event
        if not lease['delegated'] or event.get('child_id') != event['step_id']:
            raise ValueError('graph child does not own the action')
        base.add('child_id')
        identity = (event['action_id'], event['child_id'])
        if kind == 'enterprise_graph_child_started':
            if set(event) != base: raise ValueError('graph child start is invalid')
            self.children.add(identity)
        elif identity not in self.children:
            raise ValueError('graph child start was not observed')
        elif kind == 'enterprise_graph_child_tool':
            if (set(event) - base - {'activity', 'tool_name', 'tool_call_id', 'args', 'result', 'is_error', 'execution_ms'}
                    or event.get('activity') not in {'start', 'end'}):
                raise ValueError('graph child tool event is invalid')
            self._tool(event)
            if self.action_for_call(event['tool_call_id'], event['tool_name']) != event['action_id']:
                raise ValueError('graph child tool action changed')
            if 'is_error' in event and type(event['is_error']) is not bool:
                raise ValueError('graph child tool status is invalid')
            if 'execution_ms' in event and (event['activity'] != 'end'
                    or type(event['execution_ms']) not in {int, float}
                    or not math.isfinite(event['execution_ms']) or event['execution_ms'] < 0):
                raise ValueError('graph child tool execution duration is invalid')
        elif kind == 'enterprise_graph_child_response_started':
            if (set(event) != base | {'response_number'}
                    or type(event.get('response_number')) is not int or event['response_number'] < 1):
                raise ValueError('graph child response start is invalid')
        elif kind == 'enterprise_graph_child_response':
            if (set(event) - base - {'response_number', 'response_ms', 'usage', 'tool_call_ids', 'tool_requests', 'response_text', 'stop_reason'}
                    or type(event.get('response_number')) is not int or event['response_number'] < 1
                    or type(event.get('response_ms')) not in {int, float}
                    or not math.isfinite(event['response_ms']) or event['response_ms'] < 0):
                raise ValueError('graph child response is invalid')
            if 'tool_call_ids' in event:
                ids = event['tool_call_ids']
                if (not isinstance(ids, list) or any(not isinstance(value, str) or not value or len(value) > 128 for value in ids)
                        or len(set(ids)) != len(ids)):
                    raise ValueError('graph child response tool identities are invalid')
            if 'stop_reason' in event and event['stop_reason'] not in {'stop', 'length', 'toolUse', 'error', 'aborted'}:
                raise ValueError('graph child response stop reason is invalid')
            if 'tool_requests' in event:
                requests = event['tool_requests']
                if (not isinstance(requests, list) or any(not isinstance(item, dict)
                        or set(item) - {'id', 'name', 'operation'} or not isinstance(item.get('id'), str)
                        or not item['id'] or len(item['id']) > 128 or not isinstance(item.get('name'), str)
                        or not item['name'] or len(item['name']) > 128 or 'operation' in item
                        and (not isinstance(item['operation'], str) or len(item['operation']) > 180) for item in requests)
                        or len({item['id'] for item in requests}) != len(requests)
                        or 'tool_call_ids' in event and [item['id'] for item in requests] != event['tool_call_ids']):
                    raise ValueError('graph child tool requests are invalid')
            if 'response_text' in event and (not isinstance(event['response_text'], str) or len(event['response_text']) > 600):
                raise ValueError('graph child response text is invalid')
            self._usage(event.get('usage'))
        elif kind == 'enterprise_graph_child_finished':
            if (set(event) - base - {'status', 'result_summary', 'usage', 'model_responses', 'turns'}
                    or event.get('status') not in {'completed', 'failed', 'cancelled', 'unknown'}
                    or not isinstance(event.get('result_summary'), str)):
                raise ValueError('graph child finish is invalid')
            for field in ('model_responses', 'turns'):
                if field in event and (type(event[field]) is not int or event[field] < 0):
                    raise ValueError('graph child count is invalid')
            usage = event.get('usage')
            if usage is not None:
                if not isinstance(usage, list): raise ValueError('graph child usage is invalid')
                for item in usage: self._usage(item)
            if identity in self.terminals and self.terminals[identity] != event:
                raise ValueError('graph child terminal changed')
            self.terminals[identity] = deepcopy(event)
        public = {key: value for key, value in event.items() if key not in {'args', 'result'}}
        if kind == 'enterprise_graph_child_response':
            if 'response_text' in public:
                public['response_text'] = public_graph_activity({'output_excerpt': public['response_text']}, self.private_roots).get('output_excerpt', '')
            if 'tool_requests' in public:
                public['tool_requests'] = [{**item, **({'operation': _public_text(item['operation'], self.private_roots)}
                    if 'operation' in item else {})} for item in public['tool_requests']]
        if kind == 'enterprise_graph_child_tool':
            native = {'type': 'tool_execution_' + event['activity'], 'toolName': event['tool_name'],
                      'toolCallId': event['tool_call_id'], 'args': event.get('args', {}),
                      'result': event.get('result', {}), 'isError': event.get('is_error', False)}
            activity = project_graph_tool_activity(native, self.private_roots)
            if activity: public['tool_activity'] = activity
            result = event.get('result')
            details = result.get('details') if isinstance(result, dict) else None
            if (event['tool_name'] == 'agent_task_return' and event['activity'] == 'end'
                    and event.get('is_error') is False and isinstance(details, dict)
                    and details.get('task_return_saved') is True):
                notes = details.get('task_return_limitations', [])
                if isinstance(notes, list) and all(isinstance(note, str) for note in notes):
                    public['task_return'] = {'status': 'saved', 'limitation_count': len(notes),
                        'limitations': [_public_text(note, self.private_roots) for note in notes[:16]]}
        return public

    @staticmethod
    def _tool(event):
        for field in ('tool_call_id', 'tool_name'):
            if not isinstance(event.get(field), str) or not event[field] or len(event[field]) > 128:
                raise ValueError('graph tool identity is invalid')

    @staticmethod
    def _usage(value):
        if value is None: return
        if not isinstance(value, dict): raise ValueError('graph child usage is invalid')
        # Managed usage is numeric or nested numeric counters; no private text.
        for item in value.values():
            if item is None: continue  # Missing SDK counters and pricing stay unknown.
            if isinstance(item, dict): NativeGraphEvents._usage(item)
            elif type(item) not in {int, float} or not math.isfinite(item) or item < 0:
                raise ValueError('graph child usage is invalid')
