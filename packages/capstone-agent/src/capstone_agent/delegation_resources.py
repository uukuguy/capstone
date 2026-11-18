"""Explicit read-only cross-Thread grants for a single delegated Work."""
from copy import deepcopy
from hashlib import sha256
import json

from .application_capacity import limits, require_capacity
from .resource_manifest import checked_resource

GRANT_EVENT = 'delegation_resources_granted'
MISSION_REVIEW_GRANT_EVENT = 'mission_review_resources_granted'
MISSION_UPLOAD_GRANT_EVENT = 'mission_uploads_granted'
DELIVERY_EVENT = 'delegation_input_delivered'


def granted_manifest(thread_id, work_id, delegation_id, source):
    # Identity names the immutable source version. Target ownership remains
    # explicit in the manifest and in the frozen Work grant.
    token = json.dumps([source['thread_id'], source['attempt_id'], source['artifact_id'],
                       source['sha256']], separators=(',', ':'))
    return _manifest(thread_id, source, token)


def _legacy_granted_manifest(thread_id, work_id, delegation_id, source):
    token = json.dumps([thread_id, work_id, delegation_id, source['thread_id'],
                       source['attempt_id'], source['artifact_id'], source['sha256']], separators=(',', ':'))
    return _manifest(thread_id, source, token)


def _manifest(thread_id, source, token):
    return checked_resource(dict(schema='capstone-resource/1', version=1,
        resource_id='resource_' + sha256(token.encode()).hexdigest()[:32], thread_id=thread_id,
        **{key: source[key] for key in ['file_name', 'size_bytes', 'sha256']}))


def _matches_manifest(manifest, thread_id, grant):
    return manifest in (
        granted_manifest(thread_id, grant['work_id'], grant['delegation_id'], grant['source']),
        _legacy_granted_manifest(thread_id, grant['work_id'], grant['delegation_id'], grant['source']))


def _same_frozen_grants(previous, proposed, thread_id):
    return len(previous) == len(proposed) and all(
        {key: value for key, value in old.items() if key != 'resource'} ==
        {key: value for key, value in new.items() if key != 'resource'}
        and _matches_manifest(old['resource'], thread_id, old)
        for old, new in zip(previous, proposed))


def frozen_grants(service, thread_id, work_id, connection=None, *, review_id=None, mission_uploads=False):
    if work_id in {None, 'new'}:
        return []
    event_type = (MISSION_UPLOAD_GRANT_EVENT if mission_uploads else
                  GRANT_EVENT if review_id is None else MISSION_REVIEW_GRANT_EVENT)
    if connection is not None:
        rows = connection.execute('''SELECT payload FROM capstone_thread_events
            WHERE thread_id=%s AND event_type=%s AND payload->>'work_id'=%s
            AND (%s::text IS NULL OR payload->>'delegation_id'=%s)
            ORDER BY event_seq LIMIT 2''', (thread_id, event_type, work_id, review_id, review_id)).fetchall()
        records = [row['payload'] for row in rows]
    elif hasattr(service, '_lock'):
        records = [e.payload for e in service._events if e.thread_id == thread_id
                   and e.event_type == event_type
                   and e.payload['work_id'] == work_id
                   and (review_id is None or e.payload['delegation_id'] == review_id)]
    else:
        with service._connect() as opened:
            return frozen_grants(service, thread_id, work_id, opened, review_id=review_id,
                                 mission_uploads=mission_uploads)
    if len(records) > 1:
        raise ValueError('delegation Work has conflicting resource grants')
    return deepcopy(records[0]['resources']) if records else []


def grant_mission_uploads(service, workspace, thread_id, work_id, delegation_id, origin, references):
    from .mission_equipment import resolve_resource
    from .thread_materials import _mutate, _write_event

    service.require_workspace(thread_id, workspace)
    require_capacity('context_references', len(references), phase='delegation.resources')
    grants = []
    for ref in references:
        source = resolve_resource(service, workspace, origin, ref)
        grants.append({'workspace': workspace, 'work_id': work_id, 'source': source,
                       'resource': {**source, 'thread_id': thread_id}})

    def save(snapshot, connection):
        previous = frozen_grants(service, thread_id, work_id, connection, mission_uploads=True)
        if previous:
            if previous != grants:
                raise ValueError('Mission upload grant conflict')
            return
        if not any(w['work_id'] == work_id and w['latest_attempt_id'] is None for w in snapshot.works):
            raise ValueError('Mission upload grant requires an unstarted Work')
        _write_event(service, snapshot, MISSION_UPLOAD_GRANT_EVENT,
                     {'work_id': work_id, 'delegation_id': delegation_id, 'resources': grants}, connection)

    _mutate(service, thread_id, save)


def grant_resources(service, workspace, thread_id, work_id, delegation_id, products, *, mission_review=False):
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
        previous = frozen_grants(service, thread_id, work_id, connection,
                                 review_id=delegation_id if mission_review else None)
        if previous:
            if not _same_frozen_grants(previous, grants, thread_id):
                raise ValueError('delegation resource grant conflict')
            return previous
        _write_event(service, snapshot, MISSION_REVIEW_GRANT_EVENT if mission_review else GRANT_EVENT,
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
            grant['workspace'] != claim.workspace_name or
            canonical['thread_id'] != claim.thread_id or
            not _matches_manifest(canonical, claim.thread_id, grant)):
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
            grants[0]['workspace'] != claim.workspace_name or
            canonical['thread_id'] != claim.thread_id or not _matches_manifest(canonical, claim.thread_id, grants[0])
            or not isinstance(task_id, str) or not task_id):
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
