"""Resolve Mission equipment only from the selected native registry."""
from copy import deepcopy
from dataclasses import replace
import re
from psycopg.types.json import Jsonb

from capstone_control.service import fingerprint
from capstone_control.mission import references


def registry_revision(binding):
    from .native_mission import registry_revision as registered_revision
    return registered_revision(binding)


def catalog(threads, workspace, origin, *, resource_details=None):
    binding, _ = origin_binding(threads, workspace, origin)
    from .thread_resources import ResourceUploads
    page = ResourceUploads(threads, None).resource_page(origin['thread_id'], limit=16)
    if resource_details is not None:
        resource_details.extend({key: item[key] for key in ('resource_id', 'version', 'file_name', 'size_bytes')}
                                for item in page['resources'])
    resources = [
        {'schema': 'capstone-mission-equipment-reference/1', 'kind': 'resource',
         'id': item['resource_id'], 'revision': str(item['version'])}
        for item in page['resources']
    ]
    return _catalog(binding)[:64-len(resources)] + resources


def resolve_resource(threads, workspace, origin, ref):
    """Resolve published, non-draft inputs without taking a second Thread lock."""
    from .resource_manifest import checked_resource
    from .thread_resources import ResourceUploads
    thread = origin['thread_id']
    threads.require_workspace(thread, workspace)
    resource_id, revision = ref['id'], ref['revision']
    if not re.fullmatch(r'resource_[a-f0-9]{32}', resource_id) or not re.fullmatch(r'[1-9][0-9]{0,15}', revision):
        raise ValueError('invalid Mission resource version')
    if hasattr(threads, '_lock'):
        uploads = ResourceUploads(threads, None)
        with threads._lock:
            uid = uploads._version_upload(thread, resource_id, int(revision))
            state = uploads._state(thread, uid) if uid is not None else {}
        resource = state.get('resource') if state.get('state') == 'complete' and not state.get('draft') else None
    else:
        with threads._connect() as connection:
            row = connection.execute("""SELECT published.payload->'resource' AS resource
                FROM capstone_thread_events published
                JOIN capstone_thread_events started ON started.thread_id=published.thread_id
                    AND started.event_type='resource_upload_started'
                    AND started.payload->>'upload_id'=published.payload->>'upload_id'
                WHERE published.thread_id=%s AND published.event_type='resource_published'
                AND published.payload->'resource'->>'resource_id'=%s
                AND published.payload->'resource'->>'version'=%s
                AND (NOT COALESCE((started.payload->>'draft')::boolean,false)
                    OR EXISTS (SELECT 1 FROM capstone_thread_events admitted
                        WHERE admitted.thread_id=published.thread_id AND admitted.event_type='command_accepted'
                        AND admitted.event_seq>published.event_seq AND admitted.payload->'attachment_refs' ? %s))
                AND NOT EXISTS (SELECT 1 FROM capstone_thread_events cancelled
                    WHERE cancelled.thread_id=published.thread_id AND cancelled.event_type='resource_upload_cancelled'
                    AND cancelled.payload->>'upload_id'=published.payload->>'upload_id')
                LIMIT 1""", (thread, resource_id, revision, resource_id)).fetchone()
        resource = row['resource'] if row else None
    if resource is None:
        raise ValueError('Mission resource version is unavailable')
    return checked_resource(resource)


def origin_binding(threads, workspace, origin):
    from .thread_gateway import publication_binding
    threads.require_workspace(origin['thread_id'], workspace)
    binding = deepcopy(threads._native_binding or {})
    saved = threads.read_thread_gateway(origin['thread_id'])
    published = binding.get('capability', {}).get('data_gateway', {})
    reader = getattr(getattr(threads, '_native_executor', None), 'thread_gateway_publication', None)
    if callable(reader):
        published = reader(saved, refresh=False)
    elif saved is not None:
        default = publication_binding(published)
        if any(saved.get(key) != default.get(key) for key in ('instance_id', 'connection_id')):
            raise ValueError('Mission origin gateway cannot be delegated without its registered source adapter.')
    selected = publication_binding(published, locked=True)
    if saved is not None and any(
            (saved.get(key) is not None or saved.get('locked')) and saved.get(key) != selected.get(key)
            for key in ('instance_id', 'connection_id')):
        raise ValueError('Mission origin gateway identity changed before delegation.')
    if binding:
        binding['capability']['data_gateway'] = deepcopy(published)
    return binding, selected


