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
import re
import threading
from typing import NoReturn

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from .data_gateway_mcp import GatewayError, validate as validate_gateway_schema
from .grid_source_topology import REQUEST_BYTES, PAGE_BYTES, EXCHANGE_SECONDS

STREAMS = ('devices', 'ports', 'connectivity_nodes', 'connections', 'device_relations', 'groups', 'boundaries', 'issues')
SUMMARY_STREAMS = ('summary_nodes', 'summary_edges')
IDENTITY = ('model_ref', 'model_revision', 'selection_ref', 'source_snapshot_ref')
SCHEMA = 'gateway-electrical-view/1'
SCHEMA_V2 = 'gateway-electrical-view/2'
_VALIDATORS = {
    schema: Draft202012Validator(json.loads(files('capstone_agent').joinpath(
        f'resources/gateway-electrical-view-v{version}.schema.json').read_text()))
    for version, schema in ((1, SCHEMA), (2, SCHEMA_V2))
}
ERRORS = {
    'gateway_publication_changed': (409, False, 'refresh_capabilities'),
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
    'unsupported_schema': (422, False, 'choose_supported_representation'),
}


class ElectricalViewError(ValueError):
    def __init__(self, code):
        self.code = code if code in ERRORS else 'grid_electrical_observation_unavailable'
        self.status, self.retryable, self.recovery_action = ERRORS[self.code]
        super().__init__(self.code)

    def detail(self):
        return {'code': self.code, 'retryable': self.retryable, 'recovery_action': self.recovery_action}


def _invalid() -> NoReturn:
    raise ElectricalViewError('grid_electrical_response_invalid')


def _text(value, limit=2048):
    if not isinstance(value, str) or not value or len(value) > limit or any(ord(c) < 32 for c in value):
        _invalid()
    return value


def _display_name(value):
    name = _text(value)
    if not name.strip() or '\x7f' in name:
        _invalid()
    return name


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


def _validate_view(value):
    if not isinstance(value, dict) or not isinstance(value.get('schema'), str) or value['schema'] not in _VALIDATORS:
        _invalid()
    try:
        _VALIDATORS[value['schema']].validate(value)
    except ValidationError:
        _invalid()


def _streams(schema):
    return STREAMS + SUMMARY_STREAMS if schema == SCHEMA_V2 else STREAMS


