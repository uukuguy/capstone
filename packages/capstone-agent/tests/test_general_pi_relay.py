import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread
from types import SimpleNamespace
import time

import httpx
import pytest
from concurrent.futures import CancelledError


def test_private_native_timing_is_fixed_bounded_and_released(capsys):
    from capstone_agent.native_timing import NativeTiming
    from capstone_agent.general_pi_relay import ProviderRelay
    ticks = iter([10.0, 10.25, 10.5])
    timing = NativeTiming('task-fixture', clock=lambda: next(ticks))
    timing.mark('resources_configured')
    timing.mark('resources_configured')
    with pytest.raises(ValueError):
        timing.mark('PRIVATE_SECRET')
    relay = ProviderRelay()
    relay.register('task-fixture', 'grant', time.monotonic()+5, timing=timing)
    assert relay.timings['task-fixture'] is timing
    relay.revoke('task-fixture')
    assert relay.timings == {}
    output = capsys.readouterr().err
    assert 'PRIVATE_SECRET' not in output
    assert '250.0' in output
    assert output.count('resources_configured') == 1
    assert timing.closed


def test_native_timing_bounds_values_and_ignores_failed_diagnostic_sink(capsys, monkeypatch):
    import json
    from capstone_agent.native_timing import NativeTiming
    ticks = iter([0, float('inf'), 10**12, 10**12])
    timing = NativeTiming('task', clock=lambda: next(ticks))
    timing.mark('resources_configured')
    timing.mark('provider_request_started', counts={'request_bytes': 10**100, 'PRIVATE_SECRET': 1})
    records = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    assert [item['phase'] for item in records] == ['task_started', 'provider_request_started']
    assert records[-1]['elapsed_ms'] == 86400000
    assert records[-1]['request_bytes'] == 2**53-1
    assert 'PRIVATE_SECRET' not in records[-1]
    class BrokenSink:
        def write(self, _):
            raise OSError('Unavailable sink')
    monkeypatch.setattr('sys.stderr', BrokenSink())
    timing.close()
    assert timing.closed


@pytest.mark.parametrize('counts', ['callback_error', 'invalid_type', 'items_error'])
def test_native_timing_ignores_failed_optional_counts(capsys, counts):
    import json
    from capstone_agent.native_timing import NativeTiming
    def broken_counts():
        raise OSError('Private diagnostic failure')
    class BrokenItems:
        def items(self):
            raise OSError('Private diagnostic failure')
    value = {'callback_error': broken_counts, 'invalid_type': 17, 'items_error': BrokenItems()}[counts]
    timing = NativeTiming('task')
    assert timing.mark('provider_request_started', counts=value)
    timing.close()
    records = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    assert [item['phase'] for item in records] == ['task_started', 'provider_request_started', 'task_finished']
    assert all(set(item) == {'event', 'task_id', 'scope', 'phase', 'elapsed_ms'} for item in records)


def test_native_timing_close_blocks_late_phase_at_first_lock_release(capsys):
    import json
    from concurrent.futures import ThreadPoolExecutor
    from capstone_agent.native_timing import NativeTiming
    timing = NativeTiming('task')
    original = timing.lock
    with ThreadPoolExecutor(max_workers=1) as worker:
        class ExitInterleave:
            invoked = False
            def __enter__(self):
                original.acquire()
            def __exit__(self, *_):
                original.release()
                if not self.invoked:
                    self.invoked = True
                    assert worker.submit(timing.mark, 'first_bytes').result(timeout=2) is False
        timing.lock = ExitInterleave()
        timing.close()
    records = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    assert [item['phase'] for item in records] == ['task_started', 'task_finished']
    timing.close()
    assert capsys.readouterr().err == ''


@pytest.mark.parametrize('field,phase', [('reasoning', 'first_thinking'),
    ('reasoning_content', 'first_thinking'), ('reasoning_text', 'first_thinking'), ('content', 'first_text')])
def test_stream_diagnostics_marks_only_nonempty_semantics_without_retaining_text(field, phase):
    import json
    from capstone_agent.general_pi_relay import StreamDiagnostics
    phases = []
    trace = StreamDiagnostics(on_semantic=phases.append)
    for value in ['', ' ', 'PRIVATE_SECRET', 'again']:
        payload = ('data: '+json.dumps({'choices': [{'delta': {field: value}}]})+'\n\n').encode()
        for position in range(0, len(payload), 7):
            trace.feed(payload[position:position+7])
    assert phases == [phase]
    assert 'PRIVATE_SECRET' not in repr(vars(trace))


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


