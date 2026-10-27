import asyncio
from copy import deepcopy

import pytest

STREAMS = ('devices', 'ports', 'connectivity_nodes', 'connections', 'device_relations', 'groups', 'boundaries', 'issues')
V2 = 'gateway-electrical-view/2'
V2_STREAMS = STREAMS + ('summary_nodes', 'summary_edges')


def manifest(**changes):
    return {'schema': 'gateway-electrical-view/1', 'state': 'ready', 'model_ref': 'model:one',
        'model_revision': 'revision-one', 'view_ref': 'view-one', 'selection_ref': 'selection-one',
        'source_snapshot_ref': 'snapshot-one', 'representation': 'source_node_breaker',
        'target': None, 'artifact_ref': None,
        'capture': {'source_transaction_consistency_verified': False, 'read_started_at': 1, 'read_completed_at': 2},
        'streams': {stream: {'total_count': 1, 'read': {'tool': 'read_network_model_view',
            'arguments': {'view_ref': 'view-one', 'stream': stream}}} for stream in STREAMS}, **changes}


def page(stream='devices', **changes):
    return {**{key: manifest()[key] for key in ('schema', 'model_ref', 'model_revision', 'view_ref', 'selection_ref', 'source_snapshot_ref')},
        'stream': stream, 'records': [{'id': 'device:one', 'kind': 'breaker',
            'switch_position': {'value': 'unknown', 'verified': False}, 'Authorization': 'secret'}],
        'returned_count': 1, 'total_count': 1, 'next_cursor': None, 'complete': True, **changes}


class Gateway:
    def __init__(self):
        self.catalog = {'revision': 'catalog-one', 'tools': {}, 'tool_hashes': {}}
        for tool, required in [('discover_network_models', []), ('open_network_model_view', ['model_ref']),
                               ('read_network_model_view', ['view_ref', 'stream']), ('get_network_model_job', ['job_ref'])]:
            name = 'data_gateway_' + tool
            self.catalog['tools'][name] = {'inputSchema': {'type': 'object', 'required': required},
                'annotations': {'readOnlyHint': tool != 'open_network_model_view', 'destructiveHint': False}}
            self.catalog['tool_hashes'][name] = 'hash-' + tool
        self.client = self
        self.calls = []
        self.data = manifest()
        self.error = None

    async def call(self, name, arguments, catalog):
        self.calls.append((name, deepcopy(arguments)))
        return {'isError': bool(self.error), 'structuredContent': self.error or
                {'status': 'partial', 'data': deepcopy(self.data), 'provenance': {'Authorization': 'secret'}}}


def v2_manifest(**changes):
    view_ref = changes.get('view_ref', 'view-one')
    return manifest(schema=V2, default_stream='summary_nodes',
        streams={stream: {'total_count': 1, 'read': {'tool': 'read_network_model_view',
            'arguments': {'view_ref': view_ref, 'stream': stream}}} for stream in V2_STREAMS},
        overview_coverage={'active_stations': 3, 'source_station_groups': 4,
            'omitted_empty_station_groups': 1, 'dc_supported': False,
            'line_endpoint_semantics': 'source_declarations; not verified electrical connectivity',
            'source_selection': {'profile': 'station', 'min_ac_kv': 0, 'boundary_policy': 'retain_external_stub',
                'rule_version': 'source-rule', 'rule_sha256': 'a' * 64, 'model_time': 'source_snapshot',
                'station_id': None, 'Authorization': 'secret'}, 'Authorization': 'secret'}, **changes)


def v2_gateway():
    gateway = Gateway()
    gateway.catalog['tools']['data_gateway_open_network_model_view']['inputSchema']['properties'] = {
        'view_schema': {'anyOf': [{'enum': ['gateway-electrical-view/1', V2], 'type': 'string'}, {'type': 'null'}], 'default': None}}
    gateway.data = v2_manifest()
    return gateway


