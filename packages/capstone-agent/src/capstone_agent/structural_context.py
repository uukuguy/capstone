"""Management record carried by the main reasoning chain.

Domain tools keep grid calculation data. Gateway tools keep their own refs
and payloads. This record names the open model and the opaque handles a later
turn needs to organize the work.
"""

from __future__ import annotations

import re
from collections.abc import Mapping


_TOKEN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$')
_MODEL_FIELDS = (
    'model_context_id', 'model_id', 'model_revision', 'implementation_family',
    'selection_revision', 'enabled_profiles',
)


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

    if (not isinstance(value, Mapping) or set(value) != {'schema', 'model', 'handles'}
            or value.get('schema') != 'capstone-structural-context/1'):
        raise ValueError('structural context is invalid')
    return {
        'schema': 'capstone-structural-context/1',
        'model': _checked_model(value.get('model')),
        'handles': _checked_handles(value.get('handles')),
    }


def checked_management(value) -> dict:
    """The model identity a domain tool may use to find its own workspace."""

    if (not isinstance(value, Mapping) or set(value) != {'schema', 'model'}
            or value.get('schema') != 'capstone-structural-context/1'):
        raise ValueError('structural context is invalid')
    model = _checked_model(value.get('model'))
    if model is None:
        raise ValueError('structural context is invalid')
    return {'schema': 'capstone-structural-context/1', 'model': model}


def management_for(structural: Mapping | None) -> dict | None:
    """Copy the model identity out of a chain record. Omit handles and payloads."""

    if not isinstance(structural, Mapping) or structural.get('model') is None:
        return None
    checked = checked_structural_context(structural)
    return {'schema': checked['schema'], 'model': checked['model']}


def management_note(value: Mapping) -> str:
    """Reader text for the main chain. It names refs and does not carry tool data."""

    import json
    checked = checked_structural_context(value)
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
    handles = []
    for item in getattr(claim, 'prior_results', ()) or ():
        result_ref = getattr(item, 'result_ref', None)
        if isinstance(result_ref, str) and _TOKEN.fullmatch(result_ref):
            handles.append({'kind': 'result_ref', 'ref': result_ref})
        for evidence in getattr(item, 'evidence_refs', ()) or ():
            if isinstance(evidence, str) and _TOKEN.fullmatch(evidence):
                handles.append({'kind': 'evidence_ref', 'ref': evidence})
        if len(handles) >= 64:
            break
    return checked_structural_context(
        {'schema': 'capstone-structural-context/1', 'model': model, 'handles': handles[:64]})


def main_chain_native_binding(submission: Mapping | None) -> bool:
    """An enterprise main-chain attempt keeps its native execution record."""

    native = (submission or {}).get('_native_execution') if isinstance(submission, Mapping) else None
    return isinstance(native, Mapping) and isinstance(native.get('identity'), Mapping)
