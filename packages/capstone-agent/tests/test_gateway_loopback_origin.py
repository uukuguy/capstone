import asyncio
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from capstone_agent.data_gateway_mcp import DataGatewayMcp, GatewayError

POLICY={'schema':'capstone-data-gateway/2','resource_id':'data-gateway',
        'namespace':'data_gateway_','admission':'trusted-service-safe-effects'}


def connection(tmp_path, origin):
    path=tmp_path/'connection.json'
    path.write_text(json.dumps({'transport':'streamable-http','url':'http://host.docker.internal:19131/mcp',
        'origin_authority':origin,'headers':{'Authorization':'Bearer fixture-secret-canary'}}))
    path.chmod(0o600)
    return path


def test_private_loopback_origin_reaches_actual_http_client_without_exposing_credentials(tmp_path,monkeypatch):
    import mcp
    import mcp.client.streamable_http
    captured={}
    @asynccontextmanager
    async def transport(url,*,http_client):
        captured.update(url=url,host=http_client.headers['Host'],auth=http_client.headers['Authorization'])
        yield object(),object(),None
    class Session:
        def __init__(self,*_): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*_): pass
        async def initialize(self):
            return SimpleNamespace(capabilities=SimpleNamespace(experimental={}),instructions=None,
                                   serverInfo=SimpleNamespace(model_dump=lambda:{}))
    monkeypatch.setattr(mcp.client.streamable_http,'streamable_http_client',transport)
    monkeypatch.setattr(mcp,'ClientSession',Session)
    client=DataGatewayMcp(connection(tmp_path,'127.0.0.1:19131'),POLICY)
    async def run():
        async with client._connect(): pass
    asyncio.run(run())
    assert captured['url']=='http://host.docker.internal:19131/mcp'
    assert captured['host']=='127.0.0.1:19131'
    assert captured['auth']=='Bearer fixture-secret-canary'
    assert 'fixture-secret-canary' not in json.dumps(client.public_identity())


@pytest.mark.parametrize('origin',['example.com:19131','localhost:19132','user@localhost:19131',
                                 'localhost:19131/path','localhost:19131\r\nX-Header:bad',{}])
def test_origin_cannot_supply_arbitrary_authority_port_or_headers(tmp_path,origin):
    with pytest.raises(GatewayError,match='gateway_connection_config_invalid'):
        DataGatewayMcp(connection(tmp_path,origin),POLICY)
