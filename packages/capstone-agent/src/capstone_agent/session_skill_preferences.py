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
        if (not isinstance(skill, dict) or not {'id', 'version', 'role'} <= set(skill)
                or set(skill) - {'id', 'version', 'role', 'loaded_identity', 'native_name', 'catalog_revision'}
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
    identity = matching.get('loaded_identity')
    if not isinstance(identity, str) or not identity:
        raise ValueError('session_skill_content_unavailable')
    return {**skill, 'catalog_revision': profile['revision'], 'loaded_identity': identity,
            **({'native_name': matching['native_name']} if matching.get('native_name') else {})}


def revise_preferences(current, *, expected_revision, skills, profiles, mode):
    current = checked_preferences(current)
    if type(expected_revision) is not int or expected_revision != current['revision']:
        raise ValueError('skill_preferences_conflict')
    revised = checked_preferences({'revision': current['revision'] + 1, 'skills': skills})
    pinned = []
    previous = {skill['id']: skill for skill in current['skills']}
    for skill in revised['skills']:
        admitted = _available(skill, profiles, mode)
        identity = skill.get('loaded_identity')
        if not identity and skill['id'] in previous:
            identity = previous[skill['id']].get('loaded_identity')
            if not identity:
                raise ValueError('session_skill_reselect_required')
        if identity and identity != admitted['loaded_identity']:
            raise ValueError('session_skill_content_changed')
        pinned.append(admitted)
    revised['skills'] = pinned
    return revised


def freeze_preferences(current, *, profiles, mode, excluded):
    current = checked_preferences(current)
    if (not isinstance(excluded, list) or len(excluded) > limits.context_references
            or any(not isinstance(item, str) for item in excluded)
            or len(set(excluded)) != len(excluded)
            or not set(excluded) <= {skill['id'] for skill in current['skills']}):
        raise ValueError('skill_exclusion_invalid')
    selected = []
    for skill in current['skills']:
        if skill['id'] in excluded:
            continue
        if not skill.get('loaded_identity'):
            raise ValueError('session_skill_reselect_required')
        admitted = _available(skill, profiles, mode)
        if admitted['loaded_identity'] != skill['loaded_identity']:
            raise ValueError('session_skill_content_changed')
        selected.append(admitted)
    return {'revision': current['revision'], 'skills': selected, 'excluded': list(excluded)}


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
    if not frozen.get('skills') and not frozen.get('excluded'):
        return ''
    return ('Session method preferences (not mandatory steps): ' + json.dumps(frozen, ensure_ascii=False)
        + '\nChoose methods relevant to the current instruction. Excluded methods cannot be loaded in this instruction. '
          'An explicit non-excluded current-instruction skill takes priority. '
          'These preferences grant no tools or data and carry no prior business goal or evidence. '
          'Load methods only when needed; record actual use for this instruction. '
          'Continue related investigation state only from admitted context, never from a method preference.')


def checked_execution_scope(value):
    if (not isinstance(value, dict) or set(value) != {'schema', 'revision', 'skills', 'excluded'}
            or value['schema'] != 'capstone-session-skill-scope/1'):
        raise ValueError('session_skill_scope_invalid')
    selected = checked_preferences({'revision': value['revision'], 'skills': value['skills']})
    excluded = value['excluded']
    if (not isinstance(excluded, list) or len(excluded) > limits.context_references
            or any(not isinstance(item, str) or not item.strip() or len(item) > 256 for item in excluded)
            or len(set(excluded)) != len(excluded)
            or set(excluded) & {item['id'] for item in selected['skills']}
            or any(not item.get('loaded_identity') for item in selected['skills'])):
        raise ValueError('session_skill_scope_invalid')
    return {**selected, 'schema': value['schema'], 'excluded': list(excluded)}


def execution_scope(submission):
    frozen = (submission or {}).get('session_skills')
    if frozen is None:
        return None
    selected = []
    for skill in frozen['skills']:
        if skill.get('loaded_identity'):
            selected.append(skill)
        else:
            # Old accepted instructions can use only their own frozen catalog,
            # never the current session or current executor catalog.
            selected.append(_available(skill, submission.get('resource_profiles', {}),
                'pi_reference' if skill['role'] == 'direct_pi' else 'capstone'))
    return checked_execution_scope({'schema': 'capstone-session-skill-scope/1',
        'revision': frozen['revision'], 'skills': selected, 'excluded': frozen['excluded']})


def scoped_skill_names(scope, *, profile, declarations, allowed, role, task_input):
    scope = checked_execution_scope(scope)
    for skill in scope['skills']:
        current = next((item for item in profile['resources'] if item['id'] == skill['id']), None)
        if (skill['role'] != role or current is None or current.get('kind') != 'skill'
                or current.get('version') != skill['version'] or not current.get('ready')
                or current.get('loaded_identity') != skill['loaded_identity']):
            raise ValueError('session_skill_content_changed')
    if task_input.get('kind') == 'skill_invocation' and task_input.get('skill_id') in scope['excluded']:
        raise ValueError('session_skill_selection_conflict')
    blocked = {item['native_name'] for item in declarations
               if item['kind'] == 'skill' and item['id'] in scope['excluded']}
    return [name for name in allowed if name not in blocked]
