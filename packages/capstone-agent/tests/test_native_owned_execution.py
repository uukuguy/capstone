"""Protected host admission and executor-local expiry."""
from threading import Event
from threading import Thread
import time

import pytest

from capstone_agent.general_pi_server import GeneralPiHost
from capstone_agent.pi_delegation import PiTaskRequest


def grant():
    return {'schema': 'capstone-execution-authority/1', 'generation': 'a' * 64,
            'capability': 'b' * 64}


def test_owned_admission_keeps_task_budget_separate_from_authority_envelope(tmp_path, monkeypatch):
    import json
    import httpx
    from capstone_agent import general_pi_server as module
    request = PiTaskRequest('budget', 'a', 'delegated', 'Work', (), (), {'engine':'pi'}, 3)
    document = request.to_document()
    original = module.limits
    class Limits:
        native_task_bytes = len(json.dumps(document, ensure_ascii=False).encode())
        def __getattr__(self, name):return getattr(original, name)
    monkeypatch.setattr(module, 'limits', Limits())
    host = GeneralPiHost(root=tmp_path, identity={'engine':'pi'}, run_task=lambda *_:('Done', {}))
    server = module.make_server(host, control_token='test-control', address=('127.0.0.1',0))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url=f'http://127.0.0.1:{server.server_port}/owned-tasks'
        response=httpx.post(url, headers={'Authorization':'Bearer test-control'},
            json={'request':document,'execution_authority':grant()})
        assert response.status_code==202, response.text
        oversized={**document,'task_id':'budget-too-large','instruction':'Work'*100}
        assert httpx.post(url,headers={'Authorization':'Bearer test-control'},
            json={'request':oversized,'execution_authority':grant()}).status_code==400
    finally:
        server.shutdown();server.server_close();thread.join(2)


def test_owned_task_expires_without_reads_or_a_live_caller(tmp_path, monkeypatch):
    from capstone_agent import native_execution_authority as authority
    monkeypatch.setattr(authority, 'AUTHORITY_SECONDS', .08)
    stopped = Event()
    def run(request, cancelled, emit):
        while not cancelled():
            time.sleep(.002)
        stopped.set()
        raise InterruptedError('stopped')
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=run)
    request = PiTaskRequest('owned', 'attempt-a', 'delegated', 'Work', (), (), host.identity, 3)
    host.submit(request, execution_authority=grant())
    # Observe repeatedly: observation must not act as a heartbeat.
    deadline = time.monotonic() + 2
    while host.read('owned')['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(.003)
    assert stopped.is_set()
    assert host.read('owned')['status'] == 'cancelled'
    with pytest.raises(PermissionError):
        host.renew_execution('owned', {**grant(), 'sequence': 1})
    restarted = GeneralPiHost(root=tmp_path, identity=host.identity,
        run_task=lambda *_: pytest.fail('must not repeat'))
    restarted.submit(request, execution_authority=grant())
    assert restarted.read('owned')['status'] == 'cancelled'


def test_duplicate_admission_cannot_replace_or_extend_the_owner(tmp_path, monkeypatch):
    from capstone_agent import native_execution_authority as authority
    monkeypatch.setattr(authority, 'AUTHORITY_SECONDS', .2)
    release = Event()
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'},
        run_task=lambda *_: (release.wait(2) and 'Done', {}))
    request = PiTaskRequest('owned', 'attempt-a', 'delegated', 'Work', (), (), host.identity, 3)
    try:
        host.submit(request, execution_authority=grant())
        host.submit(request, execution_authority=grant())
        with pytest.raises(PermissionError):
            host.submit(request, execution_authority={**grant(), 'capability': 'c' * 64})
        with pytest.raises(PermissionError):
            host.submit(request)
        with pytest.raises(PermissionError):
            host.renew_execution('owned', {**grant(), 'generation': 'd' * 64, 'sequence': 1})
        host.renew_execution('owned', {**grant(), 'sequence': 1})
        host.renew_execution('owned', {**grant(), 'sequence': 1})
        with pytest.raises(ValueError):
            host.renew_execution('owned', {**grant(), 'sequence': 3})
    finally:
        release.set()


@pytest.mark.parametrize('change', [{'extra': True}, {'generation': 'x'}, {'capability': ''}])
def test_invalid_authority_never_admits_a_task(tmp_path, change):
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'},
        run_task=lambda *_: pytest.fail('invalid admission executed'))
    request = PiTaskRequest('bad', 'attempt-a', 'delegated', 'Work', (), (), host.identity, 3)
    with pytest.raises(ValueError):
        host.submit(request, execution_authority={**grant(), **change})
    assert not host._tasks


