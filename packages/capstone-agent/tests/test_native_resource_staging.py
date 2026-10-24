from hashlib import sha256
import base64
import pytest

from capstone_agent.native_resource_staging import NativeResourceStaging, CHUNK_BYTES


def manifest(data):
    return {'schema':'capstone-resource/1','thread_id':'thr_test','resource_id':'resource_'+'a'*32,
        'version':1,'file_name':'data.csv','size_bytes':len(data),'sha256':sha256(data).hexdigest()}


def test_resource_stage_restart_exact_identity_and_readonly_source(tmp_path):
    data = b'x' * CHUNK_BYTES + b'end'
    resource = manifest(data)
    request = {'task_id':'pi-test','resource':resource}
    store = NativeResourceStaging(tmp_path)
    assert store.control({**request,'operation':'status'})['received_parts'] == []
    store.control({**request,'operation':'part','index':0,'content_base64':base64.b64encode(data[:CHUNK_BYTES]).decode()})
    store = NativeResourceStaging(tmp_path)
    assert store.control({**request,'operation':'status'})['received_parts'] == [0]
    with pytest.raises(ValueError, match='incomplete'):
        store.control({**request,'operation':'complete'})
    store.control({**request,'operation':'part','index':1,'content_base64':base64.b64encode(b'end').decode()})
    assert store.control({**request,'operation':'complete'})['sha256'] == resource['sha256']
    assert store.source('pi-test',resource).read_bytes() == data
    assert not list(tmp_path.rglob('*.part'))
    with pytest.raises(ValueError, match='identity changed'):
        store.control({**request,'resource':{**resource,'thread_id':'thr_other'},'operation':'status'})
    with pytest.raises(ValueError, match='unavailable'):
        store.source('pi-other',resource)


def test_staging_rejects_wrong_bytes_and_paths(tmp_path):
    resource = manifest(b'abcd')
    store=NativeResourceStaging(tmp_path)
    request={'task_id':'pi-test','resource':resource}
    with pytest.raises(ValueError):
        store.control({**request,'task_id':'../escape','operation':'status'})
    store.control({**request,'operation':'part','index':0,'content_base64':base64.b64encode(b'xxxx').decode()})
    with pytest.raises(ValueError,match='digest'):
        store.control({**request,'operation':'complete'})
    with pytest.raises(ValueError,match='changed'):
        store.control({**request,'operation':'part','index':0,'content_base64':base64.b64encode(b'abcd').decode()})


def test_capacity_reserves_incomplete_files_and_cleanup_releases_it(tmp_path):
    store = NativeResourceStaging(tmp_path, max_storage_bytes=12)
    request = {'task_id': 'first', 'resource': manifest(b'abcd'), 'operation': 'status'}
    store.control(request)
    with pytest.raises(ValueError, match='capacity'):
        store.control({**request, 'task_id': 'second'})
    store.remove('first')
    assert store.control({**request, 'task_id': 'second'})['received_parts'] == []


def test_expiry_keeps_active_task_and_recent_transfer(tmp_path):
    import os
    import time
    store = NativeResourceStaging(tmp_path, retention_seconds=10)
    for task in ('active', 'old', 'recent'):
        store.control({'task_id': task, 'resource': manifest(b'abcd'), 'operation': 'status'})
    for task in ('active', 'old'):
        os.utime(tmp_path / task, (time.time() - 20,) * 2)
    store.sweep({'active'})
    assert (tmp_path / 'active').is_dir()
    assert (tmp_path / 'recent').is_dir()
    assert not (tmp_path / 'old').exists()


def test_resource_bytes_do_not_consume_receipt_quota(tmp_path):
    from capstone_agent.general_pi_server import GeneralPiHost
    host = GeneralPiHost(root=tmp_path, identity={}, run_task=lambda *_: None, max_storage_bytes=1024)
    data = b'a' * 2048
    request = {'task_id': 'task', 'resource': manifest(data)}
    host.resource_staging.control({**request, 'operation': 'part', 'index': 0,
                                  'content_base64': base64.b64encode(data).decode()})
    host.storage.save({'task_id': 'task'}, None)
    assert host.storage.load('task') is not None


def test_host_restart_removes_orphan_execution_copy_but_retains_upload(tmp_path):
    from capstone_agent.general_pi_server import GeneralPiHost
    host = GeneralPiHost(root=tmp_path, identity={}, run_task=lambda *_: None)
    request = {'task_id': 'task', 'resource': manifest(b'abcd'), 'operation': 'status'}
    host.resource_staging.control(request)
    orphan = tmp_path / 'inputs' / 'task'
    orphan.mkdir()
    (orphan / 'source.csv').write_text('abandoned execution copy')
    restarted = GeneralPiHost(root=tmp_path, identity={}, run_task=lambda *_: None)
    assert not orphan.exists()
    assert (restarted.resource_staging.root / 'task').is_dir()