def test_debug_relay_queues_pressure_and_keeps_provider_and_gateway_slots_separate():
    from capstone_agent.application_capacity import initialize_capacity, current_capacity
    from capstone_agent.general_pi_relay import ProviderRelay
    from concurrent.futures import ThreadPoolExecutor
    original = current_capacity()
    left, right = socket.socketpair()
    relay = None
    try:
        initialize_capacity(mode='debug')
        relay = ProviderRelay(max_requests=1, per_task=1, gateway_requests=1, gateway_per_task=1)
        relay.register('task', 'grant', time.monotonic()+5)
        provider = relay.acquire('task', 'grant', left)
        gateway = relay.acquire('task', 'grant', left, channel='gateway')
        with ThreadPoolExecutor(max_workers=1) as pool:
            waiting = pool.submit(relay.acquire, 'task', 'grant', left, channel='gateway')
            assert not waiting.done()
            relay.release(gateway)
            admitted = waiting.result(timeout=1)
            assert not provider.cancelled.is_set()
            assert admitted.channel == 'gateway'
            relay.release(admitted)
        relay.release(provider)
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
            relay.acquire('one', 'grant-one', left, wait=False)
        other = relay.acquire('two', 'grant-two', left)
        relay.register('three', 'grant-three', time.monotonic()+2)
        with pytest.raises(CapacityExceeded):
            relay.acquire('three', 'grant-three', left, wait=False)
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


def test_stream_relay_does_not_count_protocol_overhead_as_a_document_limit(tmp_path, capsys):
    import json
    from capstone_agent.native_timing import NativeTiming
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
    relay.register('task', 'grant', time.monotonic() + 10, timing=NativeTiming('task'))
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=lambda *_: ('unused', {}))
    server = make_server(host, control_token='control', address=('127.0.0.1', 0),
        runner=SimpleNamespace(relay=relay, model='fixture'),
        upstream=f'http://127.0.0.1:{upstream.server_port}', provider_key='fixture-only')
    for item in (server, upstream):
        Thread(target=item.serve_forever, daemon=True).start()
    try:
        result = httpx.post(f'http://127.0.0.1:{server.server_port}/provider/task/chat/completions',
            json={'model': 'fixture', 'stream': True,
                  'messages': [{'role': 'system', 'content': 'PRIVATE_PROMPT'}, {'role': 'user', 'content': 'PRIVATE_USER'}],
                  'tools': [{'type': 'function', 'function': {'name': 'PRIVATE_TOOL'}}]},
            headers={'Authorization': 'Bearer grant'}, timeout=5)
        assert result.status_code == 200
        assert result.content == payload
        timings = [json.loads(line) for line in capsys.readouterr().err.splitlines()
                   if line.startswith('{') and json.loads(line).get('event') == 'native_timing']
        assert [item['phase'] for item in timings] == ['task_started', 'provider_request_started',
            'provider_headers', 'first_bytes', 'first_text']
        assert [item['elapsed_ms'] for item in timings] == sorted(item['elapsed_ms'] for item in timings)
        assert all(set(item) <= {'event', 'task_id', 'scope', 'phase', 'elapsed_ms', 'request_bytes',
            'tools_count', 'tools_schema_bytes', 'system_message_bytes', 'other_messages_bytes'} for item in timings)
        assert timings[1]['tools_count'] == 1
        assert timings[1]['request_bytes'] > 0
        assert timings[1]['system_message_bytes'] > 0
        assert timings[1]['other_messages_bytes'] > 0
        assert 'PRIVATE_' not in json.dumps(timings)
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


