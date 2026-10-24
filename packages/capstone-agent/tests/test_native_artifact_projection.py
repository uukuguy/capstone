"""Real generated files remain process artifacts until explicit delivery."""
from hashlib import sha256
from types import SimpleNamespace
import threading
import time

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from capstone_agent.general_pi_server import GeneralPiHost, make_server
from capstone_agent.pi_delegation import HttpGeneralPiExecutor, PiTaskRequest, PiTaskResult
from capstone_agent.request_intent import NodeControl
from capstone_agent.native_artifact_projection import project_native_artifacts, register_native_artifact_routes
from test_enterprise_normal_chat import chat_store, native_executor
from test_thread_postgres import postgres_thread_service


def claim():
    return SimpleNamespace(thread_id='thr_files', run_id='run_files',
        attempt=SimpleNamespace(attempt_id='attempt_files', turn_id='turn_files'),
        task_context=SimpleNamespace(snapshot_id='task_snapshot', goal_revision=1,
            binding=SimpleNamespace(work_id='work_files', thread_id='thr_files')))


def test_native_file_bytes_cross_real_protected_host_and_thread_route(tmp_path):
    data = b'# Real generated report\n\nA saved answer.\n'
    def generate(request, *_):
        workspace = tmp_path / 'host' / 'tasks' / request.task_id
        workspace.mkdir(parents=True)
        (workspace / 'report.md').write_bytes(data)
        return 'The report is saved.', {}
    host = GeneralPiHost(root=tmp_path / 'host', identity={'engine': 'pi', 'config_revision': 'fixture'}, run_task=generate)
    server = make_server(host, control_token='private-control', address=('127.0.0.1', 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        executor = HttpGeneralPiExecutor(f'http://127.0.0.1:{server.server_port}', identity=host.identity,
            capability=host.capability, control_token='private-control')
        request = PiTaskRequest('file-task', 'attempt_files', 'delegated', 'Save report', (), (), host.identity, 5)
        result = executor.execute(request, NodeControl(lambda: None, time.monotonic() + 5), lambda _: None)
        descriptor, = project_native_artifacts(claim(), result)
        assert descriptor['scope'] == 'instruction'
        assert descriptor['work_id'] == 'work_files'
        assert descriptor['file_name'] == 'report.md'
        assert descriptor['sha256'] == sha256(data).hexdigest()
        assert descriptor['media_type'] == 'text/markdown'
        assert 'path' not in descriptor
        event = {'event_type': 'native_artifact_published', 'visibility': 'public', 'thread_id': 'thr_files',
            'attempt_id': 'attempt_files', 'payload': {'artifact': descriptor}}
        class Records:
            def read_attempt_records(self, thread_id, attempt_id, **kwargs):
                assert (thread_id, attempt_id) == ('thr_files', 'attempt_files')
                return {'events': [event], 'has_more': False, 'next_after': 1}
        app = FastAPI()
        def authorize(request):
            if request.headers.get('authorization') != 'Bearer operator':
                raise HTTPException(401)
        register_native_artifact_routes(app, service=Records(), executor_provider=lambda: executor, authorize=authorize)
        client = TestClient(app)
        url = descriptor['download_url']
        assert client.get(url).status_code == 401
        response = client.get(url, headers={'authorization': 'Bearer operator'})
        assert response.status_code == 200
        assert response.content == data
        assert response.headers['x-content-type-options'] == 'nosniff'
        assert client.get(url.replace(descriptor['artifact_id'], 'file-missing'), headers={'authorization': 'Bearer operator'}).status_code == 404
        listed = client.get('/api/v1/threads/thr_files/attempts/attempt_files/artifacts', headers={'authorization': 'Bearer operator'})
        assert listed.json()['artifacts'] == [descriptor]
        (host.storage.root / 'artifacts' / result.task_id / descriptor['host_artifact_id']).write_bytes(b'tampered')
        assert client.get(url, headers={'authorization': 'Bearer operator'}).status_code == 410
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)


@pytest.mark.parametrize('change', [
    {'task_id': 'wrong'}, {'parent_attempt_id': 'other'},
    {'metadata': {'path': '../secret', 'sha256': '0' * 64, 'size_bytes': 1}},
    {'metadata': {'path': '/host/secret', 'sha256': '0' * 64, 'size_bytes': 1}},
])
def test_invalid_file_references_do_not_become_public_artifacts(change):
    artifact = {'artifact_id': 'file-one', 'task_id': 'task-one', 'parent_attempt_id': 'attempt_files',
        'kind': 'workspace_file', 'metadata': {'path': 'out.csv', 'sha256': '0' * 64, 'size_bytes': 1}}
    result = SimpleNamespace(to_document=lambda: {'task_id': 'task-one', 'parent_attempt_id': 'attempt_files',
        'status': 'completed', 'executor_identity': {'engine': 'pi'}, 'artifacts': [{**artifact, **change}]})
    with pytest.raises(ValueError):
        project_native_artifacts(claim(), result)


def _file_result(count):
    digest = sha256(b'report').hexdigest()
    artifacts = []
    for index in range(count):
        path = f'report-{index}.md'
        artifacts.append({'artifact_id': 'file-' + sha256(path.encode()).hexdigest()[:16] + '-' + digest,
            'task_id': 'task-files', 'parent_attempt_id': 'attempt_files', 'kind': 'workspace_file',
            'metadata': {'path': path, 'sha256': digest, 'size_bytes': 6}})
    document = {'task_id': 'task-files', 'parent_attempt_id': 'attempt_files', 'status': 'completed',
                'executor_identity': {'engine': 'pi'}, 'artifacts': artifacts}
    return SimpleNamespace(to_document=lambda: document)


def test_projection_accepts_verified_files_above_old_cap_within_selected_capacity():
    from capstone_agent.application_capacity import current_capacity, initialize_capacity
    previous = current_capacity()
    try:
        initialize_capacity({'artifact_count': 128})
        descriptors = project_native_artifacts(claim(), _file_result(76))
        assert len(descriptors) == 76
        assert len({item['artifact_id'] for item in descriptors}) == 76
        assert all(item['attempt_id'] == 'attempt_files' for item in descriptors)
    finally:
        initialize_capacity(previous)


@pytest.mark.parametrize('maximum,count', [(128, 129), (2, 3)])
def test_projection_reports_the_selected_artifact_count_capacity(maximum, count):
    from capstone_agent.application_capacity import CapacityExceeded, current_capacity, initialize_capacity
    previous = current_capacity()
    try:
        initialize_capacity({'artifact_count': maximum})
        with pytest.raises(CapacityExceeded) as error:
            project_native_artifacts(claim(), _file_result(count))
        assert (error.value.dimension, error.value.actual, error.value.limit, error.value.phase) == (
            'artifact_count', count, maximum, 'artifact.projection')
    finally:
        initialize_capacity(previous)


def test_projection_still_rejects_duplicate_file_receipts_within_capacity():
    result = _file_result(1)
    result.to_document()['artifacts'] *= 2
    with pytest.raises(ValueError, match='native file receipt count is invalid'):
        project_native_artifacts(claim(), result)


def test_replayed_or_failed_file_keeps_real_producer_and_current_process_owner():
    digest = sha256(b'partial').hexdigest()
    artifact_id = 'file-' + sha256(b'partial.md').hexdigest()[:16] + '-' + digest
    result = SimpleNamespace(to_document=lambda: {'task_id': 'task-original', 'parent_attempt_id': 'attempt_original',
        'status': 'failed', 'executor_identity': {'engine': 'pi'}, 'artifacts': [{
            'artifact_id': artifact_id, 'task_id': 'task-original', 'parent_attempt_id': 'attempt_original',
            'kind': 'workspace_file', 'metadata': {'path': 'partial.md', 'sha256': digest, 'size_bytes': 7}}]})
    with pytest.raises(ValueError):
        project_native_artifacts(claim(), result)
    descriptor, = project_native_artifacts(claim(), result, expected_parent_attempt_id='attempt_original')
    assert descriptor['producer_attempt_id'] == 'attempt_original'
    assert descriptor['attempt_id'] == 'attempt_files'
    assert descriptor['source_status'] == 'failed'
    assert descriptor['scope'] == 'instruction'
    other = result.to_document()
    other['task_id'] = 'task-other'
    other['artifacts'][0]['task_id'] = 'task-other'
    second, = project_native_artifacts(claim(), SimpleNamespace(to_document=lambda: other),
                                      expected_parent_attempt_id='attempt_original')
    assert second['host_artifact_id'] == descriptor['host_artifact_id']
    assert second['artifact_id'] != descriptor['artifact_id']


@pytest.mark.parametrize('status', ['failed', 'cancelled'])
def test_host_retains_real_files_after_failure_or_cancellation(tmp_path, status):
    def generate(request, *_):
        workspace = tmp_path / 'tasks' / request.task_id
        workspace.mkdir(parents=True)
        (workspace / 'partial.csv').write_bytes(b'row,value\n1,partial\n')
        if status == 'cancelled':
            host.cancel(request.task_id)
            raise InterruptedError('cancelled after writing')
        raise RuntimeError('failed after writing')
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=generate)
    request = PiTaskRequest('partial-task', 'attempt_files', 'delegated', 'Create a file', (), (), host.identity, 5)
    host.submit(request)
    deadline = time.monotonic() + 5
    while host.read(request.task_id)['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(0.01)
    result = PiTaskResult.from_document(host.read(request.task_id)['result'], request)
    descriptor, = project_native_artifacts(claim(), result)
    assert descriptor['source_status'] == status
    assert descriptor['scope'] == 'instruction'
    assert host.read_artifact(request.task_id, descriptor['host_artifact_id']) == b'row,value\n1,partial\n'


def test_user_stop_publishes_retained_process_file_without_claiming_completion(chat_store, tmp_path):
    from capstone_agent.native_artifact_projection import read_native_artifact
    from capstone_agent.native_hosted_worker import native_runtime_factory
    from capstone_agent.thread_worker import run_pending_attempt
    from test_thread_work_execution import command
    created = threading.Event()
    def generate(request, cancelled, _emit):
        workspace = tmp_path / 'tasks' / request.task_id
        workspace.mkdir(parents=True)
        (workspace / 'partial.md').write_bytes(b'Partial output before user stop.')
        created.set()
        while not cancelled():
            time.sleep(0.005)
        raise InterruptedError('user stopped')
    published = native_executor()
    host = GeneralPiHost(root=tmp_path, identity=published.identity, run_task=generate)
    host.capability = published.capability
    server = make_server(host, control_token='private-control', address=('127.0.0.1', 0))
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    worker = None
    try:
        executor = HttpGeneralPiExecutor(f'http://127.0.0.1:{server.server_port}', identity=host.identity,
            capability=host.capability, control_token='private-control')
        store, thread_id = chat_store
        store.set_native_executor(executor)
        from capstone_agent.artifacts import MemoryObjectStore
        objects = MemoryObjectStore()
        store.set_material_store(objects)
        receipt = store.submit_command(command(store, thread_id, 'send_message', 'files_start', payload={'text': 'Generate a file'}))
        assert receipt.status == 'accepted'
        outcomes = []
        worker = threading.Thread(target=lambda: outcomes.append(run_pending_attempt(store,
            native_runtime_factory(executor), worker_id='files', implementation_family='native')))
        worker.start()
        assert created.wait(timeout=5)
        work = store.snapshot(thread_id).works[0]
        assert store.submit_command(command(store, thread_id, 'cancel_work', 'files_stop',
            work_id=work['work_id'], revision=work['revision'], payload={})).status == 'accepted'
        worker.join(timeout=5)
        assert not worker.is_alive()
        assert outcomes[0].status == 'cancelled'
        assert any(key.startswith('native-process-artifacts/') for key in objects.contents)
        rows = [event for event in store.read_events(thread_id, 0).events if event.event_type == 'native_artifact_published']
        descriptor = rows[0].payload['artifact']
        assert descriptor['source_status'] == 'cancelled'
        _, data = read_native_artifact(store, executor, thread_id, descriptor['attempt_id'], descriptor['artifact_id'])
        assert data == b'Partial output before user stop.'
        assert read_native_artifact(store, None, thread_id, descriptor['attempt_id'], descriptor['artifact_id'])[1] == data
        assert store.snapshot(thread_id).works[0]['status'] == 'cancelled'
    finally:
        if worker is not None:
            worker.join(timeout=5)
        server.shutdown(); server.server_close(); server_thread.join(timeout=2)
