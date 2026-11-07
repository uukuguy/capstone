"""Protocol tests: no gateway repository or credentials are required."""
import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
from types import SimpleNamespace
import json

import pytest

from capstone_agent.data_gateway_mcp import DataGatewayMcp, InitializedGatewaySession, fingerprint


EXTENSION = 'data-gateway/progressive-discovery'


def progressive_gateway(tmp_path, *, output=True):
    path = tmp_path / 'connection.json'
    path.write_text(json.dumps({'transport': 'streamable-http', 'url': 'http://gateway.test/mcp',
                               'headers': {'Authorization': 'Bearer secret-canary'}}))
    path.chmod(0o600)
    schemas = {'input_schema': {'type': 'object', 'properties': {'value': {'type': 'integer'}},
                                'required': ['value'], 'additionalProperties': False},
               'output_schema': {'type': 'object', 'required': ['value']} if output else None,
               'usage': {'purpose': 'Reusable source action'}}
    item = {'name': 'new_action', 'id': 'action', 'provider_id': 'provider', 'registration_id': 'reg',
            'toolset_id': 'set', 'tool_key': 'k' * 64, 'tool_contract_revision': 't' * 64,
            'summary_revision': 's' * 64, 'effects': {'readOnlyHint': True, 'destructiveHint': False,
                'openWorldHint': False}, 'capability': {'semantics': {'purpose': 'Read a value'}},
            'output_schema_state': 'declared' if output else 'absent',
            'section_fingerprints': {s: fingerprint(v) for s, v in schemas.items()}}
    declaration = {'version': '1', 'identity': {'schema_version': 1, 'instance_id': 'instance',
        'instance_name': 'Local', 'offline': False, 'environment': {'id': 'local', 'label': 'Local'},
        'data_source': {'label': 'Source'}}, 'access_view_id': 'view', 'publication_revision': 'pub',
        'fingerprint_version': 'canonical-json-sha256/1', 'transport': 'resources/read',
        'request_encoding': 'base64url-unpadded-utf8-json',
        'entries': {op: {'uri_template': 'gateway://discovery/v1/' + op + '/{request}',
                        'input_schema': {'type': 'object'}} for op in ('catalog', 'contracts', 'check')},
        'limits': {'catalog_items': 50, 'catalog_bytes': 131072, 'batch_items': 8,
                   'batch_bytes': 524288, 'request_bytes': 16384}}
    class Session:
        def __init__(self):
            self.requests = []
            self.corrupt = False
            self.changed = False
            self.page_mode = False
            self.response_view = 'view'
        async def list_tools(self, **kwargs):
            pytest.fail('Progressive path must not call tools/list')
        async def call_tool(self, *args, **kwargs):
            pytest.fail('High-level SDK call_tool can trigger tools/list')
        async def read_resource(self, uri):
            from base64 import urlsafe_b64decode
            op, encoded = str(uri).split('/')[-2:]
            args = json.loads(urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)))
            self.requests.append((op, args))
            packet = {'protocol_version': '1', 'status': 'ok', 'publication_revision': 'other' if self.changed else 'pub',
                      'access_view_id': self.response_view, 'source_accessed': False}
            if op == 'catalog':
                packet.update(view='tools', items=[deepcopy(item)], total=1, truncated=False, next_cursor=None)
                if self.page_mode:
                    packet.update(total=2, truncated=True, next_cursor='c' * 300)
            elif op == 'check':
                packet.update(changed=self.changed)
            else:
                packet['items'] = [{**deepcopy(item), 'status': 'ok',
                    'sections': {s: deepcopy(schemas[s]) for s in args['requests'][0]['sections']}}]
                if self.corrupt:
                    packet['items'][0]['sections']['input_schema'] = {'type': 'null'}
            return SimpleNamespace(contents=[SimpleNamespace(text=json.dumps(packet))])
        async def send_request(self, request, result_type):
            from mcp.types import CallToolResult, TextContent
            self.requests.append(('tools/call', request.model_dump(by_alias=True, exclude_none=True)))
            return CallToolResult(content=[TextContent(type='text', text='value')], structuredContent={'value': 4})
    session = Session()
    @asynccontextmanager
    async def connect():
        yield InitializedGatewaySession(session, '', {}, declaration['identity'], declaration)
    client = DataGatewayMcp(path, {'schema': 'capstone-data-gateway/2', 'resource_id': 'data-gateway',
                                 'namespace': 'data_gateway_', 'admission': 'trusted-service-safe-effects'}, connect=connect)
    return client, session, declaration


