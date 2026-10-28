import asyncio
import copy
import json
from contextlib import asynccontextmanager

import pytest

from capstone_agent.data_gateway_mcp import DataGatewayMcp, GatewayError


class Tool:
    def __init__(self, name='discover_data_capabilities'):
        self.name = name
        self.value = {'name': name, 'description': 'Discover data', 'inputSchema': {
            'type': 'object', 'properties': {}, 'additionalProperties': False}}

    def model_dump(self, **_):
        return copy.deepcopy(self.value)


class Session:
    def __init__(self):
        self.tools = [Tool(), Tool('build_network_model'), Tool('new_unapproved_tool')]
        self.calls = []

    async def list_tools(self):
        from types import SimpleNamespace
        return SimpleNamespace(tools=self.tools, nextCursor=None)

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        from types import SimpleNamespace
        result = {'content': [{'type': 'text', 'text': 'data'}], 'isError': False,
                  'structuredContent': {'status': 'partial', 'data': {'n': 1},
                                        'gaps': [{'reason': 'missing'}], 'provenance': {'request_id': 'source-1'}}}
        return SimpleNamespace(model_dump=lambda **_: copy.deepcopy(result))


def gateway(tmp_path):
    connection = tmp_path / 'private.json'
    connection.write_text(json.dumps({'transport': 'streamable-http', 'url': 'http://gateway.test:8000/mcp',
                                     'headers': {'Authorization': 'Bearer secret-canary'}}))
    connection.chmod(0o600)
    session = Session()

    @asynccontextmanager
    async def connect():
        yield session

    client = DataGatewayMcp(connection, {'schema': 'capstone-data-gateway/1',
        'resource_id': 'data-gateway', 'namespace': 'data_gateway_',
        'allowed_tools': ['discover_data_capabilities']}, connect=connect)
    return client, session


def test_catalog_omits_secrets_and_unapproved_tools(tmp_path):
    client, _ = gateway(tmp_path)
    catalog = asyncio.run(client.prepare())
    assert set(catalog['tools']) == {'data_gateway_discover_data_capabilities'}
    assert len(catalog['revision']) == 64
    assert 'secret-canary' not in json.dumps(catalog)
    assert 'gateway.test' not in json.dumps(catalog)


def test_call_validates_and_preserves_partial_source(tmp_path):
    client, session = gateway(tmp_path)
    catalog = asyncio.run(client.prepare())
    result = asyncio.run(client.call('data_gateway_discover_data_capabilities', {}, catalog))
    assert result['structuredContent']['status'] == 'partial'
    assert result['structuredContent']['provenance']['request_id'] == 'source-1'
    assert session.calls == [('discover_data_capabilities', {})]
    for name, args in [('build_network_model', {}), ('data_gateway_build_network_model', {}),
                       ('data_gateway_discover_data_capabilities', {'url': 'http://other'})]:
        with pytest.raises(GatewayError):
            asyncio.run(client.call(name, args, catalog))
    assert len(session.calls) == 1


def test_changed_or_forged_catalog_is_rejected_before_call(tmp_path):
    client, session = gateway(tmp_path)
    catalog = asyncio.run(client.prepare())
    session.tools[0].value['description'] = 'Changed publication'
    with pytest.raises(GatewayError, match='publication_changed'):
        asyncio.run(client.call('data_gateway_discover_data_capabilities', {}, catalog))
    assert not session.calls
    forged = copy.deepcopy(catalog)
    forged['tools']['data_gateway_build_network_model'] = Tool('build_network_model').value
    with pytest.raises(GatewayError):
        asyncio.run(client.call('data_gateway_build_network_model', {}, forged))


@pytest.mark.parametrize('change', ['addition', 'removal', 'description', 'invalid_schema', 'annotations', 'meta'])
def test_unrelated_published_tool_drift_does_not_block_the_unchanged_admitted_tool(tmp_path, change):
    initial, session = gateway(tmp_path)
    other = Tool('discover_network_models')
    if change != 'addition':
        session.tools.append(other)
    client = DataGatewayMcp(initial.connection_path, dict(initial.policy,
        allowed_tools=['discover_data_capabilities', 'discover_network_models']), connect=initial.connect)
    catalog = asyncio.run(client.prepare())
    if change == 'addition':
        session.tools.append(other)
    elif change == 'removal':
        session.tools.remove(other)
    elif change == 'invalid_schema':
        other.value['inputSchema'] = {'type': 'not-a-json-schema-type'}
    else:
        other.value[change] = {'changed': True} if change in {'annotations', 'meta'} else 'Changed unrelated tool'
    result = asyncio.run(client.call('data_gateway_discover_data_capabilities', {}, catalog))
    assert result['structuredContent']['status'] == 'partial'
    assert session.calls == [('discover_data_capabilities', {})]


