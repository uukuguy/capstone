"""Application-owned Mission tool publication and bounded native transport.

The native host only transports requests. The leased application worker calls
Control, which owns all Mission state and registered resource admission.
"""
from copy import deepcopy
import json
import re
from datetime import datetime,timedelta
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
    kind={'enum': ['capability', 'resource_profile']}, id=IDENTITY,
    revision=dict(type='string', minLength=1, maxLength=256)))
TASK = obj(dict(task_id=IDENTITY, objective=TEXT,
    delivery_requirements=dict(type='array', items=TEXT, minItems=1, maxItems=64),
    depends_on=dict(type='array', items=IDENTITY, uniqueItems=True, maxItems=64),
    agent_id=IDENTITY, mode={'enum':['single', 'goal']}, max_attempts=dict(type='integer', minimum=1),
    required_products=dict(type='array', items=dict(type='string', minLength=1, maxLength=255), uniqueItems=True, maxItems=64),
    equipment=dict(type='array', items=REF, maxItems=64), restrictions=dict(type='array', items=REF, maxItems=64)),
    ['task_id', 'objective', 'delivery_requirements', 'depends_on', 'agent_id', 'mode', 'max_attempts'])
REVISION = dict(type='integer', minimum=1,
    description='Exact Mission.revision from the latest returned Mission object (read or command receipt). Never use Mission.plan_revision as expected_revision.')
PLAN_REVISION = dict(type='integer', minimum=1,
    description='Exact Mission.plan_revision of the inspected plan being concluded. This is separate from Mission.revision used for expected_revision.')
PRODUCT_EVIDENCE = obj(dict(kind={'const':'product'},task_id=IDENTITY,
    artifact_id=dict(type='string',minLength=1,maxLength=256),sha256=dict(type='string',pattern='^[a-f0-9]{64}$')))
ANSWER_EVIDENCE = obj(dict(kind={'const':'answer'},task_id=IDENTITY,answer_ref=IDENTITY))
CRITERION_VERDICT = {**obj(dict(criterion_index=dict(type='integer',minimum=0),
    status={'enum':['met','not_met','unknown']},explanation=TEXT,
    evidence=dict(type='array',items={'oneOf':[PRODUCT_EVIDENCE,ANSWER_EVIDENCE]},maxItems=64))),
    'allOf':[{'if':{'properties':{'status':{'const':'met'}}},'then':{'properties':{'evidence':{'minItems':1}}}}]}