def test_v2_root_open_preserves_bounded_coverage_without_fetching_records():
    from capstone_agent.grid_electrical_view import ElectricalViewProvider
    gateway = v2_gateway()
    result = asyncio.run(ElectricalViewProvider(gateway).open({'model_ref': 'model:one', 'view_schema': V2}))
    assert result['schema'] == V2 and set(result['streams']) == set(V2_STREAMS)
    assert result['overview_coverage']['source_selection']['profile'] == 'station'
    assert result['overview_coverage']['omitted_empty_station_groups'] == 1
    assert 'Authorization' not in str(result)
    assert gateway.calls == [('data_gateway_open_network_model_view', {
        'model_ref': 'model:one', 'representation': 'source_node_breaker', 'view_schema': V2})]


@pytest.mark.parametrize('kind', ['grid', 'station', 'summary_edge'])
def test_v2_child_inherits_schema_and_exact_parent_identity(kind):
    from capstone_agent.grid_electrical_view import ElectricalViewProvider
    gateway = v2_gateway(); provider = ElectricalViewProvider(gateway)
    asyncio.run(provider.open({'model_ref': 'model:one', 'view_schema': V2}))
    gateway.data = v2_manifest(view_ref='child', target='returned:' + kind)
    result = asyncio.run(provider.open({'model_ref': 'model:one', 'parent_view_ref': 'view-one',
        'expected_model_revision': 'revision-one', 'target': 'returned:' + kind}))
    assert result['schema'] == V2
    assert 'view_schema' not in gateway.calls[-1][1]
    assert len(gateway.calls) == 2


@pytest.mark.parametrize('stream,record', [
    ('summary_nodes', {'id': 'grid-one', 'name': 'Published directory name', 'group_kind': 'grid',
        'expand_target': 'grid-one', 'active_station_count': 3, 'electrical_equivalent': False,
        'source_ref': {'object_id': '001', 'table': 'SG_CON_PWRGRID_B', 'source_instance': 'source-one'}}),
    ('summary_edges', {'id': 'edge-one', 'source_id': 'grid-one', 'target_id': 'external-one',
        'relation_kind': 'source_ac_line_station_endpoints', 'member_count': 2, 'expand_target': 'edge-one',
        'direction': 'undirected_display; consult member source endpoints', 'electrical_equivalent': False,
        'electrical_connectivity_verified': False, 'source_evidence': {'table': 'SG_DEV_ACLINE_B',
            'fields': ['START_ST_ID', 'END_ST_ID']}}),
])
def test_v2_summary_pages_retain_published_semantics_and_drop_private_fields(stream, record):
    from capstone_agent.grid_electrical_view import ElectricalViewProvider
    gateway = v2_gateway(); gateway.data = page(stream=stream, schema=V2, records=[{**record, 'Authorization': 'secret'}])
    result = asyncio.run(ElectricalViewProvider(gateway).read({'view_ref': 'view-one', 'stream': stream}))
    assert result['records'] == [record]
    assert len(gateway.calls) == 1


def test_v2_line_members_keep_source_endpoint_identity_without_power_direction():
    from capstone_agent.grid_electrical_view import ElectricalViewProvider
    endpoints = {'start_station_id': '001', 'end_station_id': None,
        'direction_semantics': 'source_field_order; not power_flow_direction'}
    gateway = v2_gateway(); gateway.data = page(schema=V2, records=[{'id': 'line-one', 'kind': 'line',
        'source_endpoints': {**endpoints, 'Authorization': 'secret'}}])
    result = asyncio.run(ElectricalViewProvider(gateway).read({'view_ref': 'view-one', 'stream': 'devices'}))
    assert result['records'][0]['source_endpoints'] == endpoints


@pytest.mark.parametrize('change', [{'schema': 'gateway-electrical-view/1'}, {'model_revision': 'changed'},
    {'source_snapshot_ref': 'changed'}, {'selection_ref': 'changed'}])
