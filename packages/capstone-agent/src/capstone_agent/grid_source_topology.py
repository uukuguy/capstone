"""Application-owned source display provider, separate from calculation models.

Only the protected host owns this provider. Its public projections contain no
MCP connection, raw tool catalog, credentials, or calculation-model handles.
"""
from copy import deepcopy
import asyncio
import json
import math
import re
from typing import NoReturn

from .data_gateway_mcp import GatewayError


SOURCE_ID = 'data-gateway'
PAGE_LIMIT = 1000
REQUEST_BYTES = 16 * 1024
PAGE_BYTES = 4 * 1024 * 1024
EXCHANGE_SECONDS = 45
LEVELS = {'region', 'station', 'equipment'}
TOOLS = {'discover_region_scopes', 'resolve_region_scope', 'get_network_topology_view'}


class GridSourceError(ValueError):
    """Fixed public error codes only; never include upstream exception text."""


def _invalid() -> NoReturn:
    raise GridSourceError('grid_source_response_invalid')


def _text(value, bound=512) -> str:
    if (not isinstance(value, str) or not value or len(value) > bound
            or any(ord(c) < 32 for c in value)):
        _invalid()
    return value


def _integer(value) -> int:
    if type(value) is not int or not 0 <= value <= 2**53 - 1:
        _invalid()
    return value


def _strings(value, bound=10000):
    if not isinstance(value, list) or len(value) > bound:
        _invalid()
    return [_text(item, 2048) for item in value]


def _metadata(value, fields):
    if not isinstance(value, dict):
        _invalid()
    result = {}
    for name in fields:
        if name not in value:
            continue
        item = value[name]
        if name in {'statistical_basis_required_separately', 'data_coverage_verified',
                    'electrical_model_complete', 'measurement_availability_verified'} and type(item) is not bool:
            _invalid()
        if name in {'min_ac_kv', 'voltage_kv', 'vn_kv', 'member_count'} and item is not None:
            if type(item) not in {int, float} or not math.isfinite(item) or item < 0:
                _invalid()
            if name == 'member_count':
                _integer(item)
        if item is None or type(item) is bool:
            result[name] = item
        elif isinstance(item, str):
            result[name] = _text(item, 2048)
        elif type(item) in {int, float} and math.isfinite(item):
            result[name] = item
        else:
            _invalid()
    return result


def _scope(value):
    if not isinstance(value, dict):
        _invalid()
    result = _metadata(value, ('scope_id', 'name', 'definition_version', 'definition_authority',
        'source_root_grid_id', 'membership_rule', 'statistical_basis',
        'statistical_basis_required_separately', 'data_coverage_verified', 'electrical_model_complete'))
    for name in ('scope_id', 'name', 'definition_version'):
        _text(result.get(name))
    if 'limitations' in value:
        result['limitations'] = _strings(value['limitations'], 128)
    if 'members' in value:
        if not isinstance(value['members'], list) or len(value['members']) > 128:
            _invalid()
        result['members'] = [_metadata(member, ('region_id', 'name', 'source_grid_id',
                                              'source_special_region_code')) for member in value['members']]
    return result


def _gaps(value):
    if not isinstance(value, list) or len(value) > 256:
        _invalid()
    result = []
    for item in value:
        if isinstance(item, str):
            result.append(_text(item, 2048))
        elif isinstance(item, dict):
            gap = {'reason': _text(item.get('reason')), 'message': _text(item.get('message'), 2048)}
            if item.get('data_ref') is not None:
                gap['data_ref'] = _text(item['data_ref'])
            result.append(gap)
        else:
            _invalid()
    return result


def _topology_gaps(value):
    # Raw views publish device-level topology omissions, not Result Gap
    # messages. Retain source IDs/reasons without manufacturing descriptions.
    # The completed public page is also capped by PAGE_BYTES below.
    if not isinstance(value, list) or len(value) > 100000:
        _invalid()
    result = []
    for item in value:
        if isinstance(item, dict) and set(item) == {'id', 'reason'}:
            result.append({'id': _text(item['id']), 'reason': _text(item['reason'])})
        else:
            result.extend(_gaps([item]))
    return result


