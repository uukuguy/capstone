import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread
from types import SimpleNamespace
import time

import httpx
import pytest
from concurrent.futures import CancelledError


def test_relay_grants_bound_concurrency_and_revoke_active_connections():
    from capstone_agent.general_pi_relay import ProviderRelay
    relay = ProviderRelay(max_requests=2, per_task=1)
    relay.register('one', 'grant-one', time.monotonic()+2)
    relay.register('two', 'grant-two', time.monotonic()+2)
    left, right = socket.socketpair()
    try:
        lease = relay.acquire('one', 'grant-one', left)
        with pytest.raises(RuntimeError):
            relay.acquire('one', 'grant-one', left)
        other = relay.acquire('two', 'grant-two', left)
        relay.register('three', 'grant-three', time.monotonic()+2)
        with pytest.raises(RuntimeError):
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
