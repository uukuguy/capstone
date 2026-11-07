import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest

from capstone_agent.data_gateway_mcp import GatewayError
from capstone_agent.data_gateway_relay import DataGatewayAccess


class Client:
    async def call(self, name, arguments, catalog):
        return {'isError': False, 'content': [{'type': 'text', 'text': 'source-data'}],
                'structuredContent': {'status': 'partial', 'gaps': ['missing'], 'provenance': {'id': 'actual'}}}


def test_declared_source_failure_blocks_replay_but_not_independent_metadata():
    resource = access(['data_gateway_other'])
    calls = []
    failure = {'isError': False, 'structuredContent': {'status': 'error',
        'provenance': {'request_id': 'source-request', 'execution_diagnostics': {
            'transport_phase': 'receive', 'request_sent': True, 'result_state': 'unknown',
            'remote_execution_possible': True, 'automatic_retry': False}}}}
    async def call(name, arguments, catalog):
        calls.append(name)
        return failure if name == request()['name'] else {'isError': False, 'structuredContent': {'status': 'ok', 'data': {}}}
    resource.client.call = call
    first = asyncio.run(resource.call('task-1', request()))
    assert first['is_error'] is True
    with pytest.raises(GatewayError, match='gateway_operation_retry_blocked'):
        asyncio.run(resource.call('task-1', dict(request(), call_id='new-call-id')))
    second = asyncio.run(resource.call('task-1', dict(request(), call_id='metadata', name='data_gateway_other')))
    assert second['is_error'] is False
    assert resource.publication()['available'] is True
    assert calls == [request()['name'], 'data_gateway_other']
    resource.bind('new-instruction', 'attempt-2', set(resource.catalog['tools']))
    asyncio.run(resource.call('new-instruction', request()))
    assert calls[-1] == request()['name']
    assert failure['isError'] is False


def test_contract_sections_survive_turns_without_reusing_business_results(tmp_path):
    from test_data_gateway_mcp import contract_context_gateway
    client, _, catalog, result = contract_context_gateway(tmp_path)
    calls = []
    async def call(name, arguments, catalog):
        calls.append(name)
        return (deepcopy(result) if name == 'data_gateway_describe_gateway_contract' else
                {'isError': True, 'structuredContent': {'status': 'error',
                    'gaps': [{'reason': 'source_unavailable'}]}})
    client.call = call
    resource = DataGatewayAccess(client, catalog)
    granted = set(catalog['tools'])
    resource.bind('first', 'attempt-1', granted)
    asyncio.run(resource.call('first', {'call_id': 'lookup', 'name': 'data_gateway_describe_gateway_contract',
        'arguments': {'tool_name': 'data_gateway_alpha', 'section': 'usage'}}))
    before = resource.contract_context('first')
    assert len(before['sections']) == 1
    resource.revoke('first')
    resource.bind('second', 'attempt-2', granted)
    assert resource.contract_context('second') == before
    failure = asyncio.run(resource.call('second', {'call_id': 'business', 'name': 'data_gateway_alpha', 'arguments': {}}))
    assert failure['is_error'] is True
    assert resource.contract_context('second') == before
    assert resource.publication()['available'] is True
    for allowed in [{'data_gateway_alpha'}, {'data_gateway_describe_gateway_contract'}]:
        task = 'restricted-' + str(len(allowed)) + next(iter(allowed))
        resource.bind(task, 'attempt', allowed)
        assert resource.contract_context(task)['sections'] == []
    other = DataGatewayAccess(client, catalog)
    other.bind('third', 'attempt-3', granted)
    assert other.contract_context('third')['sections'] == []
    before['sections'][0]['data']['usage']['purpose'] = 'modified'
    assert resource.contract_context('second')['sections'][0]['data']['usage']['purpose'] != 'modified'
    assert calls == ['data_gateway_describe_gateway_contract', 'data_gateway_alpha']


def test_publication_refresh_discards_metadata_and_late_old_task_results(tmp_path):
    from test_data_gateway_mcp import contract_context_gateway
    client, session, catalog, result = contract_context_gateway(tmp_path)
    async def call(*args, **kwargs):
        return deepcopy(result)
    client.call = call
    resource = DataGatewayAccess(client, catalog)
    resource.bind('old', 'attempt-1', set(catalog['tools']))
    document = {'call_id': 'first', 'name': 'data_gateway_describe_gateway_contract',
                'arguments': {'tool_name': 'alpha', 'section': 'usage'}}
    asyncio.run(resource.call('old', document))
    assert resource.contract_context('old')['sections']
    session.stamp = '2026-11-07T20:00:00+08:00'
    asyncio.run(resource.reload_contract())
    assert resource.catalog['revision'] != catalog['revision']
    asyncio.run(resource.call('old', dict(document, call_id='late')))
    resource.bind('new', 'attempt-2', set(resource.catalog['tools']))
    assert resource.contract_context('new')['sections'] == []
    asyncio.run(resource.call('new', dict(document, call_id='fresh')))
    assert resource.contract_context('new')['sections']


