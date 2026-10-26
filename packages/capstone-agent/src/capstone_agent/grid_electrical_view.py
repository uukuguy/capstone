"""Protected, bounded application projection of published frozen electrical views.

The gateway owns model identities, captures and signed cursors. This adapter
never fetches additional streams or starts a solver. A captured nontransactional
source is supported; it is not upgraded to a verified transaction snapshot.
"""
import asyncio
from collections import OrderedDict
from copy import deepcopy
from importlib.resources import files
import json
import hashlib
import threading

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from .data_gateway_mcp import GatewayError
from .grid_source_topology import REQUEST_BYTES, PAGE_BYTES, EXCHANGE_SECONDS

STREAMS = ('devices', 'ports', 'connectivity_nodes', 'connections', 'device_relations', 'groups', 'boundaries', 'issues')
IDENTITY = ('model_ref', 'model_revision', 'selection_ref', 'source_snapshot_ref')
SCHEMA = 'gateway-electrical-view/1'
_SCHEMA = json.loads(files('capstone_agent').joinpath('resources/gateway-electrical-view-v1.schema.json').read_text())
_VALIDATOR = Draft202012Validator(_SCHEMA)
ERRORS = {
    'revision_mismatch': (409, False, 'reopen_view'), 'invalid_cursor': (409, False, 'restart_stream'),
    'view_expired': (410, False, 'reopen_view'), 'unsupported_representation': (422, False, 'choose_supported_representation'),
    'unknown_model': (404, False, 'discover_models'), 'invalid_view_ref': (400, False, 'reopen_view'),
    'invalid_target': (400, False, 'choose_returned_target'), 'invalid_view_request': (400, False, 'correct_request'),
    'unsupported_stream': (400, False, 'choose_manifest_stream'), 'invalid_page_budget': (400, False, 'correct_request'),
    'source_not_connected': (503, True, 'reconnect_source'), 'view_budget_exceeded': (429, True, 'retry_later'),
    'artifact_not_ready': (409, False, 'inspect_artifact'), 'artifact_integrity_error': (409, False, 'inspect_artifact'),
    'artifact_required': (400, False, 'inspect_artifact'), 'element_map_unavailable': (409, False, 'inspect_artifact'),
    'model_not_calculation_ready': (409, False, 'inspect_artifact'),
    'grid_electrical_unavailable': (503, True, 'refresh_capabilities'),
    'grid_electrical_request_invalid': (400, False, 'correct_request'),
    'grid_electrical_response_invalid': (502, False, 'refresh_capabilities'),
    'grid_electrical_observation_unavailable': (503, True, 'retry_later'),
    'view_preparation_failed': (503, False, 'inspect_issues'),
}


class ElectricalViewError(ValueError):
    def __init__(self, code):
        self.code = code if code in ERRORS else 'grid_electrical_observation_unavailable'
        self.status, self.retryable, self.recovery_action = ERRORS[self.code]
        super().__init__(self.code)

    def detail(self):
        return {'code': self.code, 'retryable': self.retryable, 'recovery_action': self.recovery_action}


def _invalid():
    raise ElectricalViewError('grid_electrical_response_invalid')


def _text(value, limit=2048):
    if not isinstance(value, str) or not value or len(value) > limit or any(ord(c) < 32 for c in value):
        _invalid()
    return value


def _count(value):
    if type(value) is not int or not 0 <= value <= 2**53 - 1:
        _invalid()
    return value


def _bounded(value, budget=PAGE_BYTES):
    try:
        if len(json.dumps(value, allow_nan=False).encode()) > budget:
            _invalid()
    except (TypeError, ValueError, RecursionError):
        _invalid()


