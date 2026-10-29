"""Same-Work process files reuse the existing read-only resource transport."""
from hashlib import sha256
import json
import re

from .resource_manifest import checked_resource


def resource_id(thread_id, attempt_id, artifact_id):
    identity = json.dumps([thread_id, attempt_id, artifact_id], separators=(',', ':'))
    return 'resource_' + sha256(identity.encode()).hexdigest()[:32]


def artifact_resource(source):
    return checked_resource({'schema': 'capstone-resource/1', 'version': 1,
        'resource_id': resource_id(source['thread_id'], source['attempt_id'], source['artifact_id']),
        **{key: source[key] for key in ('thread_id', 'file_name', 'size_bytes', 'sha256')}})


def artifact_origin(source):
    return {'resource_id': artifact_resource(source)['resource_id'],
        **{key: source[key] for key in ('attempt_id', 'artifact_id', 'work_id', 'source_status')}}


def checked_origin(value, thread_id):
    fields = {'resource_id', 'attempt_id', 'artifact_id', 'work_id', 'source_status'}
    if (not isinstance(value, dict) or set(value) != fields
            or not isinstance(value['source_status'], str)
            or value['source_status'] not in {'completed', 'failed', 'cancelled', 'needs_clarification', 'capability_unavailable'}
            or any(not isinstance(value[key], str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', value[key])
                   for key in fields - {'source_status'})
            or value['resource_id'] != resource_id(thread_id, value['attempt_id'], value['artifact_id'])):
        raise ValueError('invalid continuation resource origin')
    return dict(value)


def resource_reader_for(service, claim):
    """Read only frozen uploads or exact same-Work artifact versions."""
    submission = claim.submission or {}
    allowed = {item['resource_id']: checked_resource(dict(item))
               for item in submission.get('_resource_manifests', ())}
    historical = {artifact_resource(source)['resource_id']: source
                  for source in submission.get('_continuation_artifacts', ())}

    def read_resource(manifest):
        canonical = checked_resource(dict(manifest))
        if canonical != allowed.get(canonical['resource_id']) or canonical['thread_id'] != claim.thread_id:
            raise ValueError('resource not admitted for this attempt')
        source = historical.get(canonical['resource_id'])
        if source is None:
            from .thread_resources import ResourceUploads
            yield from ResourceUploads(service, service._material_objects).read(claim.thread_id, canonical['resource_id'])
            return
        if (claim.task_context is None or source['thread_id'] != claim.thread_id
                or source['work_id'] != claim.task_context.binding.work_id):
            raise ValueError('continuation artifact is outside this Work')
        from .native_artifact_projection import read_native_artifact
        try:
            descriptor, data = read_native_artifact(service, getattr(service, '_native_executor', None),
                claim.thread_id, source['attempt_id'], source['artifact_id'], expected_descriptor=source)
        except OSError:
            from .thread_materials import _adopted_file_bytes
            data = _adopted_file_bytes(service, service.snapshot(claim.thread_id), source, None)
            descriptor = source
        if (dict(descriptor) != dict(source) or artifact_resource(descriptor) != canonical or len(data) != canonical['size_bytes']
                or sha256(data).hexdigest() != canonical['sha256']):
            raise ValueError('continuation artifact content identity changed')
        from .native_resource_staging import CHUNK_BYTES
        for start in range(0, len(data), CHUNK_BYTES):
            yield data[start:start + CHUNK_BYTES]

    return read_resource