def test_contract_context_budget_and_conflicting_versions_are_safe(tmp_path):
    from test_data_gateway_mcp import contract_context_gateway
    from capstone_agent.data_gateway_mcp import encode
    client, _, catalog, result = contract_context_gateway(tmp_path)
    name = 'data_gateway_describe_gateway_contract'
    args = {'tool_name': 'alpha', 'section': 'usage'}
    other = deepcopy(result)
    other['structuredContent']['data'].update(section='input_schema')
    entries = [client.contract_context_entry(name, dict(args, section=section), value, catalog)
               for section, value in [('usage', result), ('input_schema', other)]]
    limit = max(len(encode(entry)) for entry in entries) + 8
    resource = DataGatewayAccess(client, catalog, contract_context_bytes=limit)
    resource.bind('task', 'attempt', set(catalog['tools']))
    response = [result]
    async def call(*args, **kwargs):
        return deepcopy(response[0])
    client.call = call
    def submit(call_id, section):
        return asyncio.run(resource.call('task', {'call_id': call_id, 'name': name,
            'arguments': dict(args, section=section)}))
    submit('one', 'usage')
    response[0] = other
    submit('two', 'input_schema')
    assert [entry['section'] for entry in resource.contract_context('task')['sections']] == ['input_schema']
    assert resource._contract_section_bytes <= limit
    response[0] = deepcopy(result)
    response[0]['structuredContent']['data']['usage']['purpose'] = 'x' * (limit * 2)
    assert submit('large', 'usage')['is_error'] is False
    assert [entry['section'] for entry in resource.contract_context('task')['sections']] == ['input_schema']
    response[0] = deepcopy(result)
    response[0]['structuredContent']['data']['contract_revision'] = 'contract-b'
    submit('conflict', 'usage')
    assert resource.contract_context('task')['sections'] == []
    response[0] = result
    submit('late', 'usage')
    assert resource.contract_context('task')['sections'] == []


def test_contract_snapshot_files_preserve_bytes_hashes_and_readonly_modes(tmp_path):
    import hashlib
    import json
    from pathlib import Path
    from capstone_agent.data_gateway_relay import stage_gateway_contract_context
    from capstone_agent.data_gateway_mcp import encode
    entry = {'tool': 'opaque', 'section': 'usage', 'contract_revision': 'revision',
             'data': {'purpose': 'Use admitted inputs'}}
    inputs = tmp_path / 'inputs'
    inputs.mkdir()
    manifest = stage_gateway_contract_context(inputs, {'catalog_revision': 'catalog',
        'instance_id': 'instance', 'sections': [entry]})
    document = json.loads(manifest.read_bytes())
    saved = document['sections'][0]
    body = Path(saved['path']).read_bytes()
    assert body == encode(entry)
    assert saved['sha256'] == hashlib.sha256(body).hexdigest()
    assert saved['size_bytes'] == len(body)
    assert Path(saved['path']).stat().st_mode & 0o222 == 0
    assert manifest.stat().st_mode & 0o222 == 0


def access(extra_tools=(), schemas=None):
    catalog = {'revision': 'a' * 64, 'tools': {'data_gateway_discover_data_capabilities': {}},
               'tool_hashes': {'data_gateway_discover_data_capabilities': 'b' * 64}}
    for tool in extra_tools:
        catalog['tools'][tool] = {}
        catalog['tool_hashes'][tool] = 'd' * 64
    catalog['tools'].update(schemas or {})
    resource = DataGatewayAccess(Client(), catalog)
    resource.bind('task-1', 'attempt-1', set(catalog['tools']))
    return resource


def test_task_grant_rejects_catalog_tool_outside_frozen_subset():
    resource = access(['data_gateway_other'])
    allowed = {request()['name']}
    resource.bind('restricted', 'attempt-2', allowed)
    allowed.add('data_gateway_other')
    calls = []
    async def upstream(name, arguments, catalog):
        calls.append((name, catalog))
        return await Client().call(name, arguments, catalog)
    resource.client.call = upstream
    with pytest.raises(GatewayError, match='gateway_tool_not_admitted'):
        asyncio.run(resource.call('restricted', dict(request(), name='data_gateway_other')))
    assert calls == []
    response = asyncio.run(resource.call('restricted', request()))
    assert calls == [(request()['name'], resource.catalog)]
    assert response['observation']['catalog_revision'] == resource.catalog['revision']