def test_v2_pages_cannot_change_frozen_schema_or_identity(change):
    from capstone_agent.grid_electrical_view import ElectricalViewProvider, ElectricalViewError
    gateway = v2_gateway(); provider = ElectricalViewProvider(gateway)
    asyncio.run(provider.open({'model_ref': 'model:one', 'view_schema': V2}))
    gateway.data = page(schema=V2); gateway.data.update(change)
    with pytest.raises(ElectricalViewError):
        asyncio.run(provider.read({'view_ref': 'view-one', 'stream': 'devices'}))


@pytest.mark.parametrize('view_ref,stream', [('another-view', 'devices'), ('view-one', 'groups')])
def test_known_cursor_cannot_cross_view_or_stream(view_ref, stream):
    from capstone_agent.grid_electrical_view import ElectricalViewProvider, ElectricalViewError
    gateway = v2_gateway(); provider = ElectricalViewProvider(gateway)
    gateway.data = page(schema=V2, next_cursor='opaque-cursor', complete=False, total_count=2)
    asyncio.run(provider.read({'view_ref': 'view-one', 'stream': 'devices'}))
    gateway.data = page(schema=V2, view_ref=view_ref, stream=stream,
        records=[{'id': 'station-one', 'kind': 'station', 'member_count': 1, 'expand_target': 'station-one'}])
    with pytest.raises(ElectricalViewError):
        asyncio.run(provider.read({'view_ref': view_ref, 'stream': stream, 'cursor': 'opaque-cursor'}))
    assert len(gateway.calls) == 1


def test_discovered_provincial_roots_and_v2_capabilities_are_preserved_exactly():
    from capstone_agent.grid_electrical_view import ElectricalViewProvider
    gateway = v2_gateway()
    source_model = {'model_ref': 'registered:returned-province', 'scope': {'source_instance': 'source-one',
        'object_type': 'grid', 'object_id': '000123'}, 'open_arguments': {
        'model_ref': 'registered:returned-province', 'selection_profile': 'station'}, 'readiness': 'not_checked'}
    capability = {'representation': 'source_node_breaker', 'targets': ['model', 'grid', 'station', 'device', 'summary_edge', 'unresolved'],
        'streams': ['summary_nodes', 'summary_edges'], 'open_arguments': {'view_schema': V2},
        'summary_semantics': 'display_only_source_line_endpoints; not electrical_equivalents'}
    gateway.data = {'count': 0, 'scopes': [], 'electrical_views': {'schema': 'gateway-electrical-view/1',
        'view_schemas': ['gateway-electrical-view/1', V2], 'source_grid_models': [source_model], 'v2': capability}}
    result = asyncio.run(ElectricalViewProvider(gateway).models())
    assert result['electrical_views']['source_grid_models'] == [source_model]
    assert result['electrical_views']['v2'] == capability
    assert result['electrical_views']['view_schemas'] == ['gateway-electrical-view/1', V2]


@pytest.mark.parametrize('field', ['targets', 'streams', 'summary_semantics'])
def test_v2_capability_projection_rejects_nested_private_metadata(field):
    from capstone_agent.grid_electrical_view import ElectricalViewProvider, ElectricalViewError
    gateway = v2_gateway()
    capability = {'representation': 'source_node_breaker', 'targets': ['model', 'grid'],
        'streams': ['summary_nodes', 'summary_edges'], 'summary_semantics': 'display only'}
    capability[field] = {'Authorization': 'secret'}
    gateway.data = {'count': 0, 'scopes': [], 'electrical_views': {'schema': 'gateway-electrical-view/1', 'v2': capability}}
    with pytest.raises(ElectricalViewError):
        asyncio.run(ElectricalViewProvider(gateway).models())