def test_removal_of_discovery_does_not_revoke_a_different_unchanged_admitted_tool(tmp_path):
    initial, session = gateway(tmp_path)
    session.tools.append(Tool('discover_network_models'))
    client = DataGatewayMcp(initial.connection_path, dict(initial.policy,
        allowed_tools=['discover_data_capabilities', 'discover_network_models']), connect=initial.connect)
    catalog = asyncio.run(client.prepare())
    session.tools = [tool for tool in session.tools if tool.name != 'discover_data_capabilities']
    asyncio.run(client.call('data_gateway_discover_network_models', {}, catalog))
    assert session.calls == [('discover_network_models', {})]


@pytest.mark.parametrize('field', ['description', 'inputSchema', 'outputSchema', 'annotations', 'meta', 'removed'])
def test_every_part_of_the_called_tool_contract_remains_guarded(tmp_path, field):
    client, session = gateway(tmp_path)
    catalog = asyncio.run(client.prepare())
    if field == 'removed':
        session.tools = session.tools[1:]
    else:
        session.tools[0].value[field] = ({'type': 'object'} if field.endswith('Schema') else
            {'readOnlyHint': True} if field == 'annotations' else {'revision': 'changed'} if field == 'meta' else 'Changed')
    with pytest.raises(GatewayError, match='^gateway_publication_changed$'):
        asyncio.run(client.call('data_gateway_discover_data_capabilities', {}, catalog))
    assert session.calls == []


def test_forging_an_unused_catalog_entry_still_rejects_the_whole_caller_grant(tmp_path):
    initial, session = gateway(tmp_path)
    session.tools.append(Tool('discover_network_models'))
    client = DataGatewayMcp(initial.connection_path, dict(initial.policy,
        allowed_tools=['discover_data_capabilities', 'discover_network_models']), connect=initial.connect)
    catalog = asyncio.run(client.prepare())
    catalog['tools']['data_gateway_discover_network_models']['description'] = 'Forged unused entry'
    with pytest.raises(GatewayError, match='^gateway_tool_not_admitted$'):
        asyncio.run(client.call('data_gateway_discover_data_capabilities', {}, catalog))
    assert session.calls == []


def test_connection_failure_has_only_public_code(tmp_path):
    client, _ = gateway(tmp_path)

    @asynccontextmanager
    async def broken():
        raise RuntimeError('Bearer secret-canary http://gateway.test')
        yield

    client.connect = broken
    with pytest.raises(GatewayError) as caught:
        asyncio.run(client.prepare())
    assert str(caught.value) == 'gateway_connection_failed'


def test_legacy_policy_and_non_http_connection(tmp_path):
    client, _ = gateway(tmp_path)
    policy = dict(client.policy, allowed_tools=['build_network_model'])
    assert DataGatewayMcp(client.connection_path, policy).policy == policy
    connection = json.loads(client.connection_path.read_text())
    connection['url'] = 'file:///etc/passwd'
    client.connection_path.write_text(json.dumps(connection))
    with pytest.raises(GatewayError):
        DataGatewayMcp(client.connection_path, client.policy)


def test_legacy_policy_keeps_explicit_admission_without_business_name_denials(tmp_path):
    client, session = gateway(tmp_path)
    policy = dict(client.policy, allowed_tools=[*client.policy['allowed_tools'], 'discover_network_models'])
    admitted = DataGatewayMcp(client.connection_path, policy, connect=client.connect)
    session.tools.append(Tool('discover_network_models'))
    catalog = asyncio.run(admitted.prepare())
    result = asyncio.run(admitted.call('data_gateway_discover_network_models', {}, catalog))
    assert result['structuredContent']['status'] == 'partial'
    assert session.calls == [('discover_network_models', {})]
    for name in ['inspect_network_model', 'build_network_model',
                 'get_network_model_artifact', 'read_network_model_artifact']:
        assert DataGatewayMcp(client.connection_path,
            dict(policy, allowed_tools=[*policy['allowed_tools'], name])).policy['allowed_tools'][-1] == name


