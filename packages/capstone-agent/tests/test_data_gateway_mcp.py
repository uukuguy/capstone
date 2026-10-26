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


def test_rejects_model_policy_and_non_http_connection(tmp_path):
    client, _ = gateway(tmp_path)
    policy = dict(client.policy, allowed_tools=['build_network_model'])
    with pytest.raises(GatewayError):
        DataGatewayMcp(client.connection_path, policy)
    connection = json.loads(client.connection_path.read_text())
    connection['url'] = 'file:///etc/passwd'
    client.connection_path.write_text(json.dumps(connection))
    with pytest.raises(GatewayError):
        DataGatewayMcp(client.connection_path, client.policy)


def test_model_inventory_is_explicitly_admitted_but_model_execution_stays_denied(tmp_path):
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
        with pytest.raises(GatewayError, match='gateway_policy_invalid'):
            DataGatewayMcp(client.connection_path, dict(policy, allowed_tools=[*policy['allowed_tools'], name]))


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

    mcp = FastMCP('gateway fixture', stateless_http=True)

    class Response(BaseModel):
        status: str
        data: dict
        gaps: list
        provenance: dict

    @mcp.tool()
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
        client = DataGatewayMcp(existing.connection_path, dict(existing.policy,
            allowed_tools=['discover_data_capabilities', 'discover_network_models']))

        async def exercise():
            catalog = await client.prepare()
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