@pytest.mark.parametrize('document', [
    {'model_ref': 'model:one', 'view_schema': 'gateway-electrical-view/3'},
    {'model_ref': 'model:one', 'view_schema': V2, 'representation': 'calculation_bus_branch', 'artifact_ref': 'artifact-one'},
    {'model_ref': 'model:one', 'view_schema': V2, 'parent_view_ref': 'view-one', 'target': 'grid-one', 'expected_model_revision': 'revision-one'},
])
def test_invalid_or_noninherited_schema_never_reaches_gateway(document):
    from capstone_agent.grid_electrical_view import ElectricalViewProvider, ElectricalViewError
    gateway = v2_gateway()
    with pytest.raises(ElectricalViewError):
        asyncio.run(ElectricalViewProvider(gateway).open(document))
    assert not gateway.calls


def test_preparing_v2_root_and_wrong_schema_child_are_checked():
    from capstone_agent.grid_electrical_view import ElectricalViewProvider, ElectricalViewError
    gateway = v2_gateway(); provider = ElectricalViewProvider(gateway)
    gateway.data = {'schema': V2, 'state': 'preparing', 'model_ref': 'model:one', 'preparation_ref': 'job-one'}
    assert asyncio.run(provider.open({'model_ref': 'model:one', 'view_schema': V2}))['schema'] == V2
    gateway.data = v2_manifest()
    asyncio.run(provider.open({'model_ref': 'model:one', 'view_schema': V2}))
    gateway.data = manifest(view_ref='child', target='returned-station')
    with pytest.raises(ElectricalViewError):
        asyncio.run(provider.open({'model_ref': 'model:one', 'parent_view_ref': 'view-one',
            'expected_model_revision': 'revision-one', 'target': 'returned-station'}))


def test_v2_does_not_extend_page_budget_or_accept_undeclared_streams():
    from capstone_agent.grid_electrical_view import ElectricalViewProvider, ElectricalViewError, checked_manifest
    gateway = v2_gateway(); provider = ElectricalViewProvider(gateway)
    with pytest.raises(ElectricalViewError):
        asyncio.run(provider.read({'view_ref': 'view-one', 'stream': 'summary_nodes', 'limit': 1001}))
    assert not gateway.calls
    malformed = v2_manifest(); malformed['streams']['unpublished'] = malformed['streams']['devices']
    with pytest.raises(ElectricalViewError):
        checked_manifest(malformed)
    gateway.data = manifest()
    asyncio.run(provider.open({'model_ref': 'model:one'}))
    with pytest.raises(ElectricalViewError):
        asyncio.run(provider.read({'view_ref': 'view-one', 'stream': 'summary_nodes'}))
    assert len(gateway.calls) == 1


def test_nonstring_schema_is_a_typed_response_rejection():
    from capstone_agent.grid_electrical_view import ElectricalViewProvider, ElectricalViewError
    gateway = v2_gateway(); gateway.data = page(schema={'Authorization': 'secret'})
    with pytest.raises(ElectricalViewError):
        asyncio.run(ElectricalViewProvider(gateway).read({'view_ref': 'view-one', 'stream': 'devices'}))


def test_frozen_open_read_keeps_structural_unknowns_without_hidden_full_fetch():
    from capstone_agent.grid_electrical_view import ElectricalViewProvider
    gateway = Gateway()
    provider = ElectricalViewProvider(gateway)
    opened = asyncio.run(provider.open({'model_ref': 'model:one'}))
    assert opened['capture']['source_transaction_consistency_verified'] is False
    assert len(gateway.calls) == 1
    gateway.data = page()
    result = asyncio.run(provider.read({'view_ref': 'view-one', 'stream': 'devices', 'limit': 1}))
    assert result['records'][0]['switch_position'] == {'value': 'unknown', 'verified': False}
    assert 'Authorization' not in result['records'][0]
    assert len(gateway.calls) == 2


@pytest.mark.parametrize('document', [{'model_ref': 'model:one', 'url': 'https://caller'},
    {'model_ref': 'model:one', 'refresh_source': 'true'}, {'model_ref': 'model:one', 'target': 'device:one'},
    {'model_ref': 'model:one', 'parent_view_ref': 'parent', 'target': 'device:one'}])