def _scope_definitions(data):
    """Project the published definition dictionary, not a data-coverage claim."""
    if not isinstance(data, dict):
        _invalid()
    result: dict[str, object] = {'schema': 'capstone-grid-source-definitions/1',
              'definition_version': _text(data.get('definition_version')),
              'scope': _text(data.get('scope'))}
    all_scopes = []
    for key in ('regions', 'groups'):
        records = data.get(key)
        if not isinstance(records, list) or len(records) > 128:
            _invalid()
        projected = [_scope(record) for record in records]
        result[key] = projected
        all_scopes.extend(projected)
    scope_ids = {scope['scope_id'] for scope in all_scopes}
    if len(scope_ids) != len(all_scopes):
        _invalid()
    aliases = data.get('aliases')
    if not isinstance(aliases, dict) or len(aliases) > 512:
        _invalid()
    projected_aliases = {_text(name): _text(target) for name, target in aliases.items()}
    result['aliases'] = projected_aliases
    if any(target not in scope_ids for target in projected_aliases.values()):
        _invalid()
    result['not_aliases'] = _strings(data.get('not_aliases'), 256)
    bases = data.get('statistical_basis_values')
    if not isinstance(bases, list) or len(bases) > 64:
        _invalid()
    result['statistical_basis_values'] = [
        {'code': _text(item.get('code')), 'name': _text(item.get('name'))}
        if isinstance(item, dict) else _invalid() for item in bases]
    for key in ('statistical_basis_evidence', 'historical_adjustments'):
        result[key] = _text(data.get(key), 2048)
    return result, all_scopes


def checked_topology_request(document):
    allowed = {'scope_id', 'level', 'selected_object_id', 'voltage_min_kv',
               'node_offset', 'edge_offset', 'limit', 'expected_view_ref'}
    try:
        if not isinstance(document, dict) or set(document) - allowed:
            _invalid()
        request = {'scope_id': _text(document.get('scope_id')), 'level': document.get('level', 'region'),
            'selected_object_id': document.get('selected_object_id'),
            'voltage_min_kv': document.get('voltage_min_kv'),
            'node_offset': _integer(document.get('node_offset', 0)),
            'edge_offset': _integer(document.get('edge_offset', 0)),
            'limit': _integer(document.get('limit', 200)),
            'expected_view_ref': document.get('expected_view_ref')}
        if (request['level'] is not None and request['level'] not in LEVELS) or not 1 <= request['limit'] <= PAGE_LIMIT:
            _invalid()
        for key in ('selected_object_id', 'expected_view_ref'):
            if request[key] is not None:
                _text(request[key])
        if request['level'] in {'station', 'equipment'} and request['selected_object_id'] is None:
            _invalid()
        if request['level'] is None and request['selected_object_id'] is not None:
            _invalid()
        voltage = request['voltage_min_kv']
        if voltage is not None and (type(voltage) not in {int, float} or not math.isfinite(voltage) or voltage < 0):
            _invalid()
        if (request['node_offset'] or request['edge_offset']) and request['expected_view_ref'] is None:
            _invalid()
        if len(json.dumps(request, allow_nan=False).encode()) > REQUEST_BYTES:
            _invalid()
        return request
    except (GridSourceError, TypeError, ValueError):
        raise GridSourceError('grid_source_request_invalid') from None


def _element(value, edge=False):
    if not isinstance(value, dict):
        _invalid()
    kind = _text(value.get('kind'), 64)
    result: dict[str, object] = {'id': _text(value.get('id')), 'kind': kind}
    if not re.fullmatch(r'[a-z][a-z0-9_:-]*', kind):
        _invalid()
    result.update(_metadata(value, ('source_id', 'source_table', 'voltage_kv', 'vn_kv',
                                   'member_count', 'equipment_type')))
    if isinstance(value.get('label'), str):
        label = ' '.join(value['label'].split())
        if label and len(label) <= 2048 and not any(ord(char) < 32 for char in label):
            result['label'] = label
    for key in ('parent_id', 'station_id'):
        if key in value:
            result[key] = None if value[key] is None else _text(value[key])
    if 'boundary' in value:
        if type(value['boundary']) is not bool:
            _invalid()
        result['boundary'] = value['boundary']
    if edge:
        result.update(source=_text(value.get('source')), target=_text(value.get('target')))
    if 'expand' in value and value['expand'] is not None:
        expand = value['expand']
        if not isinstance(expand, dict) or expand.get('level') not in LEVELS:
            _invalid()
        result['expand'] = {'level': expand['level'], 'selected_object_id': _text(expand.get('selected_object_id'))}
    if 'member_ids' in value:
        result['member_ids'] = _strings(value['member_ids'], PAGE_LIMIT)
    return result


