"""Bound owner telemetry without converting host intervals into source execution."""
from copy import deepcopy
from datetime import datetime
import math
from collections.abc import Mapping


def checked_investigation_checkpoint(value):
    keys = {'schema', 'checkpoint_id', 'completed_leaf_calls', 'state'}
    if (not isinstance(value, Mapping) or set(value) != keys
            or value.get('schema') != 'capstone-investigation-checkpoint/1'
            or type(value.get('checkpoint_id')) is not int or not 1 <= value['checkpoint_id'] <= 1_000_000
            or type(value.get('completed_leaf_calls')) is not int or not 1 <= value['completed_leaf_calls'] <= 1_000_000_000
            or not isinstance(value.get('state'), str)
            or value['state'] not in {'context_prepared', 'response_received'}):
        return None
    return dict(value)


def checked_tool_batch(value, *, task_id):
    keys = {'schema', 'task_id', 'batch_id', 'mode', 'capacity', 'call_ids', 'elapsed_ms'}
    if (not isinstance(value, Mapping) or set(value) != keys
            or value.get('schema') != 'capstone-tool-batch/1' or value.get('task_id') != task_id
            or value.get('mode') != 'parallel' or type(value.get('capacity')) is not int
            or not 1 <= value['capacity'] <= 1024
            or not isinstance(value.get('batch_id'), str) or not 0 < len(value['batch_id']) <= 256
            or not isinstance(value.get('call_ids'), list) or not 1 <= len(value['call_ids']) <= 1024
            or any(not isinstance(item, str) or not 0 < len(item) <= 256 for item in value['call_ids'])
            or len(set(value['call_ids'])) != len(value['call_ids'])
            or type(value.get('elapsed_ms')) not in {int, float}):
        return None
    try:
        if not math.isfinite(value['elapsed_ms']) or value['elapsed_ms'] < 0:
            return None
    except OverflowError:
        return None
    return deepcopy(dict(value))


def checked_dispatch_receipt(value, *, task_id, call_id):
    """Native invocation boundaries, separate from Authority process telemetry."""
    keys = {'schema', 'owner_id', 'scope_id', 'task_id', 'call_id', 'policy_version', 'capacity', 'events'}
    if (not isinstance(value, Mapping) or set(value) != keys
            or value.get('schema') != 'capstone-tool-dispatch/1'
            or value.get('task_id') != task_id or value.get('call_id') != call_id
            or value.get('scope_id') != task_id
            or type(value.get('capacity')) is not int or not 1 <= value['capacity'] <= 1024
            or any(not isinstance(value.get(k), str) or not 0 < len(value[k]) <= 256
                   for k in keys - {'schema', 'capacity', 'events'})):
        return None
    phases = ['submitted', 'queued', 'acquired', 'invocation_started', 'invocation_settled', 'released']
    events = value['events']
    if not isinstance(events, list) or not 1 <= len(events) <= 6:
        return None
    previous, elapsed, seen = -1, -1, set()
    for event in events:
        if not isinstance(event, Mapping) or set(event) != {'phase', 'at', 'elapsed_ms', 'provenance'}:
            return None
        phase, current = event.get('phase'), event.get('elapsed_ms')
        if type(current) not in {int, float} or not isinstance(current, (int, float)):
            return None
        try:
            finite = math.isfinite(current)
        except OverflowError:
            return None
        if (phase not in phases or phases.index(phase) <= previous
                or not finite or current < 0 or current < elapsed
                or event.get('provenance') != 'native_dispatch'
                or phase == 'invocation_started' and 'acquired' not in seen
                or phase == 'invocation_settled' and 'invocation_started' not in seen
                or phase == 'released' and 'invocation_started' in seen and 'invocation_settled' not in seen):
            return None
        try:
            if not isinstance(event['at'], str) or len(event['at']) > 64 or datetime.fromisoformat(event['at'].replace('Z', '+00:00')).tzinfo is None:
                return None
        except ValueError:
            return None
        previous, elapsed = phases.index(phase), current
        seen.add(phase)
    return deepcopy(dict(value))


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
        if (not isinstance(elapsed, (int, float)) or isinstance(elapsed, bool)):
            return None
        try:
            finite = math.isfinite(elapsed)
        except OverflowError:
            return None
        if (not finite or elapsed < last_time
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
