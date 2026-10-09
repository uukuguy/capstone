from pathlib import Path
import threading
import time

import httpx
import pytest

from capstone_agent.pi_delegation import PiTaskRequest, HttpGeneralPiExecutor
from capstone_agent.request_intent import NodeControl


def test_executor_service_binds_identity_and_control_authorization(tmp_path):
    from capstone_agent.general_pi_server import GeneralPiHost, make_server
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi', 'config_revision': 'test'},
                         run_task=lambda request, cancelled, emit: ('General answer', {}))
    server = make_server(host, control_token='host-secret', address=('127.0.0.1', 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    try:
        assert httpx.get(origin + '/health/ready').status_code == 200
        assert httpx.post(origin + '/tasks', json={}).status_code == 401
        client = HttpGeneralPiExecutor(origin, identity=host.identity, capability=host.capability,
                                      control_token='host-secret')
        request = PiTaskRequest.from_document({'schema': 'capstone-pi-task/1', 'task_id': 't1',
            'parent_attempt_id': 'a1', 'entrypoint': 'direct', 'instruction': 'Explain', 'messages': [],
            'dependency_results': [], 'executor_identity': host.identity, 'timeout_seconds': 2})
        result = client.execute(request, NodeControl(lambda: None, time.monotonic()+2), lambda _: None)
        assert result.answer == 'General answer'
        assert result.status == 'completed'
        assert list(tmp_path.glob('receipts/records/*.json'))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_cancel_service_stops_child_and_duplicate_tasks_do_not_repeat_actions(tmp_path):
    from capstone_agent.general_pi_server import GeneralPiHost
    calls = []
    def run(request, cancelled, emit):
        calls.append(request.task_id)
        while not cancelled():
            time.sleep(0.01)
        raise InterruptedError()
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=run)
    request = PiTaskRequest.from_document({'schema': 'capstone-pi-task/1', 'task_id': 't1',
        'parent_attempt_id': 'a1', 'entrypoint': 'delegated', 'instruction': 'Explain', 'messages': [],
        'dependency_results': [], 'executor_identity': host.identity, 'timeout_seconds': 2})
    host.submit(request)
    host.submit(request)
    host.cancel('t1')
    deadline = time.monotonic()+2
    while host.read('t1')['status'] in {'queued', 'running'} and time.monotonic() < deadline:
        time.sleep(0.01)
    assert calls == ['t1']
    assert host.read('t1')['result']['status'] == 'cancelled'


def test_service_restart_replays_receipt_without_repeating_work(tmp_path):
    from capstone_agent.general_pi_server import GeneralPiHost
    request = PiTaskRequest.from_document({'schema': 'capstone-pi-task/1', 'task_id': 't1',
        'parent_attempt_id': 'a1', 'entrypoint': 'delegated', 'instruction': 'Explain', 'messages': [],
        'dependency_results': [], 'executor_identity': {'engine': 'pi'}, 'timeout_seconds': 2})
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'},
                         run_task=lambda *_: ('Saved answer', {}))
    host.submit(request)
    deadline = time.monotonic()+2
    while host.read('t1')['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(0.01)
    restarted = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'},
        run_task=lambda *_: (_ for _ in ()).throw(AssertionError('repeated work')))
    restarted.submit(request)
    assert restarted.read('t1')['result']['answer'] == 'Saved answer'