def test_progressive_prepare_contains_metadata_without_fake_schema(tmp_path):
    client, session, _ = progressive_gateway(tmp_path)
    catalog = asyncio.run(client.prepare())
    tool = catalog['tools']['data_gateway_new_action']
    assert 'inputSchema' not in tool and 'outputSchema' not in tool
    assert catalog['progressive']['publication_revision'] == 'pub'
    assert all(op == 'catalog' for op, _ in session.requests)


@pytest.mark.parametrize('output', [True, False])
def test_selected_exact_contract_and_first_execution_never_list_tools(tmp_path, output):
    client, session, _ = progressive_gateway(tmp_path, output=output)
    async def run():
        catalog = await client.prepare()
        await client.call('data_gateway_new_action', {'value': 4}, catalog)
        await client.call('data_gateway_new_action', {'value': 4}, catalog)
    asyncio.run(run())
    loads = [args for op, args in session.requests if op == 'contracts']
    assert len(loads) == 1
    assert loads[0]['requests'][0]['sections'] == (['input_schema', 'output_schema'] if output else ['input_schema'])
    calls = [args for op, args in session.requests if op == 'tools/call']
    assert len(calls) == 2
    assert calls[0]['params']['_meta'][EXTENSION]['expected_publication_revision'] == 'pub'


def test_corrupt_section_is_rejected_before_execution(tmp_path):
    client, session, _ = progressive_gateway(tmp_path)
    async def run():
        catalog = await client.prepare()
        session.corrupt = True
        with pytest.raises(ValueError, match='gateway_catalog_invalid'):
            await client.call('data_gateway_new_action', {'value': 4}, catalog)
    asyncio.run(run())
    assert not any(op == 'tools/call' for op, _ in session.requests)


def test_invalid_input_never_dispatches(tmp_path):
    client, session, _ = progressive_gateway(tmp_path)
    async def run():
        catalog = await client.prepare()
        with pytest.raises(ValueError, match='gateway_arguments_invalid'):
            await client.call('data_gateway_new_action', {'value': 'wrong'}, catalog)
    asyncio.run(run())
    assert not any(op == 'tools/call' for op, _ in session.requests)


def test_task_contract_resolution_preserves_frozen_metadata_and_grants(tmp_path):
    from capstone_agent.data_gateway_relay import DataGatewayAccess
    client, session, _ = progressive_gateway(tmp_path)
    async def run():
        catalog = await client.prepare()
        access = DataGatewayAccess(client, catalog)
        access.bind('task', 'attempt', {'data_gateway_new_action'})
        result = await access.resolve_contracts('task', ['data_gateway_new_action'])
        assert result['catalog_revision'] == catalog['revision']
        assert 'inputSchema' in result['tools']['data_gateway_new_action']
        assert 'inputSchema' not in access.frozen_catalog(catalog['revision'])['tools']['data_gateway_new_action']
        assert not access._tasks['task']['issued']
        assert access.validate_batch('task', [{'name': 'data_gateway_new_action', 'arguments': {'value': 4}}])['valid']
        with pytest.raises(ValueError, match='gateway_tool_not_admitted'):
            await access.resolve_contracts('task', ['ungranted'])
    asyncio.run(run())


@pytest.mark.parametrize('kind', ['authorization', 'publication'])
def test_changed_contract_response_never_dispatches(tmp_path, kind):
    client, session, _ = progressive_gateway(tmp_path)
    async def run():
        catalog = await client.prepare()
        if kind == 'authorization':
            session.response_view = 'different'
        else:
            session.changed = True
        with pytest.raises(ValueError, match='gateway_publication_changed'):
            await client.call('data_gateway_new_action', {'value': 4}, catalog)
    asyncio.run(run())
    assert not any(op == 'tools/call' for op, _ in session.requests)


def test_long_cursor_is_forwarded_but_repeated_page_is_rejected(tmp_path):
    client, session, _ = progressive_gateway(tmp_path)
    session.page_mode = True
    with pytest.raises(ValueError, match='gateway_catalog_invalid'):
        asyncio.run(client.prepare())
    assert len(session.requests) == 2
    assert session.requests[-1][1]['cursor'] == 'c' * 300


def test_malformed_supported_handshake_is_not_silently_downgraded(tmp_path):
    client, session, declaration = progressive_gateway(tmp_path)
    declaration['entries']['catalog']['uri_template'] = 'file:///private/{request}'
    with pytest.raises(ValueError, match='gateway_catalog_invalid'):
        asyncio.run(client.prepare())
    assert not session.requests
