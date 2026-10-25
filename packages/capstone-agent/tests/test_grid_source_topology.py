import asyncio
import json
from copy import deepcopy

import pytest


def topology_data():
    return {'view_ref': 'view-one', 'source_instance': 'fixture-source',
        'scope': {'scope_id': 'north', 'name': 'North', 'definition_version': 'v1',
                  'data_coverage_verified': False, 'electrical_model_complete': False},
        'selection': {'profile': 'regional', 'min_ac_kv': 330, 'boundary_policy': 'retain_external_stub'},
        'source_snapshot': {'metadata_snapshot': 'snapshot-one', 'source_nature': 'sqlite_snapshot'},
        'level': 'region', 'selected_object_id': None, 'display_grouping_only': True,
        'electrical_equivalence_performed': False,
        'nodes': [{'id': 'station:1', 'kind': 'station', 'label': 'Station one', 'boundary': False,
                   'expand': {'level': 'station', 'selected_object_id': 'station:1'}}],
        'edges': [{'id': 'line:1', 'source': 'station:2', 'target': 'station:3', 'kind': 'source_line'}],
        'total_nodes': 405, 'total_edges': 1003, 'node_offset': 0, 'edge_offset': 0,
        'next_node_offset': 1, 'next_edge_offset': 1,
        'boundary_object_ids': ['station:3'], 'source_gaps': ['switch_positions_unverified'], 'gaps': []}


class Gateway:
    def __init__(self):
        self.catalog = {'revision': 'catalog-one', 'tools': {}, 'tool_hashes': {}}
        for tool in ('discover_region_scopes', 'resolve_region_scope', 'get_network_topology_view'):
            name = 'data_gateway_' + tool
            self.catalog['tools'][name] = {'annotations': {'readOnlyHint': True, 'destructiveHint': False}}
            self.catalog['tool_hashes'][name] = 'schema-' + tool
        self.client = self
        self.calls = []
        self.data = topology_data()
        self.provenance = {'request_id': 'request-one', 'queried_at': '2026-10-26',
                           'url': 'https://private', 'Authorization': 'do-not-project'}

    async def call(self, name, arguments, catalog):
        self.calls.append((name, deepcopy(arguments), deepcopy(catalog)))
        return {'isError': False, 'structuredContent': {'status': 'ok', 'data': self.data,
                'gaps': [], 'provenance': self.provenance}}


def test_fixed_provider_returns_source_page_not_electrical_buses():
    from capstone_agent.grid_source_topology import GridSourceProvider
    gateway = Gateway()
    page = asyncio.run(GridSourceProvider(gateway).topology({'scope_id': 'north', 'limit': 3}))
    assert page['schema'] == 'capstone-grid-source-topology/1'
    assert page['source_id'] == 'data-gateway'
    assert page['catalog_revision'] == 'catalog-one'
    assert page['display_grouping_only'] is True
    assert page['electrical_equivalence_performed'] is False
    assert page['nodes'][0]['kind'] == 'station'
    assert page['edges'][0]['source'] == 'station:2'  # Other node page, never fabricate a bus.
    assert page['total_nodes'] == 405 and page['total_edges'] == 1003
    assert page['source_gaps'] == ['switch_positions_unverified']
    assert page['provenance'] == {'request_id': 'request-one', 'queried_at': '2026-10-26'}
    assert gateway.calls[0][0] == 'data_gateway_get_network_topology_view'


@pytest.mark.parametrize('change', [
    {'url': 'https://caller'}, {'name': 'build_network_model'}, {'limit': 1001},
    {'node_offset': 1}, {'edge_offset': True}, {'limit': 0}, {'level': 'bus'},
    {'voltage_min_kv': float('nan')}, {'scope_id': ''},
])
def test_request_is_closed_bounded_and_continuation_requires_view(change):
    from capstone_agent.grid_source_topology import GridSourceProvider, GridSourceError
    gateway = Gateway()
    with pytest.raises(GridSourceError):
        asyncio.run(GridSourceProvider(gateway).topology({'scope_id': 'north', **change}))
    assert gateway.calls == []


