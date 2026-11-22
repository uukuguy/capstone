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


def test_receipt_recovery_never_admits_missing_or_unknown_work(tmp_path):
    host = GeneralPiHost(root=tmp_path, identity={'engine':'pi'},
        run_task=lambda *_:pytest.fail('receipt recovery started execution'))
    request = PiTaskRequest('recover', 'a', 'delegated', 'Work', (), (), host.identity, 3)
    with pytest.raises(KeyError):
        host.recover(request)
    assert host.storage.load(request.task_id) is None
    host.storage.save(request.to_document(), None)
    result = host.recover(request)
    assert result['status']=='failed'
    assert result['failure']['code']=='native_execution_outcome_unknown'
    assert host.recover(request)==result
    assert not host._tasks
    changed = PiTaskRequest('recover', 'a', 'delegated', 'Changed', (), (), host.identity, 3)
    with pytest.raises(ValueError):
        host.recover(changed)


def test_receipt_recovery_reuses_actual_completed_result_after_host_restart(tmp_path):
    called=[]
    def run(*_):
        called.append(True)
        return 'Saved answer', {}
    host = GeneralPiHost(root=tmp_path, identity={'engine':'pi'}, run_task=run)
    request = PiTaskRequest('completed', 'a', 'delegated', 'Work', (), (), host.identity, 3)
    host.submit(request)
    deadline=time.monotonic()+2
    while host.read(request.task_id)['status']=='running' and time.monotonic()<deadline:time.sleep(.005)
    result=host.read(request.task_id)['result']
    restarted=GeneralPiHost(root=tmp_path,identity=host.identity,
        run_task=lambda *_:pytest.fail('repeated work'))
    assert restarted.recover(request)==result
    assert called==[True]


def test_receipt_recovery_cannot_terminalize_a_live_task(tmp_path):
    release=Event()
    host=GeneralPiHost(root=tmp_path, identity={'engine':'pi'},
        run_task=lambda *_:(release.wait(2) and 'Done', {}))
    request=PiTaskRequest('live', 'a', 'delegated', 'Work', (), (), host.identity,3)
    try:
        host.submit(request)
        with pytest.raises(PermissionError):host.recover(request)
        assert host.read(request.task_id)['status']=='running'
    finally:release.set()


def test_receipt_recovery_does_not_rehydrate_an_expired_tombstone(tmp_path):
    import json
    host=GeneralPiHost(root=tmp_path,identity={'engine':'pi'},run_task=lambda *_:pytest.fail('repeated'))
    request=PiTaskRequest('expired', 'a', 'delegated', 'Work', (), (), host.identity,3)
    host.storage.save(request.to_document(),None)
    tombstone={**host.storage.load(request.task_id),'expired':True}
    tombstone.pop('request')
    host.storage._write(host.storage.root/'records'/f'{request.task_id}.json',json.dumps(tombstone).encode())
    assert host.recover(request)['failure']['code']=='native_result_retention_expired'
    assert host.storage.load(request.task_id)==tombstone


def test_receipt_recovery_http_is_authenticated_exact_and_cannot_admit(tmp_path):
    import httpx
    from capstone_agent.general_pi_server import make_server
    host=GeneralPiHost(root=tmp_path,identity={'engine':'pi'},run_task=lambda *_:pytest.fail('repeated'))
    request=PiTaskRequest('recover-http','a','delegated','Work',(),(),host.identity,3)
    host.storage.save(request.to_document(),None)
    server=make_server(host,control_token='test-control',address=('127.0.0.1',0))
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        origin=f'http://127.0.0.1:{server.server_port}'
        body={'request':request.to_document()}
        url=origin+'/tasks/recover-http/recover'
        assert httpx.post(url,json=body).status_code==401
        headers={'Authorization':'Bearer test-control'}
        result=httpx.post(url,headers=headers,json=body)
        assert result.status_code==200
        assert result.json()['result']['failure']['code']=='native_execution_outcome_unknown'
        assert httpx.post(origin+'/tasks/other/recover',headers=headers,json=body).status_code==400
        missing={**request.to_document(),'task_id':'missing'}
        assert httpx.post(origin+'/tasks/missing/recover',headers=headers,json={'request':missing}).status_code==404
        assert httpx.post(origin+'/tasks/missing/authority',headers=headers,json={**grant(),'sequence':1}).status_code==409
        assert host.storage.load('missing') is None
        assert not host._tasks
    finally:server.shutdown();server.server_close();thread.join(2)


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
        if request.task_id!='cleanup-failed':
            return 'Done', {}
        entered.set()
        while not cancelled():
            time.sleep(.002)
        process._stop_process()
        return 'Stopped', {}
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=run, max_tasks=1)
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
    with pytest.raises(PermissionError):
        host.submit(request, execution_authority={**grant(), 'capability': 'c' * 64})
    from capstone_agent.application_capacity import CapacityExceeded
    with pytest.raises(CapacityExceeded):
        host.submit(PiTaskRequest('next','b','delegated','Work',(),(),host.identity,3))
    host._max_records=1
    with pytest.raises(CapacityExceeded):
        host._make_room()
    host.storage.retention=.00001
    time.sleep(.001)
    host.sweep()
    assert host.storage.load(request.task_id) is not None
    assert request.task_id in host._tasks


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


def test_observe_terminal_receipt_and_file_after_restart(tmp_path):
    import hashlib

    import httpx

    from capstone_agent.general_pi_server import make_server
    from capstone_agent.pi_delegation import HttpGeneralPiExecutor

    data = b'retained product\n'

    def run(request, *_):
        workspace = tmp_path / 'tasks' / request.task_id
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / 'report.txt').write_bytes(data)
        return 'Saved report', {}

    identity = {'engine': 'pi'}
    host = GeneralPiHost(root=tmp_path, identity=identity, run_task=run)
    request = PiTaskRequest('durable', 'parent', 'delegated', 'Write report', (), (), identity, 3)
    host.submit(request)
    deadline = time.monotonic() + 3
    while host.read('durable')['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(.01)
    result = host.read('durable')['result']
    assert result['status'] == 'completed'
    pending = PiTaskRequest('pending', 'parent', 'delegated', 'Unknown work', (), (), identity, 3)
    host.storage.save(pending.to_document(), None)
    restarted = GeneralPiHost(root=tmp_path, identity=identity,
                              run_task=lambda *_: pytest.fail('observer started execution'))
    server = make_server(restarted, control_token='test-control', address=('127.0.0.1', 0))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        origin = f'http://127.0.0.1:{server.server_port}'
        client = HttpGeneralPiExecutor(origin, identity=identity, capability={}, control_token='test-control')
        assert httpx.get(origin + '/tasks/durable').status_code == 401
        assert httpx.get(origin + '/tasks/durable?after=0',
                         headers={'Authorization': 'Bearer test-control'}).status_code == 404
        observed = client.observe_terminal_task('durable', 'parent', identity)
        assert observed.to_document() == result
        artifact, = observed.artifacts
        assert client.read_artifact('durable', artifact['artifact_id'],
                                    expected_sha256=hashlib.sha256(data).hexdigest(),
                                    expected_size=len(data)) == data
        with pytest.raises(ValueError):
            client.observe_terminal_task('durable', 'other-parent', identity)
        assert client.observe_terminal_task('pending', 'parent', identity) is None
        assert restarted.storage.load('pending')['result'] is None
        assert restarted.storage.load('durable')['result'] == result
        assert not restarted._tasks
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)
