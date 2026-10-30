import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread
from types import SimpleNamespace
import time

import httpx
import pytest
from concurrent.futures import CancelledError


def test_stream_diagnostics_retains_only_finish_metadata():
    from capstone_agent.general_pi_relay import StreamDiagnostics
    trace = StreamDiagnostics()
    stream = (b'data: {"choices":[{"delta":{"content":"PRIVATE_SECRET"},"finish_reason":null}]}\n\n'
              b'data: {"choices":[{"finish_reason":"network_error"}]}\n\ndata: [DONE]\n\n')
    for position in range(0, len(stream), 7):
        trace.feed(stream[position:position+7])
    assert trace.summary() == {'stream_done': True, 'finish_reason': 'network_error'}
    assert 'PRIVATE_SECRET' not in repr(vars(trace))
    trace.feed(b'data: ' + b'x' * 200_000)
    assert len(trace.pending) <= 131072
    trace.feed(b'\ndata: [DONE]\n')
    assert trace.summary()['stream_done'] is True


def test_relay_default_admits_parallel_children_and_debug_overflow_interrupts(tmp_path):
    from capstone_agent.application_capacity import initialize_capacity, current_capacity, CapacityExceeded
    from capstone_agent.general_pi_relay import ProviderRelay
    from capstone_agent.general_pi_server import GeneralPiHost
    from threading import Event
    original = current_capacity()
    left, right = socket.socketpair()
    relay = None
    try:
        initialize_capacity(mode='debug')
        relay = ProviderRelay()
        relay.register('task', 'grant', time.monotonic() + 30)
        leases = [relay.acquire('task', 'grant', left) for _ in range(3)]
        assert len(leases) == 3
        relay.per_task = 3
        with pytest.raises(CapacityExceeded) as raised:
            relay.acquire('task', 'grant', left)
        assert raised.value.dimension == 'provider_relay_task_requests'
        host = GeneralPiHost(root=tmp_path, identity={'engine':'pi'}, run_task=lambda *_: ('Done', {}))
        host._tasks['task'] = {'cancel': Event()}
        host.interrupt_capacity('task', raised.value)
        assert host._tasks['task']['cancel'].is_set()
        assert host._tasks['task']['capacity_failure']['fatal'] is True
    finally:
        if relay is not None:
            relay.revoke('task')
            for lease in list(relay.active):
                relay.release(lease)
        left.close(); right.close()
        initialize_capacity(original)


def test_relay_grants_bound_concurrency_and_revoke_active_connections():
    from capstone_agent.general_pi_relay import ProviderRelay
    from capstone_agent.application_capacity import CapacityExceeded
    relay = ProviderRelay(max_requests=2, per_task=1)
    relay.register('one', 'grant-one', time.monotonic()+2)
    relay.register('two', 'grant-two', time.monotonic()+2)
    left, right = socket.socketpair()
    try:
        lease = relay.acquire('one', 'grant-one', left)
        with pytest.raises(CapacityExceeded):
            relay.acquire('one', 'grant-one', left)
        other = relay.acquire('two', 'grant-two', left)
        relay.register('three', 'grant-three', time.monotonic()+2)
        with pytest.raises(CapacityExceeded):
            relay.acquire('three', 'grant-three', left)
        relay.revoke('one')
        assert lease.cancelled.is_set()
        assert right.recv(1) == b''
        with pytest.raises(PermissionError):
            relay.acquire('one', 'grant-one', left)
        relay.release(lease)
        relay.release(other)
    finally:
        left.close()
        right.close()


def test_stream_relay_does_not_count_protocol_overhead_as_a_document_limit(tmp_path):
    from capstone_agent.general_pi_relay import ProviderRelay
    from capstone_agent.general_pi_server import GeneralPiHost, make_server
    event = b'data: {"metadata":{"padding":"' + b'x' * 8192 + b'"},"choices":[{"delta":{"content":"x"},"finish_reason":null}]}\n\n'
    payload = event * 640 + b'data: {"choices":[{"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n'
    class Upstream(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            self.rfile.read(int(self.headers['Content-Length']))
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.end_headers()
            try:
                self.wfile.write(payload)
            except OSError:
                pass
    upstream = ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
    relay = ProviderRelay()
    relay.register('task', 'grant', time.monotonic() + 10)
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=lambda *_: ('unused', {}))
    server = make_server(host, control_token='control', address=('127.0.0.1', 0),
        runner=SimpleNamespace(relay=relay, model='fixture'),
        upstream=f'http://127.0.0.1:{upstream.server_port}', provider_key='fixture-only')
    for item in (server, upstream):
        Thread(target=item.serve_forever, daemon=True).start()
    try:
        result = httpx.post(f'http://127.0.0.1:{server.server_port}/provider/task/chat/completions',
            json={'model': 'fixture', 'stream': True}, headers={'Authorization': 'Bearer grant'}, timeout=5)
        assert result.status_code == 200
        assert result.content == payload
    finally:
        relay.revoke('task')
        for item in (server, upstream):
            item.shutdown()
            item.server_close()


def test_relay_deadline_closes_slow_downstream_without_new_task_work():
    from capstone_agent.general_pi_relay import ProviderRelay
    relay = ProviderRelay()
    relay.register('one', 'grant', time.monotonic()+0.1)
    left, right = socket.socketpair()
    right.settimeout(1)
    lease = relay.acquire('one', 'grant', left)
    try:
        assert right.recv(1) == b''
        assert lease.cancelled.is_set()
    finally:
        relay.release(lease)
        left.close()
        right.close()