def test_batch_validation_uses_frozen_schema_without_calls_or_argument_changes():
    schema = {'type': 'object', 'properties': {'rows': {'type': 'array', 'items': {
        'type': 'object', 'properties': {'n': {'type': 'integer', 'minimum': 1}},
        'required': ['n'], 'additionalProperties': False}}}, 'required': ['rows'],
        'additionalProperties': False}
    resource = access(['dynamic_read'], {'dynamic_read': {'inputSchema': schema}})
    calls = [{'name': 'dynamic_read', 'arguments': {'rows': [{'n': 2}]}},
             {'name': 'dynamic_read', 'arguments': {'rows': [{'n': '2'}]}},
             {'name': 'dynamic_read', 'arguments': {'rows': [], 'extra': True}}]
    original = deepcopy(calls)
    result = resource.validate_batch('task-1', calls)
    assert result['valid'] is False
    assert [e['index'] for e in result['errors']] == [1, 2]
    assert result['errors'][0]['validation_errors'][0]['path'] == '/rows/0/n'
    assert calls == original
    assert resource._tasks['task-1']['started'] == set()
    resource.bind('restricted', 'attempt-2', [])
    assert resource.validate_batch('restricted', calls[:1])['errors'][0]['code'] == 'gateway_tool_not_admitted'
    resource.catalog['tools']['dynamic_read']['inputSchema'] = {'type': 'null'}
    assert resource.validate_batch('task-1', calls[:1])['valid'] is True
    with pytest.raises(GatewayError, match='gateway_task_not_admitted'):
        resource.validate_batch('absent', calls)


@pytest.mark.parametrize('allowed', [None, 'data_gateway_other', {'missing'}, {1}])
def test_task_binding_rejects_invalid_tool_grants(allowed):
    resource = access()
    with pytest.raises(GatewayError, match='gateway_tool_not_admitted'):
        resource.bind('restricted', 'attempt-2', allowed)


def test_empty_task_grant_does_not_inherit_catalog():
    resource = access()
    resource.bind('restricted', 'attempt-2', set())
    with pytest.raises(GatewayError, match='gateway_tool_not_admitted'):
        asyncio.run(resource.call('restricted', request()))


def request():
    return {'call_id': 'call-1', 'name': 'data_gateway_discover_data_capabilities', 'arguments': {}}


@pytest.mark.parametrize('budget', [0, 2])
def test_sequential_calls_retain_receipts_with_optional_total_budget(budget):
    from capstone_agent.application_capacity import CapacityExceeded, initialize_capacity
    initialize_capacity({'mcp_call_count': budget})
    try:
        resource = access()
        async def run():
            for index in range(4 if budget == 0 else 2):
                call_id = f'sequential-{index}'
                result = await resource.call('task-1', dict(request(), call_id=call_id))
                assert resource.verify('task-1', call_id, request()['name'], result['observation'], result['result_json'])
            if budget:
                with pytest.raises(CapacityExceeded):
                    await resource.call('task-1', dict(request(), call_id='over-budget'))
        asyncio.run(run())
    finally:
        initialize_capacity()


def test_batch_remains_bounded_when_total_call_budget_is_disabled():
    from capstone_agent.application_capacity import CapacityExceeded, initialize_capacity
    initialize_capacity({'mcp_call_count': 0, 'rpc_batch_requests': 2})
    try:
        with pytest.raises(CapacityExceeded) as caught:
            access().validate_batch('task-1', [dict(request(), call_id=f'batch-{i}') for i in range(3)])
        assert caught.value.dimension == 'rpc_batch_requests'
    finally:
        initialize_capacity()


def test_direct_and_composed_requests_share_task_read_reuse_with_verified_receipts():
    schema = {'inputSchema': {'type': 'object'}, 'annotations': {'readOnlyHint': True, 'idempotentHint': True}}
    resource = access(schemas={request()['name']: schema})
    calls = []
    async def upstream(name, arguments, catalog):
        calls.append(arguments)
        await asyncio.sleep(.01)
        return {'structuredContent': {'status': 'ok', 'data': {'n': len(calls)}}}
    resource.client.call = upstream
    async def run():
        a, b = await asyncio.gather(resource.call('task-1', request()),
                                   resource.call('task-1', dict(request(), call_id='composed:1')))
        assert len(calls) == 1
        assert b['observation']['reused_from'] == a['observation']['tool_call_id']
        assert a['result_json'] == b['result_json']
        assert resource.verify('task-1', 'composed:1', request()['name'], b['observation'], b['result_json'])
        fresh = await resource.call('task-1', dict(request(), call_id='refresh',
            observation_policy={'refresh_reason': 'User requested current source'}))
        assert len(calls) == 2 and 'reused_from' not in fresh['observation']
        resource.bind('other', 'other-attempt', {request()['name']})
        await resource.call('other', request())
        assert len(calls) == 3
    asyncio.run(run())


