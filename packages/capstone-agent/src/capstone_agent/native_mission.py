"""Application-owned Mission tool publication and bounded native transport.

The native host only transports requests. The leased application worker calls
Control, which owns all Mission state and registered resource admission.
"""
from copy import deepcopy
import json
import re
from hashlib import sha256
from threading import RLock

from jsonschema import Draft202012Validator

from .application_capacity import limits, require_capacity

SCHEMA = 'capstone-native-mission/1'


def registry_revision(binding):
    capability = deepcopy(binding.get('capability', {}))
    gateway = capability.get('data_gateway')
    if isinstance(gateway, dict):
        gateway.pop('session_binding', None)
        if not gateway:
            capability.pop('data_gateway')
    return sha256(json.dumps({'identity': binding.get('identity'), 'capability': capability},
        sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def obj(properties, required=None):
    return dict(type='object', properties=properties, additionalProperties=False,
                required=list(properties) if required is None else required)


IDENTITY = dict(type='string', pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$')
TEXT = dict(type='string', minLength=1, maxLength=16384)
REF = obj(dict(schema={'const': 'capstone-mission-equipment-reference/1'},
    kind={'enum': ['capability', 'resource_profile', 'skill', 'resource']}, id=IDENTITY,
    revision=dict(type='string', minLength=1, maxLength=256)))
TASK = obj(dict(task_id=IDENTITY, objective=TEXT,
    delivery_requirements=dict(type='array', items=TEXT, minItems=1, maxItems=64),
    depends_on=dict(type='array', items=IDENTITY, uniqueItems=True, maxItems=64),
    agent_id=IDENTITY, mode={'enum':['single', 'goal']}, max_attempts=dict(type='integer', minimum=1),
    required_products=dict(type='array', items=dict(type='string', minLength=1, maxLength=255), uniqueItems=True, maxItems=64),
    equipment=dict(type='array', items=REF, maxItems=64), restrictions=dict(type='array', items=REF, maxItems=64)),
    ['task_id', 'objective', 'delivery_requirements', 'depends_on', 'agent_id', 'mode', 'max_attempts'])
REVISION = dict(type='integer', minimum=1)
CATALOG = {
    'agent_mission_read': dict(description='Read the Mission associated with this conversation. Planning is not execution or acceptance.', inputSchema=obj({})),
    'agent_mission_update_plan': dict(description='Incrementally prepare the associated Mission plan from the user intent. Preserve unrelated Tasks; planning does not dispatch work.',
        inputSchema=obj(dict(expected_revision=REVISION, acceptance_criteria=dict(type='array', items=TEXT, maxItems=64),
                             tasks=dict(type='array', items=TASK, maxItems=64)))),
    'agent_mission_prepare_task': dict(description='Add or update one pending executable Task with registered equipment references. Active Tasks cannot be rewritten.',
        inputSchema=obj(dict(expected_revision=REVISION, task=TASK))),
    'agent_mission_ready': dict(description='Make the current Mission plan ready only when Tasks, acceptance criteria and equipment are admitted. This is not product acceptance.',
        inputSchema=obj(dict(expected_revision=REVISION))),
    'agent_mission_control': dict(description='Request pause, resume or cancellation of the associated Mission. A request does not confirm a running Task has stopped. Read actual state before replanning; organizer text never broadcasts to Tasks.',
        inputSchema=obj(dict(expected_revision=REVISION, action={'enum':['pause','resume','cancel']}))),
}


def checked_binding(value):
    if (not isinstance(value, dict) or set(value) != {'schema', 'mission_id', 'origin'} or value.get('schema') != SCHEMA
            or not isinstance(value['mission_id'], str) or re.fullmatch(IDENTITY['pattern'], value['mission_id']) is None):
        raise ValueError('invalid native Mission binding')
    origin = value['origin']
    if (not isinstance(origin, dict) or 'thread_id' not in origin or set(origin) - {'thread_id', 'work_id'}
            or any(not isinstance(item, str) or re.fullmatch(IDENTITY['pattern'], item) is None for item in origin.values())):
        raise ValueError('invalid native Mission origin')
    return deepcopy(value)


def checked_equipment(value):
    if (not isinstance(value, dict) or set(value) != {'schema', 'allowed_tools', 'denied_tools'}
            or value.get('schema') != 'capstone-mission-tool-selection/1'):
        raise ValueError('invalid Mission tool selection')
    for field in ('allowed_tools', 'denied_tools'):
        items = value[field]
        if field == 'allowed_tools' and items is None:
            continue
        if (not isinstance(items, list) or len(items) > 256
                or any(not isinstance(item, str) or not item or len(item) > 256 for item in items)
                or len(set(items)) != len(items)):
            raise ValueError('invalid Mission selected tools')
    return deepcopy(value)


def equipment_tools(current, selection, *, require_selected=True):
    checked_equipment(selection)
    available = set(current)
    selected = selection['allowed_tools']
    if selected is not None:
        if require_selected and not set(selected) <= available:
            raise ValueError('Mission equipment exceeds current admitted tools')
        available.intersection_update(selected)
    available.difference_update(selection['denied_tools'])
    if not available:
        raise ValueError('Mission equipment leaves no executable tool')
    return available


class MissionTaskChannel:
    """No execution authority: only immutable pending calls and bound receipts."""
    def __init__(self):
        self._lock = RLock()
        self._calls = {}

    def request(self, document):
        if (not isinstance(document, dict) or set(document) != {'call_id', 'name', 'arguments'}
                or not isinstance(document['call_id'], str)
                or not 1 <= len(document['call_id']) <= 256 or any(ord(char) < 32 for char in document['call_id'])
                or not isinstance(document.get('name'), str) or document['name'] not in CATALOG):
            raise ValueError('invalid Mission tool request')
        Draft202012Validator(CATALOG[document['name']]['inputSchema']).validate(document['arguments'])
        require_capacity('control_document_bytes', len(json.dumps(document).encode()), 'mission_tool_request')
        with self._lock:
            old = self._calls.get(document['call_id'])
            if old is not None:
                if old['request'] != document:
                    raise ValueError('Mission tool call identity conflict')
                return deepcopy(old.get('receipt'))
            require_capacity('rpc_batch_requests', len(self._calls) + 1, 'mission_tool_calls')
            self._calls[document['call_id']] = {'request': deepcopy(document)}
            return None

    def pending(self):
        with self._lock:
            return [deepcopy(value['request']) for value in self._calls.values() if 'receipt' not in value]

    def acknowledge(self, receipts):
        if not isinstance(receipts, list) or len(receipts) > limits.rpc_batch_requests:
            raise ValueError('invalid Mission tool receipts')
        with self._lock:
            for receipt in receipts:
                if (not isinstance(receipt, dict) or set(receipt) != {'call_id', 'result', 'is_error'}
                        or type(receipt['is_error']) is not bool or not isinstance(receipt['result'], dict)):
                    raise ValueError('invalid Mission tool receipt')
                require_capacity('control_document_bytes', len(json.dumps(receipt).encode()), 'mission_tool_receipt')
                old = self._calls[receipt['call_id']]
                if 'receipt' in old and old['receipt'] != receipt:
                    raise ValueError('Mission tool receipt identity conflict')
            for receipt in receipts:
                self._calls[receipt['call_id']]['receipt'] = deepcopy(receipt)
