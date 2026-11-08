"""Session method preferences, separate from task goals and skill activity."""
from copy import deepcopy
import json

from .application_capacity import limits, require_capacity


def checked_preferences(value):
    if value is None:
        return {'revision': 0, 'skills': []}
    if (not isinstance(value, dict) or set(value) != {'revision', 'skills'}
            or type(value['revision']) is not int or value['revision'] < 0
            or not isinstance(value['skills'], list)):
        raise ValueError('skill_preferences_invalid')
    require_capacity('context_references', len(value['skills']), phase='session_skills')
    seen = set()
    for skill in value['skills']:
        if (not isinstance(skill, dict) or set(skill) != {'id', 'version', 'role'}
                or any(not isinstance(v, str) or not v.strip() or len(v) > 256 for v in skill.values())
                or skill['role'] not in {'direct_pi', 'delegated_pi'} or skill['id'] in seen):
            raise ValueError('skill_preferences_invalid')
        seen.add(skill['id'])
    return deepcopy(value)


def _available(skill, profiles, mode):
    role = 'direct_pi' if mode == 'pi_reference' else 'delegated_pi'
    profile = profiles.get(role, {})
    matching = next((item for item in profile.get('resources', []) if
            item.get('id') == skill['id'] and item.get('kind') == 'skill'
            and item.get('version') == skill['version'] and item.get('ready') is True
            ), None)
    if skill['role'] != role or matching is None:
        raise ValueError('session_skill_unavailable')
    return {**skill, 'catalog_revision': profile['revision'],
            **({'native_name': matching['native_name']} if matching.get('native_name') else {})}


def revise_preferences(current, *, expected_revision, skills, profiles, mode):
    current = checked_preferences(current)
    if type(expected_revision) is not int or expected_revision != current['revision']:
        raise ValueError('skill_preferences_conflict')
    revised = checked_preferences({'revision': current['revision'] + 1, 'skills': skills})
    for skill in revised['skills']:
        _available(skill, profiles, mode)
    return revised


def freeze_preferences(current, *, profiles, mode, excluded):
    current = checked_preferences(current)
    if (not isinstance(excluded, list) or len(excluded) > limits.context_references
            or any(not isinstance(item, str) for item in excluded)
            or len(set(excluded)) != len(excluded)
            or not set(excluded) <= {skill['id'] for skill in current['skills']}):
        raise ValueError('skill_exclusion_invalid')
    return {'revision': current['revision'], 'skills': [
        _available(skill, profiles, mode) for skill in current['skills'] if skill['id'] not in excluded],
        'excluded': list(excluded)}


def apply_preferences(snapshot, command, *, archived, provider):
    if archived:
        return None, 'thread_archived'
    if command.get('run_id') not in {None, snapshot.run.run_id}:
        return None, 'run_mismatch'
    if command['target']['id'] != snapshot.thread_id:
        return None, 'skill_preferences_target_mismatch'
    if set(command['payload']) != {'skills'}:
        return None, 'skill_preferences_invalid'
    try:
        return revise_preferences(snapshot.session_skills,
            expected_revision=command['target']['expected_revision'], skills=command['payload']['skills'],
            profiles={} if provider is None else provider(snapshot)['resource_profiles'],
            mode=snapshot.runtime_mode), None
    except ValueError as error:
        return None, str(error)


def method_guidance(submission):
    frozen = (submission or {}).get('session_skills') or {}
    if not frozen.get('skills'):
        return ''
    return ('Session method preferences (not mandatory steps): ' + json.dumps(frozen, ensure_ascii=False)
        + '\nChoose methods relevant to the current instruction. An explicit current-instruction skill takes priority. '
          'These preferences grant no tools or data and carry no prior business goal or evidence. '
          'Load methods only when needed; record actual use for this instruction. '
          'Continue related investigation state only from admitted context, never from a method preference.')