@pytest.mark.parametrize('change', [
    {'view_ref': 'changed'}, {'scope': {'scope_id': 'another'}}, {'node_offset': 2},
    {'next_node_offset': 0}, {'total_edges': 0}, {'display_grouping_only': False},
    {'electrical_equivalence_performed': True}, {'source_gaps': None},
    {'nodes': [{'id': 'station:1', 'kind': 'station'}, {'id': 'station:1', 'kind': 'station'}]},
])
def test_rejects_changed_revision_inconsistent_page_and_missing_quality(change):
    from capstone_agent.grid_source_topology import GridSourceProvider, GridSourceError
    gateway = Gateway()
    gateway.data.update(change)
    with pytest.raises(GridSourceError):
        asyncio.run(GridSourceProvider(gateway).topology(
            {'scope_id': 'north', 'expected_view_ref': 'view-one', 'limit': 3}))


def test_separate_streams_can_finish_at_different_offsets():
    from capstone_agent.grid_source_topology import GridSourceProvider
    gateway = Gateway()
    gateway.data.update(nodes=[], node_offset=405, next_node_offset=None,
                        edge_offset=10, next_edge_offset=11)
    page = asyncio.run(GridSourceProvider(gateway).topology({'scope_id': 'north',
        'expected_view_ref': 'view-one', 'node_offset': 405, 'edge_offset': 10, 'limit': 3}))
    assert page['next_node_offset'] is None
    assert page['next_edge_offset'] == 11
    assert page['complete'] is False


def test_scope_discovery_and_resolution_are_fixed_sanitized_operations():
    from capstone_agent.grid_source_topology import GridSourceProvider
    gateway = Gateway()
    scope = topology_data()['scope']
    gateway.data = {'scopes': [scope], 'url': 'private'}
    provider = GridSourceProvider(gateway)
    assert asyncio.run(provider.scopes())['scopes'] == [scope]
    gateway.data = scope
    assert asyncio.run(provider.resolve_scope({'scope': 'North'}))['scope'] == scope
    assert [call[0] for call in gateway.calls] == [
        'data_gateway_discover_region_scopes', 'data_gateway_resolve_region_scope']
    assert gateway.calls[1][1] == {'scope': 'North'}


def test_public_catalog_excludes_mcp_schemas_and_connection_details():
    from capstone_agent.grid_source_topology import GridSourceProvider
    provider = GridSourceProvider(Gateway())
    assert provider.catalog()['schema'] == 'capstone-grid-source-catalog/1'
    source = provider.catalog()['sources'][0]
    assert source['source_id'] == 'data-gateway' and source['available'] is True
    assert 'tools' not in source and 'url' not in source
    assert GridSourceProvider(None).catalog()['sources'][0]['available'] is False


def test_provider_does_not_admit_missing_or_mutating_publications():
    from capstone_agent.grid_source_topology import GridSourceProvider, GridSourceError
    gateway = Gateway()
    gateway.catalog['tools']['data_gateway_get_network_topology_view']['annotations']['destructiveHint'] = True
    provider = GridSourceProvider(gateway)
    assert provider.catalog()['sources'][0]['available'] is False
    with pytest.raises(GridSourceError, match='^grid_source_unavailable$'):
        asyncio.run(provider.topology({'scope_id': 'north'}))
    assert gateway.calls == []


def test_gateway_failures_never_expose_upstream_connection_diagnostics():
    from capstone_agent.grid_source_topology import GridSourceProvider, GridSourceError
    from capstone_agent.data_gateway_mcp import GatewayError
    gateway = Gateway()
    async def fail(*_):
        raise GatewayError('private endpoint and credential diagnostic')
    gateway.call = fail
    with pytest.raises(GridSourceError, match='^grid_source_observation_unavailable$'):
        asyncio.run(GridSourceProvider(gateway).topology({'scope_id': 'north'}))


@pytest.mark.parametrize('field,value', [('data_coverage_verified', 'false'),
                                        ('electrical_model_complete', 0)])
def test_scope_quality_is_typed_not_truthy(field, value):
    from capstone_agent.grid_source_topology import GridSourceProvider, GridSourceError
    gateway = Gateway()
    gateway.data['scope'][field] = value
    with pytest.raises(GridSourceError):
        asyncio.run(GridSourceProvider(gateway).topology({'scope_id': 'north'}))