def test_task_read_reuse_preserves_live_polling_failed_reads_and_refresh_recovery():
    schema = {'inputSchema': {'type': 'object'}, 'annotations': {'readOnlyHint': True, 'idempotentHint': True}}
    resource = access(schemas={request()['name']: schema})
    calls = []
    async def upstream(name, arguments, catalog):
        calls.append(arguments)
        return {'structuredContent': {'status': 'error' if len(calls) == 2 else 'ok', 'data': {'job_ref': arguments.get('job_ref')}}}
    resource.client.call = upstream
    async def run():
        await resource.call('task-1', request())
        await resource.call('task-1', dict(request(), call_id='refresh', observation_policy={'refresh_reason':'Source changed'}))
        await resource.call('task-1', dict(request(), call_id='after-failure'))
        assert len(calls) == 3
        with pytest.raises(GatewayError, match='gateway_request_invalid'):
            await resource.call('task-1', dict(request(), call_id='bad', observation_policy={'refresh_reason':''}))
        with pytest.raises(GatewayError, match='gateway_call_already_started'):
            await resource.call('task-1', request())
        assert len(calls) == 3
        resource._tasks['task-1']['catalog']['tools'][request()['name']]['inputSchema']['properties'] = {'job_ref':{'type':'string'}}
        resource._tasks['task-1']['operation_refs'] = {'issued-job'}
        for i in range(2):
            await resource.call('task-1', dict(request(), call_id=f'poll-{i}', arguments={'job_ref':'issued-job'}))
        assert len(calls) == 5
    asyncio.run(run())


def test_contract_reload_updates_future_bindings_and_preserves_bound_catalog():
    resource = access()
    old = deepcopy(resource.catalog)
    new = deepcopy(old)
    new['revision'] = 'c' * 64
    new['tool_hashes'][request()['name']] = 'd' * 64
    seen = []

    async def prepare():
        return new

    async def upstream(name, arguments, catalog):
        seen.append(deepcopy(catalog))
        return await Client().call(name, arguments, catalog)

    resource.client.prepare = prepare
    resource.client.call = upstream
    asyncio.run(resource.reload_contract())
    resource.bind('new-task', 'new-attempt', {request()['name']})
    older = asyncio.run(resource.call('task-1', request()))
    newer = asyncio.run(resource.call('new-task', request()))
    assert seen == [old, new]
    assert older['observation']['catalog_revision'] == old['revision']
    assert newer['observation']['catalog_revision'] == new['revision']
    assert resource.verify('task-1', 'call-1', request()['name'], older['observation'], older['result_json'])


def test_failed_reload_does_not_offer_stale_contract_to_new_tasks():
    resource = access()
    async def prepare():
        raise GatewayError('gateway_connection_failed')
    resource.client.prepare = prepare
    with pytest.raises(GatewayError, match='gateway_connection_failed'):
        asyncio.run(resource.reload_contract())
    assert resource.publication()['available'] is False
    with pytest.raises(GatewayError):
        resource.bind('new-task', 'new-attempt', {request()['name']})
    assert asyncio.run(resource.call('task-1', request()))['observation']['catalog_revision'] == 'a' * 64


def test_only_admitted_successful_observations_reach_connection_bindings():
    resource = access()
    observed = []
    resource.view_bindings = SimpleNamespace(observe=lambda *args: observed.append(args))
    response = asyncio.run(resource.call('task-1', request()))
    assert len(observed) == 1
    name, arguments, result, catalog = observed[0]
    assert name == request()['name'] and arguments == {}
    assert result['structuredContent']['status'] == 'partial'
    assert catalog == resource.catalog
    assert response['observation']['tool'] == name
    with pytest.raises(GatewayError):
        asyncio.run(resource.call('task-1', dict(request(), call_id='bad', name='ungranted')))
    assert len(observed) == 1


def test_validated_failure_reaches_bindings_without_becoming_success():
    resource = access()
    observed = []
    resource.view_bindings = SimpleNamespace(observe=lambda *args: observed.append(args))
    async def upstream(name, arguments, catalog):
        return {'isError': False, 'structuredContent': {'status': 'error',
            'data': {'state': 'failed', 'error': {'reason': 'invalid_revision'}}}}
    resource.client.call = upstream
    response = asyncio.run(resource.call('task-1', request()))
    assert len(observed) == 1
    assert observed[0][2]['structuredContent']['data']['state'] == 'failed'
    assert response['observation']['tool'] == request()['name']


