"""Public, bounded native context; no credentials, paths, or query endpoints."""
import json
from collections.abc import Mapping

MAX_NATIVE_CONTEXT_BYTES = 2 * 1024 * 1024
POLICY_TEXT = ('Answer the current user message using its conversation context. '
    'General knowledge is not an Authority result. Do not claim model calculations '
    'or external retrieval without an admitted source. External lookup is disabled. '
    'Do not use shell commands or MCP tools to bypass that application restriction.')
GENERAL_CHAT_POLICY_TEXT = ('Provide a direct conversational answer to the current user message. '
    + POLICY_TEXT)


def public_document(value):
    if isinstance(value, Mapping):
        return {key: public_document(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [public_document(item) for item in value]
    return value


def checked_native_context(value):
    value = public_document(value)
    if (not isinstance(value, dict) or set(value) != {'policy', 'selected_task_records', 'selected_task_source', 'records_truncated'}
            or type(value['records_truncated']) is not bool
            or not isinstance(value['selected_task_records'], list) or len(value['selected_task_records']) > 64):
        raise ValueError('native task context is invalid')
    declared = value['selected_task_source']
    if declared is not None and (not isinstance(declared, dict) or set(declared) != {'thread_id', 'attempt_id'}
            or any(not isinstance(item, str) or not item for item in declared.values())):
        raise ValueError('native selected task source is invalid')
    policy = value['policy']
    if (not isinstance(policy, dict) or set(policy) != {'schema', 'system_policy', 'allowed_tools', 'external_lookup_enabled'}
            or policy['schema'] != 'capstone-conversation-policy/1'
            or policy['system_policy'] not in (POLICY_TEXT, GENERAL_CHAT_POLICY_TEXT)
            or policy['external_lookup_enabled'] is not False
            or not isinstance(policy['allowed_tools'], list) or len(policy['allowed_tools']) > 256
            or any(not isinstance(item, str) or not item or len(item) > 256 for item in policy['allowed_tools'])
            or len(set(policy['allowed_tools'])) != len(policy['allowed_tools'])):
        raise ValueError('native application policy is invalid')
    source = None
    cursor = 0
    for page in value['selected_task_records']:
        if (not isinstance(page, dict) or page.get('schema') != 'capstone-selected-task-records/1'
                or page.get('historical_only') is not True or type(page.get('has_more')) is not bool
                or not isinstance(page.get('events'), list) or type(page.get('next_after')) is not int
                or page['next_after'] < cursor):
            raise ValueError('native selected task records are invalid')
        identity = (page.get('thread_id'), page.get('attempt_id'))
        if any(not isinstance(item, str) or not item for item in identity) or source is not None and source != identity:
            raise ValueError('native selected task source changed')
        source, cursor = identity, page['next_after']
    if source is not None and declared != {'thread_id': source[0], 'attempt_id': source[1]}:
        raise ValueError('native selected task identity changed')
    encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    if len(encoded.encode()) > MAX_NATIVE_CONTEXT_BYTES:
        raise ValueError('native context exceeds bounds')
    return json.loads(encoded)


def native_context_for(claim, binding):
    from .enterprise_application import resolve_native_profile
    profile = resolve_native_profile(binding['application_profile']['profile_id'])
    tools = set(binding['capability'].get('native_builtin_tools', ()))
    submission = claim.submission or {}
    if submission.get('input', {}).get('kind') == 'skill_invocation':
        selected = next((item for item in binding['capability']['resource_profiles']['delegated_pi']['resources']
                         if item['id'] == submission['input']['skill_id'] and item['kind'] == 'skill'), None)
        if selected is None or not selected['ready']:
            raise ValueError('selected native skill is unavailable')
        tools.update(selected['required_tools'])
    pages, cursor, truncated, source = [], 0, False, None
    reader = claim.selected_task_reader
    while reader is not None:
        page = reader.read(after=cursor, limit=4)
        source = {'thread_id': page['thread_id'], 'attempt_id': page['attempt_id']}
        if len(json.dumps([*pages, page], ensure_ascii=False).encode()) > MAX_NATIVE_CONTEXT_BYTES - 32768 or len(pages) >= 64:
            truncated = True
            break
        pages.append(page)
        if not page['has_more']:
            break
        if page['next_after'] <= cursor:
            raise ValueError('native history cursor did not advance')
        cursor = page['next_after']
    if pages:
        tools.add('agent_task_records_read')
    return checked_native_context({'policy': {'schema': 'capstone-conversation-policy/1',
        'system_policy': profile.application_policy.load(), 'allowed_tools': sorted(tools),
        'external_lookup_enabled': False}, 'selected_task_records': pages,
        'selected_task_source': source, 'records_truncated': truncated})
