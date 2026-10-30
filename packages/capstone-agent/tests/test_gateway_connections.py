import asyncio
from contextlib import asynccontextmanager, contextmanager
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


def test_task_start_during_candidate_prepare_can_reject_commit_without_losing_selection(registry):
    first = registry.add(entry())['entries'][0]['id']
    second = registry.add(entry('http://other.example/mcp'))['entries'][1]['id']
    registry.select(first)
    original = registry.current_access
    paths = set(registry._paths)
    @contextmanager
    def task_guard():
        raise GatewayError('gateway_connections_busy')
        yield
    with pytest.raises(GatewayError, match='gateway_connections_busy'):
        registry.select(second, commit_guard=task_guard)
    assert registry.current_access is original
    assert registry.snapshot()['selected_id'] == first
    assert registry._paths == paths


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


def test_protected_seed_rotates_same_id_preserving_selection_and_custom_entries(tmp_path):
    from capstone_agent.gateway_connections import GatewayConnectionRegistry
    def seed(token, label):
        return {'id': 'local', 'label': label, 'connection': {
            'transport': 'streamable-http', 'url': 'http://localhost:18001/mcp',
            'headers': {'Authorization': 'Bearer ' + token}}}
    previous = GatewayConnectionRegistry(tmp_path, POLICY, seeds=[seed(TOKEN, 'Before')], client_factory=Client)
    previous.select('local')
    custom = previous.add(entry('http://custom.example/mcp'))['entries'][1]
    previous.close()
    rotated = GatewayConnectionRegistry(tmp_path, POLICY, seeds=[seed('rotated-private-token', 'After')], client_factory=Client)
    try:
        rotated.prepare_selected()
        assert rotated.current_access.client.config['headers']['Authorization'] == 'Bearer rotated-private-token'
        assert rotated.snapshot()['selected_id'] == 'local'
        assert rotated.snapshot()['entries'][0]['label'] == 'After'
        assert rotated.snapshot()['entries'][1]['id'] == custom['id']
        assert rotated.snapshot()['entries'][1]['url'] == custom['url']
    finally:
        rotated.close()
    with pytest.raises(GatewayError, match='gateway_connection_duplicate'):
        GatewayConnectionRegistry(tmp_path, POLICY, seeds=[{**seed(TOKEN, 'Conflict'), 'id': 'other'}], client_factory=Client)


def test_selected_startup_outage_recovers_in_background_once(tmp_path):
    from capstone_agent.gateway_connections import GatewayConnectionRegistry
    previous = GatewayConnectionRegistry(tmp_path, POLICY, client_factory=Client)
    selected = previous.add(entry())['entries'][0]['id']
    previous.select(selected)
    previous.close()
    restored = GatewayConnectionRegistry(tmp_path, POLICY, client_factory=Client)
    try:
        Client.fail_prepare = True
        with pytest.raises(GatewayError):
            restored.prepare_selected()
        assert restored.current_access is None
        revision = restored.snapshot()['revision']
        restored.refresh()
        deadline = time.monotonic() + 2
        while restored.snapshot()['checking'] and time.monotonic() < deadline:
            time.sleep(.005)
        assert restored.current_access is None
        failed = restored.snapshot()['entries'][0]
        assert failed['status'] == 'disconnected'
        assert failed['error'] == 'gateway_connection_failed'
        assert TOKEN not in json.dumps(failed)
        Client.fail_prepare = False
        prepares = Client.prepares
        restored.refresh()
        deadline = time.monotonic() + 2
        while restored.snapshot()['checking'] and time.monotonic() < deadline:
            time.sleep(.005)
        assert restored.current_access is not None
        assert restored.current_access.catalog['revision'] == 'r1'
        assert Client.prepares == prepares + 1
        assert restored.snapshot()['revision'] == revision
        restored.refresh()
        while restored.snapshot()['checking'] and time.monotonic() < deadline:
            time.sleep(.005)
        assert Client.prepares == prepares + 1
        retained = restored.current_access
        @asynccontextmanager
        async def unavailable(client):
            raise RuntimeError(TOKEN)
            yield
        original = Client.connect
        Client.connect = unavailable
        try:
            restored.refresh()
            while restored.snapshot()['checking'] and time.monotonic() < deadline:
                time.sleep(.005)
            assert restored.current_access is retained
        finally:
            Client.connect = original
    finally:
        Client.fail_prepare = False
        restored.close()


def test_background_recovery_cannot_replace_new_selection_and_releases_candidate(tmp_path):
    from capstone_agent.gateway_connections import GatewayConnectionRegistry
    initial = GatewayConnectionRegistry(tmp_path, POLICY, client_factory=Client)
    first = initial.add(entry())['entries'][0]['id']
    second = initial.add(entry('http://localhost:18003/mcp'))['entries'][1]['id']
    initial.select(first)
    initial.close()
    gate, started = threading.Event(), threading.Event()
    class Recovering(Client):
        async def prepare(self):
            if ':18001/' in self.config['url']:
                started.set()
                while not gate.is_set():
                    await asyncio.sleep(.005)
            return await super().prepare()
    restored = GatewayConnectionRegistry(tmp_path, POLICY, client_factory=Recovering)
    try:
        restored.refresh()
        assert started.wait(1)
        assert restored.snapshot()['checking']
        restored.select(second)
        revision = restored.snapshot()['revision']
        retained = restored.current_access
        gate.set()
        deadline = time.monotonic() + 2
        while restored.snapshot()['checking'] and time.monotonic() < deadline:
            time.sleep(.005)
        assert restored.current_access is retained
        assert restored.snapshot()['selected_id'] == second
        assert restored.snapshot()['revision'] == revision
        assert len(list(tmp_path.glob('.connection-*'))) == 1
    finally:
        gate.set()
        restored.close()


def test_health_and_admission_timeouts_are_bounded_and_sanitized(registry, monkeypatch):
    import capstone_agent.gateway_connections as module
    assert module.HEALTH_TIMEOUT_SECONDS == 3
    assert module.ADMISSION_TIMEOUT_SECONDS == 5
    registry.add(entry())
    monkeypatch.setattr(module, 'HEALTH_TIMEOUT_SECONDS', .01)
    monkeypatch.setattr(module, 'ADMISSION_TIMEOUT_SECONDS', .01)
    @asynccontextmanager
    async def hanging_connect(client):
        await asyncio.Event().wait()
        yield
    monkeypatch.setattr(Client, 'connect', hanging_connect)
    registry.refresh()
    deadline = time.monotonic() + 1
    while registry.snapshot()['checking'] and time.monotonic() < deadline:
        time.sleep(.005)
    assert not registry.snapshot()['checking']
    record = registry.snapshot()['entries'][0]
    assert record['status'] == 'disconnected'
    assert record['error'] == 'gateway_timeout'
    async def hanging_prepare(client):
        await asyncio.Event().wait()
    monkeypatch.setattr(Client, 'prepare', hanging_prepare)
    before = time.monotonic()
    with pytest.raises(GatewayError, match='^gateway_timeout$'):
        registry.probe(entry('http://other.example/mcp'))
    assert time.monotonic() - before < 1


@pytest.mark.parametrize('url', ['http://x/?token=secret', 'http://user:secret@x', 'file:///tmp/a', 'http://x/#a'])
def test_rejects_unsafe_addresses(registry, url):
    with pytest.raises(GatewayError, match='gateway_connection_input_invalid'):
        registry.probe(entry(url))