def checked_electrical_request(operation, value):
    """Closed App request shape; client URLs, tools and SQL are never accepted."""
    fields = {'open': {'model_ref', 'representation', 'expected_model_revision', 'selection_ref', 'parent_view_ref',
                       'target', 'boundary_policy', 'selection_profile', 'artifact_ref', 'refresh_source'},
              'read': {'view_ref', 'stream', 'cursor', 'limit'}, 'job': {'job_ref'}}
    try:
        if operation not in fields or not isinstance(value, dict) or set(value) - fields[operation]:
            _invalid()
        _bounded(value, REQUEST_BYTES)
        result = deepcopy(value)
        for key, item in result.items():
            if key == 'refresh_source':
                if type(item) is not bool:
                    _invalid()
            elif key == 'limit':
                if not 1 <= _count(item) <= 1000:
                    _invalid()
            elif item is not None:
                _text(item)
        if operation == 'open':
            _text(result.get('model_ref'))
            representation = result.setdefault('representation', 'source_node_breaker')
            if representation not in {'source_node_breaker', 'calculation_bus_branch'}:
                raise ElectricalViewError('unsupported_representation')
            if result.get('parent_view_ref'):
                _text(result.get('target')); _text(result.get('expected_model_revision'))
                if result.get('refresh_source') or result.get('selection_profile') is not None or result.get('boundary_policy') is not None:
                    _invalid()
            elif result.get('target') is not None:
                _invalid()
            if representation == 'source_node_breaker' and result.get('artifact_ref') is not None:
                _invalid()
            if representation == 'calculation_bus_branch' and not result.get('parent_view_ref'):
                _text(result.get('artifact_ref'))
        elif operation == 'read':
            _text(result.get('view_ref'))
            if result.get('stream') not in STREAMS:
                _invalid()
            result.setdefault('limit', 200)
        else:
            _text(result.get('job_ref'))
        return result
    except ElectricalViewError as error:
        if error.code == 'unsupported_representation':
            raise
        raise ElectricalViewError('grid_electrical_request_invalid') from None


def _pick(value, fields):
    if not isinstance(value, dict):
        _invalid()
    return {key: deepcopy(value[key]) for key in fields if key in value}


SOURCE_FIELDS = ('object_id', 'source_instance', 'table', 'field', 'row_sha256', 'occurrence', 'element_key', 'model_ref', 'artifact_ref')
COMMON = ('id', 'kind', 'name', 'source_kind', 'legacy_object_ref', 'quality_refs', 'station_refs', 'source_station_ids', 'element_key', 'source_refs')
RECORD_FIELDS = {
    'devices': COMMON + ('in_service', 'switch_position'),
    'ports': COMMON + ('device_id', 'identity_origin', 'role', 'sequence', 'source_slot', 'rule_version'),
    'connectivity_nodes': COMMON + ('nominal_kv', 'ownership', 'source_record_present', 'voltage_origin'),
    'connections': COMMON + ('port_id', 'connectivity_node_id'),
    'device_relations': COMMON + ('parent_id', 'child_id', 'child_stream', 'electrical_connection'),
    'groups': COMMON + ('member_count', 'expand_target', 'electrical_equivalent', 'membership_basis', 'parent_id'),
    'boundaries': COMMON + ('port_id', 'device_id', 'reason', 'identity_retained'),
    'issues': ('id', 'code', 'subject_ref', 'evidence'),
}


def _record(stream, value):
    result = _pick(value, RECORD_FIELDS[stream])
    for key, item in result.items():
        if key in {'in_service', 'switch_position', 'ownership', 'evidence'}:
            continue
        if isinstance(item, list):
            if key not in {'quality_refs', 'station_refs', 'source_station_ids', 'source_refs'} or len(item) > 1000:
                _invalid()
            for ref in item:
                _text(ref)
        elif item is not None and type(item) not in {str, int, float, bool}:
            _invalid()
        elif isinstance(item, str):
            _text(item)
    if isinstance(value.get('source_ref'), dict):
        result['source_ref'] = _pick(value['source_ref'], SOURCE_FIELDS)
        if any(item is not None and type(item) not in {str, int} for item in result['source_ref'].values()):
            _invalid()
    for key in ('in_service', 'switch_position'):
        if key in result:
            state = _pick(result[key], ('value', 'verified', 'observed_at', 'origin'))
            if type(state.get('verified')) is not bool:
                _invalid()
            if key == 'switch_position' and state.get('value') not in {'open', 'closed', 'unknown'}:
                _invalid()
            if any(item is not None and type(item) not in {str, int, float, bool} for item in state.values()):
                _invalid()
            result[key] = state
    if 'ownership' in result:
        result['ownership'] = _pick(result['ownership'], ('basis', 'station_refs', 'status'))
        for ref in result['ownership'].get('station_refs', []):
            _text(ref)
    if isinstance(result.get('evidence'), dict):
        # Gateway issues may include the original topology row. Project only
        # connection evidence, not arbitrary row columns or upstream metadata.
        result['evidence'] = _pick(result['evidence'], ('ID', 'FIRST_NODE_ID', 'SECOND_NODE_ID', 'source_id', 'count'))
        if any(item is not None and type(item) not in {str, int} for item in result['evidence'].values()):
            _invalid()
    elif isinstance(result.get('evidence'), list):
        if len(result['evidence']) > 1000:
            _invalid()
        for ref in result['evidence']:
            _text(ref)
    elif result.get('evidence') is not None:
        _text(result['evidence'])
    return result