@pytest.mark.parametrize('failed_open', [False, True])
def test_preparation_jobs_require_an_issued_open_in_the_same_task(failed_open):
    resource = access(['data_gateway_open_network_model_view', 'data_gateway_get_network_model_job'],
        schemas={'data_gateway_get_network_model_job': {
        'inputSchema': {'type': 'object', 'properties': {'job_ref': {'type': 'string'}}, 'required': ['job_ref']}}})
    calls = []
    async def upstream(name, arguments, catalog):
        calls.append(name)
        data = ({'schema': 'gateway-electrical-view/1', 'state': 'preparing',
                 'model_ref': 'grid:test', 'preparation_ref': 'prepare-one'}
                if name.endswith('open_network_model_view') else
                {'job_ref': arguments['job_ref'], 'task_type': 'view_preparation', 'state': 'running'})
        return {'isError': failed_open, 'structuredContent': {'status': 'error' if failed_open else 'ok', 'data': data}}
    resource.client.call = upstream
    def job(task, call, ref='prepare-one'):
        return asyncio.run(resource.call(task, {'call_id': call, 'name': 'data_gateway_get_network_model_job', 'arguments': {'job_ref': ref}}))
    with pytest.raises(GatewayError, match='gateway_tool_not_admitted'):
        job('task-1', 'before')
    assert calls == []
    asyncio.run(resource.call('task-1', {'call_id': 'open', 'name': 'data_gateway_open_network_model_view', 'arguments': {'model_ref': 'grid:test'}}))
    if failed_open:
        with pytest.raises(GatewayError, match='gateway_tool_not_admitted'): job('task-1', 'after')
    else:
        assert job('task-1', 'after')['is_error'] is False
    resource.bind('task-2', 'attempt-2', set(resource.catalog['tools']))
    with pytest.raises(GatewayError, match='gateway_tool_not_admitted'): job('task-2', 'foreign')
    with pytest.raises(GatewayError, match='gateway_tool_not_admitted'): job('task-1', 'build', 'build-job')
    if not failed_open:
        async def wrong_kind(*_):
            return {'structuredContent': {'status':'ok','data':{'job_ref':'other-job','task_type':'build','state':'succeeded'}}}
        resource.client.call = wrong_kind
        with pytest.raises(GatewayError, match='gateway_output_invalid'): job('task-1', 'wrong-kind')
        assert not resource.verify('task-1', 'wrong-kind', 'data_gateway_get_network_model_job', {}, '{}')


@pytest.mark.parametrize('producer,reader', [
    ('data_gateway_build_network_model', 'data_gateway_get_network_model_job'),
    ('data_gateway_start_export', 'data_gateway_export_status')])
@pytest.mark.parametrize('field', ['job_ref', 'preparation_ref'])
def test_generic_operation_refs_are_task_owned(producer, reader, field):
    resource = access([producer, reader], schemas={reader: {'inputSchema': {
        'type': 'object', 'properties': {'job_ref': {'type': 'string'}}, 'required': ['job_ref']}}})
    calls = []
    async def upstream(name, arguments, catalog):
        calls.append(name)
        data = {field: 'operation-one'} if name == producer else {'job_ref': arguments['job_ref'], 'task_type': 'build'}
        return {'structuredContent': {'status': 'ok', 'data': data}}
    resource.client.call = upstream
    value = {'call_id': 'poll', 'name': reader, 'arguments': {'job_ref': 'operation-one'}}
    with pytest.raises(GatewayError, match='gateway_tool_not_admitted'):
        asyncio.run(resource.call('task-1', value))
    asyncio.run(resource.call('task-1', {'call_id': 'produce', 'name': producer, 'arguments': {}}))
    assert asyncio.run(resource.call('task-1', value))['is_error'] is False
    async def mismatch(*_):
        return {'structuredContent': {'status': 'ok', 'data': {'job_ref': 'foreign-operation'}}}
    resource.client.call = mismatch
    with pytest.raises(GatewayError, match='gateway_output_invalid'):
        asyncio.run(resource.call('task-1', {**value, 'call_id': 'wrong-reply'}))
    assert not resource.verify('task-1', 'wrong-reply', reader, {}, '{}')
    with pytest.raises(GatewayError, match='gateway_tool_not_admitted'):
        asyncio.run(resource.call('task-1', {**value, 'call_id': 'foreign-reply',
            'arguments': {'job_ref': 'foreign-operation'}}))
    async def stopped(*_):
        raise GatewayError('gateway_timeout')
    resource.client.call = stopped
    with pytest.raises(GatewayError, match='gateway_timeout'):
        asyncio.run(resource.call('task-1', {**value, 'call_id': 'timeout'}))
    with pytest.raises(GatewayError, match='gateway_timeout'):
        asyncio.run(resource.call('task-1', {**value, 'call_id': 'after-stop'}))
    resource.bind('foreign', 'attempt-other', {reader})
    with pytest.raises(GatewayError, match='gateway_tool_not_admitted'):
        asyncio.run(resource.call('foreign', value))
    resource.revoke('task-1')
    with pytest.raises(GatewayError, match='gateway_task_not_admitted'):
        asyncio.run(resource.call('task-1', {**value, 'call_id': 'after-revoke'}))
    assert calls == [producer, reader]


@pytest.mark.parametrize('data,status,is_error', [
    ({'rows': [{'job_ref': 'operation-one'}]}, 'ok', False),
    ({'job_ref': 'operation-one'}, 'error', False),
    ({'job_ref': 'operation-one'}, 'ok', True)])
