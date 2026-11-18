"""Management record carried by the main reasoning chain.

Domain tools keep grid calculation data. Gateway tools keep their own refs
and payloads. This record names the open model and the opaque handles a later
turn needs to organize the work.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from hashlib import sha256


_TOKEN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$')
_MODEL_FIELDS = (
    'model_context_id', 'model_id', 'model_revision', 'implementation_family',
    'selection_revision', 'enabled_profiles',
)

AUTHORITY_REFERENCE_SOURCE = 'domain_authority_references'


def checked_authority_references(value: object) -> dict:
    if not isinstance(value, Mapping) or set(value) != {
        'authority_id', 'capability_id', 'result_refs', 'evidence_refs',
    }:
        raise ValueError('authority references are invalid')
    receipt: dict = {key: _token(value[key]) for key in ('authority_id', 'capability_id')}
    for kind in ('result', 'evidence'):
        key = kind + '_refs'
        refs = value[key]
        if (not isinstance(refs, (list, tuple)) or len(refs) > 64
                or any(not isinstance(ref, str)
                       or not re.fullmatch(kind + r':sha256:[0-9a-f]{64}', ref) for ref in refs)):
            raise ValueError('authority references are invalid')
        receipt[key] = list(dict.fromkeys(refs))
    if not (receipt['result_refs'] or receipt['evidence_refs']):
        raise ValueError('authority references are empty')
    return receipt


def _token(value, *, limit: int = 128) -> str:
    if not isinstance(value, str) or not _TOKEN.fullmatch(value) or len(value) > limit:
        raise ValueError('structural context is invalid')
    return value


def _checked_model(value) -> dict | None:
    if value is None:
        return None
    if not isinstance(value, Mapping) or set(value) != set(_MODEL_FIELDS):
        raise ValueError('structural context is invalid')
    profiles = value['enabled_profiles']
    if not isinstance(profiles, (list, tuple)) or len(profiles) > 16:
        raise ValueError('structural context is invalid')
    checked_profiles = []
    for item in profiles:
        if not isinstance(item, Mapping) or set(item) != {'profile_id', 'profile_version'}:
            raise ValueError('structural context is invalid')
        checked_profiles.append({
            'profile_id': _token(item['profile_id']),
            'profile_version': _token(item['profile_version']),
        })
    return {
        'model_context_id': _token(value['model_context_id']),
        'model_id': _token(value['model_id']),
        'model_revision': _token(value['model_revision']),
        'implementation_family': _token(value['implementation_family']),
        'selection_revision': _token(value['selection_revision']),
        'enabled_profiles': checked_profiles,
    }


def _checked_handles(value) -> list[dict]:
    if not isinstance(value, (list, tuple)) or len(value) > 64:
        raise ValueError('structural context is invalid')
    checked = []
    for item in value:
        if not isinstance(item, Mapping) or set(item) != {'kind', 'ref'}:
            raise ValueError('structural context is invalid')
        if item['kind'] not in {'result_ref', 'evidence_ref'}:
            raise ValueError('structural context is invalid')
        checked.append({'kind': item['kind'], 'ref': _token(item['ref'], limit=256)})
    return checked


def checked_structural_context(value) -> dict:
    """Admit identities and opaque refs. Reject tool payloads."""

    if (not isinstance(value, Mapping) or set(value) - {'work_scope', 'authority_inputs'} != {'schema', 'model', 'handles'}
            or value.get('schema') != 'capstone-structural-context/1'):
        raise ValueError('structural context is invalid')
    document = {
        'schema': 'capstone-structural-context/1',
        'model': _checked_model(value.get('model')),
        'handles': _checked_handles(value.get('handles')),
    }
    if 'work_scope' in value:
        if document['model'] is not None:
            raise ValueError('structural context is invalid')
        document['work_scope'] = _checked_work_scope(value['work_scope'])
    if 'authority_inputs' in value:
        document['authority_inputs'] = _checked_authority_inputs(value['authority_inputs'])
    return document


def _checked_authority_inputs(value):
    if not isinstance(value, (list, tuple)) or len(value) > 64:
        raise ValueError('invalid authority inputs')
    inputs = []
    for item in value:
        if not isinstance(item, Mapping) or 'owner' not in item:
            raise ValueError('invalid authority input')
        owner = item['owner']
        if isinstance(owner, Mapping) and set(owner) == {'model'} and owner['model'] is not None:
            selector = {'model': _checked_model(owner['model'])}
        elif isinstance(owner, Mapping) and set(owner) == {'work_scope'}:
            selector = {'work_scope': _checked_work_scope(owner['work_scope'])}
        else:
            raise ValueError('invalid authority input owner')
        inputs.append({'owner': selector, **checked_authority_references(
            {key: entry for key, entry in item.items() if key != 'owner'})})
    return inputs


def _checked_work_scope(value):
    if not isinstance(value, str) or not re.fullmatch(r'work-[a-f0-9]{40}', value):
        raise ValueError('structural context is invalid')
    return value


def checked_management(value) -> dict:
    """The model identity or Work scope for a Domain Pack workspace."""

    if (not isinstance(value, Mapping) or set(value) - {'prior_evidence_refs', 'authority_inputs'} not in ({'schema', 'model'}, {'schema', 'work_scope'})
            or value.get('schema') != 'capstone-structural-context/1'):
        raise ValueError('structural context is invalid')
    evidence = value.get('prior_evidence_refs', [])
    if (not isinstance(evidence, (list, tuple)) or len(evidence) > 64
            or any(not isinstance(ref, str) or not re.fullmatch(r'evidence:sha256:[0-9a-f]{64}', ref)
                   for ref in evidence)):
        raise ValueError('structural context is invalid')
    prior = {'prior_evidence_refs': list(dict.fromkeys(evidence))} if evidence else {}
    if 'authority_inputs' in value:
        prior['authority_inputs'] = _checked_authority_inputs(value['authority_inputs'])
    if 'work_scope' in value:
        return {'schema': value['schema'], 'work_scope': _checked_work_scope(value['work_scope']), **prior}
    model = _checked_model(value.get('model'))
    if model is None:
        raise ValueError('structural context is invalid')
    return {'schema': 'capstone-structural-context/1', 'model': model, **prior}


def management_for(structural: Mapping | None) -> dict | None:
    """Return the private workspace selector from the frozen chain record."""

    if not isinstance(structural, Mapping):
        return None
    checked = checked_structural_context(structural)
    evidence = list(dict.fromkeys(item['ref'] for item in checked['handles']
        if item['kind'] == 'evidence_ref' and re.fullmatch(r'evidence:sha256:[0-9a-f]{64}', item['ref'])))
    prior = {'prior_evidence_refs': evidence} if evidence else {}
    if 'authority_inputs' in checked:
        prior['authority_inputs'] = checked['authority_inputs']
    if 'work_scope' in checked:
        return {'schema': checked['schema'], 'work_scope': checked['work_scope'], **prior}
    if checked['model'] is None:
        return None
    return {'schema': checked['schema'], 'model': checked['model'], **prior}


def management_note(value: Mapping) -> str:
    """Reader text for the main chain. It names refs and does not carry tool data."""

    checked = checked_structural_context(value)
    checked.pop('work_scope', None)
    checked.pop('authority_inputs', None)
    return (
        'Main-chain management context. It names the open model and opaque handles. '
        'Domain Pack tools keep grid calculation data. Gateway tools keep their own refs and payloads. '
        'Use these identities to organize later tool calls. '
        'Do not copy network tables or gateway rows into this context.\n'
        + json.dumps(checked, ensure_ascii=False, sort_keys=True)
    )


def structural_context_for(claim) -> dict:
    """Return identities and refs. Do not copy tool payloads into the chain."""

    context = getattr(claim, 'model_context', None)
    model = None
    if context is not None:
        model = {
            'model_context_id': context.id,
            'model_id': context.model_id,
            'model_revision': context.model_revision,
            'implementation_family': context.implementation_family,
            'selection_revision': context.selection_revision,
            'enabled_profiles': [
                {'profile_id': profile_id, 'profile_version': version}
                for profile_id, version in getattr(context, 'enabled_profiles', ())[:16]
            ],
        }
    inputs = _checked_authority_inputs((getattr(claim, 'submission', None) or {}).get('_authority_inputs', []))
    handles = [{'kind': kind + '_ref', 'ref': ref} for item in inputs
               for kind in ('result', 'evidence') for ref in item[kind + '_refs']]
    selection = (getattr(claim, 'submission', None) or {}).get('_goal_authority_selection')
    if selection is not None:
        from .goal_receipts import validate_goal_authority_refs
        validate_goal_authority_refs(selection['refs'])
        identity = None if context is None else context.to_document()
        if selection['refs'] and selection['model'] != identity:
            raise ValueError('goal authority input model changed')
        handles.extend({'kind': ref.split(':', 1)[0] + '_ref', 'ref': ref} for ref in selection['refs'])
    for item in (() if selection is not None else getattr(claim, 'prior_results', ()) or ()):
        result_ref = getattr(item, 'result_ref', None)
        if isinstance(result_ref, str) and _TOKEN.fullmatch(result_ref):
            handles.append({'kind': 'result_ref', 'ref': result_ref})
        for evidence in getattr(item, 'evidence_refs', ()) or ():
            if isinstance(evidence, str) and _TOKEN.fullmatch(evidence):
                handles.append({'kind': 'evidence_ref', 'ref': evidence})
        if len(handles) >= 64:
            break
    if selection is None:
        handles.extend({'kind': 'evidence_ref', 'ref': ref} for ref in getattr(claim, 'prior_evidence_refs', ()))
    unique = {(item['kind'], item['ref']): item for item in handles}
    if (inputs or selection is not None) and len(unique) > 64:
        raise ValueError('authority handles exceed structural context capacity')
    document = {'schema': 'capstone-structural-context/1', 'model': model, 'handles': list(unique.values())[:64]}
    if inputs:
        document['authority_inputs'] = inputs
    task = getattr(claim, 'task_context', None)
    if model is None and task is not None:
        identity = json.dumps([claim.thread_id, claim.run_id, task.binding.work_id], separators=(',', ':'))
        document['work_scope'] = 'work-' + sha256(identity.encode()).hexdigest()[:40]
    return checked_structural_context(document)


def main_chain_native_binding(submission: Mapping | None) -> bool:
    """An enterprise main-chain attempt keeps its native execution record."""

    native = (submission or {}).get('_native_execution') if isinstance(submission, Mapping) else None
    return isinstance(native, Mapping) and isinstance(native.get('identity'), Mapping)
