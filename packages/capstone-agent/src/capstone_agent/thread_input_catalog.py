"""Bounded application input catalog, prepared by the registered family worker."""
from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping
import json
from pathlib import Path
from threading import RLock
from typing import cast
from urllib.request import Request, urlopen

from .runtime_resources import content_hash, resolve_resource_profile
from .thread_protocol import AttemptSnapshot


def input_catalog_document(snapshot, profiles: dict, historical: list[dict], *, family_available=False) -> dict:
    context = snapshot.active_model_context
    current = {'object_id': context.id, 'model_id': context.model_id,
               'model_revision': context.model_revision, 'implementation_family': context.implementation_family}
    objects = [current, *[item for item in historical if item['object_id'] != context.id]][:16]
    operations = []
    idle = snapshot.current_attempt is None and snapshot.run.state == 'open'
    for operation, scope, role, available, reason in (
        ('view_context', 'draft', 'application', True, None),
        ('view_topology', 'workspace', 'application', True, None),
        ('open_model', 'workspace', 'application', idle and family_available, 'model_control_unavailable'),
        ('activate_model', 'workspace', 'application', idle and family_available, 'model_control_unavailable'),
        ('close_model', 'workspace', 'application', idle and family_available, 'model_control_unavailable'),
        ('start_case_execution', 'workspace', 'harness_engine', False, 'case_capability_unavailable'),
    ):
        operations.append({'operation_id': operation, 'scope': scope, 'role': role,
            'input_schema': {'type': 'object'}, 'available': available,
            'reason': None if available else reason, 'revision': '1'})
    public = {'schema': 'capstone-thread-input-catalog/1', 'thread_id': snapshot.thread_id,
        'runtime_mode': snapshot.runtime_mode, 'context_id': context.id,
        'implementation_family': context.implementation_family,
        'selection_revision': context.selection_revision, 'resource_profiles': profiles,
        'objects': objects, 'materials': [], 'operations': operations,
        'coverage': {'full_model_tables': False, 'history': 'bounded', 'material_status': 'unavailable'}}
    return {**public, 'revision': content_hash(public)}


def with_case_availability(document: dict, availability: dict) -> dict:
    """The host that owns Case dispatch supplies its registered availability."""
    public = {key: value for key, value in document.items() if key != 'revision'}
    public['operations'] = [{**item, **availability} if item['operation_id'] == 'start_case_execution' else item
                            for item in document['operations']]
    return {**public, 'revision': content_hash(public)}


def historical_objects(service, snapshot) -> list[dict]:
    page = service.read_history(snapshot.thread_id, limit=128)
    result = {}
    for event in page['events']:
        for key in ('previous_context', 'model_context', 'restored_context'):
            value = event['payload'].get(key)
            if isinstance(value, dict) and {'id', 'model_id', 'model_revision', 'implementation_family'} <= value.keys():
                result[value['id']] = {'object_id': value['id'], **{name: value[name] for name in
                    ('model_id', 'model_revision', 'implementation_family')}}
    return list(result.values())[-15:]


def catalog_provider(service, resource_profiles, *, family_available):
    def provide(snapshot):
        return input_catalog_document(snapshot, resource_profiles(snapshot), historical_objects(service, snapshot),
            family_available=family_available(snapshot.active_model_context.implementation_family))
    return provide


def prepared_bindings(context) -> dict:
    bindings = {}
    for contribution in context.contributions:
        prepared = getattr(contribution, 'prepared', None)
        application = getattr(prepared, 'prepared_application', None)
        selected = getattr(application, 'bindings', {})
        if isinstance(selected, Mapping):
            bindings.update(selected)
    return bindings


class PreparedResourceCatalog:
    """Cache immutable profiles, never borrowed bindings. Preparation is serialized."""
    def __init__(self, owner, executor, config_root: Path):
        self.owner, self.executor, self.config_root = owner, executor, config_root
        self._lock = RLock()
        self._cache = OrderedDict()

    def __call__(self, snapshot):
        from .professional_resources import resolve_harness_resource_profile
        from .thread_service import AttemptClaim
        from .delegated_runtime import json_document
        native = {} if self.executor is None else cast(dict[str, object],
            json_document(self.executor.capability.get('resource_profiles', {})))
        if snapshot.runtime_mode == 'pi_reference' or self.owner is None or not (self.config_root / 'agent-resources.json').is_file():
            return native
        base = resolve_resource_profile(self.config_root, 'harness_engine')
        key = content_hash({'context': snapshot.active_model_context.to_document(), 'run': snapshot.run.run_id,
            'thread': snapshot.thread_id, 'configuration': base.revision})
        with self._lock:
            if key not in self._cache:
                context = snapshot.active_model_context
                claim = AttemptClaim(snapshot.thread_id, snapshot.run.run_id,
                    AttemptSnapshot('catalog', 'catalog', 'accepted', context.id), 'catalog', 'Read resource availability',
                    context.id, context.selection_revision, 'catalog', context)
                prepared = self.owner.acquire(claim)
                try:
                    profile = resolve_harness_resource_profile(self.config_root, prepared_bindings(prepared))
                    self._cache[key] = profile.document_json
                finally:
                    self.owner.release(prepared)
                while len(self._cache) > 8:
                    self._cache.popitem(last=False)
            self._cache.move_to_end(key)
            return {**native, 'harness_engine': json.loads(self._cache[key])}


class RemoteResourceCatalog:
    """Use only configured family origins and the existing private worker token."""
    def __init__(self, origins: str, operator_token: str):
        from .worker_wake import wake_token
        self._origins = {}
        for entry in origins.split(','):
            if entry.strip():
                family, separator, origin = entry.partition('=')
                if not separator or family not in {'pandapower', 'pypsa'}:
                    raise ValueError('worker resource family configuration is invalid')
                self._origins[family] = origin.rstrip('/')
        self._token = wake_token(operator_token)

    def __call__(self, snapshot):
        origin = self._origins.get(snapshot.active_model_context.implementation_family)
        if origin is None:
            return {}
        request = Request(origin + '/threads/' + snapshot.thread_id + '/input-resources',
                          headers={'Authorization': 'Bearer ' + self._token})
        try:
            with urlopen(request, timeout=30) as response:
                raw = response.read(131073)
            if len(raw) > 131072:
                raise ValueError('resource projection is too large')
            document = json.loads(raw)
            if document.get('implementation_family') != snapshot.active_model_context.implementation_family or document['context_id'] != snapshot.active_model_context.id or document['selection_revision'] != snapshot.active_model_context.selection_revision:
                raise ValueError('worker resource context changed')
            return document['resource_profiles']
        except Exception:
            return {}  # Bounded unavailable state; no private endpoint or token in errors.