def test_invalid_open_never_reaches_gateway(document):
    from capstone_agent.grid_electrical_view import ElectricalViewProvider, ElectricalViewError
    gateway = Gateway()
    with pytest.raises(ElectricalViewError):
        asyncio.run(ElectricalViewProvider(gateway).open(document))
    assert gateway.calls == []


@pytest.mark.parametrize('change', [{'model_revision': 'other'}, {'model_ref': 'model:other'},
    {'view_ref': 'other'}, {'selection_ref': 'other'}, {'source_snapshot_ref': 'other'},
    {'total_count': 2}, {'stream': 'ports'}, {'returned_count': 2}, {'complete': False},
    {'records': [{'id': 'same', 'kind': 'breaker'}, {'id': 'same', 'kind': 'breaker'}], 'returned_count': 2}])
def test_wrong_frozen_identity_counts_or_page_shape_are_rejected(change):
    from capstone_agent.grid_electrical_view import ElectricalViewProvider, ElectricalViewError
    gateway = Gateway(); provider = ElectricalViewProvider(gateway)
    asyncio.run(provider.open({'model_ref': 'model:one'}))
    gateway.data = page(**change)
    with pytest.raises(ElectricalViewError):
        asyncio.run(provider.read({'view_ref': 'view-one', 'stream': 'devices', 'limit': 10}))


def test_child_uses_parent_baseline_and_never_implicitly_reopens_root():
    from capstone_agent.grid_electrical_view import ElectricalViewProvider, ElectricalViewError
    gateway = Gateway(); provider = ElectricalViewProvider(gateway)
    asyncio.run(provider.open({'model_ref': 'model:one'}))
    gateway.data = manifest(view_ref='child', target='device:one', model_revision='other',
        streams={stream: {'total_count': 1, 'read': {'tool': 'read_network_model_view',
                 'arguments': {'view_ref': 'child', 'stream': stream}}} for stream in STREAMS})
    with pytest.raises(ElectricalViewError):
        asyncio.run(provider.open({'model_ref': 'model:one', 'parent_view_ref': 'view-one',
            'expected_model_revision': 'revision-one', 'target': 'device:one'}))
    assert len(gateway.calls) == 2


def test_preparation_and_task_type_are_explicit():
    from capstone_agent.grid_electrical_view import ElectricalViewProvider, ElectricalViewError
    gateway = Gateway(); provider = ElectricalViewProvider(gateway)
    gateway.data = {'schema': 'gateway-electrical-view/1', 'state': 'preparing',
                    'model_ref': 'model:one', 'preparation_ref': 'prepare-one'}
    assert asyncio.run(provider.open({'model_ref': 'model:one'}))['state'] == 'preparing'
    gateway.data = {'job_ref': 'prepare-one', 'task_type': 'view_preparation', 'model_ref': 'model:one',
                    'state': 'succeeded', 'stage': 'complete', 'view_ref': 'view-one', 'model_revision': 'revision-one',
                    'owner_pid': 123, 'path': '/private/file'}
    job = asyncio.run(provider.job({'job_ref': 'prepare-one'}))
    assert 'owner_pid' not in job and 'path' not in job
    gateway.data['task_type'] = 'model_build'
    with pytest.raises(ElectricalViewError):
        asyncio.run(provider.job({'job_ref': 'prepare-one'}))


def test_known_errors_are_typed_without_private_upstream_text():
    from capstone_agent.grid_electrical_view import ElectricalViewProvider, ElectricalViewError
    gateway = Gateway()
    gateway.error = {'status': 'error', 'data': None, 'gaps': [{'reason': 'view_expired',
        'message': 'private connection string', 'scope': {'retryable': False, 'recovery_action': 'reopen_view'}}]}
    with pytest.raises(ElectricalViewError) as raised:
        asyncio.run(ElectricalViewProvider(gateway).read({'view_ref': 'old', 'stream': 'groups'}))
    assert raised.value.code == 'view_expired'
    assert raised.value.status == 410
    assert 'private' not in str(raised.value)


