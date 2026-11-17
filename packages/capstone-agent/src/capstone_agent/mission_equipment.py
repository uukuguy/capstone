"""Resolve Mission equipment only from the selected native registry."""
from copy import deepcopy
from dataclasses import replace
from psycopg.types.json import Jsonb

from capstone_control.service import fingerprint
from capstone_control.mission import references


def registry_revision(binding):
    from .native_mission import registry_revision as registered_revision
    return registered_revision(binding)


def catalog(threads, workspace, origin):
    binding, _ = origin_binding(threads, workspace, origin)
    return _catalog(binding)


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
        return ref in catalog(threads, workspace, origin)
    except (ValueError, KeyError):
        return False


def resolve(threads, workspace, origin, equipment, restrictions):
    return resolve_admission(threads, workspace, origin, equipment, restrictions)[0]


def resolve_admission(threads, workspace, origin, equipment, restrictions):
    equipment, restrictions = references(equipment), references(restrictions)
    binding, source = origin_binding(threads, workspace, origin)
    published = _catalog(binding)
    if any(ref not in published for ref in equipment + restrictions):
        raise ValueError('Mission equipment revision is unavailable')
    if any(ref['kind'] == 'resource_profile' for ref in restrictions):
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