def test_published_scope_dictionary_preserves_definitions_aliases_and_statistical_limits():
    """Gateway1.30 real discovery shape (2026-10-26); no invented resolved scope."""
    from capstone_agent.grid_source_topology import GridSourceProvider
    gateway = Gateway()
    north = topology_data()['scope']
    group = {**north, 'scope_id': 'north_three', 'name': '北三区'}
    gateway.data = {'definition_version': 'national-dispatch-2026-10-24',
        'scope': 'national_dispatch_state_grid', 'regions': [north], 'groups': [group],
        'aliases': {'华北': 'north', '北三区': 'north_three'}, 'not_aliases': ['全国电网'],
        'statistical_basis_values': [{'code': '1001', 'name': '经营区'}],
        'statistical_basis_evidence': 'SG_META_PROPERTY.DATARANGE annotations; not a universal field mapping',
        'historical_adjustments': 'Preserve source RUNINDEXRANGE and effective versions',
        'url': 'private endpoint must be omitted'}
    page = asyncio.run(GridSourceProvider(gateway).scopes())
    assert page['scopes'] == [north, group]
    definitions = page['definitions']
    assert definitions['regions'] == [north] and definitions['groups'] == [group]
    assert definitions['definition_version'] == gateway.data['definition_version']
    assert definitions['aliases'] == {'华北': 'north', '北三区': 'north_three'}
    assert definitions['not_aliases'] == ['全国电网']
    assert definitions['statistical_basis_values'] == [{'code': '1001', 'name': '经营区'}]
    assert definitions['statistical_basis_evidence'].endswith('not a universal field mapping')
    assert 'url' not in definitions


def test_station_source_shape_keeps_unverified_voltage_and_hierarchy():
    """Representative published station records, including the unknown voltage group."""
    from capstone_agent.grid_source_topology import GridSourceProvider
    gateway = Gateway()
    station = 'station:01121100000001'
    gateway.data.update(level='station', selected_object_id=station,
        nodes=[{'id': 'voltage:01121100000001:None', 'kind': 'voltage_level',
                'label': '未核准电压层', 'parent_id': station, 'voltage_kv': None,
                'expand': {'level': 'equipment', 'selected_object_id': station}},
               {'id': 'breakers:132111000000000007', 'kind': 'breakers',
                'label': '5011断路器', 'source_id': '132111000000000007',
                'station_id': '01121100000001', 'parent_id': 'voltage:01121100000001:500'}],
        edges=[{'id': 'line:one:terminal:one', 'source': 'line:one', 'target': 'terminal:one', 'kind': 'line_terminal'}],
        total_nodes=2, total_edges=1, next_node_offset=None, next_edge_offset=None)
    page = asyncio.run(GridSourceProvider(gateway).topology({'scope_id': 'north', 'level': 'station',
                      'selected_object_id': station, 'limit': 1000}))
    assert page['nodes'][0]['voltage_kv'] is None
    assert page['nodes'][0]['parent_id'] == station
    assert page['nodes'][1]['station_id'] == '01121100000001'
    assert page['complete'] is True


def test_explicit_raw_source_view_keeps_equipment_kinds_and_full_independent_totals():
    from capstone_agent.grid_source_topology import GridSourceProvider
    gateway = Gateway()
    gateway.data.update(level=None, selected_object_id=None, display_grouping_only=False,
        nodes=[{'id':'breakers:132111000000000001','kind':'breakers','label':'5045断路器',
                'source_id':'132111000000000001','station_id':'01121100000003',
                'expand':{'level':'equipment','selected_object_id':'breakers:132111000000000001'}}],
        edges=[{'id':'breaker:one:node:one','source':'breakers:132111000000000001',
                'target':'node:0112110000000310030042','kind':'source_connection'}],
        total_nodes=52625,total_edges=48319)
    provider=GridSourceProvider(gateway)
    page=asyncio.run(provider.topology({'scope_id':'north','level':None,'limit':1000}))
    assert page['level'] is None and page['selected_object_id'] is None
    assert page['display_grouping_only'] is False and page['electrical_equivalence_performed'] is False
    assert page['nodes'][0]['kind']=='breakers' and page['nodes'][0]['station_id']=='01121100000003'
    assert page['edges'][0]['kind']=='source_connection'
    assert (page['total_nodes'],page['total_edges'])==(52625,48319)
    assert page['next_node_offset']==1 and page['next_edge_offset']==1
    assert gateway.calls[0][1]['level'] is None
    assert None in provider.catalog()['sources'][0]['levels']
    # One stream can end while the other still has a page. No repeated starts.
    gateway.data.update(nodes=[],node_offset=52625,next_node_offset=None,
                        edge_offset=48318,next_edge_offset=None)
    last=asyncio.run(provider.topology({'scope_id':'north','level':None,'limit':1000,
        'node_offset':52625,'edge_offset':48318,'expected_view_ref':'view-one'}))
    assert last['complete'] is True