def test_nested_or_failed_results_do_not_issue_operation_refs(data, status, is_error):
    resource = access(['data_gateway_start_export', 'data_gateway_export_status'])
    resource.catalog['tools']['data_gateway_export_status'] = {'inputSchema': {
        'properties': {'job_ref': {'type': 'string'}}}}
    async def upstream(*_):
        return {'isError': is_error, 'structuredContent': {'status': status, 'data': data}}
    resource.client.call = upstream
    asyncio.run(resource.call('task-1', {'call_id': 'produce', 'name': 'data_gateway_start_export', 'arguments': {}}))
    with pytest.raises(GatewayError, match='gateway_tool_not_admitted'):
        asyncio.run(resource.call('task-1', {'call_id': 'poll', 'name': 'data_gateway_export_status',
            'arguments': {'job_ref': 'operation-one'}}))


def test_undeclared_job_parameter_cannot_bypass_operation_ref_check():
    resource = access()
    with pytest.raises(GatewayError, match='gateway_tool_not_admitted'):
        asyncio.run(resource.call('task-1', {**request(), 'arguments': {'job_ref': 'foreign'}}))


def test_issued_receipt_binds_exact_task_call_and_result():
    resource = access()
    result = asyncio.run(resource.call('task-1', request()))
    assert result['observation']['parent_attempt_id'] == 'attempt-1'
    assert resource.verify('task-1', 'call-1', request()['name'], result['observation'], result['result_json'])
    augmented = dict(result['observation'], native_research_source={'source_ref': 'host-wrapper'})
    assert resource.verify('task-1', 'call-1', request()['name'], augmented, result['result_json'])
    assert not resource.verify('task-2', 'call-1', request()['name'], result['observation'], result['result_json'])
    assert not resource.verify('task-1', 'call-other', request()['name'], result['observation'], result['result_json'])
    assert not resource.verify('task-1', 'call-1', request()['name'], result['observation'], '{}')


def test_unknown_task_duplicate_call_and_model_tool_are_refused():
    resource = access()
    for task, value in [('other-task', request()), ('task-1', dict(request(), name='data_gateway_build_network_model')),
                        ('task-1', dict(request(), url='http://untrusted'))]:
        with pytest.raises(GatewayError):
            asyncio.run(resource.call(task, value))
    asyncio.run(resource.call('task-1', request()))
    with pytest.raises(GatewayError, match='gateway_call_already_started'):
        asyncio.run(resource.call('task-1', request()))
    resource.revoke('task-1')
    with pytest.raises(GatewayError):
        asyncio.run(resource.call('task-1', request()))


def test_verified_arguments_are_host_owned_and_available_only_for_exact_receipt():
    resource=access()
    arguments={'scope_id':'north','level':'equipment','selected_object_id':'station:one','voltage_min_kv':None}
    result=asyncio.run(resource.call('task-1',{**request(),'arguments':arguments}))
    arguments['voltage_min_kv']=330
    saved=resource.verified_arguments('task-1','call-1',request()['name'],result['observation'],result['result_json'])
    assert saved['voltage_min_kv'] is None
    saved['level']='region'
    assert resource.verified_arguments('task-1','call-1',request()['name'],result['observation'],result['result_json'])['level']=='equipment'
    assert 'arguments' not in result and 'arguments' not in result['observation']
    with pytest.raises(GatewayError):
        resource.verified_arguments('task-1','call-1',request()['name'],result['observation'],'forged')
    resource.revoke('task-1')
    with pytest.raises(GatewayError):
        resource.verified_arguments('task-1','call-1',request()['name'],result['observation'],result['result_json'])


def test_failed_call_is_not_replayed_or_issued_as_source():
    resource = access()

    async def failed(*_):
        raise GatewayError('gateway_call_failed_no_retry')

    resource.client.call = failed
    with pytest.raises(GatewayError):
        asyncio.run(resource.call('task-1', request()))
    with pytest.raises(GatewayError, match='gateway_call_already_started'):
        asyncio.run(resource.call('task-1', request()))
    assert not resource.verify('task-1', 'call-1', request()['name'], {}, '{}')


def test_transport_failure_stops_other_probes_only_for_the_failed_task():
    other = 'data_gateway_discover_business_services'
    resource = access([other])
    calls = []

    async def failed(name, *_):
        calls.append(name)
        raise GatewayError('gateway_timeout')

    resource.client.call = failed
    for value in [request(), dict(request(), call_id='call-2', name=other)]:
        with pytest.raises(GatewayError, match='gateway_timeout'):
            asyncio.run(resource.call('task-1', value))
    assert calls == [request()['name']]
    assert not resource.verify('task-1', 'call-2', other, {}, '{}')
    resource.bind('task-2', 'attempt-2', set(resource.catalog['tools']))
    resource.client = Client()
    assert asyncio.run(resource.call('task-2', request()))['is_error'] is False


def test_argument_failure_does_not_stop_a_corrected_call():
    resource = access()

    async def failed(*_):
        raise GatewayError('gateway_arguments_invalid')

    resource.client.call = failed
    with pytest.raises(GatewayError, match='gateway_arguments_invalid'):
        asyncio.run(resource.call('task-1', request()))
    resource.client = Client()
    assert asyncio.run(resource.call('task-1', dict(request(), call_id='call-2')))['is_error'] is False