def test_electrical_view_tools_can_be_published_without_build_permissions(tmp_path):
    client, session = gateway(tmp_path)
    names = ['open_network_model_view', 'read_network_model_view', 'get_network_model_job']
    policy = dict(client.policy, allowed_tools=[*client.policy['allowed_tools'], *names])
    session.tools.extend(Tool(name) for name in names)
    admitted = DataGatewayMcp(client.connection_path, policy, connect=client.connect)
    assert all('data_gateway_' + name in asyncio.run(admitted.prepare())['tools'] for name in names)


def test_wrapped_transport_failures_keep_safe_diagnostic_codes():
    import httpx
    from capstone_agent.data_gateway_mcp import public_failure
    for error, expected in [
        (httpx.ReadTimeout('secret-canary'), 'gateway_timeout'),
        (TimeoutError('secret-canary'), 'gateway_timeout'),
        (httpx.ConnectError('secret-canary'), 'gateway_transport_failed'),
        (httpx.HTTPStatusError('secret-canary', request=httpx.Request('POST', 'http://localhost/mcp'),
            response=httpx.Response(421)), 'gateway_endpoint_rejected'),
    ]:
        wrapped = ExceptionGroup('secret-canary', [error])
        assert public_failure(wrapped, 'gateway_call_failed_no_retry') == expected


def test_wrapped_publication_guard_remains_precise_and_does_not_expose_unknown_messages():
    from capstone_agent.data_gateway_mcp import public_failure
    assert public_failure(ExceptionGroup('private', [GatewayError('gateway_publication_changed')]),
                          'gateway_call_failed_no_retry') == 'gateway_publication_changed'
    assert public_failure(ExceptionGroup('private', [GatewayError('secret-canary')]),
                          'gateway_call_failed_no_retry') == 'gateway_call_failed_no_retry'


def test_wrapped_mcp_teardown_preserves_the_pre_call_publication_rejection(tmp_path):
    client, session = gateway(tmp_path)
    catalog = asyncio.run(client.prepare())
    @asynccontextmanager
    async def wrapped_connect():
        try:
            yield session
        except Exception as error:
            raise ExceptionGroup('transport cleanup', [error]) from None
    client.connect = wrapped_connect
    session.tools[0].value['description'] = 'Changed publication'
    with pytest.raises(GatewayError, match='^gateway_publication_changed$'):
        asyncio.run(client.call('data_gateway_discover_data_capabilities', {}, catalog))
    assert session.calls == []


