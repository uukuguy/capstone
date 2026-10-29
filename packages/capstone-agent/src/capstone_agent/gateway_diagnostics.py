"""Host-only MCP correlation, without business arguments or hidden reasoning."""
from copy import deepcopy
import re

_ID = re.compile(r'[A-Za-z0-9_.:-]{1,128}')
FIELDS = ('task_id', 'run_id', 'trace_id', 'parent_span_id')

def diagnostic_id(value):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError('gateway_diagnostics_identifier_invalid')
    return value

def checked_diagnostics(value):
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != set(FIELDS):
        raise ValueError('gateway_diagnostics_context_invalid')
    return {key: diagnostic_id(value[key]) for key in FIELDS}

def response_diagnostics(result):
    content = result.get('structuredContent', {})
    provenance = content.get('provenance', {}) if isinstance(content, dict) else {}
    if not isinstance(provenance, dict):
        return {}
    retained = {}
    for source, target in (('request_id', 'request_id'), ('span_id', 'gateway_span_id')):
        try:
            retained[target] = diagnostic_id(provenance.get(source))
        except ValueError:
            pass  # Absent gateway evidence is never synthesized.
    return deepcopy(retained)
