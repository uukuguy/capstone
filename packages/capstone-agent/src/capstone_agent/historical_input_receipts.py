"""Host-acknowledged delivery; never a claim of analysis or derivation."""
from hashlib import sha256
import json
import re

from .continuation_resources import artifact_resource
from .resource_manifest import checked_resource

EVENT = 'historical_input_delivered'


def delivery_receipt(claim, task_id, manifest):
    resource = checked_resource(dict(manifest))
    if (not isinstance(task_id, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', task_id)
            or resource['thread_id'] != claim.thread_id
            or resource not in (claim.submission or {}).get('_resource_manifests', ())):
        raise ValueError('delivery is outside the frozen resource grant')
    sources = [source for source in (claim.submission or {}).get('_continuation_artifacts', ())
               if artifact_resource(source)['resource_id'] == resource['resource_id']]
    if not sources:
        return None
    if (len(sources) != 1 or artifact_resource(sources[0]) != resource or claim.task_context is None
            or sources[0]['work_id'] != claim.task_context.binding.work_id):
        raise ValueError('historical delivery source identity changed')
    source = {key: sources[0][key] for key in ('thread_id', 'attempt_id', 'artifact_id', 'work_id',
              'source_status', 'file_name', 'size_bytes', 'sha256')}
    receipt = dict(schema='capstone-historical-input-delivery/1', thread_id=claim.thread_id,
                   attempt_id=claim.attempt.attempt_id, task_id=task_id, resource=resource, source=source)
    receipt['receipt_id'] = sha256(json.dumps(receipt, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return receipt


def previous_delivery(service, claim, payload, connection=None):
    expected = delivery_receipt(claim, payload.get('task_id'), payload.get('resource', {}))
    if expected is None or dict(payload) != expected:
        raise ValueError('historical delivery receipt is invalid')
    if connection is None:
        matches = [event for event in service._events if event.thread_id == claim.thread_id
                   and event.event_type == EVENT and event.attempt_id == claim.attempt.attempt_id
                   and event.payload.get('receipt_id') == expected['receipt_id']]
    else:
        rows = connection.execute(
            "SELECT * FROM capstone_thread_events WHERE thread_id=%s AND attempt_id=%s "
            "AND event_type=%s AND payload->>'receipt_id'=%s LIMIT 2",
            (claim.thread_id, claim.attempt.attempt_id, EVENT, expected['receipt_id'])).fetchall()
        matches = [service._event_from_row(row) for row in rows]
    if len(matches) > 1 or matches and dict(matches[0].payload) != expected:
        raise ValueError('historical delivery receipt conflict')
    return matches[0] if matches else None
