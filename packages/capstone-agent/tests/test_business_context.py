from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import importlib
import json

import pytest

from capstone_agent.request_intent import IntentDecision, IntentRequest


def context_api():
    try:
        return importlib.import_module('capstone_agent.business_context')
    except ModuleNotFoundError:
        pytest.fail('The public business context contract is not implemented')


def intent(refs=(), *, goal_id='g1', clarification=None):
    request = IntentRequest.from_document({
        'schema': 'capstone-intent-request/1', 'thread_id': 'thread1',
        'turn_id': 'turn2', 'attempt_id': 'attempt2', 'instruction': 'Explain the selected model.',
        'instruction_message_id': 'attempt2:user', 'history_cutoff': 12,
        'messages': [{'message_id': 'message1', 'role': 'user', 'content': 'Open the old model.',
                      'turn_id': 'turn1', 'attempt_id': 'attempt1', 'model_context_id': 'old',
                      'status': 'completed', 'event_seq': 10}],
        'objects': [{'object_id': 'current', 'model_id': 'ieee39', 'model_revision': 'private-revision-current',
                     'implementation_family': 'pandapower'},
                    {'object_id': 'old', 'model_id': 'ieee14', 'model_revision': 'private-revision-old',
                     'implementation_family': 'pandapower'}],
        'capabilities': [{'capability_id': 'grid-read', 'available': True, 'enabled': True}],
        'mode_hint': None})
    decision = IntentDecision.from_document({
        'schema': 'capstone-intent-decision/1', 'attempt_id': 'attempt2', 'history_cutoff': 12,
        'relationship': 'independent', 'clarification': clarification,
        'goals': [{'goal_id': goal_id, 'description': 'Diagnostic model prose must not become instructions.',
                   'operation': 'business_read', 'message_refs': ['attempt2:user'],
                   'object_refs': list(refs), 'capability_refs': ['grid-read'], 'missing_requirements': []}]}, request)
    return request, decision