def _catalog(binding):
    capability = binding.get('capability', {})
    entries = []
    for name in sorted(capability.get('native_builtin_tools', ())):
        entries.append({'schema': 'capstone-mission-equipment-reference/1', 'kind': 'capability',
            'id': name, 'revision': fingerprint({'executor': binding.get('identity'), 'native_tool': name})})
    gateway = capability.get('data_gateway', {})
    if gateway.get('available'):
        published = gateway.get('catalog', {})
        for name, tool in sorted(published.get('tools', {}).items()):
            entries.append({'schema': 'capstone-mission-equipment-reference/1', 'kind': 'capability',
                'id': name, 'revision': fingerprint({'catalog_revision': published.get('revision'), 'tool': tool})})
    profile = capability.get('resource_profiles', {}).get('delegated_pi')
    if profile is not None:
        entries.append({'schema': 'capstone-mission-equipment-reference/1', 'kind': 'resource_profile',
            'id': profile['profile_id'], 'revision': profile['revision']})
    return references(entries[:64])


def admitted(threads, workspace, origin, ref):
    try:
        if ref['kind'] == 'resource':
            return bool(resolve_resource(threads, workspace, origin, ref))
        binding, _ = origin_binding(threads, workspace, origin)
        return ref in _catalog(binding)
    except (ValueError, KeyError):
        return False


def resolve(threads, workspace, origin, equipment, restrictions):
    return resolve_admission(threads, workspace, origin, equipment, restrictions)[0]


def resolve_admission(threads, workspace, origin, equipment, restrictions):
    equipment, restrictions = references(equipment), references(restrictions)
    binding, source = origin_binding(threads, workspace, origin)
    published = _catalog(binding)
    resources = [ref for ref in equipment if ref['kind'] == 'resource']
    if len({ref['id'] for ref in resources}) != len(resources):
        raise ValueError('Mission Task must select one version per resource')
    for ref in resources:
        resolve_resource(threads, workspace, origin, ref)
    if any(ref not in published for ref in equipment + restrictions if ref not in resources):
        raise ValueError('Mission equipment revision is unavailable')
    if any(ref['kind'] != 'capability' for ref in restrictions):
        raise ValueError('The required native resource profile cannot be excluded')
    selected = [ref['id'] for ref in equipment if ref['kind'] == 'capability']
    denied = [ref['id'] for ref in restrictions if ref['kind'] == 'capability']
    if set(selected) & set(denied):
        raise ValueError('Mission equipment cannot select a restricted capability')
    return ({'schema': 'capstone-mission-tool-selection/1',
             'allowed_tools': sorted(selected) if selected else None, 'denied_tools': sorted(denied)},
            registry_revision(binding), source)


def bind_work(threads, workspace, thread_id, work_id, selection, *, binding_revision=None):
    """Persist the resolved selection before creating the execution Attempt."""
    from .native_mission import checked_equipment
    selection = checked_equipment(selection)
    binding_revision = binding_revision or registry_revision(threads._native_binding)
    def change(snapshot):
        works = deepcopy(list(snapshot.works))
        work = next(item for item in works if item['work_id'] == work_id)
        previous = work.get('mission_equipment')
        if previous == selection and work.get('mission_equipment_binding_revision') == binding_revision:
            return snapshot
        if work.get('latest_attempt_id') is not None:
            raise ValueError('Mission equipment cannot change after execution admission')
        work['mission_equipment'] = deepcopy(selection)
        work['mission_equipment_binding_revision'] = binding_revision
        work['revision'] += 1
        return replace(snapshot, works=tuple(works))
    if hasattr(threads, '_lock'):
        with threads._lock:
            threads.require_workspace(thread_id, workspace)
            threads._snapshot = change(threads._snapshot)
        return
    with threads._connect() as connection:
        row = connection.execute('SELECT * FROM capstone_threads WHERE thread_id=%s AND workspace_name=%s FOR UPDATE',
            (thread_id, workspace)).fetchone()
        if row is None:
            raise ValueError('Mission equipment Thread is unavailable')
        updated = change(threads._snapshot_from_row(row))
        connection.execute('UPDATE capstone_threads SET works=%s WHERE thread_id=%s',
            (Jsonb(list(updated.works)), thread_id))
