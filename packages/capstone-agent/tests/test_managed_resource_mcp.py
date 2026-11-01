import asyncio
import json
import os
import sys
from types import SimpleNamespace

import pytest
from mcp.types import Tool, CallToolResult, Implementation

from capstone_agent.managed_resource_mcp import (
    ManagedMcpError, ManagedMcpSession, checked_endpoint, published_tool_name, local_mcp_session,
)


class Session:
    def __init__(self):
        self.tools = [Tool(name='any.published-method', description='actual capability',
                           inputSchema={'type': 'object', 'properties': {'value': {'type': 'integer'}},
                                        'required': ['value'], 'additionalProperties': False})]
        self.calls = []

    async def list_tools(self, **kwargs):
        return SimpleNamespace(tools=self.tools, nextCursor=None)

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return CallToolResult(content=[], structuredContent={'value': arguments['value']})


def connection(session=None, access=lambda: None):
    return ManagedMcpSession(session or Session(), SimpleNamespace(
        instructions='Read these server instructions first', serverInfo=Implementation(name='fixture', version='1')),
        check_access=access)


def test_dynamic_discovery_and_exact_argument_admission():
    async def run():
        remote = Session()
        client = connection(remote)
        catalog = await client.discover()
        assert catalog['instructions'] == 'Read these server instructions first'
        name = next(iter(catalog['tools']))
        assert (await client.call(name, {'value': 7}, expected_revision=catalog['revision']))['structuredContent'] == {'value': 7}
        for args in ({'value': 'wrong'}, {'value': 7, 'extra': True}):
            with pytest.raises(ManagedMcpError, match='resource_arguments_invalid'):
                await client.call(name, args, expected_revision=catalog['revision'])
        assert remote.calls == [(name, {'value': 7})]
    asyncio.run(run())


def test_renamed_tool_changes_publication_before_execution():
    async def run():
        remote = Session()
        client = connection(remote)
        original = await client.discover()
        remote.tools[0] = remote.tools[0].model_copy(update={'name': 'renamed_method'})
        with pytest.raises(ManagedMcpError, match='resource_contract_changed'):
            await client.call('any.published-method', {'value': 1}, expected_revision=original['revision'])
        assert remote.calls == []
        current = await client.discover()
        await client.call('renamed_method', {'value': 1}, expected_revision=current['revision'])
        assert remote.calls[0][0] == 'renamed_method'
    asyncio.run(run())


def test_permission_revocation_stops_discovery_and_call():
    async def run():
        allowed = True
        def check():
            if not allowed:
                raise PermissionError('resource_permission_denied')
        remote = Session()
        client = connection(remote, check)
        original = await client.discover()
        allowed = False
        with pytest.raises(PermissionError):
            await client.call('any.published-method', {'value': 1}, expected_revision=original['revision'])
        assert remote.calls == []
    asyncio.run(run())


def test_call_failure_is_unknown_and_not_retried():
    async def run():
        remote = Session()
        async def fail(name, arguments):
            remote.calls.append((name, arguments))
            raise OSError('private server failure')
        remote.call_tool = fail
        client = connection(remote)
        catalog = await client.discover()
        with pytest.raises(ManagedMcpError) as caught:
            await client.call('any.published-method', {'value': 1}, expected_revision=catalog['revision'])
        assert caught.value.executed is None
        assert str(caught.value) == 'resource_call_outcome_unknown'
        assert len(remote.calls) == 1
    asyncio.run(run())


@pytest.mark.parametrize('url', ['file:///tmp/server', 'https://user:secret@host/mcp',
                                 'https://host/mcp?token=secret', 'https://host:99999/mcp', 'http://host/ bad'])
def test_endpoint_rejects_credentials_and_unsupported_addresses(url):
    with pytest.raises(ManagedMcpError):
        checked_endpoint(url)


def test_intranet_endpoint_and_deterministic_tool_identity():
    assert checked_endpoint('http://127.0.0.1:18001/mcp') == 'http://127.0.0.1:18001/mcp'
    assert published_tool_name('resource-one', 'tool') == published_tool_name('resource-one', 'tool')
    assert published_tool_name('resource-one', 'tool') != published_tool_name('resource-two', 'tool')


@pytest.mark.skipif(os.geteuid() == 0, reason='This fixture uses the unprivileged local developer account')
def test_real_local_mcp_handshake_discovery_and_call(tmp_path):
    source = tmp_path / 'server.py'
    source.write_text('''from mcp.server.fastmcp import FastMCP
server = FastMCP("managed-install-fixture", instructions="Fixture capability guidance")
@server.tool()
def renamed_capability(value: int) -> dict:
    return {"value": value + 1}
server.run(transport="stdio")
''')
    async def run():
        async with local_mcp_session(sys.executable, [str(source)], cwd=tmp_path,
                                     environment={}, uid=None, check_access=lambda: None) as client:
            catalog = await client.discover()
            assert catalog['instructions'] == 'Fixture capability guidance'
            assert 'renamed_capability' in catalog['tools']
            result = await client.call('renamed_capability', {'value': 4}, expected_revision=catalog['revision'])
            assert not result.get('isError')
            assert (result.get('structuredContent') or json.loads(result['content'][0]['text'])) == {'value': 5}
    asyncio.run(run())