def test_real_streamable_http_discovery_call_and_bad_auth(tmp_path):
    import socket
    import threading
    import time
    import uvicorn
    from mcp.server.fastmcp import FastMCP
    from pydantic import BaseModel

    mcp = FastMCP('gateway fixture', stateless_http=True,
                  instructions='Start with discovery. Host policy remains authoritative.')

    class Response(BaseModel):
        status: str
        data: dict
        gaps: list
        provenance: dict

    @mcp.tool(annotations={'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': False})
    def discover_data_capabilities() -> Response:
        return Response(status='partial', data={'sample': 7},
                        gaps=[{'reason': 'not_full_coverage'}], provenance={'request_id': 'real-http'})

    app = mcp.streamable_http_app()

    class Auth:
        async def __call__(self, scope, receive, send):
            if scope['type'] == 'http' and dict(scope['headers']).get(b'authorization') != b'Bearer secret-canary':
                await send({'type': 'http.response.start', 'status': 401, 'headers': []})
                await send({'type': 'http.response.body', 'body': b'Unauthorized'})
                return
            await app(scope, receive, send)

    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(Auth(), log_level='critical', access_log=False))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not server.started and time.monotonic() < deadline:
            time.sleep(.01)
        assert server.started
        existing, _ = gateway(tmp_path)
        config = json.loads(existing.connection_path.read_text())
        config['url'] = f'http://127.0.0.1:{port}/mcp'
        existing.connection_path.write_text(json.dumps(config))
        client = DataGatewayMcp(existing.connection_path, DYNAMIC_POLICY)

        async def exercise():
            catalog = await client.prepare()
            assert catalog['instructions'] == 'Start with discovery. Host policy remains authoritative.'
            result = await client.call('data_gateway_discover_data_capabilities', {}, catalog)
            assert result['structuredContent']['provenance']['request_id'] == 'real-http'
            assert result['structuredContent']['status'] == 'partial'
            def discover_network_models() -> dict:
                return {'models': []}
            mcp.add_tool(discover_network_models)
            result = await client.call('data_gateway_discover_data_capabilities', {}, catalog)
            assert result['structuredContent']['provenance']['request_id'] == 'real-http'
            mcp.remove_tool('discover_network_models')
            await client.call('data_gateway_discover_data_capabilities', {}, catalog)
            mcp.remove_tool('discover_data_capabilities')
            with pytest.raises(GatewayError, match='^gateway_publication_changed$'):
                await client.call('data_gateway_discover_data_capabilities', {}, catalog)

        asyncio.run(exercise())
        config['headers']['Authorization'] = 'Bearer wrong-credential'
        existing.connection_path.write_text(json.dumps(config))
        with pytest.raises(GatewayError, match='gateway_authentication_failed'):
            asyncio.run(DataGatewayMcp(existing.connection_path, existing.policy).prepare())
    finally:
        server.should_exit = True
        thread.join(5)
        sock.close()


DYNAMIC_POLICY = {'schema': 'capstone-data-gateway/2', 'resource_id': 'data-gateway',
                  'namespace': 'data_gateway_', 'admission': 'trusted-service-safe-effects'}
SAFE_EFFECTS = {'readOnlyHint': True, 'destructiveHint': False, 'openWorldHint': False}


def dynamic_gateway(tmp_path):
    legacy, session = gateway(tmp_path)
    session.tools = [Tool('previously_unknown_action'), Tool('build_network_model')]
    for tool in session.tools:
        tool.value['annotations'] = dict(SAFE_EFFECTS,
            readOnlyHint=tool.name != 'build_network_model')
    return DataGatewayMcp(legacy.connection_path, DYNAMIC_POLICY, connect=legacy.connect), session


def test_dynamic_trusted_service_admits_new_read_and_closed_non_destructive_tools(tmp_path):
    client, session = dynamic_gateway(tmp_path)
    catalog = asyncio.run(client.prepare())
    assert set(catalog['tools']) == {'data_gateway_previously_unknown_action', 'data_gateway_build_network_model'}
    for name in catalog['tools']:
        assert asyncio.run(client.call(name, {}, catalog))['structuredContent']['status'] == 'partial'
    assert len(session.calls) == 2
    assert catalog['instructions'] == ''


@pytest.mark.parametrize('effects', [None, {}, {'readOnlyHint': True},
    dict(SAFE_EFFECTS, destructiveHint=True), dict(SAFE_EFFECTS, openWorldHint=True),
    dict(SAFE_EFFECTS, readOnlyHint=1), dict(SAFE_EFFECTS, destructiveHint=0),
    dict(SAFE_EFFECTS, openWorldHint=None)])
def test_dynamic_effects_fail_closed(tmp_path, effects):
    client, session = dynamic_gateway(tmp_path)
    session.tools[0].value['annotations'] = effects
    catalog = asyncio.run(client.prepare())
    assert set(catalog['tools']) == {'data_gateway_build_network_model'}
    with pytest.raises(GatewayError, match='gateway_tool_not_admitted'):
        asyncio.run(client.call('data_gateway_previously_unknown_action', {}, catalog))


@pytest.mark.parametrize('bad_name', ['UpperCase', 'bad-name', 'x' * 51, '', 'a.b'])
def test_dynamic_invalid_tool_names_reject_catalog(tmp_path, bad_name):
    client, session = dynamic_gateway(tmp_path)
    session.tools[0].name = bad_name
    session.tools[0].value['name'] = bad_name
    with pytest.raises(GatewayError, match='gateway_catalog_invalid'):
        asyncio.run(client.prepare())


