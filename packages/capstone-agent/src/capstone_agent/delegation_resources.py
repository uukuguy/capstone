"""Explicit read-only cross-Thread grants for a single delegated Work."""
from copy import deepcopy
from hashlib import sha256
import json

from .application_capacity import limits, require_capacity
from .resource_manifest import checked_resource

GRANT_EVENT = 'delegation_resources_granted'
DELIVERY_EVENT = 'delegation_input_delivered'


def granted_manifest(thread_id, work_id, delegation_id, source):
    token = json.dumps([thread_id, work_id, delegation_id, source['thread_id'],
                       source['attempt_id'], source['artifact_id'], source['sha256']], separators=(',', ':'))
    return checked_resource(dict(schema='capstone-resource/1', version=1,
        resource_id='resource_' + sha256(token.encode()).hexdigest()[:32], thread_id=thread_id,
        **{key: source[key] for key in ['file_name', 'size_bytes', 'sha256']}))


def frozen_grants(service, thread_id, work_id, connection=None):
    if work_id in {None, 'new'}:
        return []
    if connection is not None:
        rows = connection.execute('''SELECT payload FROM capstone_thread_events
            WHERE thread_id=%s AND event_type=%s AND payload->>'work_id'=%s
            ORDER BY event_seq LIMIT 2''', (thread_id, GRANT_EVENT, work_id)).fetchall()
        records = [row['payload'] for row in rows]
    elif hasattr(service, '_lock'):
        records = [e.payload for e in service._events if e.thread_id == thread_id
                   and e.event_type == GRANT_EVENT and e.payload['work_id'] == work_id]
    else:
        with service._connect() as opened:
            return frozen_grants(service, thread_id, work_id, opened)
    if len(records) > 1:
        raise ValueError('delegation Work has conflicting resource grants')
    return deepcopy(records[0]['resources']) if records else []


def grant_resources(service, workspace, thread_id, work_id, delegation_id, products):
    """Host-selected immutable descriptors, never caller file paths or bodies."""
    from .native_artifact_projection import native_artifact_page, _matches_frozen_descriptor
    from .thread_materials import _mutate, _write_event
    service.require_workspace(thread_id, workspace)
    require_capacity('context_references', len(products), phase='delegation.resources')
    grants = []
    for source in products:
        if not isinstance(source, dict) or source.get('source_status') != 'completed':
            raise ValueError('delegation context requires a completed process product')
        service.require_workspace(source['thread_id'], workspace)
        after, found = 0, False
        for _ in range(128):
            page = native_artifact_page(service, source['thread_id'], source['attempt_id'],
                                        after=after, include_presentation=False)
            if any(_matches_frozen_descriptor(item, source) for item in page['artifacts']):
                found = True
                break
            if not page['has_more']:
                break
            if page['next_after'] <= after:
                raise ValueError('source product cursor did not advance')
            after = page['next_after']
        if not found:
            raise ValueError('delegation source is not a published immutable product')
        grants.append({'delegation_id': delegation_id, 'workspace': workspace,
                       'work_id': work_id, 'source': deepcopy(source),
                       'resource': granted_manifest(thread_id, work_id, delegation_id, source)})
    def save(snapshot, connection):
        if not any(w['work_id'] == work_id for w in snapshot.works):
            raise ValueError('delegation Work not found')
        previous = frozen_grants(service, thread_id, work_id, connection)
        if previous:
            if previous != grants:
                raise ValueError('delegation resource grant conflict')
            return previous
        _write_event(service, snapshot, GRANT_EVENT,
                     {'work_id': work_id, 'delegation_id': delegation_id, 'resources': grants}, connection)
        return grants
    return _mutate(service, thread_id, save)


def read_granted_resource(service, claim, manifest):
    canonical = checked_resource(dict(manifest))
    grants = [g for g in (claim.submission or {}).get('_delegation_resources', []) if g['resource'] == canonical]
    if len(grants) != 1 or claim.task_context is None:
        raise ValueError('resource is outside the frozen delegation grant')
    grant = grants[0]
    if (grant['work_id'] != claim.task_context.binding.work_id or
            canonical['thread_id'] != claim.thread_id or
            canonical != granted_manifest(claim.thread_id, grant['work_id'], grant['delegation_id'], grant['source'])):
        raise ValueError('delegation resource ownership mismatch')
    source = grant['source']
    service.require_workspace(claim.thread_id, grant['workspace'])
    service.require_workspace(source['thread_id'], grant['workspace'])
    from .native_artifact_projection import read_native_artifact
    _, data = read_native_artifact(service, getattr(service, '_native_executor', None),
        source['thread_id'], source['attempt_id'], source['artifact_id'], expected_descriptor=source)
    if len(data) != canonical['size_bytes'] or sha256(data).hexdigest() != canonical['sha256']:
        raise ValueError('delegation resource bytes changed')
    from .native_resource_staging import CHUNK_BYTES
    for offset in range(0, len(data), CHUNK_BYTES):
        yield data[offset:offset + CHUNK_BYTES]


def delivery_receipt(claim, task_id, manifest):
    canonical = checked_resource(dict(manifest))
    grants = [g for g in (claim.submission or {}).get('_delegation_resources', []) if g['resource'] == canonical]
    if not grants:
        return None
    if (len(grants) != 1 or claim.task_context is None or
            grants[0]['work_id'] != claim.task_context.binding.work_id or
            canonical['thread_id'] != claim.thread_id or not isinstance(task_id, str) or not task_id):
        raise ValueError('invalid delegated resource delivery identity')
    grant = grants[0]
    receipt = dict(schema='capstone-delegation-input-delivery/1', thread_id=claim.thread_id,
        attempt_id=claim.attempt.attempt_id, task_id=task_id, delegation_id=grant['delegation_id'],
        resource=canonical, source={key: grant['source'][key] for key in
            ['thread_id', 'attempt_id', 'work_id', 'artifact_id', 'file_name', 'size_bytes', 'sha256']})
    receipt['receipt_id'] = sha256(json.dumps(receipt, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return receipt


def previous_delivery(service, claim, payload, connection=None):
    if delivery_receipt(claim, payload.get('task_id'), payload.get('resource', {})) != dict(payload):
        raise ValueError('invalid delegated resource delivery receipt')
    if connection is None:
        matches = [e for e in service._events if e.thread_id == claim.thread_id
                   and e.attempt_id == claim.attempt.attempt_id and e.event_type == DELIVERY_EVENT
                   and e.payload.get('receipt_id') == payload['receipt_id']]
    else:
        rows = connection.execute('''SELECT * FROM capstone_thread_events
            WHERE thread_id=%s AND attempt_id=%s AND event_type=%s
            AND payload->>'receipt_id'=%s LIMIT 2''',
            (claim.thread_id, claim.attempt.attempt_id, DELIVERY_EVENT, payload['receipt_id'])).fetchall()
        matches = [service._event_from_row(row) for row in rows]
    if len(matches) > 1 or matches and dict(matches[0].payload) != payload:
        raise ValueError('delegated resource receipt conflict')
    return matches[0] if matches else None
