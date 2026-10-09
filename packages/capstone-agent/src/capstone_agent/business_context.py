"""Public, immutable application context; no Authority handles or admission.

The content identity binds exactly the selected public projection. Source kinds
retain the distinction between historical Authority summaries and observations.
Neither kind authorizes a current-run professional claim.
"""

from dataclasses import dataclass, field
import hashlib
import json
import re

from .request_intent import IntentDecision, IntentRequest

SCHEMA = 'capstone-business-context/1'
MAX_CONTEXT_BYTES = 24 * 1024
MAX_OBJECTS = 16
MAX_MATERIALS = 8
MAX_MATERIAL_BYTES = 4 * 1024 * 1024
MAX_TOTAL_MATERIAL_BYTES = 16 * 1024 * 1024
_FIELDS = {'schema', 'workspace_id', 'snapshot_id', 'history_cutoff', 'selection',
           'object_refs', 'goals', 'constraints', 'materials', 'outcomes', 'coverage'}
_SOURCE_KINDS = {'workspace', 'user', 'historical_authority', 'external_observation', 'pi_observation'}


def _fields(value, fields):
    if type(value) is not dict or set(value) != set(fields):
        raise ValueError('business context fields are invalid')


def _text(value, *, limit=256):
    if type(value) is not str or not value.strip() or len(value.encode('utf-8')) > limit:
        raise ValueError('business context text exceeds bounds or is invalid')


def _integer(value, maximum=2**63 - 1):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError('business context integer exceeds bounds or is invalid')


def _items(value, limit=32):
    if type(value) is not list or len(value) > limit:
        raise ValueError('business context list exceeds bounds or is invalid')
    return value


def _refs(value, limit=128):
    refs = _items(value, limit)
    for ref in refs:
        _text(ref)
    if len(set(refs)) != len(refs):
        raise ValueError('duplicate business context reference')
    return set(refs)


def _hash(value):
    if type(value) is not str or not re.fullmatch(r'sha256:[0-9a-f]{64}', value):
        raise ValueError('business context content identity is invalid')


def _canonical(value):
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError, RecursionError, UnicodeError) as exc:
        raise ValueError('business context must contain finite JSON') from exc


def _digest(value):
    return 'sha256:' + hashlib.sha256(_canonical(value).encode('utf-8')).hexdigest()


def _with_snapshot(document):
    content = {k: v for k, v in document.items() if k != 'snapshot_id'}
    return {**content, 'snapshot_id': _digest(content)}


def _source(value, workspace_id, *, user=False):
    _fields(value, {'kind', 'workspace_id', 'message_refs'})
    if type(value['kind']) is not str or value['kind'] not in ({'user'} if user else _SOURCE_KINDS):
        raise ValueError('business context provenance kind is invalid')
    if value['workspace_id'] != workspace_id:
        raise ValueError('business context provenance workspace is invalid')
    refs = _refs(value['message_refs'], 32)
    if value['kind'] != 'workspace' and not refs:
        raise ValueError('business context source must have message provenance')


def _validate(document):
    _fields(document, _FIELDS)
    if document['schema'] != SCHEMA:
        raise ValueError('business context schema is invalid')
    _text(document['workspace_id'])
    _integer(document['history_cutoff'])
    _hash(document['snapshot_id'])
    selection = document['selection']
    _fields(selection, {'state', 'source'})
    if (type(selection['state']) is not str or selection['state'] not in {'none', 'selected', 'needs_clarification'}
            or type(selection['source']) is not str or selection['source'] not in {'semantic', 'explicit'}):
        raise ValueError('business context selection is invalid')
    identities = set()

    def identity(item, key):
        _text(item[key])
        if item[key] in identities:
            raise ValueError('duplicate business context identity')
        identities.add(item[key])

    workspace = document['workspace_id']
    for item in _items(document['object_refs'], MAX_OBJECTS):
        _fields(item, {'object_id', 'display_name', 'kind', 'version', 'relation', 'source'})
        identity(item, 'object_id')
        _text(item['display_name'])
        _text(item['kind'], limit=64)
        _hash(item['version'])
        if type(item['relation']) is not str or item['relation'] not in {'current', 'historical'}:
            raise ValueError('business object relation is invalid')
        _source(item['source'], workspace)
    for collection, key in (('goals', 'goal_id'), ('constraints', 'constraint_id')):
        for item in _items(document[collection]):
            _fields(item, {key, 'text', 'source'})
            identity(item, key)
            _text(item['text'], limit=8192)
            _source(item['source'], workspace, user=True)
    total_material_bytes = 0
    for item in _items(document['materials'], MAX_MATERIALS):
        _fields(item, {'material_id', 'kind', 'summary', 'content_hash', 'size_bytes',
                       'availability', 'purpose', 'source'})
        identity(item, 'material_id')
        _text(item['kind'], limit=64)
        _text(item['summary'], limit=4096)
        _hash(item['content_hash'])
        _integer(item['size_bytes'], MAX_MATERIAL_BYTES)
        total_material_bytes += item['size_bytes']
        if type(item['availability']) is not str or item['availability'] not in {'available', 'unavailable', 'revoked'}:
            raise ValueError('business material availability is invalid')
        _text(item['purpose'], limit=1024)
        _source(item['source'], workspace)
    if total_material_bytes > MAX_TOTAL_MATERIAL_BYTES:
        raise ValueError('business materials exceed aggregate byte bounds')
    for item in _items(document['outcomes']):
        _fields(item, {'outcome_id', 'kind', 'summary', 'object_refs', 'source'})
        identity(item, 'outcome_id')
        if type(item['kind']) is not str or item['kind'] not in {'historical_authority', 'external_observation', 'pi_observation'}:
            raise ValueError('business outcome kind is invalid')
        _text(item['summary'], limit=4096)
        seen_objects = set()
        for ref in _items(item['object_refs'], MAX_OBJECTS):
            _fields(ref, {'object_id', 'version'})
            _text(ref['object_id'])
            _hash(ref['version'])
            if ref['object_id'] in seen_objects:
                raise ValueError('duplicate outcome object reference')
            seen_objects.add(ref['object_id'])
        _source(item['source'], workspace)
        if item['source']['kind'] != item['kind']:
            raise ValueError('business outcome provenance does not match its kind')
    coverage = document['coverage']
    _fields(coverage, {'provided_refs', 'omitted_refs', 'truncated'})
    provided, omitted = _refs(coverage['provided_refs']), _refs(coverage['omitted_refs'])
    if provided != identities or provided & omitted or type(coverage['truncated']) is not bool:
        raise ValueError('business context coverage is invalid')
    if omitted and not coverage['truncated']:
        raise ValueError('omitted business context requires a truncation marker')
    if selection['state'] == 'none' and identities:
        raise ValueError('unselected business context must be empty')
    if _with_snapshot(document)['snapshot_id'] != document['snapshot_id']:
        raise ValueError('business context snapshot does not match its content')