def test_changed_tool_publication_does_not_stop_another_granted_tool():
    other = 'data_gateway_other'
    resource = access([other])
    calls = []
    async def upstream(name, arguments, catalog):
        calls.append(name)
        if name == request()['name']:
            raise GatewayError('gateway_publication_changed')
        return await Client().call(name, arguments, catalog)
    resource.client.call = upstream
    with pytest.raises(GatewayError, match='gateway_publication_changed'):
        asyncio.run(resource.call('task-1', request()))
    with pytest.raises(GatewayError, match='gateway_call_already_started'):
        asyncio.run(resource.call('task-1', request()))
    assert not resource.verify('task-1', 'call-1', request()['name'], {}, '{}')
    response = asyncio.run(resource.call('task-1', dict(request(), call_id='call-2', name=other)))
    assert response['is_error'] is False
    assert calls == [request()['name'], other]


def test_http_route_requires_task_grant_and_revocation(tmp_path):
    import threading
    import time
    import httpx
    from capstone_agent.general_pi_server import GeneralPiHost, make_server
    from capstone_agent.general_pi_relay import ProviderRelay
    resource = access()
    relay = ProviderRelay()
    runner = SimpleNamespace(gateway=resource, relay=relay)
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=lambda *_: ('', {}))
    server = make_server(host, control_token='host-secret', address=('127.0.0.1', 0), runner=runner)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f'http://127.0.0.1:{server.server_port}/data-gateway/task-1'
    try:
        with httpx.Client(trust_env=False) as client:
            # Start task lifetime after host/server/client initialization. Cold
            # runner startup must not consume the authorization under test.
            relay.register('task-1', 'task-grant', time.monotonic() + 10)
            assert client.post(url, json=request()).status_code == 401
            assert client.post(url, json=request(), headers={'Authorization': 'Bearer host-secret'}).status_code == 401
            response = client.post(url, json=request(), headers={'Authorization': 'Bearer task-grant'})
            assert response.status_code == 200
            assert response.json()['observation']['tool_call_id'] == 'call-1'
            relay.revoke('task-1')
            assert client.post(url, json=dict(request(), call_id='call-2'),
                               headers={'Authorization': 'Bearer task-grant'}).status_code == 401
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)


def test_host_publishes_gateway_only_for_explicit_enterprise_admission(tmp_path):
    from capstone_agent.data_gateway_relay import research_gateway_tools
    from capstone_agent.native_task_context import CURRENT_RESEARCH_POLICY_TEXT, GENERAL_CHAT_POLICY_TEXT
    from capstone_agent.general_pi_server import GeneralPiHost
    class Runner:
        gateway = access()
        def __call__(self, *_):
            return '', {}
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=Runner())
    publication = host.capability['data_gateway']
    assert publication['available']
    native = {'policy': {'system_policy': CURRENT_RESEARCH_POLICY_TEXT}}
    assert research_gateway_tools(native, publication) == {'data_gateway_discover_data_capabilities'}
    native['policy']['system_policy'] = GENERAL_CHAT_POLICY_TEXT
    assert research_gateway_tools(native, publication) == set()
    assert research_gateway_tools(None, publication) == set()
    assert research_gateway_tools({'policy': {'system_policy': CURRENT_RESEARCH_POLICY_TEXT}}, {'available': False}) == set()


def test_actual_sdk_child_calls_protected_http_relay_and_has_host_receipt(tmp_path):
    import json
    from pathlib import Path
    import subprocess
    import threading
    import time
    from capstone_agent.general_pi_server import GeneralPiHost, make_server
    from capstone_agent.general_pi_relay import ProviderRelay
    schema = {'name': 'discover_data_capabilities', 'inputSchema': {'type': 'object', 'properties': {}, 'additionalProperties': False}}
    resource = access(schemas={'data_gateway_discover_data_capabilities': schema})
    relay = ProviderRelay()
    runner = SimpleNamespace(gateway=resource, relay=relay)
    host = GeneralPiHost(root=tmp_path / 'host', identity={'engine': 'pi'}, run_task=lambda *_: ('', {}))
    server = make_server(host, control_token='host-control', address=('127.0.0.1', 0), runner=runner)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    try:
        fixture = Path(__file__).parent / 'fixtures/data-gateway-child-sdk.mjs'
        relay.register('task-1', 'task-grant', time.monotonic() + 20)
        config = {'workspace': str(workspace), 'gateway': {'url': f'http://127.0.0.1:{server.server_port}/data-gateway/task-1',
            'grant': 'task-grant', 'taskId': 'task-1', 'catalog': resource.catalog}}
        process = subprocess.run(['node', str(fixture)], cwd=Path(__file__).resolve().parents[3],
            input=json.dumps(config), text=True, capture_output=True, timeout=20)
        assert process.returncode == 0, process.stderr
        value = json.loads(process.stdout)
        event = value['event']
        assert value['turns'] == 2
        assert len(resource._tasks['task-1']['started']) == 1
        assert resource.verify('task-1', event['tool_call_id'], event['tool_name'],
                               event['result']['details'], event['result']['content'][0]['text'])
        assert value['receipt']['ref'] == event['result']['details']['native_research_source']['source_ref']
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)


