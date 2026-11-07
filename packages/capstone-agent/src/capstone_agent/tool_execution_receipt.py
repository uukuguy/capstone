"""Bound owner telemetry without converting host intervals into source execution."""
from copy import deepcopy
from datetime import datetime
import math
from collections.abc import Mapping


def checked_execution_receipt(value, *, task_id, call_id):
    keys = {'schema', 'owner_id', 'scope_id', 'task_id', 'call_id', 'policy_version', 'capacity', 'events'}
    if (not isinstance(value, Mapping) or set(value) != keys
            or value.get('schema') != 'capstone-tool-execution/1'
            or value.get('task_id') != task_id or value.get('call_id') != call_id
            or type(value.get('capacity')) is not int or not 1 <= value['capacity'] <= 1024
            or any(not isinstance(value.get(key), str) or not 0 < len(value[key]) <= 256
                   for key in keys - {'schema', 'capacity', 'events'})):
        return None
    phases = ['submitted', 'queued', 'acquired', 'execution_started', 'execution_ended', 'released']
    events = value.get('events')
    if not isinstance(events, list) or not 1 <= len(events) <= len(phases) + 1:
        return None
    last_phase, last_time, cancelled = -1, -1, False
    seen = set()
    for event in events:
        if not isinstance(event, Mapping) or set(event) != {'phase', 'at', 'elapsed_ms', 'provenance'}:
            return None
        phase, elapsed = event.get('phase'), event.get('elapsed_ms')
        cancelling = phase == 'cancellation_requested'
        if cancelling and (cancelled or last_phase < 1 or last_phase >= 5):
            return None
        if not cancelling and (phase not in phases or phases.index(phase) <= last_phase):
            return None
        if (type(elapsed) not in {int, float} or not math.isfinite(elapsed) or elapsed < last_time
                or event.get('provenance') != ('authority_process' if phase.startswith('execution_') else 'owner_scheduler')):
            return None
        try:
            if not isinstance(event['at'], str) or len(event['at']) > 64 or datetime.fromisoformat(event['at'].replace('Z', '+00:00')).tzinfo is None:
                return None
        except ValueError:
            return None
        if cancelling:
            cancelled = True
        else:
            if cancelled and phase in {'acquired', 'execution_started'}:
                return None
            if (phase == 'execution_ended' and 'execution_started' not in seen
                    or phase == 'released' and 'execution_started' in seen and 'execution_ended' not in seen):
                return None
            last_phase = phases.index(phase)
        seen.add(phase)
        last_time = elapsed
    return deepcopy(dict(value))