def checked_manifest(value):
    _bounded(value)
    try:
        _VALIDATOR.validate(value)
    except ValidationError:
        _invalid()
    if value.get('state') != 'ready':
        _invalid()
    for key in (*IDENTITY, 'view_ref'):
        _text(value.get(key))
    if set(value['streams']) != set(STREAMS):
        _invalid()
    streams = {}
    for stream in STREAMS:
        entry = value['streams'][stream]
        if not isinstance(entry, dict):
            _invalid()
        total = _count(entry.get('total_count'))
        expected = {'tool': 'read_network_model_view', 'arguments': {'view_ref': value['view_ref'], 'stream': stream}}
        if entry.get('read') != expected:
            _invalid()
        streams[stream] = {'total_count': total, 'read': expected}
    result = _pick(value, ('schema', 'state', *IDENTITY, 'view_ref', 'representation', 'target', 'artifact_ref',
                           'frozen_at', 'expires_at', 'issue_count', 'readiness', 'readiness_scope',
                           'default_stream', 'closure', 'electrical_equivalence_performed'))
    result['streams'] = streams
    for key in ('capture', 'last_source_read'):
        if key in value:
            result[key] = _pick(value[key], ('change_detection', 'read_started_at', 'read_completed_at',
                                              'source_transaction_consistency_verified'))
    if type(result['capture'].get('source_transaction_consistency_verified')) is not bool:
        _invalid()
    if isinstance(value.get('source_manifest'), dict):
        result['source_manifest'] = _pick(value['source_manifest'], ('consistency', 'metadata_snapshot', 'missing_tables', 'source_instance'))
    if isinstance(value.get('derivation'), dict):
        result['derivation'] = _pick(value['derivation'], ('artifact_ref', 'model_revision', 'source_snapshot_ref',
            'selection_ref', 'purpose', 'demo_only', 'target_format', 'engine', 'engine_version', 'element_map_sha256',
            'artifact_revision', 'scenario_revision', 'mapping_rule_version', 'operating_scenario_verified'))
        if isinstance(value['derivation'].get('quality'), dict):
            result['derivation']['quality'] = _pick(value['derivation']['quality'], ('power_flow_ready', 'real_power_flow_ready', 'demo_only', 'blocking_reasons'))
    return result


def checked_electrical_descriptor(value):
    fields = {'schema', 'source_id', *IDENTITY, 'view_ref', 'representation', 'target', 'artifact_ref'}
    if not isinstance(value, dict) or set(value) != fields or value['schema'] != 'capstone-electrical-view-request/1' or value['source_id'] != 'data-gateway':
        _invalid()
    for key in (*IDENTITY, 'view_ref'):
        _text(value[key])
    for key in ('target', 'artifact_ref'):
        if value[key] is not None:
            _text(value[key])
    if value['representation'] not in {'source_node_breaker', 'calculation_bus_branch'}:
        _invalid()
    return deepcopy(value)


def electrical_descriptor(data):
    try:
        value = checked_manifest(data)
        return checked_electrical_descriptor({'schema': 'capstone-electrical-view-request/1', 'source_id': 'data-gateway',
            **{key: value[key] for key in (*IDENTITY, 'view_ref', 'representation')},
            'target': value.get('target'), 'artifact_ref': value.get('artifact_ref')})
    except (ElectricalViewError, TypeError, KeyError, AttributeError):
        return None


