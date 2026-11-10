"""Bounded public skill-use records; reports confer no evidence authority."""
import re
from collections.abc import Mapping


def checked_skill_activity(value):
    if not isinstance(value, Mapping) or value.get('schema') != 'capstone-skill-activity/1':
        return None
    name, version = value.get('name'), value.get('version')
    if not isinstance(name, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,127}', name):
        return None
    if not isinstance(version, str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', version):
        return None
    state = value.get('state')
    if (state, value.get('source')) not in {('loaded', 'host'), ('reported', 'model')}:
        return None
    result = {key: value[key] for key in ('schema', 'name', 'version', 'state', 'source')}
    if state == 'reported':
        for key, limit in (('phase', 80), ('summary', 600)):
            text = value.get(key)
            if not isinstance(text, str) or not text.strip() or len(text) > limit:
                return None
            if re.search(r'(?i)(password|secret|authorization|api[_ -]?key|access[_ -]?token)\s*[:=]', text):
                return None
            result[key] = text
        for key in ('refs', 'tool_call_ids'):
            refs = value.get(key)
            if not isinstance(refs, list) or len(refs) > 32 or any(
                not isinstance(ref, str) or not ref or len(ref) > 256 for ref in refs
            ):
                return None
            result[key] = refs
    return result
