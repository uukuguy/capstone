"""Validate instruction-owned model scheduling metadata, never model answers."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re

MODEL_REQUEST_POOL_POLICY = json.loads(
    (Path(__file__).parent / 'resources' / 'model-request-pool-policy.json').read_text())
_TERMINAL = {'completed', 'failed', 'cancelled', 'blocked'}
_TRANSITIONS = {
    'queued': {'queued', 'waiting_dependencies', 'running', 'cancelled', 'blocked'},
    'waiting_dependencies': {'waiting_dependencies', 'queued', 'running', 'cancelled', 'blocked'},
    'running': {'running', 'cancelling', 'completed', 'failed', 'cancelled'},
    'cancelling': {'cancelling', 'cancelled', 'failed'},
}


def registered_model_request_pool(value):
    return (isinstance(value, dict) and set(value) == set(MODEL_REQUEST_POOL_POLICY)
        and all(type(value[key]) is type(expected) and value[key] == expected
                for key, expected in MODEL_REQUEST_POOL_POLICY.items()))


def checked_model_request_pool(event, native, capability, record):
    """Commit a validated transition atomically; the caller owns event serialization."""
    from .native_task_context import public_document
    from .native_llm_pool import registered_llm_call_pool
    native = public_document(native)
    if (not isinstance(native, dict) or native.get('deep_research') is not False
            or not registered_model_request_pool(capability.get('model_request_pool'))):
        raise ValueError('model request pool is not admitted')
    required = {'type', 'schema', 'request_id', 'chain_id', 'kind', 'depends_on', 'status', 'queued_at_ms'}
    optional = {'started_at_ms', 'finished_at_ms', 'cancel_reason', 'parent_tool_call_id', 'child_id', 'model_turn_number', 'title'}
    def text(value):
        return (isinstance(value, str) and 0 < len(value) <= 128 and bool(value.strip())
            and all(ord(char) >= 32 and ord(char) != 127 for char in value))
    def number(value):
        return type(value) is int and 0 <= value <= 9007199254740991
    if (not isinstance(event, dict) or not required <= set(event) or set(event) - required - optional
            or event['type'] != 'model_request_pool' or event['schema'] != MODEL_REQUEST_POOL_POLICY['schema']
            or not isinstance(event['request_id'], str) or not re.fullmatch(r'request-[1-9][0-9]{0,8}', event['request_id'])
            or not isinstance(event['status'], str) or event['status'] not in set(_TRANSITIONS) | _TERMINAL
            or not isinstance(event['depends_on'], list) or len(event['depends_on']) > MODEL_REQUEST_POOL_POLICY['max_requests']
            or any(not isinstance(ref, str) for ref in event['depends_on'])
            or len(set(event['depends_on'])) != len(event['depends_on'])
            or 'model_turn_number' in event and (not number(event['model_turn_number']) or event['model_turn_number'] < 1)
            or 'title' in event and (not text(event['title']) or len(event['title']) > 120)
            or any(not number(event[key]) for key in ('queued_at_ms', 'started_at_ms', 'finished_at_ms') if key in event)):
        raise ValueError('model request pool event is invalid')
    if event['kind'] == 'main':
        if event['chain_id'] != 'main' or {'child_id', 'parent_tool_call_id'} & set(event):
            raise ValueError('main model request identity is invalid')
    elif event['kind'] == 'analysis':
        native_policy = native.get('policy')
        if (not text(event.get('child_id')) or not text(event.get('parent_tool_call_id'))
                or event['chain_id'] != 'analysis:' + sha256(event['child_id'].encode()).hexdigest()
                or not registered_llm_call_pool(native.get('llm_call_pool'))
                or not registered_llm_call_pool(capability.get('llm_call_pool'))
                or not isinstance(native_policy, dict)
                or 'agent_llm_submit' not in native_policy.get('allowed_tools', ())
                or event['parent_tool_call_id'] not in record.get('llm_pool_submit_calls', ())):
            raise ValueError('analysis model request is not admitted')
    else:
        raise ValueError('model request kind is invalid')
    status = event['status']
    start, finish = event.get('started_at_ms'), event.get('finished_at_ms')
    if ((start is not None and start < event['queued_at_ms'])
            or finish is not None and finish < (start if start is not None else event['queued_at_ms'])
            or (status in _TERMINAL) != (finish is not None)
            or status in {'running', 'cancelling', 'completed'} and start is None
            or status in {'queued', 'waiting_dependencies', 'blocked'} and start is not None
            or 'cancel_reason' in event and event['cancel_reason'] not in {'timeout', 'cancelled', 'closed', 'parent_cancelled'}):
        raise ValueError('model request timing is invalid')
    bindings = record.get('model_request_pool_bindings', {})
    previous = bindings.get(event['request_id'])
    index = int(event['request_id'][8:])
    if any(ref not in bindings or int(ref[8:]) >= index for ref in event['depends_on']):
        raise ValueError('model request dependency is unknown')
    if previous is None:
        if (len(bindings) >= MODEL_REQUEST_POOL_POLICY['max_requests'] or index != len(bindings) + 1
                or status not in {'queued', 'waiting_dependencies'}):
            raise ValueError('model request was not queued')
        same_chain = [row for row in bindings.values() if row['chain_id'] == event['chain_id']]
        if same_chain and (same_chain[-1]['request_id'] not in event['depends_on']
                or same_chain[-1].get('parent_tool_call_id') != event.get('parent_tool_call_id')):
            raise ValueError('model request chain changed')
        prior_turns = [row['model_turn_number'] for row in same_chain if 'model_turn_number' in row]
        if prior_turns and 'model_turn_number' in event and event['model_turn_number'] < max(prior_turns):
            raise ValueError('model request turn moved backwards')
    else:
        if any(event.get(key) != previous.get(key) for key in
                ('request_id', 'chain_id', 'kind', 'depends_on', 'queued_at_ms', 'child_id', 'parent_tool_call_id', 'model_turn_number', 'title')):
            raise ValueError('model request identity changed')
        if previous['status'] in _TERMINAL:
            if event != previous:raise ValueError('model request terminal changed')
        elif status not in _TRANSITIONS[previous['status']]:
            raise ValueError('model request transition is invalid')
        if any(key in previous and event.get(key) != previous[key] for key in ('started_at_ms', 'cancel_reason')):
            raise ValueError('model request start or cancellation changed')
    if status == 'running' and any(bindings[ref]['status'] not in _TERMINAL for ref in event['depends_on']):
        raise ValueError('model request dependencies have not settled')
    active = sum(row['status'] in {'running', 'cancelling'} for key, row in bindings.items() if key != event['request_id'])
    if active + (status in {'running', 'cancelling'}) > MODEL_REQUEST_POOL_POLICY['concurrency']:
        raise ValueError('model request concurrency exceeded')
    checked = deepcopy(event)
    record.setdefault('model_request_pool_bindings', {})[event['request_id']] = checked
    return deepcopy(checked)