def test_only_discovered_model_references_are_projected_without_synthesis():
    from capstone_agent.grid_electrical_view import ElectricalViewProvider
    gateway = Gateway()
    gateway.data = {'count': 1, 'listing_complete': True, 'scopes': [
        {'scope_id': 'scope-one', 'model_ref': 'registered:actual', 'model_revision': None,
         'name': 'Arbitrary grid', 'readiness': 'not_checked', 'password': 'secret'}],
        'electrical_views': {'schema': 'gateway-electrical-view/1', 'targets': ['model', 'station', 'device'],
                             'optimization': {'support': 'unsupported', 'readiness': 'not_checked'}}}
    result = asyncio.run(ElectricalViewProvider(gateway).models())
    assert result['scopes'][0]['model_ref'] == 'registered:actual'
    assert 'password' not in result['scopes'][0]
    assert gateway.calls == [('data_gateway_discover_network_models', {'detail': False})]


def test_ready_descriptor_is_exact_and_rejects_raw_unvalidated_graph():
    from capstone_agent.grid_electrical_view import electrical_descriptor, checked_electrical_descriptor
    descriptor = electrical_descriptor(manifest())
    assert descriptor['schema'] == 'capstone-electrical-view-request/1'
    assert checked_electrical_descriptor(descriptor) == descriptor
    assert electrical_descriptor({'view_ref': 'raw'}) is None


def test_v2_root_descriptor_keeps_the_returned_schema_and_source_selection():
    from capstone_agent.grid_electrical_view import electrical_descriptor, checked_electrical_descriptor
    descriptor = electrical_descriptor(v2_manifest())
    assert descriptor['view_schema'] == V2
    assert descriptor['selection_profile'] == 'station'
    assert descriptor['boundary_policy'] == 'retain_external_stub'
    assert checked_electrical_descriptor(descriptor) == descriptor


def test_legacy_descriptor_remains_valid_without_new_optional_fields():
    from capstone_agent.grid_electrical_view import electrical_descriptor, checked_electrical_descriptor
    descriptor = electrical_descriptor(manifest())
    for key in ('view_schema', 'selection_profile', 'boundary_policy', 'parent_view_ref'):
        descriptor.pop(key, None)
    assert checked_electrical_descriptor(descriptor) == descriptor


def test_child_descriptor_uses_actual_parent_arguments_and_does_not_invent_a_parent():
    from capstone_agent.grid_electrical_view import electrical_descriptor
    child = v2_manifest(view_ref='child-view', target='returned-station')
    arguments = {'model_ref': 'model:one', 'parent_view_ref': 'actual-parent-view',
        'expected_model_revision': 'revision-one', 'target': 'returned-station'}
    descriptor = electrical_descriptor(child, arguments)
    assert descriptor['parent_view_ref'] == 'actual-parent-view'
    assert descriptor['view_schema'] == V2
    assert 'selection_profile' not in descriptor and 'boundary_policy' not in descriptor
    assert 'parent_view_ref' not in electrical_descriptor(child)


@pytest.mark.parametrize('fields', [
    {'view_schema': 'gateway-electrical-view/3'}, {'view_schema': None},
    {'selection_profile': {'Authorization': 'secret'}}, {'selection_profile': 'bad profile'},
    {'boundary_policy': 'unknown'}, {'parent_view_ref': ''}, {'parent_view_ref': 'view-one'},
    {'parent_view_ref': 'parent', 'selection_profile': 'station'},
    {'parent_view_ref': 'parent', 'boundary_policy': 'internal_only'},
])
def test_descriptor_optional_fields_are_closed_typed_and_scope_bound(fields):
    from capstone_agent.grid_electrical_view import electrical_descriptor, checked_electrical_descriptor, ElectricalViewError
    descriptor = electrical_descriptor(manifest())
    descriptor.update(fields)
    with pytest.raises(ElectricalViewError):
        checked_electrical_descriptor(descriptor)