@pytest.mark.parametrize('change',[{'display_grouping_only':True},{'electrical_equivalence_performed':True}])
def test_raw_view_does_not_accept_grouped_or_electrically_reduced_claims(change):
    from capstone_agent.grid_source_topology import GridSourceProvider,GridSourceError
    gateway=Gateway()
    gateway.data.update(level=None,display_grouping_only=False)
    gateway.data.update(change)
    with pytest.raises(GridSourceError):
        asyncio.run(GridSourceProvider(gateway).topology({'scope_id':'north','level':None}))


def test_raw_request_has_no_selected_group_and_omitted_level_stays_regional():
    from capstone_agent.grid_source_topology import checked_topology_request,GridSourceError
    assert checked_topology_request({'scope_id':'north'})['level']=='region'
    with pytest.raises(GridSourceError):
        checked_topology_request({'scope_id':'north','level':None,'selected_object_id':'station:one'})


def test_raw_source_object_gaps_preserve_actual_ids_without_inventing_messages():
    from capstone_agent.grid_source_topology import GridSourceProvider
    gateway=Gateway()
    object_gaps=[{'id':f'windings:{index}','reason':'device_topology_missing'} for index in range(5926)]
    gateway.data.update(level=None,display_grouping_only=False,gaps=object_gaps)
    page=asyncio.run(GridSourceProvider(gateway).topology({'scope_id':'north','level':None}))
    assert page['gaps']==object_gaps
    assert 'message' not in page['gaps'][0]


def test_source_view_hint_is_small_and_derived_from_a_strict_actual_page():
    from capstone_agent.grid_source_topology import source_view_from_gateway_result,checked_source_view_request
    data=topology_data()
    data.update(level=None,display_grouping_only=False)
    upstream={'structuredContent':{'status':'ok','data':data,'gaps':[],'provenance':{}},'isError':False}
    result={'content':[{'type':'text','text':json.dumps(upstream)}],
            'details':{'catalog_revision':'catalog-one','tool_schema_sha256':'schema-one'}}
    hint=source_view_from_gateway_result(result)
    assert hint=={'schema':'capstone-grid-source-view-request/1','source_id':'data-gateway',
        'scope_id':'north','scope_name':'North','level':None,'selected_object_id':None,'view_ref':'view-one',
        'source_snapshot':{'metadata_snapshot':'snapshot-one','source_instance':'fixture-source'},
        'voltage_min_kv':330,'display_grouping_only':False}
    assert checked_source_view_request(hint)==hint
    assert 'nodes' not in hint and 'gaps' not in hint
    data['next_node_offset']=0
    result['content'][0]['text']=json.dumps(upstream)
    assert source_view_from_gateway_result(result) is None
    with pytest.raises(ValueError):
        checked_source_view_request({**hint,'credential':'never publish'})


def test_optional_source_labels_normalize_whitespace_without_rewriting_source_identity():
    from capstone_agent.grid_source_topology import GridSourceProvider,GridSourceError
    gateway=Gateway()
    gateway.data['nodes'][0]['label']='500kV四串联络50422刀闸\t\t'
    page=asyncio.run(GridSourceProvider(gateway).topology({'scope_id':'north'}))
    assert page['nodes'][0]['label']=='500kV四串联络50422刀闸'
    gateway.data['nodes'][0]['source_id']='source\t'
    with pytest.raises(GridSourceError):
        asyncio.run(GridSourceProvider(gateway).topology({'scope_id':'north'}))


def test_unpresentable_optional_label_retains_object_with_declared_projection_gap():
    from capstone_agent.grid_source_topology import GridSourceProvider
    gateway=Gateway()
    gateway.data['nodes'][0]['label']='\x00'
    page=asyncio.run(GridSourceProvider(gateway).topology({'scope_id':'north'}))
    assert page['nodes'][0]['id']=='station:1' and 'label' not in page['nodes'][0]
    assert {'id':'station:1','reason':'source_label_unpresentable'} in page['gaps']
