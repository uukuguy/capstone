import asyncio
from copy import deepcopy

import pytest

STREAMS = ('devices', 'ports', 'connectivity_nodes', 'connections', 'device_relations', 'groups', 'boundaries', 'issues')


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

