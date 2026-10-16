"""Public semantic context selection without professional routing or authority."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import TYPE_CHECKING, Protocol
from collections.abc import Callable

from .business_context import BusinessContext
from .request_intent import (IntentEngineIdentity, IntentRequest, NodeControl,
                             _canonical, _fields, _integer, _items, _text)

REQUEST_SCHEMA = 'capstone-context-selection-request/1'
DECISION_SCHEMA = 'capstone-context-selection-decision/1'

if TYPE_CHECKING:
    from .harness import PiPromptSession


@dataclass(frozen=True, slots=True, init=False)
class ContextSelectionRequest:
    _document_json: str = field(repr=False)

    def __init__(self, document: dict):
        serialized = _canonical(document, 262144)
        source = _fields(json.loads(serialized), {'schema', 'workspace_id', 'turn_id',
            'attempt_id', 'instruction_message_id', 'instruction', 'history_cutoff',
            'history_truncated', 'current_object_id', 'messages', 'objects'}, {'context_selection'})
        if source['schema'] != REQUEST_SCHEMA:
            raise ValueError('context selection request schema is invalid')
        # Reuse the exact existing history/identity bounds. No professional catalog
        # or private model metadata is retained in this public request.
        IntentRequest.from_document({'schema': 'capstone-intent-request/1',
            'thread_id': source['workspace_id'], **{key: source[key] for key in
            ('turn_id', 'attempt_id', 'instruction_message_id', 'instruction',
             'history_cutoff', 'history_truncated', 'messages')},
            'objects': [], 'capabilities': [], 'mode_hint': None})
        ids = set()
        known_messages = {message['message_id'] for message in source['messages']}
        for item in _items(source['objects'], 'context objects'):
            _fields(item, {'object_id', 'display_name', 'kind', 'version', 'relation', 'source'})
            _text(item['object_id'], 'object_id', limit=256)
            if item['object_id'] in ids:
                raise ValueError('duplicate context object reference')
            ids.add(item['object_id'])
            context = BusinessContext.empty(source['workspace_id'], source['history_cutoff']).to_document()
            context.pop('snapshot_id')
            context.update(selection={'state': 'selected', 'source': 'semantic'},
                object_refs=[{**item, 'version': item['version'] or 'sha256:' + '0' * 64}],
                coverage={'provided_refs': [item['object_id']], 'omitted_refs': [], 'truncated': False})
            if item['version'] is not None and not isinstance(item['version'], str):
                raise ValueError('context object version is invalid')
            if item['version'] == '':
                raise ValueError('context object version is invalid')
            BusinessContext.from_content(context)
            if any(ref not in known_messages
                   for ref in item['source']['message_refs']):
                raise ValueError('context object source has an unknown message reference')
        _text(source['current_object_id'], 'current_object_id', limit=256)
        if source['current_object_id'] not in ids:
            raise ValueError('current context object reference is invalid')
        if any(item['relation'] != ('current' if item['object_id'] == source['current_object_id'] else 'historical')
               for item in source['objects']):
            raise ValueError('context object relation is invalid')
        if 'context_selection' in source:
            from .thread_input import context_selection
            context_selection(source['context_selection'], ids)
        object.__setattr__(self, '_document_json', serialized)

    @classmethod
    def from_document(cls, document: dict) -> ContextSelectionRequest:
        return cls(document)

    @property
    def request_id(self) -> str:
        return self.to_document()['attempt_id']

    def to_document(self) -> dict:
        return json.loads(self._document_json)


@dataclass(frozen=True, slots=True, init=False)
class ContextSelectionDecision:
    _document_json: str = field(repr=False)

    def __init__(self, document: dict, request: ContextSelectionRequest):
        serialized = _canonical(document, 32768)
        value = _fields(json.loads(serialized), {'schema', 'attempt_id', 'history_cutoff',
            'object_refs', 'message_refs', 'clarification_required', 'clarification'})
        source = request.to_document()
        from .thread_input import validate_context_decision, selected_context_refs
        validate_context_decision(source, value['object_refs'])
        if not value['clarification_required'] and not set(selected_context_refs(source, [])) <= set(value['object_refs']):
            raise ValueError('explicitly included context must be selected or clarified')
        if (value['schema'] != DECISION_SCHEMA or value['attempt_id'] != source['attempt_id']
            or value['history_cutoff'] != source['history_cutoff']):
            raise ValueError('context selection decision is not bound to its request')
        _integer(value['history_cutoff'], 'history_cutoff')
        known_messages = {m['message_id'] for m in source['messages']} | {source['instruction_message_id']}
        objects = {item['object_id']: item for item in source['objects']}
        for key, known, limit in (('object_refs', set(objects), 16), ('message_refs', known_messages, 32)):
            refs = _items(value[key], key, limit=limit)
            for ref in refs:
                _text(ref, key, limit=256)
            if len(set(refs)) != len(refs) or not set(refs) <= known:
                raise ValueError('unknown or duplicate context selection reference')
        if type(value['clarification_required']) is not bool:
            raise ValueError('context clarification_required must be a boolean')
        _text(value['clarification'], 'clarification', limit=8192, nullable=True)
        if value['clarification_required'] and value['clarification'] is None:
            raise ValueError('context selection clarification question is required')
        if not value['clarification_required'] and any(objects[ref]['version'] is None for ref in value['object_refs']):
            raise ValueError('selected context object version is unavailable; clarification is required')
        object.__setattr__(self, '_document_json', serialized)

    @classmethod
    def from_document(cls, document: dict, request: ContextSelectionRequest) -> ContextSelectionDecision:
        return cls(document, request)

    def to_document(self) -> dict:
        return json.loads(self._document_json)


def selected_business_context(request: ContextSelectionRequest, decision: ContextSelectionDecision) -> BusinessContext:
    source = request.to_document()
    selected = ContextSelectionDecision.from_document(decision.to_document(), request).to_document()
    context = BusinessContext.empty(source['workspace_id'], source['history_cutoff']).to_document()
    context.pop('snapshot_id')
    context['object_refs'] = [item for item in source['objects']
        if item['object_id'] in selected['object_refs'] and item['version'] is not None]
    context['selection']['state'] = ('needs_clarification' if selected['clarification_required']
        else 'selected' if context['object_refs'] else 'none')
    omitted = [ref for ref in selected['object_refs'] if not any(item['object_id'] == ref for item in context['object_refs'])]
    context['coverage'] = {'provided_refs': [item['object_id'] for item in context['object_refs']],
        'omitted_refs': omitted, 'truncated': bool(omitted)}
    return BusinessContext.from_content(context)


class ContextSelector(Protocol):
    identity: IntentEngineIdentity

    def select(self, request: ContextSelectionRequest, control: NodeControl) -> ContextSelectionDecision: ...


class PiContextSelector:
    """Accept exactly one structured native tool result, under the node deadline."""
    def __init__(self, prepared_session_factory: Callable[[ContextSelectionRequest, NodeControl], PiPromptSession],
                 identity: IntentEngineIdentity):
        if not callable(prepared_session_factory) or not isinstance(identity, IntentEngineIdentity):
            raise TypeError('context selector requires a session factory and engine identity')
        self._factory, self.identity = prepared_session_factory, identity

    def select(self, request: ContextSelectionRequest, control: NodeControl) -> ContextSelectionDecision:
        control.checkpoint()
        session = self._factory(request, control)
        decisions = []

        def observe(event):
            control.checkpoint()
            if event.get('type') != 'tool_result':
                return
            if event.get('capability') != 'capstone.context.selection' or event.get('ok') is not True:
                raise ValueError('context selection returned an unexpected tool result')
            if decisions:
                raise ValueError('Pi must return exactly one context selection decision')
            decisions.append(ContextSelectionDecision.from_document(event.get('result'), request))

        try:
            control.checkpoint()
            session.start()
            control.checkpoint()
            session.prompt_and_wait(json.dumps(request.to_document(), ensure_ascii=False, separators=(',', ':')),
                on_semantic_event=observe, correlation_id=request.request_id, on_heartbeat=control.checkpoint)
            control.checkpoint()
            if len(decisions) != 1:
                raise ValueError('Pi must return exactly one context selection decision')
            return decisions[0]
        finally:
            session.stop()
