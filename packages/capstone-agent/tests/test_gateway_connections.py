import asyncio
from contextlib import asynccontextmanager
import json
import stat
import threading
import time

import pytest

from capstone_agent.data_gateway_mcp import GatewayError, InitializedGatewaySession

POLICY = {'schema': 'capstone-data-gateway/2', 'resource_id': 'data-gateway',
          'namespace': 'data_gateway_', 'admission': 'trusted-service-safe-effects'}
TOKEN = 'private-token-never-public'


class Client:
    active = peak = prepares = 0
    gate = None
    urls = []

    def __init__(self, path, policy):
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        self.path = path
        self.config = json.loads(path.read_text())
        self.urls.append(self.config['url'])

    def public_identity(self):
        return {'display_address': 'actual:18001'}

    async def prepare(self):
        type(self).prepares += 1
        if 'bad' in self.config['url'] or getattr(type(self), 'fail_prepare', False):
            raise RuntimeError(TOKEN)
        return {'tools': {'data_gateway_read': {}}, 'revision': 'r1',
                'server_info': {'name': 'actual-server', 'version': '1.0'}}

    @asynccontextmanager
    async def connect(self):
        cls = type(self)
        cls.active += 1
        cls.peak = max(cls.peak, cls.active)
        try:
            while cls.gate is not None and not cls.gate.is_set():
                await asyncio.sleep(.005)
            yield InitializedGatewaySession(object(), server_info={'name': 'actual-server', 'version': '1.0'})
        finally:
            cls.active -= 1


@pytest.fixture
def registry(tmp_path):
    from capstone_agent.gateway_connections import GatewayConnectionRegistry
    Client.active = Client.peak = Client.prepares = 0
    Client.gate = None
    Client.fail_prepare = False
    Client.urls = []
    item = GatewayConnectionRegistry(tmp_path / 'private', POLICY, client_factory=Client)
    yield item
    Client.gate = None
    item.close()


def entry(url='http://localhost:18001/mcp'):
    return {'url': url, 'token': TOKEN, 'name': 'User label'}


def test_persistent_selection_and_private_public_projection(registry):
    from capstone_agent.gateway_connections import GatewayConnectionRegistry
    added = registry.add(entry())
    key = added['entries'][0]['id']
    registry.select(key)
    assert registry.current_access is not None
    assert TOKEN not in json.dumps(registry.snapshot())
    assert registry.snapshot()['entries'][0]['identity']['server_name'] == 'actual-server'
    assert registry.snapshot()['entries'][0]['identity']['available'] is True
    assert stat.S_IMODE((registry.root / 'registry.json').stat().st_mode) == 0o600
    assert stat.S_IMODE(registry.root.stat().st_mode) == 0o700
    restored = GatewayConnectionRegistry(registry.root, POLICY, client_factory=Client)
    try:
        assert restored.snapshot()['selected_id'] == key
        assert restored.current_access is None
        restored.prepare_selected()
        assert restored.current_access is not None
    finally:
        restored.close()


def test_probe_does_not_save_and_errors_never_expose_upstream(registry):
    assert registry.probe(entry())['identity']['server_name'] == 'actual-server'
    assert registry.probe(entry())['identity']['available'] is True
    assert registry.snapshot()['entries'] == []
    with pytest.raises(GatewayError, match='gateway_connection_failed'):
        registry.add(entry('http://bad.example/mcp'))
    assert TOKEN not in json.dumps(registry.snapshot())
    with pytest.raises(GatewayError, match='gateway_authentication_failed'):
        registry.probe({'url': 'http://new.example/mcp'})


def test_failed_selection_or_save_preserves_old_access(registry, monkeypatch):
    first = registry.add(entry())['entries'][0]['id']
    registry.select(first)
    previous = registry.current_access
    other = registry.add(entry('http://localhost:18003/mcp'))['entries'][1]['id']
    Client.fail_prepare = True
    with pytest.raises(GatewayError, match='gateway_connection_failed'):
        registry.select(other)
    assert registry.current_access is previous
    assert registry.snapshot()['selected_id'] == first
    Client.fail_prepare = False
    monkeypatch.setattr(registry, '_persist', lambda value: (_ for _ in ()).throw(OSError(TOKEN)))
    with pytest.raises(GatewayError, match='gateway_registry_unavailable'):
        registry.select(other)
    assert registry.current_access is previous
    assert registry.snapshot()['selected_id'] == first


def test_refresh_nonblocking_deduplicated_bounded_initialize_only(registry):
    for port in range(18001, 18006):
        registry.add(entry(f'http://localhost:{port}/mcp'))
    prepares = Client.prepares
    Client.gate = threading.Event()
    before = time.monotonic()
    assert registry.refresh()['checking'] is True
    assert time.monotonic() - before < .2
    registry.refresh()
    deadline = time.monotonic() + 2
    while Client.active < 3 and time.monotonic() < deadline:
        time.sleep(.01)
    assert Client.active == Client.peak == 3
    Client.gate.set()
    while registry.snapshot()['checking'] and time.monotonic() < deadline:
        time.sleep(.01)
    assert not registry.snapshot()['checking']
    assert Client.prepares == prepares
    assert all(item['status'] == 'connected' for item in registry.snapshot()['entries'])


