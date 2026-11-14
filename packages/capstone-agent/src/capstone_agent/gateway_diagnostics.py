"""Host-only MCP correlation, without business arguments or hidden reasoning."""
from copy import deepcopy
import re
import math
from typing import Any

_ID = re.compile(r'[A-Za-z0-9_.:-]{1,128}')
FIELDS = ('task_id', 'run_id', 'trace_id', 'parent_span_id')

def service_bus_calls(result):
    """Project only the gateway's current-call counters, never job totals.

    Absence is unknown. Details are bounded diagnostics, not business evidence.
    """
    content = result.get('structuredContent')
    provenance = content.get('provenance') if isinstance(content, dict) else None
    source = provenance.get('service_bus_calls') if isinstance(provenance, dict) else None
    return _service_bus_projection(source)


def checked_service_bus_calls(value):
    """Validate the host event DTO at the application persistence boundary."""
    if (not isinstance(value, dict) or value.get('schema') != 'capstone-service-bus-calls/1'
            or value.get('scope') != 'current_tool_call' or type(value.get('reused')) is not bool):
        return None
    return {**_service_bus_projection(value), 'reused': value['reused']}


def _service_bus_projection(source):
    output: dict[str, Any] = {'schema': 'capstone-service-bus-calls/1', 'scope': 'current_tool_call'}
    if not isinstance(source, dict) or source.get('scope') != 'current_tool_call':
        return output
    counts = ('attempt_count', 'observed_attempt_count', 'finished_count', 'response_count',
        'bus_declared_success_count', 'bus_declared_error_count', 'transport_error_count',
        'unknown_result_count', 'inflight_or_unknown_count')
    for key in counts:
        value = source.get(key)
        if type(value) is int and 0 <= value <= 9007199254740991:
            output[key] = value
    for key in ('history_complete', 'details_truncated'):
        if type(source.get(key)) is bool:
            output[key] = source[key]
    for key in ('observed_elapsed_ms', 'completed_observed_elapsed_ms'):
        if key not in source:
            continue
        value = source.get(key)
        if value is None or isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 9007199254740991 and math.isfinite(value):
            output[key] = value
    details = source.get('details')
    if isinstance(details, list):
        rows = []
        for row in details[-10:]:
            if not isinstance(row, dict):
                continue
            retained = {}
            for key in ('call_id', 'request_id', 'span_id', 'service', 'method', 'table',
                        'query_class', 'status', 'started_at', 'finished_at', 'bus_response_code',
                        'bus_result', 'remote_execution'):
                value = row.get(key)
                if (isinstance(value, str) and len(value) <= 256
                        and not any(ord(char) < 32 or ord(char) == 127 for char in value)):
                    retained[key] = value
            for key in ('elapsed_ms', 'page_index', 'page_size', 'returned_records',
                        'reported_output_rows', 'response_body_bytes'):
                value = row.get(key)
                if isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 9007199254740991 and math.isfinite(value):
                    retained[key] = value
            if type(row.get('bridge_response_received')) is bool:
                retained['bridge_response_received'] = row['bridge_response_received']
            rows.append(retained)
        output['details'] = rows
    return output

def diagnostic_id(value):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError('gateway_diagnostics_identifier_invalid')
    return value

def checked_diagnostics(value):
    if value is None:
        return None
    if (not isinstance(value, dict) or not set(FIELDS).issubset(value)
            or set(value) - set(FIELDS) - {'client_call_id'}):
        raise ValueError('gateway_diagnostics_context_invalid')
    return {key: diagnostic_id(item) for key, item in value.items()}


def research_diagnostics(binding, attempt_id):
    """Use the admitted Work identity, never the ephemeral executor task ID."""
    if not isinstance(binding, dict) or not isinstance(binding.get('cycle_owner'), dict):
        return None
    from hashlib import sha256
    work_id = diagnostic_id(binding['cycle_owner'].get('work_id'))
    run_id = diagnostic_id(attempt_id)
    trace_id = sha256(('gateway-run:' + work_id + ':' + run_id).encode()).hexdigest()[:32]
    return checked_diagnostics({'task_id': work_id, 'run_id': run_id,
        'trace_id': trace_id, 'parent_span_id': 'attempt:' + trace_id})

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