def test_dynamic_duplicates_and_invalid_admitted_schema_reject_catalog(tmp_path):
    client, session = dynamic_gateway(tmp_path)
    session.tools.append(session.tools[0])
    with pytest.raises(GatewayError, match='gateway_catalog_invalid'):
        asyncio.run(client.prepare())
    session.tools.pop()
    session.tools[0].value['inputSchema'] = {'type': 'not-a-type'}
    with pytest.raises(GatewayError, match='gateway_catalog_invalid'):
        asyncio.run(client.prepare())


def test_initialize_guidance_is_bounded_revisioned_and_connection_local(tmp_path):
    from types import SimpleNamespace
    client, session = dynamic_gateway(tmp_path)
    guidance = 'Trusted service usage guidance; host policy remains authoritative.'
    @asynccontextmanager
    async def connect():
        yield SimpleNamespace(session=session, instructions=guidance)
    client.connect = connect
    original = asyncio.run(client.prepare())
    assert original['instructions'] == guidance
    guidance = 'Different usage guidance'
    second = asyncio.run(client.prepare())
    assert original['revision'] != second['revision']
    assert original['instructions'].startswith('Trusted')
    # Guidance drift is unrelated to the unchanged invoked tool contract.
    asyncio.run(client.call('data_gateway_previously_unknown_action', {}, original))
    guidance = '界' * 6000
    with pytest.raises(GatewayError, match='gateway_catalog_invalid'):
        asyncio.run(client.prepare())


def test_dynamic_pagination_keeps_all_tools_and_rejects_cursor_cycles(tmp_path):
    from types import SimpleNamespace
    client, session = dynamic_gateway(tmp_path)
    async def pages(cursor=None):
        return SimpleNamespace(tools=[session.tools[0 if cursor is None else 1]],
                               nextCursor='second' if cursor is None else None)
    session.list_tools = pages
    assert len(asyncio.run(client.prepare())['tools']) == 2
    async def cycle(cursor=None):
        return SimpleNamespace(tools=[], nextCursor='b' if cursor in (None, 'a') else 'a')
    session.list_tools = cycle
    with pytest.raises(GatewayError, match='gateway_catalog_invalid'):
        asyncio.run(client.prepare())


def test_concurrent_initialization_guidance_does_not_cross_sessions(tmp_path):
    from types import SimpleNamespace
    client, session = dynamic_gateway(tmp_path)
    sequence = iter(['first guidance', 'second guidance'])
    @asynccontextmanager
    async def connect():
        guidance = next(sequence)
        await asyncio.sleep(0)
        yield SimpleNamespace(session=session, instructions=guidance)
    client.connect = connect
    async def exercise():
        return await asyncio.gather(client.prepare(), client.prepare())
    first, second = asyncio.run(exercise())
    assert first['instructions'] == 'first guidance'
    assert second['instructions'] == 'second guidance'
    assert first['revision'] != second['revision']


def test_dynamic_called_effect_change_is_rejected_without_execution(tmp_path):
    client, session = dynamic_gateway(tmp_path)
    catalog = asyncio.run(client.prepare())
    session.tools[0].value['annotations']['openWorldHint'] = True
    with pytest.raises(GatewayError, match='gateway_publication_changed'):
        asyncio.run(client.call('data_gateway_previously_unknown_action', {}, catalog))
    assert session.calls == []
    asyncio.run(client.call('data_gateway_build_network_model', {}, catalog))
    assert session.calls == [('build_network_model', {})]


def test_repository_production_policy_uses_dynamic_admission():
    from pathlib import Path
    policy = json.loads((Path(__file__).resolve().parents[3] / 'configs/runtime/data-gateway.json').read_text())
    assert policy == DYNAMIC_POLICY


def test_invalid_changed_schema_is_a_tool_publication_rejection_not_a_global_catalog_failure(tmp_path):
    client, session = dynamic_gateway(tmp_path)
    catalog = asyncio.run(client.prepare())
    session.tools[0].value['inputSchema'] = {'type': 'not-a-type'}
    with pytest.raises(GatewayError, match='^gateway_publication_changed$'):
        asyncio.run(client.call('data_gateway_previously_unknown_action', {}, catalog))
    assert session.calls == []
    asyncio.run(client.call('data_gateway_build_network_model', {}, catalog))