def signed(document):
    document = deepcopy(document)
    document.pop('snapshot_id', None)
    digest = hashlib.sha256(json.dumps(document, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    return {**document, 'snapshot_id': 'sha256:' + digest}


def populated_document():
    api = context_api()
    request, decision = intent(['current'])
    doc = api.business_context_for(request, decision).to_document()
    source = {'kind': 'user', 'workspace_id': 'thread1', 'message_refs': ['attempt2:user']}
    doc['goals'] = [{'goal_id': 'goal1', 'text': 'Explain the model', 'source': source}]
    doc['constraints'] = [{'constraint_id': 'constraint1', 'text': 'Use public data', 'source': source}]
    doc['materials'] = [{'material_id': 'material1', 'kind': 'text', 'summary': 'Model description',
                         'content_hash': 'sha256:' + 'a' * 64, 'size_bytes': 1024,
                         'availability': 'available', 'purpose': 'reference', 'source': source}]
    doc['outcomes'] = [{'outcome_id': 'outcome1', 'kind': 'historical_authority', 'summary': 'Prior report',
                        'object_refs': [{'object_id': 'current', 'version': doc['object_refs'][0]['version']}],
                        'source': {'kind': 'historical_authority', 'workspace_id': 'thread1',
                                   'message_refs': ['message1']}}]
    doc['coverage']['provided_refs'] += ['goal1', 'constraint1', 'material1', 'outcome1']
    return signed(doc)


def test_empty_projection_does_not_infer_business_context_from_capabilities_or_text():
    api = context_api()
    request, decision = intent()
    doc = api.business_context_for(request, decision).to_document()
    assert doc == api.BusinessContext.empty('thread1', 12).to_document()
    assert doc['selection'] == {'state': 'none', 'source': 'semantic'}
    for field in ('object_refs', 'goals', 'constraints', 'materials', 'outcomes'):
        assert doc[field] == []


@pytest.mark.parametrize('object_id,name,relation', [('current', 'ieee39', 'current'), ('old', 'ieee14', 'historical')])
def test_selected_objects_have_public_identity_version_and_provenance(object_id, name, relation):
    api = context_api()
    request, decision = intent([object_id])
    doc = api.business_context_for(request, decision, goal_id='g1').to_document()
    obj = doc['object_refs'][0]
    assert obj['object_id'] == object_id
    assert obj['display_name'] == name
    assert obj['kind'] == 'model'
    assert obj['relation'] == relation
    assert obj['version'].startswith('sha256:')
    assert obj['source']['workspace_id'] == 'thread1'
    assert 'private-revision' not in repr(doc)
    assert 'enabled_profiles' not in repr(doc)
    assert 'Diagnostic' not in repr(doc)
    assert doc['selection']['state'] == 'selected'
    assert signed(doc) == doc


def test_projection_is_per_goal_and_rejects_unbound_decisions():
    api = context_api()
    request, decision = intent(['old'])
    doc = decision.to_document()
    doc['goals'].append({**doc['goals'][0], 'goal_id': 'g2', 'object_refs': [], 'operation': 'external_lookup'})
    mixed = IntentDecision.from_document(doc, request)
    assert api.business_context_for(request, mixed, goal_id='g2').to_document()['object_refs'] == []
    with pytest.raises(ValueError):
        api.business_context_for(request, mixed, goal_id='unknown')
    changed = request.to_document()
    changed['objects'] = changed['objects'][:1]
    with pytest.raises(ValueError):
        api.business_context_for(IntentRequest.from_document(changed), decision)


def test_clarification_keeps_selected_background_without_instruction_prose():
    api = context_api()
    request, decision = intent(['old'], clarification='Which object?')
    doc = api.business_context_for(request, decision).to_document()
    assert doc['selection']['state'] == 'needs_clarification'
    assert doc['object_refs'][0]['object_id'] == 'old'
    assert 'Which object?' not in repr(doc)


def test_context_exports_are_deep_copies_and_snapshot_is_verified():
    api = context_api()
    document = populated_document()
    original = deepcopy(document)
    context = api.BusinessContext.from_document(document)
    document['materials'][0]['source']['message_refs'].clear()
    context.to_document()['outcomes'][0]['object_refs'].clear()
    assert context.to_document() == original
    with pytest.raises((FrozenInstanceError, AttributeError)):
        context._document_json = '{}'
    altered = deepcopy(original)
    altered['materials'][0]['summary'] = 'changed'
    with pytest.raises(ValueError, match='snapshot'):
        api.BusinessContext.from_document(altered)


def test_from_content_creates_and_validates_the_content_identity():
    api = context_api()
    original = populated_document()
    content = {k: v for k, v in deepcopy(original).items() if k != 'snapshot_id'}
    context = api.BusinessContext.from_content(content)
    assert context.to_document() == original
    content['materials'].clear()
    assert context.to_document() == original
    with pytest.raises(ValueError):
        api.BusinessContext.from_content(original)
    content = {k: v for k, v in deepcopy(original).items() if k != 'snapshot_id'}
    content['materials'][0]['token'] = 'private'
    with pytest.raises(ValueError):
        api.BusinessContext.from_content(content)


@pytest.mark.parametrize('mutation', [
    lambda d: d.update(extra=True),
    lambda d: d.update(history_cutoff=True),
    lambda d: d['selection'].update(state='guessed'),
    lambda d: d['selection'].update(source='keyword'),
    lambda d: d['object_refs'][0].update(version='private-revision'),
    lambda d: d['object_refs'][0].update(model_revision='private'),
    lambda d: d['object_refs'][0]['source'].update(workspace_id='other'),
    lambda d: d['object_refs'][0]['source'].update(endpoint='http://internal'),
    lambda d: d['materials'][0].update(size_bytes=float('inf')),
    lambda d: d['materials'][0].update(size_bytes=4 * 1024 * 1024 + 1),
    lambda d: d['materials'][0].update(content_hash='unknown'),
    lambda d: d['materials'][0].update(path='/private/model'),
    lambda d: d['materials'][0].update(availability='guessed'),
    lambda d: d['outcomes'][0].update(evidence_refs=['forged']),
    lambda d: d['outcomes'][0]['object_refs'][0].update(version='invalid'),
    lambda d: d['goals'][0]['source'].update(kind='model_guess'),
    lambda d: d['goals'][0]['source'].update(message_refs=[]),
    lambda d: d['outcomes'][0]['source'].update(message_refs=[]),
    lambda d: d['constraints'][0].update(text='界' * 8193),
    lambda d: d['coverage'].update(truncated='yes'),
    lambda d: d['coverage'].update(provided_refs=['unknown']),
])
def test_context_rejects_invalid_or_protected_fields(mutation):
    api = context_api()
    document = populated_document()
    mutation(document)
    # Nonfinite input must fail even before it can acquire a content identity.
    try:
        document = signed(document)
    except ValueError:
        pass
    with pytest.raises(ValueError):
        api.BusinessContext.from_document(document)


def test_required_projection_is_not_silently_truncated():
    api = context_api()
    request, decision = intent(['current'])
    doc = request.to_document()
    doc['objects'] = [dict(doc['objects'][0], object_id=f'o{i}') for i in range(17)]
    request = IntentRequest.from_document(doc)
    selection = decision.to_document()
    selection['goals'][0]['object_refs'] = [o['object_id'] for o in doc['objects']]
    decision = IntentDecision.from_document(selection, request)
    with pytest.raises(ValueError, match='bounds|limit'):
        api.business_context_for(request, decision)


def test_explicit_current_identity_overrides_object_order_and_missing_revision_fails():
    api = context_api()
    request, decision = intent(['old'])
    doc = api.business_context_for(request, decision, current_object_id='old').to_document()
    assert doc['object_refs'][0]['relation'] == 'current'
    with pytest.raises(ValueError):
        api.business_context_for(request, decision, current_object_id='unknown')
    source = request.to_document()
    source['objects'][1].pop('model_revision')
    with pytest.raises(ValueError):
        api.business_context_for(IntentRequest.from_document(source), decision)


def test_material_count_and_aggregate_bounds():
    api = context_api()
    doc = populated_document()
    for count, size in [(9, 1), (5, 4 * 1024 * 1024)]:
        candidate = deepcopy(doc)
        candidate['materials'] = [dict(doc['materials'][0], material_id=f'm{i}', size_bytes=size)
                                  for i in range(count)]
        candidate['coverage']['provided_refs'] = ['current', 'goal1', 'constraint1', 'outcome1'] + [f'm{i}' for i in range(count)]
        with pytest.raises(ValueError):
            api.BusinessContext.from_document(signed(candidate))


def test_complete_context_text_budget_is_bounded():
    api = context_api()
    doc = populated_document()
    doc['goals'] = [dict(doc['goals'][0], goal_id=f'g{i}', text='x' * 8192) for i in range(4)]
    doc['coverage']['provided_refs'] = ['current', 'constraint1', 'material1', 'outcome1'] + [f'g{i}' for i in range(4)]
    with pytest.raises(ValueError, match='byte bounds'):
        api.BusinessContext.from_document(signed(doc))