def checked_electrical_request(operation, value):
    """Closed App request shape; client URLs, tools and SQL are never accepted."""
    fields = {'open': {'model_ref', 'representation', 'expected_model_revision', 'selection_ref', 'parent_view_ref',
                       'target', 'boundary_policy', 'selection_profile', 'artifact_ref', 'refresh_source', 'view_schema'},
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
            if 'view_schema' in result and result['view_schema'] not in _VALIDATORS:
                _invalid()
            if result.get('view_schema') == SCHEMA_V2 and representation != 'source_node_breaker':
                raise ElectricalViewError('unsupported_schema')
            if result.get('parent_view_ref'):
                _text(result.get('target')); _text(result.get('expected_model_revision'))
                if ('view_schema' in result or result.get('refresh_source') or
                    result.get('selection_profile') is not None or result.get('boundary_policy') is not None):
                    _invalid()
            elif result.get('target') is not None:
                _invalid()
            if representation == 'source_node_breaker' and result.get('artifact_ref') is not None:
                _invalid()
            if representation == 'calculation_bus_branch' and not result.get('parent_view_ref'):
                _text(result.get('artifact_ref'))
        elif operation == 'read':
            _text(result.get('view_ref'))
            if result.get('stream') not in STREAMS + SUMMARY_STREAMS:
                _invalid()
            result.setdefault('limit', 200)
        else:
            _text(result.get('job_ref'))
        return result
    except ElectricalViewError as error:
        if error.code in {'unsupported_representation', 'unsupported_schema'}:
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
    'summary_nodes': ('id', 'name', 'group_kind', 'expand_target', 'electrical_equivalent',
        'active_station_count', 'ownership_status', 'source_station_id', 'member_count'),
    'summary_edges': ('id', 'source_id', 'target_id', 'relation_kind', 'member_count', 'expand_target',
        'direction', 'electrical_equivalent', 'electrical_connectivity_verified'),
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
    if stream == 'devices' and 'source_endpoints' in value:
        result['source_endpoints'] = _pick(value['source_endpoints'],
            ('start_station_id', 'end_station_id', 'direction_semantics'))
        for item in result['source_endpoints'].values():
            if item is not None:
                _text(item)
    if stream == 'summary_edges' and 'source_evidence' in value:
        evidence = _pick(value['source_evidence'], ('table', 'fields'))
        if 'table' in evidence:
            _text(evidence['table'])
        if 'fields' in evidence:
            if not isinstance(evidence['fields'], list) or len(evidence['fields']) > 32:
                _invalid()
            for field in evidence['fields']:
                _text(field)
        result['source_evidence'] = evidence
    for field in ('member_count', 'active_station_count'):
        if field in result:
            _count(result[field])
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
    _validate_view(value)
    if value.get('state') != 'ready':
        _invalid()
    for key in (*IDENTITY, 'view_ref'):
        _text(value.get(key))
    if set(value['streams']) != set(_streams(value['schema'])):
        _invalid()
    streams = {}
    for stream in _streams(value['schema']):
        entry = value['streams'][stream]
        if not isinstance(entry, dict):
            _invalid()
        total = _count(entry.get('total_count'))
        expected = entry.get('read')
        if (not isinstance(expected, dict) or not isinstance(expected.get('arguments'), dict)
                or expected['arguments'].get('view_ref') != value['view_ref']
                or expected['arguments'].get('stream') != stream):
            _invalid()
        _text(expected.get('tool'))
        streams[stream] = {'total_count': total, 'read': expected}
    result = _pick(value, ('schema', 'state', *IDENTITY, 'view_ref', 'representation', 'target', 'artifact_ref',
                           'frozen_at', 'expires_at', 'issue_count', 'readiness', 'readiness_scope',
                           'default_stream', 'closure', 'electrical_equivalence_performed', 'name'))
    if 'name' in result:
        _display_name(result['name'])
    result['streams'] = streams
    if 'default_stream' in result and result['default_stream'] not in streams:
        _invalid()
    if 'overview_coverage' in value:
        coverage = _pick(value['overview_coverage'], ('active_stations', 'source_station_groups',
            'omitted_empty_station_groups', 'line_endpoint_semantics', 'dc_supported'))
        for field in ('active_stations', 'source_station_groups', 'omitted_empty_station_groups'):
            if field in coverage:
                _count(coverage[field])
        if 'dc_supported' in coverage and type(coverage['dc_supported']) is not bool:
            _invalid()
        if 'line_endpoint_semantics' in coverage:
            _text(coverage['line_endpoint_semantics'])
        if 'source_selection' in value['overview_coverage']:
            selection = _pick(value['overview_coverage']['source_selection'], ('profile', 'min_ac_kv',
                'boundary_policy', 'rule_version', 'rule_sha256', 'model_time', 'station_id'))
            for key, item in selection.items():
                if key == 'min_ac_kv':
                    if type(item) not in {int, float} or item < 0:
                        _invalid()
                elif item is not None:
                    _text(item)
            coverage['source_selection'] = selection
        result['overview_coverage'] = coverage
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
    optional = {'view_schema', 'selection_profile', 'boundary_policy', 'parent_view_ref', 'name'}
    if (not isinstance(value, dict) or not fields <= set(value) or set(value) - fields - optional or
        value['schema'] != 'capstone-electrical-view-request/1' or value['source_id'] != 'data-gateway'):
        _invalid()
    _bounded(value, REQUEST_BYTES)
    if 'name' in value:
        _display_name(value['name'])
    for key in (*IDENTITY, 'view_ref'):
        _text(value[key])
    for key in ('target', 'artifact_ref'):
        if value[key] is not None:
            _text(value[key])
    if value['representation'] not in {'source_node_breaker', 'calculation_bus_branch'}:
        _invalid()
    if 'view_schema' in value:
        if value['view_schema'] not in (SCHEMA, SCHEMA_V2):
            _invalid()
        if value['view_schema'] == SCHEMA_V2 and value['representation'] != 'source_node_breaker':
            _invalid()
    if 'selection_profile' in value:
        profile = _text(value['selection_profile'], 64)
        if not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', profile):
            _invalid()
    if 'boundary_policy' in value and value['boundary_policy'] not in ('retain_external_stub', 'internal_only'):
        _invalid()
    if 'parent_view_ref' in value:
        _text(value['parent_view_ref'])
        if value['parent_view_ref'] == value['view_ref'] or not value['target'] or set(value) & {'selection_profile', 'boundary_policy'}:
            _invalid()
    if value['representation'] == 'calculation_bus_branch' and set(value) & {'selection_profile', 'boundary_policy'}:
        _invalid()
    return deepcopy(value)


def electrical_descriptor(data, open_arguments=None):
    try:
        value = checked_manifest(data)
        arguments = {} if open_arguments is None else open_arguments
        if not isinstance(arguments, dict):
            _invalid()
        for key, field in (('view_schema', 'schema'), ('model_ref', 'model_ref'),
                           ('representation', 'representation'), ('expected_model_revision', 'model_revision'),
                           ('selection_ref', 'selection_ref'), ('target', 'target'), ('artifact_ref', 'artifact_ref')):
            if arguments.get(key) is not None and arguments[key] != value.get(field):
                _invalid()
        retained = {}
        if 'name' in value:
            retained['name'] = value['name']
        if value['schema'] == SCHEMA_V2 or arguments.get('view_schema') is not None:
            retained['view_schema'] = value['schema']
        if value.get('target') is not None:
            if arguments.get('selection_profile') is not None or arguments.get('boundary_policy') is not None:
                _invalid()
            if arguments.get('parent_view_ref') is not None:
                retained['parent_view_ref'] = arguments['parent_view_ref']
        else:
            if arguments.get('parent_view_ref') is not None:
                _invalid()
            selection = value.get('overview_coverage', {}).get('source_selection', {})
            for key, field in (('selection_profile', 'profile'), ('boundary_policy', 'boundary_policy')):
                actual, requested = selection.get(field), arguments.get(key)
                if actual is not None and requested is not None and actual != requested:
                    _invalid()
                selected = actual if actual is not None else requested
                if selected is not None:
                    retained[key] = selected
        return checked_electrical_descriptor({'schema': 'capstone-electrical-view-request/1', 'source_id': 'data-gateway',
            **{key: value[key] for key in (*IDENTITY, 'view_ref', 'representation')},
            'target': value.get('target'), 'artifact_ref': value.get('artifact_ref'), **retained})
    except (ElectricalViewError, TypeError, KeyError, AttributeError):
        return None


class ElectricalViewProvider:
    def __init__(self, gateway):
        self.gateway = gateway
        # Protected UI reads can re-admit a compatible publication without
        # rewriting the immutable catalog granted to running research tasks.
        self._catalog = deepcopy(gateway.catalog) if gateway is not None else {}
        self._refresh_lock = asyncio.Lock()
        self._views = OrderedDict()
        self._jobs = OrderedDict()
        self._page_receipts = OrderedDict()
        self._cursors = OrderedDict()
        self._lock = threading.RLock()

    def _remember(self, view, totals=None):
        identity = {key: view[key] for key in ('schema', *IDENTITY)}
        with self._lock:
            previous = self._views.get(view['view_ref'])
            if previous and any(previous[key] != identity[key] for key in identity):
                _invalid()
            entry = {**identity, 'totals': {**(previous or {}).get('totals', {}), **(totals or {})}}
            if previous and any(previous['totals'].get(key, count) != count for key, count in (totals or {}).items()):
                _invalid()
            self._views[view['view_ref']] = entry
            self._views.move_to_end(view['view_ref'])
            while len(self._views) > 256:
                self._views.popitem(last=False)

    async def _call(self, arguments, original=None, *, read=False, open_view=False):
        bindings = getattr(self.gateway, 'view_bindings', None)
        if bindings is None:
            raise ElectricalViewError('grid_electrical_unavailable')
        action = bindings.action(arguments)
        if action is None and original is not None:
            action = bindings.action(original)
        if action is None and (read or open_view):
            match = getattr(bindings, 'view_action', None)
            action = match(arguments, read=read) if match is not None else None
        if action is None:
            raise ElectricalViewError('grid_electrical_unavailable')
        tool = action['tool']
        name = tool if tool in self._catalog.get('tools', {}) else 'data_gateway_' + tool
        published = self._catalog.get('tools', {}).get(name, {})
        if (published.get('annotations', {}).get('destructiveHint') is not False
                or not isinstance(published.get('inputSchema'), dict)
                or not isinstance(self._catalog.get('tool_hashes', {}).get(name), str)):
            raise ElectricalViewError('grid_electrical_unavailable')
        try:
            validate_gateway_schema(published['inputSchema'], action['arguments'])
            async with asyncio.timeout(EXCHANGE_SECONDS):
                response = await self.gateway.client.call(name, deepcopy(action['arguments']), self._catalog)
            _bounded(response)
            content = response.get('structuredContent')
            if not isinstance(content, dict):
                _invalid()
            if response.get('isError') or content.get('status') not in {'ok', 'partial'}:
                bindings.observe(tool, action['arguments'], response, self._catalog)
                gaps = content.get('gaps')
                code = gaps[0].get('reason') if isinstance(gaps, list) and gaps and isinstance(gaps[0], dict) else None
                raise ElectricalViewError(code)
            data = content.get('data')
            if not isinstance(data, dict):
                _invalid()
            bindings.observe(tool, action['arguments'], response, self._catalog)
            return data
        except ElectricalViewError:
            raise
        except GatewayError as error:
            if str(error) == 'gateway_publication_changed':
                raise ElectricalViewError('gateway_publication_changed') from None
            raise ElectricalViewError('grid_electrical_observation_unavailable') from None
        except (TimeoutError, OSError, ValueError, TypeError, KeyError, AttributeError):
            raise ElectricalViewError('grid_electrical_observation_unavailable') from None

    async def models(self):
        bindings = getattr(self.gateway, 'view_bindings', None)
        value = bindings.discovery() if bindings is not None else None
        if value is None:
            raise ElectricalViewError('grid_electrical_unavailable')
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
        if not isinstance(capabilities, dict) or capabilities.get('schema') not in (SCHEMA, SCHEMA_V2):
            raise ElectricalViewError('grid_electrical_unavailable')
        public_capabilities = _pick(capabilities, ('schema', 'targets', 'max_page_records', 'source_coordinates',
            'computational_readiness_implied', 'source_transaction_consistency_verified', 'cache_policy', 'open_tool', 'read_tool',
            'view_schemas', 'default_view_schema', 'macro_default_view_schema', 'macro_models', 'locate_tool'))
        if 'view_schemas' in public_capabilities:
            versions = public_capabilities['view_schemas']
            if (not isinstance(versions, list) or not versions or len(versions) > len(_VALIDATORS) or
                any(not isinstance(item, str) or item not in _VALIDATORS for item in versions) or len(set(versions)) != len(versions)):
                _invalid()
        for field in ('default_view_schema', 'macro_default_view_schema'):
            if field in public_capabilities and public_capabilities[field] not in (SCHEMA, SCHEMA_V2):
                _invalid()
        if 'macro_models' in public_capabilities:
            if not isinstance(public_capabilities['macro_models'], list) or len(public_capabilities['macro_models']) > 1000:
                _invalid()
            for model_ref in public_capabilities['macro_models']:
                _text(model_ref)
        if 'locate_tool' in public_capabilities:
            _text(public_capabilities['locate_tool'])
        if 'v2' in capabilities:
            public_capabilities['v2'] = _pick(capabilities['v2'],
                ('representation', 'targets', 'streams', 'summary_semantics'))
            v2 = public_capabilities['v2']
            if v2.get('representation') != 'source_node_breaker':
                _invalid()
            for field, allowed in (('targets', {'model', 'grid', 'station', 'device', 'summary_edge', 'unresolved'}),
                                   ('streams', set(SUMMARY_STREAMS))):
                items = v2.get(field)
                if (not isinstance(items, list) or len(items) > len(allowed) or
                    any(not isinstance(item, str) or item not in allowed for item in items) or len(set(items)) != len(items)):
                    _invalid()
            if 'summary_semantics' in v2:
                _text(v2['summary_semantics'])
            if 'open_arguments' in capabilities['v2']:
                arguments = _pick(capabilities['v2']['open_arguments'], ('view_schema',))
                if arguments.get('view_schema') != SCHEMA_V2:
                    _invalid()
                public_capabilities['v2']['open_arguments'] = arguments
        if 'source_grid_root' in capabilities:
            public_capabilities['source_grid_root'] = _pick(capabilities['source_grid_root'],
                ('argument', 'source', 'default_selection_profile', 'all_available_ac_selection_profile',
                 'default_view_schema', 'omit_model_ref'))
            for field, item in public_capabilities['source_grid_root'].items():
                if field == 'omit_model_ref':
                    if type(item) is not bool:
                        _invalid()
                else:
                    _text(item)
        if 'source_grid_models' in capabilities:
            models = capabilities['source_grid_models']
            if not isinstance(models, list) or len(models) > 1000:
                _invalid()
            provincial = []
            seen_models = set()
            for model in models:
                projected_model = _pick(model, ('model_ref', 'readiness', 'name'))
                _text(projected_model.get('model_ref'))
                if 'name' in projected_model:
                    _display_name(projected_model['name'])
                if 'readiness' in projected_model:
                    _text(projected_model['readiness'])
                if projected_model['model_ref'] in seen_models:
                    _invalid()
                seen_models.add(projected_model['model_ref'])
                if 'scope' in model:
                    scope = _pick(model['scope'], ('source_instance', 'object_type', 'object_id'))
                    if set(scope) != {'source_instance', 'object_type', 'object_id'} or scope['object_type'] != 'grid':
                        _invalid()
                    for item in scope.values():
                        _text(item)
                    projected_model['scope'] = scope
                if 'open_arguments' in model:
                    arguments = _pick(model['open_arguments'], ('model_ref', 'selection_profile'))
                    if arguments.get('model_ref') != projected_model['model_ref']:
                        _invalid()
                    for item in arguments.values():
                        _text(item)
                    projected_model['open_arguments'] = arguments
                provincial.append(projected_model)
            public_capabilities['source_grid_models'] = provincial
        for kind in ('source_node_breaker', 'calculation_bus_branch', 'optimization'):
            if kind in capabilities:
                public_capabilities[kind] = _pick(capabilities[kind], ('support', 'readiness', 'consistency', 'requires'))
        result = _pick(value, ('count', 'listing_complete', 'time_basis', 'selection_rule_version', 'selection_rule_status',
            'selection_note', 'default_purpose', 'supported_purposes', 'availability', 'build_enabled', 'message', 'warning'))
        result.update(scopes=projected, electrical_views=public_capabilities)
        return result

    async def open(self, document):
        request = checked_electrical_request('open', document)
        expected_schema = request.get('view_schema', SCHEMA)
        if request.get('parent_view_ref'):
            with self._lock:
                parent = deepcopy(self._views.get(request['parent_view_ref']))
            expected_schema = parent['schema'] if parent else None
        bindings = getattr(self.gateway, 'view_bindings', None)
        restore = getattr(bindings, 'restore', None)
        value = restore(request) if restore is not None else None
        if value is None:
            value = await self._call(request, document, open_view=True)
        if value.get('model_ref') != request['model_ref']:
            _invalid()
        if expected_schema is not None and value.get('schema') != expected_schema:
            _invalid()
        if value.get('state') == 'preparing':
            _validate_view(value)
            _text(value.get('preparation_ref'))
            if 'poll_after_seconds' in value:
                _count(value['poll_after_seconds'])
            with self._lock:
                self._jobs[value['preparation_ref']] = request['model_ref']
                while len(self._jobs) > 256:
                    self._jobs.popitem(last=False)
            return _pick(value, ('schema', 'state', 'model_ref', 'preparation_ref', 'poll_after_seconds'))
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
        self._remember(result, {stream: entry['total_count'] for stream, entry in result['streams'].items()})
        return result

    async def read(self, document):
        request = checked_electrical_request('read', document)
        with self._lock:
            previous = self._views.get(request['view_ref'])
            cursor_scope = self._cursors.get(request.get('cursor'))
            if previous and request['stream'] not in _streams(previous['schema']):
                _invalid()
            if cursor_scope and cursor_scope != (request['view_ref'], request['stream']):
                raise ElectricalViewError('invalid_cursor')
        value = await self._call(request, document, read=True)
        _validate_view(value)
        for key in (*IDENTITY, 'view_ref'):
            _text(value.get(key))
        if value.get('view_ref') != request['view_ref'] or value.get('stream') != request['stream']:
            _invalid()
        records = value['records']
        total = _count(value['total_count'])
        if len(records) != value['returned_count'] or len(records) > 1000 or len(records) > total:
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
            if result['next_cursor'] is not None:
                scope = (request['view_ref'], request['stream'])
                if result['next_cursor'] in self._cursors and self._cursors[result['next_cursor']] != scope:
                    _invalid()
                self._cursors[result['next_cursor']] = scope
                self._cursors.move_to_end(result['next_cursor'])
                while len(self._cursors) > 2048:
                    self._cursors.popitem(last=False)
        return result

    async def job(self, document):
        request = checked_electrical_request('job', document)
        value = await self._call(request, document)
        if value.get('job_ref') != request['job_ref'] or value.get('task_type') != 'view_preparation' or value.get('state') not in {'queued', 'running', 'succeeded', 'failed'}:
            _invalid()
        _text(value.get('model_ref'))
        with self._lock:
            model = self._jobs.get(request['job_ref'])
        if model and model != value['model_ref']:
            _invalid()
        if value['state'] == 'succeeded':
            _text(value.get('view_ref')); _text(value.get('model_revision'))
        if value['state'] in {'queued', 'running'} and 'poll_after_seconds' in value:
            _count(value['poll_after_seconds'])
        result = _pick(value, ('job_ref', 'task_type', 'model_ref', 'state', 'stage', 'view_ref', 'model_revision', 'created_at', 'completed_at', 'expires_at', 'poll_after_seconds'))
        if value['state'] == 'failed':
            failure = value.get('error')
            reason = failure.get('reason') if isinstance(failure, dict) else None
            result['error'] = ElectricalViewError(reason).detail()
        return result