def topology_page(data, request, *, catalog_revision, tool_schema_sha256, status, gaps, provenance):
    if not isinstance(data, dict):
        _invalid()
    view_ref = _text(data.get('view_ref'))
    if request['expected_view_ref'] is not None and view_ref != request['expected_view_ref']:
        raise GridSourceError('grid_source_view_changed')
    scope = _scope(data.get('scope'))
    grouped = request['level'] is not None
    if ('level' not in data or scope['scope_id'] != request['scope_id'] or data.get('level') != request['level']
            or data.get('selected_object_id') != request['selected_object_id']
            or data.get('display_grouping_only') is not grouped
            or data.get('electrical_equivalence_performed') is not False):
        _invalid()
    selection = _metadata(data.get('selection'), ('profile', 'min_ac_kv', 'rule_version', 'rule_sha256',
                                                 'boundary_policy', 'station_id', 'model_time'))
    if request['voltage_min_kv'] is not None and selection.get('min_ac_kv') != request['voltage_min_kv']:
        _invalid()
    snapshot = _metadata(data.get('source_snapshot'), ('metadata_snapshot', 'source_instance',
        'source_nature', 'data_backend', 'database_driver', 'measurement_availability_verified'))
    _text(snapshot.get('metadata_snapshot'))
    result = {'schema': 'capstone-grid-source-topology/1', 'source_id': SOURCE_ID,
        'catalog_revision': catalog_revision, 'tool_schema_sha256': tool_schema_sha256,
        'status': status, 'view_ref': view_ref, 'source_instance': _text(data.get('source_instance')),
        'scope': scope, 'selection': selection, 'source_snapshot': snapshot,
        'level': request['level'], 'selected_object_id': request['selected_object_id'],
        'display_grouping_only': grouped, 'electrical_equivalence_performed': False,
        'coordinate_system': 'schematic',
        'boundary_object_ids': _strings(data.get('boundary_object_ids')),
        'source_gaps': _strings(data.get('source_gaps'), 256),
        'gaps': _gaps(gaps) + _topology_gaps(data.get('gaps', [])),
        'provenance': _metadata(provenance, ('request_id', 'queried_at', 'source_instance',
            'metadata_snapshot', 'source_nature', 'data_backend', 'database_driver',
            'measurement_availability_verified'))}
    for stream in ('node', 'edge'):
        rows = data.get(stream + 's')
        if not isinstance(rows, list) or len(rows) > request['limit']:
            _invalid()
        source_rows = rows
        rows = [_element(row, edge=stream == 'edge') for row in source_rows]
        for original, projected in zip(source_rows, rows):
            if original.get('label') is not None and 'label' not in projected:
                result['gaps'].append({'id': projected['id'], 'reason': 'source_label_unpresentable'})
        if len({row['id'] for row in rows}) != len(rows):
            _invalid()
        total = _integer(data.get('total_' + stream + 's'))
        offset = _integer(data.get(stream + '_offset'))
        following = data.get('next_' + stream + '_offset')
        if offset != request[stream + '_offset'] or offset > total or offset + len(rows) > total:
            _invalid()
        if following is None:
            if offset + len(rows) != total:
                _invalid()
        elif _integer(following) != offset + len(rows) or not offset < following < total:
            _invalid()
        result.update({stream + 's': rows, 'total_' + stream + 's': total,
                       stream + '_offset': offset, 'next_' + stream + '_offset': following})
    result['complete'] = result['next_node_offset'] is None and result['next_edge_offset'] is None
    # Edges can refer to a node in another page. Preserve their source IDs;
    # clients keep unresolved endpoints until the node stream is complete.
    if len(json.dumps(result, allow_nan=False).encode()) > PAGE_BYTES:
        _invalid()
    return result


def checked_source_view_request(value):
    """A bounded display request, never a model binding or evidence grant."""
    fields = {'schema', 'source_id', 'scope_id', 'scope_name', 'level', 'selected_object_id',
              'view_ref', 'source_snapshot', 'voltage_min_kv', 'display_grouping_only'}
    if (not isinstance(value, dict) or set(value) != fields
            or value['schema'] != 'capstone-grid-source-view-request/1' or value['source_id'] != SOURCE_ID):
        _invalid()
    checked_topology_request({key: value[key] for key in
        ('scope_id', 'level', 'selected_object_id', 'voltage_min_kv')})
    _text(value['scope_name'])
    _text(value['view_ref'])
    if value['display_grouping_only'] is not (value['level'] is not None):
        _invalid()
    snapshot = value['source_snapshot']
    if not isinstance(snapshot, dict) or set(snapshot) != {'metadata_snapshot', 'source_instance'}:
        _invalid()
    for text in snapshot.values():
        _text(text)
    return deepcopy(value)