def test_root_descriptor_rejects_selection_or_schema_drift_from_the_actual_request():
    from capstone_agent.grid_electrical_view import electrical_descriptor
    assert electrical_descriptor(v2_manifest(), {'model_ref': 'model:one', 'view_schema': 'gateway-electrical-view/1'}) is None
    assert electrical_descriptor(v2_manifest(), {'model_ref': 'model:one', 'selection_profile': 'regional'}) is None


def test_page_retry_cannot_mutate_records_and_cursor_cannot_repeat():
    from capstone_agent.grid_electrical_view import ElectricalViewProvider, ElectricalViewError
    gateway = Gateway(); provider = ElectricalViewProvider(gateway)
    gateway.data = page()
    asyncio.run(provider.read({'view_ref': 'view-one', 'stream': 'devices'}))
    gateway.data['records'][0]['kind'] = 'load'
    with pytest.raises(ElectricalViewError):
        asyncio.run(provider.read({'view_ref': 'view-one', 'stream': 'devices'}))
    gateway.data = page(next_cursor='cursor-one', complete=False, total_count=3)
    with pytest.raises(ElectricalViewError):
        asyncio.run(provider.read({'view_ref': 'view-one', 'stream': 'devices', 'cursor': 'cursor-one'}))


def test_issue_evidence_projects_connection_fields_not_arbitrary_source_rows():
    from capstone_agent.grid_electrical_view import ElectricalViewProvider
    gateway = Gateway(); gateway.data = page(stream='issues', records=[{'id': 'issue-one', 'code': 'duplicate_node_slots',
        'subject_ref': 'device:one', 'evidence': {'ID': 'source-one', 'FIRST_NODE_ID': 'node-one', 'password': 'secret'}}])
    result = asyncio.run(ElectricalViewProvider(gateway).read({'view_ref': 'view-one', 'stream': 'issues'}))
    assert result['records'][0]['evidence'] == {'ID': 'source-one', 'FIRST_NODE_ID': 'node-one'}


@pytest.mark.parametrize('incompatible', [False, True])
def test_only_pre_call_publication_change_gets_one_compatible_protected_refresh(incompatible):
    from capstone_agent.grid_electrical_view import ElectricalViewProvider, ElectricalViewError
    from capstone_agent.data_gateway_mcp import GatewayError
    gateway = Gateway(); original = deepcopy(gateway.catalog); calls = []; refreshes = []
    fresh = deepcopy(original); fresh['revision'] = 'catalog-two'
    schema = fresh['tools']['data_gateway_open_network_model_view']['inputSchema']
    schema['properties'] = {'view_schema': {'type': 'string', 'default': 'gateway-electrical-view/2'}}
    if incompatible:
        schema['required'] = ['model_ref', 'unpublished_input']
    async def prepare():
        refreshes.append(True); await asyncio.sleep(0)
        return fresh
    async def call(name, arguments, catalog):
        calls.append((name, deepcopy(arguments), catalog['revision']))
        if catalog['revision'] == 'catalog-one':
            raise GatewayError('gateway_publication_changed')
        return {'structuredContent': {'status': 'ok', 'data': manifest()}}
    gateway.prepare = prepare; gateway.call = call
    provider = ElectricalViewProvider(gateway)
    if incompatible:
        with pytest.raises(ElectricalViewError) as caught:
            asyncio.run(provider.open({'model_ref': 'model:one'}))
        assert caught.value.code == 'gateway_publication_changed'
        assert len(calls) == 1
    else:
        assert asyncio.run(provider.open({'model_ref': 'model:one'}))['state'] == 'ready'
        assert calls[-1][1]['view_schema'] == 'gateway-electrical-view/1'
        assert len(calls) == 2
    assert len(refreshes) == 1
    assert gateway.catalog == original  # Running research task grants do not change.