def test_default_receipt_capacity_supports_multiple_research_sessions(tmp_path):
    from capstone_agent.general_pi_server import GeneralPiHost
    host = GeneralPiHost(root=tmp_path, identity={}, run_task=lambda *_: None)
    with (host.storage.root / 'observations' / 'prior.json').open('wb') as f:
        f.truncate(65 * 1024**2)
    host.storage.save({'task_id': 'next'}, None)
    assert host.storage.load('next') is not None


@pytest.mark.parametrize('interrupted_operation', ['status', 'part', 'complete'])
def test_staging_retries_same_request_after_confirmed_write_timeout(tmp_path, monkeypatch, interrupted_operation):
    import time
    from capstone_agent.pi_delegation import HttpGeneralPiExecutor, PiTransportTimeout
    from capstone_agent.request_intent import NodeControl
    data = b'real saved bytes'; resource = manifest(data)
    store = NativeResourceStaging(tmp_path)
    executor = HttpGeneralPiExecutor('http://localhost:1', identity={'engine':'fixture'}, capability={})
    calls = []; events = []; interrupted = False
    def call(method, path, *, document, **kwargs):
        nonlocal interrupted
        calls.append(document.copy())
        result = store.control(document)
        if document['operation'] == interrupted_operation and not interrupted:
            interrupted = True
            error = PiTransportTimeout('Pi transport deadline expired; task state is unknown')
            error.transport_phase = 'ReadTimeout'
            raise error
        return result
    monkeypatch.setattr(executor, '_call', call)
    executor.stage_resources_with_events('task', [resource], lambda _: iter([data]),
        NodeControl(lambda: None, time.monotonic()+2), events.append)
    assert store.source('task', resource).read_bytes() == data
    repeated = [d for d in calls if d['operation'] == interrupted_operation]
    assert len(repeated) == 2 and repeated[0] == repeated[1]
    assert [e['type'] for e in events] == ['transport_interrupted', 'transport_restored']
    assert events[0]['operation'] == 'resource_' + interrupted_operation


def test_staging_permanent_rejection_is_not_retried_and_cancel_interrupts_wait(tmp_path, monkeypatch):
    import time
    from capstone_agent.pi_delegation import HttpGeneralPiExecutor, PiTransportTimeout, PiHTTPFailure
    from capstone_agent.request_intent import NodeControl
    executor = HttpGeneralPiExecutor('http://localhost:1', identity={'engine':'fixture'}, capability={})
    calls = []
    def reject(*args, **kwargs):
        calls.append(1); raise PiHTTPFailure(400, 'invalid_task')
    monkeypatch.setattr(executor, '_call', reject)
    with pytest.raises(PiHTTPFailure):
        executor.stage_resources_with_events('task', [manifest(b'x')], lambda _: iter([b'x']),
            NodeControl(lambda: None, time.monotonic()+2), lambda _: None)
    assert len(calls) == 1
    def timeout(*args, **kwargs):
        raise PiTransportTimeout('Pi transport deadline expired; task state is unknown')
    monkeypatch.setattr(executor, '_call', timeout)
    stopped = False
    def event(_):
        nonlocal stopped
        stopped = True
    def check():
        if stopped: raise InterruptedError('user cancelled')
    with pytest.raises(InterruptedError):
        executor.stage_resources_with_events('task', [manifest(b'x')], lambda _: iter([b'x']),
            NodeControl(check, time.monotonic()+2), event)