CATALOG = {
    'agent_mission_read': dict(description='Read the Mission associated with this conversation and its currently registered equipment references and agents. Use their exact identities and revisions; availability does not require initialization or selection. Planning is not execution or acceptance.', inputSchema=obj({})),
    'agent_mission_update_plan': dict(description='Incrementally prepare the associated Mission plan from the user intent. Preserve unrelated Tasks; planning does not dispatch work.',
        inputSchema=obj(dict(expected_revision=REVISION, acceptance_criteria=dict(type='array', items=TEXT, maxItems=64),
                             tasks=dict(type='array', items=TASK, maxItems=64),
                             removed_task_ids=dict(type='array',items=IDENTITY,maxItems=64,uniqueItems=True)),
                        ['expected_revision','acceptance_criteria','tasks'])),
    'agent_mission_prepare_task': dict(description='Add or update one pending executable Task with task-relevant registered capability or resource_profile equipment from the current Mission publication. Skill/resource equipment adapters are not published. Use depends_on to carry authorized saved products from verified predecessor Tasks; resource_id is an input reference, not equipment. Select a relevant subset when useful and briefly explain the choice in conversation; empty references retain application defaults for simple tasks. For frozen authorized inputs, the application preserves required bounded read-only resource interfaces within source grants and explicit denies; do not guess these helpers as business equipment. Exact denied tool names do not imply filesystem isolation: bash can still write when admitted. Active Tasks cannot be rewritten; request pause and confirm the actual stop before replanning.',
        inputSchema=obj(dict(expected_revision=REVISION, task=TASK))),
    'agent_mission_ready': dict(description='Make an executable Mission plan ready only when Tasks, acceptance criteria and equipment are admitted. Then finish this organizer turn: a real Task boundary resumes organization automatically. Do not loop over state reads while waiting. If no dependency-ready Task remains, inspect actual results and conclude or wait. This is not product acceptance.',
        inputSchema=obj(dict(expected_revision=REVISION))),
    'agent_mission_control': dict(description='Request pause, resume or cancellation of the associated Mission. A request does not confirm a running Task has stopped. Read actual state before replanning; organizer text never broadcasts to Tasks.',
        inputSchema=obj(dict(expected_revision=REVISION, action={'enum':['pause','resume','cancel']}))),
    'agent_mission_conclude': dict(description='Assess every current acceptance criterion once against actual saved results. Include exact verified product artifact/hash or saved answer references for every met verdict; report not_met or unknown honestly. Requires current plan revision and no active execution; all-met delivery additionally requires all Tasks verified. Any not_met/unknown records partial findings and waits for user direction. Delivery remains subject to user acceptance.',
        inputSchema=obj(dict(expected_revision=REVISION,plan_revision=PLAN_REVISION,summary=dict(type='string',minLength=1,maxLength=4096),
            criteria_verdicts=dict(type='array',items=CRITERION_VERDICT,minItems=1,maxItems=64)))),
    'agent_mission_wait': dict(description='Record a deliberate wait for an admitted Task boundary or for user input, then finish this organizer turn. Actual Task boundary events resume organization; do not poll state in a read loop. Waiting never concludes the plan; user waits suspend automatic organizer continuation.',
        inputSchema=obj(dict(expected_revision=REVISION,until={'enum':['task_boundary','user']},reason=dict(type='string',minLength=1,maxLength=4096)))),
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


def checked_review(value):
    fields={'schema','workspace','mission_id','review_id','origin','objective','deadline_at','boundary','revision'}
    if (not isinstance(value,dict) or set(value)!=fields or value['schema']!='capstone-mission-review-intent/1'
            or not isinstance(value['workspace'],str) or not 1<=len(value['workspace'])<=128
            or not isinstance(value['objective'],str) or not 1<=len(value['objective'])<=16384
            or type(value['revision']) is not int or value['revision']<1):
        raise ValueError('invalid admitted Mission review')
    try:
        if not isinstance(value['deadline_at'],str) or len(value['deadline_at'])>64 or datetime.fromisoformat(value['deadline_at'].replace('Z','+00:00')).utcoffset()!=timedelta(0):
            raise ValueError('invalid Mission review UTC deadline')
    except (TypeError,ValueError):
        raise ValueError('invalid Mission review UTC deadline') from None
    checked_binding(dict(schema=SCHEMA,mission_id=value['mission_id'],origin=value['origin']))
    if not isinstance(value['review_id'],str) or re.fullmatch(IDENTITY['pattern'],value['review_id']) is None:
        raise ValueError('invalid Mission review identity')
    source=value['boundary']
    if (not isinstance(source,dict) or set(source)!={'digest','plan_revision','tasks'}
            or not isinstance(source['digest'],str) or re.fullmatch(r'[0-9a-f]{64}',source['digest']) is None
            or type(source['plan_revision']) is not int or source['plan_revision']<1
            or not isinstance(source['tasks'],list) or not 1<=len(source['tasks'])<=64):
        raise ValueError('invalid Mission review boundary')
    if any(not isinstance(task,dict) for task in source['tasks']):
        raise ValueError('invalid Mission review Task projection')
    original={key:source[key] for key in ('plan_revision','tasks')}
    if sha256(json.dumps(original,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()!=source['digest']:
        raise ValueError('Mission review boundary digest changed')
    require_capacity('native_context_bytes',len(json.dumps(value).encode()),'mission_review_context')
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


def resource_protocol_tools(current,resource_manifests):
    """Preserve registered readers of already frozen sources, never native file tools."""
    if not resource_manifests:
        return set()
    return set(current).intersection({'agent_resource_open','agent_resource_read'})


def equipment_tools(current, selection, *, require_selected=True, protocol_tools=()):
    checked_equipment(selection)
    available = set(current)
    protocol = set(protocol_tools).intersection(available)
    selected = selection['allowed_tools']
    if selected is not None:
        if require_selected and not set(selected) <= available:
            raise ValueError('Mission equipment exceeds current admitted tools')
        available.intersection_update(selected)
    available.update(protocol)
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