def test_sources_reference_actual_host_observed_tool_results(tmp_path):
    from capstone_agent.general_pi_server import GeneralPiHost
    def run(request, cancelled, emit):
        emit({'type': 'tool_execution_end', 'toolName': 'bash', 'toolCallId': 'call-1',
              'result': {'content': [{'type': 'text', 'text': 'Observed output'}]}})
        return 'Answer', {}
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=run)
    request = PiTaskRequest.from_document({'schema': 'capstone-pi-task/1', 'task_id': 't1',
        'parent_attempt_id': 'a1', 'entrypoint': 'direct', 'instruction': 'Explain', 'messages': [],
        'dependency_results': [], 'executor_identity': host.identity, 'timeout_seconds': 2})
    host.submit(request)
    deadline = time.monotonic()+2
    while host.read('t1')['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(0.01)
    sources = host.read('t1')['result']['sources']
    assert len(sources) == 1
    assert sources[0]['kind'] == 'native_tool_observation'
    assert sources[0]['task_id'] == 't1'
    assert sources[0]['metadata']['tool_name'] == 'bash'
    assert list((tmp_path / 'receipts/observations/t1').glob('*.json'))


def test_invalid_native_answer_finishes_failed_instead_of_stranding_task(tmp_path):
    from capstone_agent.general_pi_server import GeneralPiHost
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'},
                         run_task=lambda *_: ('字' * 64000, {}))
    request = PiTaskRequest.from_document({'schema': 'capstone-pi-task/1', 'task_id': 't1',
        'parent_attempt_id': 'a1', 'entrypoint': 'direct', 'instruction': 'Explain', 'messages': [],
        'dependency_results': [], 'executor_identity': host.identity, 'timeout_seconds': 2})
    host.submit(request)
    deadline = time.monotonic()+0.3
    while host.read('t1')['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(0.01)
    assert host.read('t1')['status'] == 'failed'


def test_artifact_bytes_persist_and_workspaces_are_released(tmp_path):
    from capstone_agent.general_pi_server import GeneralPiHost
    def run(request, cancelled, emit):
        work = tmp_path / 'tasks' / request.task_id
        work.mkdir(parents=True)
        (work / 'output.txt').write_text('Saved product')
        return 'Done', {}
    identity = {'engine': 'pi'}
    host = GeneralPiHost(root=tmp_path, identity=identity, run_task=run)
    request = PiTaskRequest.from_document({'schema': 'capstone-pi-task/1', 'task_id': 't1',
        'parent_attempt_id': 'a1', 'entrypoint': 'direct', 'instruction': 'Explain', 'messages': [],
        'dependency_results': [], 'executor_identity': identity, 'timeout_seconds': 2})
    host.submit(request)
    deadline = time.monotonic()+2
    while host.read('t1')['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(0.01)
    assert not (tmp_path / 'tasks/t1').exists()
    result = host.read('t1')['result']
    artifact = result['artifacts'][0]
    restarted = GeneralPiHost(root=tmp_path, identity=identity, run_task=run)
    assert restarted.read_artifact('t1', artifact['artifact_id']) == b'Saved product'


def test_retention_keeps_tombstone_and_cannot_repeat_expired_side_effect(tmp_path):
    from capstone_agent.general_pi_server import GeneralPiHost
    calls = []
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'},
        run_task=lambda request, *_: (calls.append(request.task_id) or 'Done', {}), retention_seconds=0.05)
    request = PiTaskRequest.from_document({'schema': 'capstone-pi-task/1', 'task_id': 't1',
        'parent_attempt_id': 'a1', 'entrypoint': 'direct', 'instruction': 'Explain', 'messages': [],
        'dependency_results': [], 'executor_identity': host.identity, 'timeout_seconds': 2})
    host.submit(request)
    deadline = time.monotonic()+2
    while host.read('t1')['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(0.01)
    time.sleep(0.06)
    host.sweep()
    host.submit(request)
    assert calls == ['t1']
    assert host.read('t1')['result']['status'] == 'failed'
    assert 'not repeated' in host.read('t1')['result']['answer']


def test_storage_quota_rejects_new_work_without_losing_saved_products(tmp_path):
    from capstone_agent.general_pi_storage import GeneralPiStorage
    storage = GeneralPiStorage(tmp_path, max_bytes=1024, max_receipts=1)
    storage.save({'task_id': 'first'}, {'answer': 'kept'})
    with pytest.raises(OSError, match='capacity'):
        storage.save({'task_id': 'second'}, None)
    with pytest.raises(OSError, match='quota'):
        storage.observation('first', 'large', b'x' * 1024)
    assert storage.load('first')['result']['answer'] == 'kept'
    assert storage.load('second') is None


def test_artifact_persistence_failure_settles_failed_and_releases_workspace(tmp_path, monkeypatch):
    from capstone_agent.general_pi_server import GeneralPiHost
    def run(request, *_):
        workspace = tmp_path / 'tasks' / request.task_id
        workspace.mkdir(parents=True)
        (workspace / 'product.txt').write_text('Product')
        return 'Done', {}
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=run)
    def fail(*_):
        raise OSError('Private storage unavailable')
    monkeypatch.setattr(host.storage, 'artifacts', fail)
    request = PiTaskRequest.from_document({'schema': 'capstone-pi-task/1', 'task_id': 't1',
        'parent_attempt_id': 'a1', 'entrypoint': 'direct', 'instruction': 'Explain', 'messages': [],
        'dependency_results': [], 'executor_identity': host.identity, 'timeout_seconds': 2})
    host.submit(request)
    deadline = time.monotonic()+2
    while host.read('t1')['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(0.01)
    assert host.read('t1')['status'] == 'failed'
    assert not (tmp_path / 'tasks/t1').exists()
    assert host.storage.load('t1')['result']['status'] == 'failed'