@dataclass(frozen=True, slots=True, init=False)
class BusinessContext:
    _document_json: str = field(repr=False)

    def __init__(self, document: dict):
        serialized = _canonical(document)
        if len(serialized.encode('utf-8')) > MAX_CONTEXT_BYTES:
            raise ValueError('business context exceeds byte bounds')
        _validate(json.loads(serialized))
        object.__setattr__(self, '_document_json', serialized)

    @classmethod
    def from_document(cls, document: dict) -> 'BusinessContext':
        return cls(document)

    @classmethod
    def from_content(cls, document: dict) -> 'BusinessContext':
        """Build a host projection's content identity, then validate all fields.

        This is a content hash, not a signature or an authorization receipt.
        Received snapshots must use from_document so tampering is rejected.
        """
        _fields(document, _FIELDS - {'snapshot_id'})
        return cls(_with_snapshot(document))

    @classmethod
    def empty(cls, workspace_id: str, history_cutoff: int) -> 'BusinessContext':
        return cls.from_content({'schema': SCHEMA, 'workspace_id': workspace_id,
                            'history_cutoff': history_cutoff,
                            'selection': {'state': 'none', 'source': 'semantic'},
                            'object_refs': [], 'goals': [], 'constraints': [], 'materials': [], 'outcomes': [],
                            'coverage': {'provided_refs': [], 'omitted_refs': [], 'truncated': False}})

    def to_document(self) -> dict:
        return json.loads(self._document_json)


def business_context_for(request: IntentRequest, decision: IntentDecision, *,
                         goal_id: str | None = None, current_object_id: str | None = None) -> BusinessContext:
    """Select exact goal references; intent diagnostics never become instructions.

    Existing IntentRequest producers list the active object first. Callers with
    another index order can provide its active public identity explicitly.
    """
    if not isinstance(request, IntentRequest) or not isinstance(decision, IntentDecision):
        raise ValueError('business projection requires validated intent contracts')
    source = request.to_document()
    selected = IntentDecision.from_document(decision.to_document(), request).to_document()
    goals = selected['goals']
    if goal_id is not None:
        goals = [goal for goal in goals if goal['goal_id'] == goal_id]
        if not goals:
            raise ValueError('unknown business projection goal')
    objects = {item['object_id']: item for item in source['objects']}
    if current_object_id is not None and current_object_id not in objects:
        raise ValueError('unknown current business object')
    if current_object_id is None and source['objects']:
        current_object_id = source['objects'][0]['object_id']
    refs = list(dict.fromkeys(ref for goal in goals for ref in goal['object_refs']))
    document = BusinessContext.empty(source['thread_id'], source['history_cutoff']).to_document()
    for ref in refs:
        item = objects[ref]
        if not item.get('model_revision'):
            raise ValueError('selected business object has no version')
        document['object_refs'].append({
            'object_id': ref, 'display_name': item.get('display_name', item.get('model_id', ref)),
            'kind': 'model', 'version': _digest({'workspace_id': source['thread_id'],
                                               'object_id': ref, 'revision': item['model_revision']}),
            'relation': 'current' if ref == current_object_id else 'historical',
            'source': {'kind': 'workspace', 'workspace_id': source['thread_id'],
                       'message_refs': [message['message_id'] for message in source['messages']
                                        if message['model_context_id'] == ref]}})
    state = 'needs_clarification' if decision.needs_clarification else ('selected' if refs else 'none')
    document['selection']['state'] = state
    document['coverage']['provided_refs'] = refs
    return BusinessContext.from_document(_with_snapshot(document))