def test_duplicate_canonical_url_and_known_credential_reuse(registry):
    registry.add(entry('http://LOCALHOST:80/mcp'))
    assert registry.probe({'url': 'http://localhost/mcp'})['identity']
    with pytest.raises(GatewayError, match='gateway_connection_duplicate'):
        registry.add(entry('http://localhost/mcp'))


@pytest.mark.parametrize('selected_only', [False, True])
def test_published_instance_identity_rejects_alias_without_other_probes(registry, monkeypatch, selected_only):
    original = Client.prepare
    instance = {'schema_version': 1, 'instance_id': 'real-instance', 'instance_name': 'Actual instance',
                'environment': {'id': 'local', 'label': 'Local'}, 'offline': False,
                'data_source': {'label': 'Source'}}
    async def prepare(client):
        return {**await original(client), 'instance': instance}
    monkeypatch.setattr(Client, 'prepare', prepare)
    first = registry.add(entry())['entries'][0]['id']
    if selected_only:
        registry.select(first)
        # The retained selected publication remains authoritative when health
        # has not yet observed an identity (for example, after a refresh).
        registry._health.clear()
    before = Client.prepares
    with pytest.raises(GatewayError, match='^gateway_connection_duplicate$'):
        registry.add(entry('http://127.0.0.1:18001/mcp'))
    assert Client.prepares == before + 1
    assert len(registry.snapshot()['entries']) == 1


def test_distinct_published_instances_allow_same_port_alias(registry, monkeypatch):
    original = Client.prepare
    async def prepare(client):
        instance = {'schema_version': 1, 'instance_id': client.config['url'], 'instance_name': 'Actual instance',
                    'environment': {'id': 'local', 'label': 'Local'}, 'offline': False,
                    'data_source': {'label': 'Source'}}
        return {**await original(client), 'instance': instance}
    monkeypatch.setattr(Client, 'prepare', prepare)
    registry.add(entry())
    assert len(registry.add(entry('http://127.0.0.1:18001/mcp'))['entries']) == 2


def test_seeds_transport_rewrite_and_live_private_path(tmp_path):
    from capstone_agent.gateway_connections import GatewayConnectionRegistry
    seed = {'id': 'local', 'label': 'Known', 'connection': {
        'name': 'Known', 'transport': 'streamable-http', 'url': 'http://localhost:18001/mcp',
        'headers': {'Authorization': 'Bearer ' + TOKEN}}}
    item = GatewayConnectionRegistry(tmp_path, POLICY, seeds=[seed], client_factory=Client,
                                     transport_host='host.docker.internal')
    try:
        item.select('local')
        assert item.current_access.client.config['url'] == 'http://host.docker.internal:18001/mcp'
        assert item.current_access.client.path.exists()
        assert item.snapshot()['entries'][0]['url'] == seed['connection']['url']
        assert TOKEN not in json.dumps(item.snapshot())
    finally:
        item.close()
    assert not list(tmp_path.glob('.connection-*'))


def test_health_publishes_only_real_checked_instance_even_offline(registry, monkeypatch):
    registry.add(entry())
    instance = {'schema_version': 1, 'instance_id': 'real-id', 'instance_name': 'Published name',
                'environment': {'id': 'local', 'label': 'Local'}, 'offline': True,
                'data_source': {'label': 'Saved source'}, 'secret': TOKEN}
    @asynccontextmanager
    async def initialize(client):
        yield InitializedGatewaySession(object(), server_info={'name': 'Actual', 'version': '2', 'secret': TOKEN},
                                        instance_identity=instance)
    monkeypatch.setattr(Client, 'connect', initialize)
    registry.refresh()
    deadline = time.monotonic() + 2
    while registry.snapshot()['checking'] and time.monotonic() < deadline:
        time.sleep(.01)
    record = registry.snapshot()['entries'][0]
    assert record['status'] == 'connected'
    assert record['identity']['instance_name'] == 'Published name'
    assert record['identity']['offline'] is True
    assert record['identity']['available'] is True
    assert TOKEN not in json.dumps(record)


def test_close_skips_queued_health_probes(tmp_path):
    from capstone_agent.gateway_connections import GatewayConnectionRegistry
    seeds = [{'id': f'local-{i}', 'label': str(i), 'connection': {
        'transport': 'streamable-http', 'url': f'http://localhost:{18001+i}/mcp',
        'headers': {'Authorization': 'Bearer ' + TOKEN}}} for i in range(8)]
    started = []
    class Slow(Client):
        @asynccontextmanager
        async def connect(self):
            started.append(self.config['url'])
            await asyncio.sleep(.06)
            yield InitializedGatewaySession(object())
    item = GatewayConnectionRegistry(tmp_path, POLICY, seeds=seeds, client_factory=Slow)
    item.refresh()
    deadline = time.monotonic() + 2
    while not started and time.monotonic() < deadline:
        time.sleep(.001)
    item.close()
    assert len(started) <= 3


@pytest.mark.parametrize('url', ['http://x/?token=secret', 'http://user:secret@x', 'file:///tmp/a', 'http://x/#a'])
def test_rejects_unsafe_addresses(registry, url):
    with pytest.raises(GatewayError, match='gateway_connection_input_invalid'):
        registry.probe(entry(url))