@pytest.mark.parametrize('stage', ['headers', 'body'])
@pytest.mark.parametrize('ending', ['deadline', 'revoke'])
def test_actual_relay_cancels_slow_headers_and_body_and_rejects_extra_requests(tmp_path, stage, ending):
    from capstone_agent.general_pi_relay import ProviderRelay
    from capstone_agent.general_pi_server import GeneralPiHost, make_server
    started, stopped = Event(), Event()
    class Upstream(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass
        def do_POST(self):
            self.rfile.read(int(self.headers['Content-Length']))
            started.set()
            try:
                if stage == 'headers':
                    for byte in b'HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n\r\n':
                        self.wfile.write(bytes([byte]))
                        self.wfile.flush()
                        time.sleep(0.02)
                else:
                    self.send_response(200)
                    self.end_headers()
                for _ in range(200):
                    self.wfile.write(b'x')
                    self.wfile.flush()
                    time.sleep(0.02)
            except OSError:
                pass
            finally:
                stopped.set()
    upstream = ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
    relay = ProviderRelay(max_requests=1, per_task=1)
    relay.register('task', 'grant', time.monotonic()+0.7)
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=lambda *_: ('Done', {}))
    server = make_server(host, control_token='control', address=('127.0.0.1', 0),
        runner=SimpleNamespace(relay=relay, model='fixture'),
        upstream=f'http://127.0.0.1:{upstream.server_port}', provider_key='fixture-only')
    threads = [Thread(target=item.serve_forever, daemon=True) for item in (server, upstream)]
    for thread in threads:
        thread.start()
    url = f'http://127.0.0.1:{server.server_port}/provider/task/chat/completions'
    headers = {'Authorization': 'Bearer grant'}
    def post():
        try:
            httpx.post(url, json={'model': 'fixture'}, headers=headers, timeout=2)
        except httpx.HTTPError:
            pass
    client = Thread(target=post)
    client.start()
    try:
        assert started.wait(1)
        extra = httpx.post(url, json={'model': 'fixture'}, headers=headers, timeout=1)
        assert extra.status_code == 503
        if ending == 'revoke':
            relay.revoke('task')
        client.join(timeout=1)
        assert not client.is_alive()
        assert stopped.wait(0.5), 'Upstream exchange survived task termination'
        deadline = time.monotonic()+0.5
        while relay.active and time.monotonic() < deadline:
            time.sleep(0.01)
        assert not relay.active
    finally:
        relay.revoke('task')
        for item in (server, upstream):
            item.shutdown()
            item.server_close()
        for thread in threads:
            thread.join(timeout=1)
        client.join(timeout=1)


@pytest.mark.parametrize('entry', ['control_client', 'provider_relay'])
def test_deadline_does_not_join_slow_dns_resolver(monkeypatch, entry):
    from capstone_agent.bounded_http_loop import run_http
    from capstone_agent.general_pi_relay import ProviderRelay, forward_provider
    from capstone_agent.pi_delegation import HttpGeneralPiExecutor
    original = socket.getaddrinfo
    entered = Event()
    def slow(host, port, *args, **kwargs):
        entered.set()
        time.sleep(1.2)
        return original('127.0.0.1', port, *args, **kwargs)
    monkeypatch.setattr(socket, 'getaddrinfo', slow)
    started = time.monotonic()
    if entry == 'control_client':
        client = HttpGeneralPiExecutor('http://fixture.invalid:8790', identity={'engine': 'pi'}, capability={})
        with pytest.raises(TimeoutError):
            client._call('GET', '/health/ready', total_timeout=0.1)
    else:
        relay = ProviderRelay()
        relay.register('task', 'grant', time.monotonic()+0.1)
        left, right = socket.socketpair()
        lease = relay.acquire('task', 'grant', left)
        try:
            with pytest.raises(CancelledError):
                run_http(forward_provider(SimpleNamespace(), lease, 'http://fixture.invalid:8790', b'{}', 'fixture'))
        finally:
            relay.release(lease)
            left.close()
            right.close()
    assert entered.is_set()
    assert time.monotonic() - started < 0.5


def test_downstream_writer_does_not_block_other_exchange_deadlines():
    import asyncio
    from capstone_agent.bounded_http_loop import run_http, write_http
    def slow():
        time.sleep(1)
    async def timed_write():
        await asyncio.wait_for(write_http(slow), timeout=0.1)
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        run_http(timed_write())
    assert time.monotonic()-started < 0.5
    async def other():
        await asyncio.sleep(0.01)
        return 'available'
    assert run_http(other()) == 'available'


def test_stream_failure_classifies_protocol_state_without_a_time_heuristic():
    from capstone_agent.general_pi_relay import StreamDiagnostics
    trace = StreamDiagnostics()
    assert trace.failure_code() == 'stream_incomplete'
    trace.feed(b'data: {"choices":[{"finish_reason":"stop"}]}\n\n')
    assert trace.failure_code() is None
    trace.feed(b'data: {"choices":[{"finish_reason":"network_error"}]}\n\n')
    assert trace.failure_code() == 'stream_network_error'