def test_revocation_cancels_inflight_gateway_and_issues_no_receipt(tmp_path):
    import concurrent.futures
    import threading
    import time
    import httpx
    from capstone_agent.general_pi_server import GeneralPiHost, make_server
    from capstone_agent.general_pi_relay import ProviderRelay
    resource = access()
    started, stopped, released = threading.Event(), threading.Event(), threading.Event()

    async def waiting(*_):
        started.set()
        try:
            await asyncio.sleep(20)
        finally:
            stopped.set()

    resource.client.call = waiting
    relay = ProviderRelay()
    release = relay.release
    def release_and_signal(lease):
        release(lease)
        released.set()
    relay.release = release_and_signal
    runner = SimpleNamespace(gateway=resource, relay=relay)
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=lambda *_: ('', {}))
    server = make_server(host, control_token='host-control', address=('127.0.0.1', 0), runner=runner)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            relay.register('task-1', 'task-grant', time.monotonic() + 5)
            future = pool.submit(httpx.post, f'http://127.0.0.1:{server.server_port}/data-gateway/task-1',
                json=request(), headers={'Authorization': 'Bearer task-grant'}, trust_env=False, timeout=3)
            assert started.wait(2)
            relay.revoke('task-1')
            assert stopped.wait(2)
            with pytest.raises(httpx.HTTPError):
                future.result(timeout=2)
        assert not resource.verify('task-1', 'call-1', request()['name'], {}, '{}')
        # The cancelled coroutine and socket finish before the handler's finally
        # block. Wait for actual lease release, not merely client disconnection.
        assert released.wait(2)
        assert not relay.active
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)


def test_container_gateway_refuses_unprotected_mount_parent(tmp_path, monkeypatch):
    import os
    from pathlib import Path
    from capstone_agent import data_gateway_mcp
    from capstone_agent.data_gateway_relay import load_container_gateway
    root = tmp_path / 'private'
    root.mkdir(mode=0o700)
    selected = root / 'data-gateway/connection.json'
    calls = []
    class Prepared:
        def __init__(self, *_):
            calls.append('constructed')
        async def prepare(self):
            return access().catalog
    policy = tmp_path / 'policy.json'
    policy.write_text('{}')
    monkeypatch.setattr(data_gateway_mcp, 'DataGatewayMcp', Prepared)
    resource, publication = load_container_gateway(str(selected), policy, private_root=root, owner_uid=os.getuid())
    assert resource and publication['available']
    root.chmod(0o755)
    resource, publication = load_container_gateway(str(selected), policy, private_root=root, owner_uid=os.getuid())
    assert resource is None and publication['reason'] == 'gateway_private_mount_invalid'
    root.chmod(0o700)
    resource, publication = load_container_gateway(str(tmp_path / 'public/connection.json'), policy,
        private_root=root, owner_uid=os.getuid())
    assert resource is None and publication['reason'] == 'gateway_private_mount_invalid'
    assert len(calls) == 1


def test_unavailable_gateway_retains_only_configured_identity(tmp_path, monkeypatch):
    import os
    import json
    from capstone_agent.data_gateway_mcp import DataGatewayMcp, GatewayError
    from capstone_agent.data_gateway_relay import load_container_gateway
    root = tmp_path / 'private'
    root.mkdir(mode=0o700)
    directory = root / 'data-gateway'
    directory.mkdir()
    connection = directory / 'connection.json'
    connection.write_text(json.dumps({'name': 'Configured gateway', 'transport': 'streamable-http',
        'url': 'https://gateway.test/mcp', 'headers': {'Authorization': 'Bearer secret-canary'}}))
    connection.chmod(0o600)
    policy = tmp_path / 'policy.json'
    policy.write_text(json.dumps({'schema': 'capstone-data-gateway/2', 'resource_id': 'data-gateway',
        'namespace': 'data_gateway_', 'admission': 'trusted-service-safe-effects'}))
    async def unavailable(self):
        raise GatewayError('gateway_timeout')
    monkeypatch.setattr(DataGatewayMcp, 'prepare', unavailable)
    resource, publication = load_container_gateway(str(connection), policy, private_root=root, owner_uid=os.getuid())
    assert resource is None
    assert publication['identity'] == {'connection_name': 'Configured gateway', 'display_address': 'gateway.test:443'}
    assert publication['available'] is False
    assert 'secret-canary' not in json.dumps(publication)