def test_concurrent_protected_calls_share_refresh_but_do_not_retry_transport_failures():
    from capstone_agent.grid_electrical_view import ElectricalViewProvider, ElectricalViewError
    from capstone_agent.data_gateway_mcp import GatewayError
    gateway = Gateway(); fresh = deepcopy(gateway.catalog); fresh['revision'] = 'catalog-two'; refreshes = []; calls = []
    async def prepare():
        refreshes.append(True); await asyncio.sleep(0.01); return fresh
    async def call(name, arguments, catalog):
        calls.append(catalog['revision'])
        if catalog['revision'] == 'catalog-one':
            await asyncio.sleep(0)
            raise GatewayError('gateway_publication_changed')
        return {'structuredContent': {'status': 'ok', 'data': manifest()}}
    gateway.prepare = prepare; gateway.call = call; provider = ElectricalViewProvider(gateway)
    async def concurrent():
        return await asyncio.gather(provider.open({'model_ref': 'model:one'}), provider.open({'model_ref': 'model:one'}))
    assert len(asyncio.run(concurrent())) == 2
    assert len(refreshes) == 1 and len(calls) == 4
    calls.clear()
    async def failure(*args):
        calls.append(True); raise GatewayError('gateway_timeout')
    gateway.call = failure
    with pytest.raises(ElectricalViewError):
        asyncio.run(provider.open({'model_ref': 'model:one'}))
    assert len(calls) == 1 and len(refreshes) == 1


@pytest.mark.parametrize('change', ['required_argument', 'unsupported_v1', 'destructive', 'changed_existing_type'])
def test_incompatible_publication_is_not_used_even_for_a_valid_cached_request(change):
    from capstone_agent.grid_electrical_view import ElectricalViewProvider, ElectricalViewError
    from capstone_agent.data_gateway_mcp import GatewayError
    gateway = Gateway()
    gateway.catalog['tools']['data_gateway_open_network_model_view']['inputSchema']['properties'] = {'model_ref': {'type': 'string'}}
    fresh = deepcopy(gateway.catalog); fresh['revision'] = 'incompatible'; calls = []
    tool = fresh['tools']['data_gateway_open_network_model_view']
    if change == 'required_argument':
        tool['inputSchema']['required'].append('caller_selected_url')
    elif change == 'unsupported_v1':
        tool['inputSchema']['properties']['view_schema'] = {'enum': ['gateway-electrical-view/2']}
    elif change == 'destructive':
        tool['annotations']['destructiveHint'] = True
    else:
        tool['inputSchema']['properties']['model_ref']['type'] = 'integer'
    async def prepare():
        return fresh
    async def call(*args):
        calls.append(True); raise GatewayError('gateway_publication_changed')
    gateway.prepare = prepare; gateway.call = call
    with pytest.raises(ElectricalViewError) as raised:
        asyncio.run(ElectricalViewProvider(gateway).open({'model_ref': 'model:one'}))
    assert raised.value.code == 'gateway_publication_changed' and raised.value.status == 409
    assert calls == [True]


def test_a_second_publication_change_stops_without_repeated_catalog_or_tool_probes():
    from capstone_agent.grid_electrical_view import ElectricalViewProvider, ElectricalViewError
    from capstone_agent.data_gateway_mcp import GatewayError
    gateway = Gateway(); calls = []; refreshes = []
    async def prepare():
        refreshes.append(True); return {**gateway.catalog, 'revision': 'second'}
    async def call(*args):
        calls.append(True); raise GatewayError('gateway_publication_changed')
    gateway.prepare = prepare; gateway.call = call
    with pytest.raises(ElectricalViewError) as raised:
        asyncio.run(ElectricalViewProvider(gateway).open({'model_ref': 'model:one'}))
    assert raised.value.code == 'gateway_publication_changed'
    assert len(calls) == 2 and len(refreshes) == 1