def test_sse_done_releases_permit_without_waiting_for_upstream_connection_close(tmp_path):
    from capstone_agent.general_pi_relay import ProviderRelay
    from capstone_agent.general_pi_server import GeneralPiHost, make_server
    closed = Event()
    class Upstream(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            self.rfile.read(int(self.headers['Content-Length']))
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.end_headers()
            self.wfile.write(b'data: {"choices":[{"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n')
            self.wfile.flush()
            closed.wait(2)
    upstream = ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
    relay = ProviderRelay(max_requests=1, per_task=1)
    relay.register('task', 'grant', time.monotonic()+5)
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=lambda *_: ('unused', {}))
    server = make_server(host, control_token='control', address=('127.0.0.1', 0),
        runner=SimpleNamespace(relay=relay, model='fixture'),
        upstream=f'http://127.0.0.1:{upstream.server_port}', provider_key='fixture-only')
    for item in (server, upstream):
        Thread(target=item.serve_forever, daemon=True).start()
    try:
        for _ in range(2):
            result = httpx.post(f'http://127.0.0.1:{server.server_port}/provider/task/chat/completions',
                json={'model': 'fixture', 'stream': True}, headers={'Authorization': 'Bearer grant'},
                timeout=.7, trust_env=False)
            assert result.status_code == 200 and b'[DONE]' in result.content
            assert not relay.active
    finally:
        closed.set(); relay.revoke('task')
        for item in (server, upstream):
            item.shutdown(); item.server_close()


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
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=1) as pool:
            queued = pool.submit(httpx.post, url, json={'model': 'fixture'}, headers=headers, timeout=2)
            if ending == 'revoke':
                relay.revoke('task')
            assert queued.result(timeout=2).status_code == 401
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


def test_model_transport_policy_bounds_network_idle_not_total_generation():
    from capstone_agent.general_pi_relay import model_transport_timeout
    timeout = model_transport_timeout()
    assert timeout.connect == 15 and timeout.read == 90
    assert timeout.write == 30 and timeout.pool == 15
    policy = {'schema':'capstone-model-transport/1','connect_seconds':.1,
              'read_idle_seconds':.2,'write_seconds':.3,'pool_seconds':.4}
    assert model_transport_timeout(policy).read == .2
    for value in (None, 0, -1, True, float('inf'), 3601):
        with pytest.raises(ValueError):
            model_transport_timeout({**policy,'read_idle_seconds':value})


@pytest.mark.parametrize('progressing', [False, True])
def test_actual_network_idle_budget_releases_stall_but_allows_long_progress(tmp_path, monkeypatch, progressing):
    import capstone_agent.general_pi_relay as module
    from capstone_agent.general_pi_server import GeneralPiHost, make_server
    monkeypatch.setattr(module, 'model_transport_timeout', lambda: httpx.Timeout(0.2))
    finish = Event()
    payload = b'data: {"choices":[{"delta":{"content":"x"}}]}\n\n'
    class Upstream(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            self.rfile.read(int(self.headers['Content-Length']))
            self.send_response(200); self.send_header('Content-Type','text/event-stream'); self.end_headers()
            try:
                self.wfile.write(payload); self.wfile.flush()
                if progressing:
                    for _ in range(8):
                        time.sleep(.04); self.wfile.write(payload); self.wfile.flush()
                    self.wfile.write(b'data: [DONE]\n\n'); self.wfile.flush()
                else:
                    finish.wait(3)
            except OSError: pass
    upstream = ThreadingHTTPServer(('127.0.0.1',0),Upstream)
    relay = module.ProviderRelay(); relay.register('task','grant',time.monotonic()+5)
    host = GeneralPiHost(root=tmp_path,identity={'engine':'pi'},run_task=lambda *_: ('unused',{}))
    server = make_server(host,control_token='control',address=('127.0.0.1',0),
        runner=SimpleNamespace(relay=relay,model='fixture'),upstream=f'http://127.0.0.1:{upstream.server_port}',provider_key='fixture-only')
    for item in (server,upstream): Thread(target=item.serve_forever,daemon=True).start()
    try:
        result=httpx.post(f'http://127.0.0.1:{server.server_port}/provider/task/chat/completions',json={'model':'fixture','stream':True},headers={'Authorization':'Bearer grant'},timeout=2)
        assert (b'[DONE]' in result.content) is progressing
        deadline=time.monotonic()+1
        while relay.active and time.monotonic()<deadline: time.sleep(.01)
        assert not relay.active
        assert relay.failure_reason('task') == (None if progressing else 'model_read_timeout')
    finally:
        finish.set();relay.revoke('task')
        for item in (server,upstream):item.shutdown();item.server_close()