def test_unconfirmed_process_cleanup_stays_failed_even_after_cancellation(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from capstone_agent import general_pi_executor as module
    entered = Event()
    process = module.GeneralPiProcess(('unused',), {}, tmp_path, uid=10000)
    process.process = SimpleNamespace(pid=12345, stdin=None, stdout=None, stderr=None, wait=lambda **_:None)
    monkeypatch.setattr(module.os, 'killpg', lambda *_:None)
    monkeypatch.setattr(module, '_kill_task_process', lambda *_:None)
    monkeypatch.setattr(module, '_live_task_processes', lambda uid:[12346])
    def run(request, cancelled, emit):
        entered.set()
        while not cancelled():
            time.sleep(.002)
        process._stop_process()
        return 'Stopped', {}
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=run)
    request = PiTaskRequest('cleanup-failed', 'a', 'delegated', 'Work', (), (), host.identity, 3)
    host.submit(request, execution_authority=grant())
    assert entered.wait(1)
    host.cancel(request.task_id)
    deadline = time.monotonic()+2
    while host.read(request.task_id)['status']=='running' and time.monotonic()<deadline:
        time.sleep(.005)
    result = host.read(request.task_id)
    assert result['status']=='failed'
    assert result['result']['status']=='failed'
    assert result['result']['failure']['code']=='native_process_cleanup_unconfirmed'
    assert process.process is not None


@pytest.mark.parametrize('outcome', ['complete', 'guard_lost', 'lost_ack'])
def test_http_client_renews_during_quiet_work_and_stops_when_guard_is_lost(tmp_path, monkeypatch, outcome):
    from capstone_agent.general_pi_server import make_server
    from capstone_agent.pi_delegation import HttpGeneralPiExecutor
    from capstone_agent.request_intent import NodeControl
    from capstone_agent import native_execution_authority as authority
    monkeypatch.setattr(authority, 'AUTHORITY_SECONDS', .4)
    monkeypatch.setattr(authority, 'RENEW_SECONDS', .04)
    entered, finish, lost = Event(), Event(), Event()
    renewals = []
    def run(request, cancelled, emit):
        entered.set()
        while not finish.is_set():
            if cancelled():
                raise InterruptedError('authority expired')
            time.sleep(.003)
        return 'Done', {}
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=run)
    original = host.renew_execution
    def renew(task_id, document):
        renewals.append(document['sequence'])
        return original(task_id, document)
    monkeypatch.setattr(host, 'renew_execution', renew)
    server = make_server(host, control_token='test-control', address=('127.0.0.1', 0))
    server_thread = Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    client = HttpGeneralPiExecutor(f'http://127.0.0.1:{server.server_port}',
        identity=host.identity, capability=host.capability, control_token='test-control')
    original_call = client._call
    discarded = []
    def call(method, path, **kwargs):
        value = original_call(method, path, **kwargs)
        if outcome == 'lost_ack' and path.endswith('/authority') and not discarded:
            from capstone_agent.pi_delegation import PiTransportUnavailable
            discarded.append(True)
            raise PiTransportUnavailable('simulated lost acknowledgement')
        return value
    monkeypatch.setattr(client, '_call', call)
    request = PiTaskRequest('http-owned', 'a', 'delegated', 'Work', (), (), host.identity, 4)
    results, failures = [], []
    def guard():
        if lost.is_set():
            raise InterruptedError('attempt lease lost')
    def execute():
        try:
            results.append(client.execute(request, NodeControl(guard, time.monotonic()+4), lambda _:None))
        except Exception as error:
            failures.append(error)
    thread = Thread(target=execute)
    try:
        thread.start()
        assert entered.wait(2)
        deadline = time.monotonic() + 2
        while len(renewals) < 3 and time.monotonic() < deadline:
            time.sleep(.01)
        assert len(renewals) >= 3
        assert host.read('http-owned')['status'] == 'running'
        if outcome == 'guard_lost':
            lost.set()
        else:
            finish.set()
        thread.join(3)
        assert not thread.is_alive()
        if outcome == 'guard_lost':
            assert failures and isinstance(failures[0], (InterruptedError, RuntimeError))
            assert host.read('http-owned')['status'] == 'cancelled'
        else:
            assert not failures
            assert results[0].status == 'completed'
        if outcome == 'lost_ack':
            assert renewals[:3] == [1, 1, 2]
        assert 'execution_authority' not in host.storage.load('http-owned')
    finally:
        finish.set()
        thread.join(4)
        server.shutdown()
        server.server_close()
        server_thread.join(2)
