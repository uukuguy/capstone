"""Application-owned typed composer input and explicit public context choices."""
from __future__ import annotations

from collections.abc import Mapping
import json

from .request_intent import _canonical, _fields, _items, _text


class InputRejected(ValueError):
    """A bounded public admission reason."""


def context_selection(value: object, known: set[str] | None = None) -> dict:
    value = _fields(value, {'include_refs', 'exclude_refs'})
    for key in ('include_refs', 'exclude_refs'):
        refs = _items(value[key], key, limit=24)
        for ref in refs:
            _text(ref, key, limit=256)
        if len(set(refs)) != len(refs) or (known is not None and not set(refs) <= known):
            raise ValueError('context selection reference is unavailable')
    return json.loads(_canonical(value, 16384))


def validate_submission(payload: Mapping, *, mode: str, objects: list[dict],
                        profiles: Mapping | None = None) -> dict:
    """Resolve only declared public identities; never accept a client adapter."""
    try:
        if {'professional_resource', '_professional_backend', '_professional_selection'} & payload.keys():
            raise ValueError('private resource selection is not a public input')
        raw = payload.get('input', {'kind': 'text', 'text': payload['text']})
        if not isinstance(raw, dict):
            raise ValueError('input must be an object')
        kind = raw.get('kind')
        _fields(raw, {'kind', 'text'} if kind == 'text' else
                {'kind', 'text', 'skill_id', 'skill_version'})
        if kind not in {'text', 'skill_invocation'} or raw['text'] != payload['text']:
            raise ValueError('input does not match message')
        _text(raw['text'], 'input text')
        result = {'input': raw, 'runtime_mode': mode, 'objects': objects,
                  'resource_profiles': {role: {key: value for key, value in profile.items()
                      if key != '_professional_selection'} for role, profile in (profiles or {}).items()},
                  'context_selection': context_selection(payload.get('context_selection',
                      {'include_refs': [], 'exclude_refs': []}), {item['object_id'] for item in objects})}
        if kind == 'skill_invocation':
            for key in ('skill_id', 'skill_version'):
                _text(raw[key], key, limit=256)
            selected = _fields(payload.get('resource_profile'), {'profile_id', 'revision'})
            role = selected['profile_id']
            if role not in ({'direct_pi'} if mode == 'pi_reference' else {'harness_engine', 'delegated_pi'}):
                raise InputRejected('resource_role_incompatible')
            profile = (profiles or {}).get(role)
            if not isinstance(profile, Mapping):
                raise InputRejected('resource_unavailable')
            if selected['revision'] != profile.get('revision'):
                raise InputRejected('resource_catalog_stale')
            skill = next((item for item in profile.get('resources', [])
                          if item['id'] == raw['skill_id'] and item['kind'] == 'skill'), None)
            if skill is None or skill['version'] != raw['skill_version'] or not skill['ready']:
                raise InputRejected('resource_unavailable')
            result['resource_profile'] = selected
            if role == 'harness_engine':
                from .professional_resources import parse_harness_selection
                private = profile.get('_professional_selection')
                if (not isinstance(private, dict) or private.get('profile_revision') != selected['revision']
                        or private.get('skill_id') != raw['skill_id'] or private.get('skill_version') != raw['skill_version']):
                    raise InputRejected('resource_unavailable')
                parse_harness_selection(private)
                result['professional_resource'] = private
        elif 'resource_profile' in payload:
            raise ValueError('plain text cannot select a resource profile')
        return json.loads(_canonical(result, 65536))
    except InputRejected:
        raise
    except (KeyError, TypeError, ValueError) as error:
        raise InputRejected('input_invalid') from error


def admission_submission(snapshot, command, provider=None) -> tuple[dict | None, str | None]:
    if command['kind'] not in {'send_auto', 'send_ordinary', 'send_professional', 'send_control'}:
        return None, None
    payload = command['payload']
    if {'professional_resource', '_professional_backend', '_professional_selection'} & payload.keys():
        return None, 'input_invalid'
    if not {'input', 'context_selection', 'resource_profile'} & payload.keys():
        return None, None  # Existing clients retain their accepted legacy contract.
    context = snapshot.active_model_context
    selected = payload.get('resource_profile')
    if isinstance(selected, Mapping) and selected.get('profile_id') == 'harness_engine':
        current_profiles = [{'profile_id': profile_id, 'profile_version': version}
                            for profile_id, version in context.enabled_profiles]
        if snapshot.pending_model_switch is not None or snapshot.pending_selection is not None or (
            'enabled_profiles' in payload and payload['enabled_profiles'] != current_profiles
        ):
            # A professional catalog belongs to the currently prepared selection.
            # Apply the workspace change, then select its fresh resource identity.
            return None, 'resource_catalog_stale'
    catalog = provider(snapshot) if provider is not None else {
        'objects': [{'object_id': context.id, 'model_id': context.model_id,
                     'model_revision': context.model_revision,
                     'implementation_family': context.implementation_family}], 'resource_profiles': {}}
    try:
        submission = validate_submission(payload, mode=snapshot.runtime_mode,
            objects=catalog['objects'], profiles=catalog['resource_profiles'])
        submission['model_context'] = context.to_document()
        return submission, None
    except InputRejected as error:
        return None, str(error)


def freeze_activated_submission(submission: dict | None, context) -> dict | None:
    """Finalize the accepted identity after atomic model/selection activation."""
    if submission is None:
        return None
    result = json.loads(json.dumps(submission))
    current = {'object_id': context.id, 'model_id': context.model_id,
               'model_revision': context.model_revision, 'implementation_family': context.implementation_family}
    if result['model_context'] != context.to_document():
        # No professional skill can reach this branch: admission refuses a
        # binding from the prior selection. Unselected profiles are not reused.
        result['resource_profiles'].pop('harness_engine', None)
    result['model_context'] = context.to_document()
    result['objects'] = [current, *[item for item in result['objects'] if item['object_id'] != context.id]]
    return result


def validate_context_decision(source: dict, refs: list[str]) -> None:
    selection = source.get('context_selection')
    if selection is not None and set(refs) & set(selection['exclude_refs']):
        raise ValueError('context selection uses an explicitly excluded reference')


def selected_context_refs(source: dict, refs: list[str]) -> list[str]:
    selection = source.get('context_selection', {'include_refs': [], 'exclude_refs': []})
    excluded = set(selection['exclude_refs'])
    return [ref for ref in dict.fromkeys([*refs, *selection['include_refs']]) if ref not in excluded]