def source_view_from_gateway_result(result, arguments):
    """Optional projection of an already host-verified gateway observation.

    Receipt and original argument verification belong to the caller.
    An unpresentable page omits this hint without failing the business result.
    """
    try:
        text = result['content'][0]['text']
        if not isinstance(text, str) or len(text.encode()) > PAGE_BYTES * 2:
            return None
        def invalid_constant(_value):
            raise ValueError('invalid JSON constant')
        upstream = json.loads(text, parse_constant=invalid_constant)
        content = upstream.get('structuredContent')
        if upstream.get('isError') or not isinstance(content, dict) or content.get('status') not in {'ok', 'partial'}:
            return None
        data = content['data']
        # The gateway defaults to the raw view; the public display API defaults
        # to region. Bind that default explicitly, but never infer selectors
        # from effective selection metadata (None and 330 have distinct hashes).
        request = checked_topology_request({**arguments, 'level': arguments.get('level')})
        page = topology_page(data, request, catalog_revision=result['details']['catalog_revision'],
            tool_schema_sha256=result['details']['tool_schema_sha256'], status=content['status'],
            gaps=content.get('gaps', []), provenance=content.get('provenance', {}))
        return checked_source_view_request({'schema': 'capstone-grid-source-view-request/1', 'source_id': SOURCE_ID,
            'scope_id': page['scope']['scope_id'], 'scope_name': page['scope']['name'], 'level': page['level'],
            'selected_object_id': page['selected_object_id'], 'view_ref': page['view_ref'],
            'source_snapshot': {'metadata_snapshot': page['source_snapshot']['metadata_snapshot'],
                                'source_instance': page['source_snapshot'].get('source_instance', page['source_instance'])},
            'voltage_min_kv': request['voltage_min_kv'], 'display_grouping_only': page['display_grouping_only']})
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        return None


class GridSourceProvider:
    def __init__(self, gateway):
        self.gateway = gateway

    def _available(self):
        if self.gateway is None:
            return False
        catalog = self.gateway.catalog
        for tool in TOOLS:
            name = 'data_gateway_' + tool
            schema = catalog.get('tools', {}).get(name, {})
            annotations = schema.get('annotations', {})
            if (annotations.get('readOnlyHint') is not True or annotations.get('destructiveHint') is not False
                    or not isinstance(catalog.get('tool_hashes', {}).get(name), str)):
                return False
        return True

    def catalog(self):
        available = self._available()
        return {'schema': 'capstone-grid-source-catalog/1', 'sources': [{
            'source_id': SOURCE_ID, 'display_name': 'Data gateway source topology',
            'available': available, 'unavailable_reason': None if available else 'grid_source_unavailable',
            'levels': [None, 'region', 'station', 'equipment'], 'page_limit': PAGE_LIMIT,
            'display_only': True}]}

    async def _call(self, tool, arguments):
        if tool not in TOOLS or not self._available():
            raise GridSourceError('grid_source_unavailable')
        try:
            async with asyncio.timeout(EXCHANGE_SECONDS):
                value = await self.gateway.client.call('data_gateway_' + tool, arguments, self.gateway.catalog)
            content = value.get('structuredContent')
            if value.get('isError') or not isinstance(content, dict) or content.get('status') not in {'ok', 'partial'}:
                raise GridSourceError('grid_source_observation_unavailable')
            return deepcopy(content)
        except GridSourceError:
            raise
        except (GatewayError, TimeoutError, OSError, ValueError, TypeError):
            raise GridSourceError('grid_source_observation_unavailable') from None

    async def scopes(self):
        content = await self._call('discover_region_scopes', {})
        data = content.get('data')
        if isinstance(data, dict) and 'regions' in data and 'groups' in data:
            definitions, scopes = _scope_definitions(data)
        else:
            records = data.get('scopes') if isinstance(data, dict) else data
            if not isinstance(records, list) or len(records) > 128:
                _invalid()
            definitions, scopes = None, [_scope(scope) for scope in records]
        result = {'schema': 'capstone-grid-source-scopes/1', 'source_id': SOURCE_ID,
                  'status': content['status'], 'scopes': scopes,
                  'gaps': _gaps(content.get('gaps', [])),
                  **({'definitions': definitions} if definitions is not None else {})}
        if len(json.dumps(result, allow_nan=False).encode()) > PAGE_BYTES:
            _invalid()
        return result

    async def resolve_scope(self, document):
        if not isinstance(document, dict) or set(document) != {'scope'}:
            raise GridSourceError('grid_source_request_invalid')
        try:
            scope = _text(document['scope'])
        except GridSourceError:
            raise GridSourceError('grid_source_request_invalid') from None
        content = await self._call('resolve_region_scope', {'scope': scope})
        return {'schema': 'capstone-grid-source-scope/1', 'source_id': SOURCE_ID,
                'status': content['status'], 'scope': _scope(content.get('data')),
                'gaps': _gaps(content.get('gaps', []))}

    async def topology(self, document):
        request = checked_topology_request(document)
        content = await self._call('get_network_topology_view', request)
        catalog = self.gateway.catalog
        return topology_page(content.get('data'), request, catalog_revision=catalog['revision'],
            tool_schema_sha256=catalog['tool_hashes']['data_gateway_get_network_topology_view'],
            status=content['status'], gaps=content.get('gaps', []), provenance=content.get('provenance', {}))