class ElectricalViewProvider:
    def __init__(self, gateway):
        self.gateway = gateway
        self._views = OrderedDict()
        self._jobs = OrderedDict()
        self._page_receipts = OrderedDict()
        self._lock = threading.RLock()

    def _remember(self, view, totals=None):
        identity = {key: view[key] for key in IDENTITY}
        with self._lock:
            previous = self._views.get(view['view_ref'])
            if previous and any(previous[key] != identity[key] for key in IDENTITY):
                _invalid()
            entry = {**identity, 'totals': {**(previous or {}).get('totals', {}), **(totals or {})}}
            if previous and any(previous['totals'].get(key, count) != count for key, count in (totals or {}).items()):
                _invalid()
            self._views[view['view_ref']] = entry
            self._views.move_to_end(view['view_ref'])
            while len(self._views) > 256:
                self._views.popitem(last=False)

    async def _call(self, tool, arguments):
        if self.gateway is None:
            raise ElectricalViewError('grid_electrical_unavailable')
        name = 'data_gateway_' + tool
        catalog = self.gateway.catalog
        published = catalog.get('tools', {}).get(name, {})
        annotations = published.get('annotations', {})
        if (annotations.get('destructiveHint') is not False or
            annotations.get('readOnlyHint') is not (tool != 'open_network_model_view') or
            not isinstance(published.get('inputSchema'), dict) or
            not isinstance(catalog.get('tool_hashes', {}).get(name), str)):
            raise ElectricalViewError('grid_electrical_unavailable')
        try:
            async with asyncio.timeout(EXCHANGE_SECONDS):
                response = await self.gateway.client.call(name, arguments, catalog)
            _bounded(response)
            content = response.get('structuredContent')
            if not isinstance(content, dict):
                _invalid()
            if response.get('isError') or content.get('status') not in {'ok', 'partial'}:
                gaps = content.get('gaps')
                code = gaps[0].get('reason') if isinstance(gaps, list) and gaps and isinstance(gaps[0], dict) else None
                raise ElectricalViewError(code)
            data = content.get('data')
            if not isinstance(data, dict):
                _invalid()
            return data
        except ElectricalViewError:
            raise
        except (GatewayError, TimeoutError, OSError, ValueError, TypeError, KeyError, AttributeError):
            raise ElectricalViewError('grid_electrical_observation_unavailable') from None

    async def models(self):
        value = await self._call('discover_network_models', {'detail': False})
        scopes = value.get('scopes')
        if not isinstance(scopes, list) or len(scopes) > 1000 or value.get('count') != len(scopes):
            _invalid()
        projected = []
        seen = set()
        for scope in scopes:
            if not isinstance(scope, dict):
                _invalid()
            _text(scope.get('model_ref')); _text(scope.get('scope_id')); _text(scope.get('name'))
            if scope['model_ref'] in seen:
                _invalid()
            seen.add(scope['model_ref'])
            projected.append(_pick(scope, ('scope_id', 'model_ref', 'model_revision', 'name', 'coverage', 'selection_profile', 'min_ac_kv', 'readiness')))
        capabilities = value.get('electrical_views')
        if not isinstance(capabilities, dict) or capabilities.get('schema') != SCHEMA:
            raise ElectricalViewError('grid_electrical_unavailable')
        public_capabilities = _pick(capabilities, ('schema', 'targets', 'max_page_records', 'source_coordinates',
            'computational_readiness_implied', 'source_transaction_consistency_verified', 'cache_policy', 'open_tool', 'read_tool'))
        for kind in ('source_node_breaker', 'calculation_bus_branch', 'optimization'):
            if kind in capabilities:
                public_capabilities[kind] = _pick(capabilities[kind], ('support', 'readiness', 'consistency', 'requires'))
        result = _pick(value, ('count', 'listing_complete', 'time_basis', 'selection_rule_version', 'selection_rule_status',
            'selection_note', 'default_purpose', 'supported_purposes', 'availability', 'build_enabled', 'message', 'warning'))
        result.update(scopes=projected, electrical_views=public_capabilities)
        return result

    async def open(self, document):
        request = checked_electrical_request('open', document)
        value = await self._call('open_network_model_view', request)
        if value.get('model_ref') != request['model_ref']:
            _invalid()
        if value.get('state') == 'preparing':
            try:
                _VALIDATOR.validate(value)
            except ValidationError:
                _invalid()
            _text(value.get('preparation_ref'))
            with self._lock:
                self._jobs[value['preparation_ref']] = request['model_ref']
                while len(self._jobs) > 256:
                    self._jobs.popitem(last=False)
            return _pick(value, ('schema', 'state', 'model_ref', 'preparation_ref'))
        result = checked_manifest(value)
        if result['representation'] != request['representation']:
            _invalid()
        for key, requested in [('model_revision', request.get('expected_model_revision')), ('selection_ref', request.get('selection_ref')),
                               ('target', request.get('target')), ('artifact_ref', request.get('artifact_ref'))]:
            if (requested is not None or key == 'target') and result.get(key) != requested:
                _invalid()
        if request.get('parent_view_ref'):
            with self._lock:
                parent = self._views.get(request['parent_view_ref'])
            if parent and any(parent[key] != result[key] for key in IDENTITY):
                _invalid()
        self._remember(result, {stream: result['streams'][stream]['total_count'] for stream in STREAMS})
        return result

    async def read(self, document):
        request = checked_electrical_request('read', document)
        value = await self._call('read_network_model_view', request)
        try:
            _VALIDATOR.validate(value)
        except ValidationError:
            _invalid()
        for key in (*IDENTITY, 'view_ref'):
            _text(value.get(key))
        if value.get('view_ref') != request['view_ref'] or value.get('stream') != request['stream']:
            _invalid()
        records = value['records']
        total = _count(value['total_count'])
        if len(records) != value['returned_count'] or len(records) > request['limit'] or len(records) > total:
            _invalid()
        if len({item['id'] for item in records}) != len(records):
            _invalid()
        if value['complete'] != (value['next_cursor'] is None):
            _invalid()
        if value['next_cursor'] is not None:
            _text(value['next_cursor'])
            if not records or value['next_cursor'] == request.get('cursor'):
                _invalid()
        if not request.get('cursor') and value['complete'] and len(records) != total:
            _invalid()
        self._remember(value, {value['stream']: total})
        result = _pick(value, ('schema', *IDENTITY, 'view_ref', 'stream', 'returned_count', 'total_count', 'next_cursor', 'complete'))
        result['records'] = [_record(value['stream'], item) for item in records]
        receipt = hashlib.sha256(json.dumps(result, sort_keys=True, allow_nan=False).encode()).hexdigest()
        key = (request['view_ref'], request['stream'], request.get('cursor'), request['limit'])
        with self._lock:
            if key in self._page_receipts and self._page_receipts[key] != receipt:
                _invalid()
            self._page_receipts[key] = receipt
            self._page_receipts.move_to_end(key)
            while len(self._page_receipts) > 2048:
                self._page_receipts.popitem(last=False)
        return result

    async def job(self, document):
        request = checked_electrical_request('job', document)
        value = await self._call('get_network_model_job', request)
        if value.get('job_ref') != request['job_ref'] or value.get('task_type') != 'view_preparation' or value.get('state') not in {'queued', 'running', 'succeeded', 'failed'}:
            _invalid()
        _text(value.get('model_ref'))
        with self._lock:
            model = self._jobs.get(request['job_ref'])
        if model and model != value['model_ref']:
            _invalid()
        if value['state'] == 'succeeded':
            _text(value.get('view_ref')); _text(value.get('model_revision'))
        result = _pick(value, ('job_ref', 'task_type', 'model_ref', 'state', 'stage', 'view_ref', 'model_revision', 'created_at', 'completed_at', 'expires_at'))
        if value['state'] == 'failed':
            failure = value.get('error')
            reason = failure.get('reason') if isinstance(failure, dict) else None
            result['error'] = ElectricalViewError(reason).detail()
        return result