def test_actual_http_slow_completed_write_recovers_without_starting_a_model(tmp_path, monkeypatch):
    import threading
    import time
    from capstone_agent.general_pi_server import GeneralPiHost, make_server
    from capstone_agent.pi_delegation import HttpGeneralPiExecutor
    from capstone_agent.request_intent import NodeControl
    host = GeneralPiHost(root=tmp_path / 'host', identity={'engine':'fixture'},
        run_task=lambda *_: pytest.fail('staging must not start a model'))
    original_control = host.resource_staging.control
    completed = 0
    def control(value):
        nonlocal completed
        result = original_control(value)
        if value['operation'] == 'complete':
            completed += 1
            if completed == 1: time.sleep(.12)
        return result
    monkeypatch.setattr(host.resource_staging, 'control', control)
    server = make_server(host, control_token='fixture-private', address=('127.0.0.1',0))
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        executor = HttpGeneralPiExecutor(f'http://127.0.0.1:{server.server_port}',
            identity=host.identity, capability=host.capability, control_token='fixture-private')
        original_call = executor._call
        def short_window(*args, **kwargs):
            kwargs['timeout'] = .04 if kwargs['document']['operation'] == 'complete' else 2
            return original_call(*args, **kwargs)
        monkeypatch.setattr(executor, '_call', short_window)
        events = []; data=b'saved once, recovered after reply timeout'
        executor.stage_resources_with_events('task', [manifest(data)], lambda _: iter([data]),
            NodeControl(lambda:None,time.monotonic()+3),events.append)
        assert completed == 2
        assert host.resource_staging.source('task',manifest(data)).read_bytes() == data
        assert events[0]['transport_phase'] == 'ReadTimeout'
        assert events[-1]['type'] == 'transport_restored'
        assert host._tasks == {}
    finally:
        server.shutdown();server.server_close();thread.join(2)


def test_staging_hard_task_deadline_retains_safe_operation(tmp_path, monkeypatch):
    import time
    from capstone_agent.pi_delegation import HttpGeneralPiExecutor, PiTransportTimeout
    from capstone_agent.request_intent import NodeControl
    executor = HttpGeneralPiExecutor('http://localhost:1',identity={'engine':'fixture'},capability={})
    def interrupted(*args,**kwargs):
        raise PiTransportTimeout('Pi transport deadline expired; task state is unknown')
    monkeypatch.setattr(executor,'_call',interrupted)
    with pytest.raises(PiTransportTimeout) as caught:
        executor.stage_resources_with_events('task',[manifest(b'x')],lambda _:iter([b'x']),
            NodeControl(lambda:None,time.monotonic()+.06),lambda _:None)
    assert caught.value.diagnostic == {'operation':'resource_status','transport_phase':'task_deadline'}


def test_debug_staging_soft_window_interrupts_before_retry(monkeypatch):
    from capstone_agent.application_capacity import initialize_capacity,current_capacity,CapacityExceeded
    from capstone_agent.pi_delegation import HttpGeneralPiExecutor,PiTransportTimeout
    from capstone_agent.request_intent import NodeControl
    original=current_capacity();clock=[0.];calls=[];events=[]
    executor=HttpGeneralPiExecutor('http://localhost:1',identity={'engine':'fixture'},capability={})
    def interrupted(*args,**kwargs):
        calls.append(1);clock[0]+=2.1
        raise PiTransportTimeout('Pi transport deadline expired; task state is unknown')
    try:
        initialize_capacity({'native_staging_wait_seconds':1},mode='debug')
        monkeypatch.setattr('capstone_agent.pi_delegation.time.monotonic',lambda:clock[0])
        monkeypatch.setattr(executor,'_call',interrupted)
        with pytest.raises(CapacityExceeded) as caught:
            executor.stage_resources_with_events('task',[manifest(b'x')],lambda _:iter([b'x']),
                NodeControl(lambda:None,100),events.append)
        assert len(calls)==1 and events==[]
        assert caught.value.to_document()['mode']=='debug'
        assert caught.value.to_document()['actual']==3
        assert caught.value.to_document()['phase']=='resource_status'
    finally:initialize_capacity(original)


def test_debug_server_request_inactivity_returns_typed_capacity_without_model(tmp_path):
    import socket,threading,json
    from capstone_agent.application_capacity import initialize_capacity,current_capacity
    from capstone_agent.general_pi_server import GeneralPiHost,make_server
    previous=current_capacity()
    server=None
    try:
        initialize_capacity({'native_server_wait_seconds':1},mode='debug')
        host=GeneralPiHost(root=tmp_path/'host',identity={'engine':'fixture'},run_task=lambda *_:pytest.fail('No model'))
        server=make_server(host,control_token='fixture',address=('127.0.0.1',0))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        with socket.create_connection(server.server_address,timeout=3) as client:
            client.sendall(b'POST /tasks HTTP/1.0\r\nAuthorization: Bearer fixture\r\nContent-Length: 100\r\n\r\n{')
            data=b''
            while chunk:=client.recv(4096):data+=chunk
        headers,body=data.split(b'\r\n\r\n',1)
        assert b'408' in headers
        detail=json.loads(body)['capacity']
        assert detail['mode']=='debug' and detail['fatal'] is True
        assert detail['dimension']=='native_server_wait_seconds' and detail['actual']>detail['limit']==1
        assert host._tasks=={}
    finally:
        if server:server.shutdown();server.server_close()
        initialize_capacity(previous)
