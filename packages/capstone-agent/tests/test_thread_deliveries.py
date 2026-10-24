from copy import deepcopy

import pytest

from capstone_agent.artifacts import MemoryObjectStore
from capstone_agent.thread_deliveries import publish_delivery, delivery_page, read_delivery_content
from test_thread_http_api import _service
from test_thread_management import _message
from test_thread_postgres import postgres_thread_service
from test_thread_work_execution import execution_store


THREAD = 'thr_demo_39'


def completed(service, ordinal=1, phase='completed'):
    _message(service, ordinal)
    claim = service.claim_attempt('worker', 30)
    service.finish_attempt(claim, phase=phase, payload={'answer': 'An answer is not a delivery.'}
                           if phase == 'completed' else {'error_code': 'solver_unavailable', 'debug': 'PRIVATE'})
    return claim.attempt.attempt_id


def request(attempt, **changes):
    return {'schema': 'capstone-delivery-request/1', 'command_id': 'cmd_delivery',
            'idempotency_key': 'idem_delivery', 'request_id': 'request_report',
            'expected_revision': 0, 'work_id': None, 'trigger_attempt_id': attempt,
            'title': 'Requested report', 'scope': 'Summarize the saved work and remaining gaps',
            'format': 'markdown', 'supporting_process_ids': ['process_' + attempt], **changes}


def test_explicit_report_is_real_downloadable_artifact_and_does_not_close_session():
    service, objects = _service(), MemoryObjectStore()
    attempt = completed(service)
    assert delivery_page(service, THREAD)['deliveries'] == []
    receipt = publish_delivery(service, objects, THREAD, request(attempt))
    assert receipt.status == 'accepted'
    delivery = receipt.target['delivery']
    assert delivery['scope'] == 'task'
    assert delivery['work_id'] is None  # Do not invent a Work for legacy history.
    assert delivery['request']['trigger_attempt_id'] == attempt
    assert delivery['supporting_process_ids'] == ['process_' + attempt]
    assert delivery['supporting_process_refs'][0]['attempt_id'] == attempt
    assert delivery['supporting_process_refs'][0]['model_context_id'] == 'ctx_ieee39_7'
    assert delivery['requirements_status'] == 'not_independently_checked'
    content = read_delivery_content(service, objects, THREAD, delivery['artifact_id'], 1)
    assert content.startswith(b'# Requested report')
    assert b'Summarize the saved work' in content
    assert b'PRIVATE' not in content
    assert content != b'An answer is not a delivery.'
    _message(service, 2)
    assert service.snapshot(THREAD).current_attempt is not None


def test_exact_retry_and_revision_history_survive_new_service_facade():
    service, objects = _service(), MemoryObjectStore()
    attempt = completed(service)
    original = request(attempt)
    first = publish_delivery(service, objects, THREAD, original)
    count = len(service._events)
    assert publish_delivery(service, objects, THREAD, deepcopy(original)) == first
    assert len(service._events) == count
    changed = publish_delivery(service, objects, THREAD, {**original, 'scope': 'changed'})
    assert changed.rejection == 'idempotency_conflict'
    second = publish_delivery(service, objects, THREAD, request(attempt,
        command_id='cmd_revision', idempotency_key='idem_revision', expected_revision=1, title='Revised report'))
    assert second.target['delivery']['artifact_id'] == first.target['delivery']['artifact_id']
    page = delivery_page(service, THREAD)
    assert [item['revision'] for item in page['deliveries']] == [2, 1]
    old = read_delivery_content(service, objects, THREAD, first.target['delivery']['artifact_id'], 1)
    assert old.startswith(b'# Requested report')


def test_failure_support_is_preserved_without_private_diagnostics_or_claimed_success():
    service, objects = _service(), MemoryObjectStore()
    attempt = completed(service, phase='failed')
    receipt = publish_delivery(service, objects, THREAD, request(attempt))
    item = receipt.target['delivery']
    assert item['supporting_statuses'] == [{'process_id': 'process_' + attempt, 'status': 'failed'}]
    content = read_delivery_content(service, objects, THREAD, item['artifact_id'], 1)
    assert b'failed' in content and b'PRIVATE' not in content


@pytest.mark.parametrize('changes', [
    {'format': 'pdf'}, {'title': 'bad\r\nheader'}, {'supporting_process_ids': ['process_other']},
    {'trigger_attempt_id': 'other'}, {'work_id': 'work_invented'},
])
def test_invalid_or_unbound_requests_never_publish(changes):
    service, objects = _service(), MemoryObjectStore()
    attempt = completed(service)
    before = service.snapshot(THREAD)
    with pytest.raises(ValueError):
        publish_delivery(service, objects, THREAD, request(attempt, **changes))
    assert delivery_page(service, THREAD)['deliveries'] == []
    assert service.snapshot(THREAD) == before
    assert not objects.contents


def test_integrity_failure_does_not_return_corrupt_download():
    service, objects = _service(), MemoryObjectStore()
    receipt = publish_delivery(service, objects, THREAD, request(completed(service)))
    item = receipt.target['delivery']
    objects.contents[next(iter(objects.contents))] = b'corrupt'
    with pytest.raises(ValueError, match='integrity'):
        read_delivery_content(service, objects, THREAD, item['artifact_id'], 1)


def test_storage_failure_has_no_published_event_or_lost_retry():
    service = _service()
    attempt = completed(service)
    class BrokenStore(MemoryObjectStore):
        def put(self, *args):
            raise OSError('store unavailable')
    with pytest.raises(OSError):
        publish_delivery(service, BrokenStore(), THREAD, request(attempt))
    assert delivery_page(service, THREAD)['deliveries'] == []
    assert publish_delivery(service, MemoryObjectStore(), THREAD, request(attempt)).status == 'accepted'


def test_storage_corruption_during_write_never_publishes_ready_delivery():
    class CorruptStore(MemoryObjectStore):
        def put(self, key, content, mime):
            super().put(key, b'incomplete', mime)
    service = _service()
    attempt = completed(service)
    with pytest.raises(OSError):
        publish_delivery(service, CorruptStore(), THREAD, request(attempt))
    assert delivery_page(service, THREAD)['deliveries'] == []


def test_report_uses_real_admitted_table_values_and_records_truncated_tables():
    from test_thread_result_projection import _service as projection_service, _claim_and_projection, RESULT_ONE, EVIDENCE_ONE
    service, objects = projection_service(), MemoryObjectStore()
    claim, document = _claim_and_projection(service, 1, RESULT_ONE, EVIDENCE_ONE)
    attempt, thread_id = claim.attempt.attempt_id, claim.thread_id
    document['tables'] = [{'table_id': 'saved_values', 'title': '已保存数值',
        'columns': [{'column_id': 'p', 'label': '有功', 'unit': 'MW'}],
        'rows': [{'row_id': 'one', 'cells': {'p': 67.15}}]}]
    document['tables'][0]['pagination'] = {'manifest_ref': 'table-manifest:sha256:' + 'd' * 64,
                                          'total_rows': 42, 'page_size': 1}
    service.finish_attempt(claim, phase='completed', payload={'answer': 'saved', 'result_projections': [document],
        'result_refs': [RESULT_ONE], 'evidence_refs': [EVIDENCE_ONE],
        'admission': {'mode': 'authority_backed', 'assurance': 'lineage_verified'}})
    item = publish_delivery(service, objects, thread_id, request(attempt)).target['delivery']
    content = read_delivery_content(service, objects, thread_id, item['artifact_id'], 1).decode()
    assert '67.15' in content and 'MW' in content
    assert RESULT_ONE in content
    assert '42' in content and 'table-manifest:sha256:' in content


@pytest.mark.parametrize('tamper', ['turn', 'context', 'admission', 'result_ref', 'evidence_ref'])
def test_report_does_not_adopt_projection_without_matching_terminal_admission(tamper):
    from dataclasses import replace
    from test_thread_result_projection import _service as projection_service, _claim_and_projection, RESULT_ONE, EVIDENCE_ONE
    service, objects = projection_service(), MemoryObjectStore()
    claim, document = _claim_and_projection(service, 1, RESULT_ONE, EVIDENCE_ONE)
    service.finish_attempt(claim, phase='completed', payload={'answer': 'saved', 'result_projections': [document],
        'result_refs': [RESULT_ONE], 'evidence_refs': [EVIDENCE_ONE],
        'admission': {'mode': 'authority_backed', 'assurance': 'lineage_verified'}})
    terminal = service._events[-1]
    payload = deepcopy(terminal.payload)
    if tamper == 'admission':
        payload['admission'] = {'mode': 'offline_information', 'assurance': 'general_knowledge'}
    elif tamper == 'result_ref':
        payload['result_refs'] = []
    elif tamper == 'evidence_ref':
        payload['evidence_refs'] = []
    else:
        field = 'turn_id' if tamper == 'turn' else 'model_context_id'
        payload['result_projections'][0][field] = 'other_identity'
    service._events[-1] = replace(terminal, payload=payload)
    with pytest.raises(ValueError):
        publish_delivery(service, objects, claim.thread_id, request(claim.attempt.attempt_id))
    assert delivery_page(service, claim.thread_id)['deliveries'] == []


def delivery_app(service, objects, executor=None):
    from capstone_agent.host_api import create_host_app
    from capstone_agent.artifacts import ArtifactService
    from capstone_agent.session import WorkerRegistry
    from test_thread_http_api import _Ledger
    from pathlib import Path
    return create_host_app(_Ledger(), WorkerRegistry(()), operator_token='hosted-secret',
        allowed_hosts={'localhost'}, allowed_origins={'http://localhost:5173'},
        thread_service=service, artifacts=ArtifactService(_Ledger(), objects, Path('/unused')),
        native_artifact_executor=executor)


def test_http_explicit_request_download_auth_and_old_versions():
    from fastapi.testclient import TestClient
    from test_thread_http_api import _auth
    service, objects = _service(), MemoryObjectStore()
    attempt = completed(service)
    with TestClient(delivery_app(service, objects), base_url='http://localhost') as client:
        assert client.post(f'/api/v1/threads/{THREAD}/deliveries', json=request(attempt)).status_code == 401
        response = client.post(f'/api/v1/threads/{THREAD}/deliveries', json=request(attempt), headers=_auth())
        assert response.status_code == 201
        item = response.json()['target']['delivery']
        path = f'/api/v1/threads/{THREAD}/deliveries/{item["artifact_id"]}/revisions/1/content'
        assert client.get(path).status_code == 401
        download = client.get(path, headers=_auth())
        assert download.status_code == 200
        assert download.headers['Content-Disposition'].startswith('attachment; filename="delivery_')
        assert download.headers['Content-Type'].startswith('text/markdown')
        assert download.content.startswith(b'# Requested report')
        assert client.get(f'/api/v1/threads/{THREAD}/deliveries', headers=_auth()).json()['deliveries'] == [item]
        assert client.get('/api/v1/threads/other/deliveries', headers=_auth()).status_code == 404
        assert client.post(f'/api/v1/threads/{THREAD}/deliveries', json=request(attempt, format='pdf'), headers=_auth()).status_code == 422


def test_postgres_restart_concurrent_revisions_and_command_identity(postgres_thread_service):
    from concurrent.futures import ThreadPoolExecutor
    from capstone_agent.thread_service import PostgresThreadService
    from capstone_agent.thread_commands import ThreadCommandFactory
    from test_thread_postgres import _snapshot
    service, thread_id = postgres_thread_service
    service.create_thread(_snapshot(thread_id))
    message = ThreadCommandFactory(thread_id).send_auto('Source for requested output', expected_event_seq=0,
        command_id='cmd_source', idempotency_key='idem_source')
    assert service.submit_command(message).status == 'accepted'
    claim = service.claim_attempt('worker', 30)
    service.finish_attempt(claim, phase='completed', payload={'answer': 'Source saved'})
    objects = MemoryObjectStore()
    original = request(claim.attempt.attempt_id)
    first = publish_delivery(service, objects, thread_id, original)
    assert first.status == 'accepted'
    reopened = PostgresThreadService(service.dsn)
    assert publish_delivery(reopened, objects, thread_id, original) == first
    # A new key must not reuse an existing command identity or hit a SQL unique constraint.
    conflict = publish_delivery(reopened, objects, thread_id, {**original, 'idempotency_key': 'idem_other'})
    assert conflict.rejection == 'command_id_conflict'
    def revise(index):
        return publish_delivery(PostgresThreadService(service.dsn), objects, thread_id,
            {**original, 'expected_revision': 1, 'command_id': f'cmd_rev_{index}', 'idempotency_key': f'idem_rev_{index}'})
    with ThreadPoolExecutor(2) as pool:
        receipts = list(pool.map(revise, (1, 2)))
    assert sorted(item.status for item in receipts) == ['accepted', 'rejected']
    assert [item['revision'] for item in delivery_page(reopened, thread_id)['deliveries']] == [2, 1]
    assert read_delivery_content(reopened, objects, thread_id, first.target['delivery']['artifact_id'], 1)
    assert reopened.snapshot(thread_id).session_title.source == 'automatic'


def test_delivery_names_session_once_but_user_title_remains_locked():
    from test_thread_title import rename
    service, objects = _service(), MemoryObjectStore()
    attempt = completed(service)
    original = request(attempt)
    first = publish_delivery(service, objects, THREAD, original)
    title = service.snapshot(THREAD).session_title
    assert title.text == 'Requested report' and title.source == 'automatic'
    assert title.source_ref == first.target['delivery']['artifact_id'] + ':1'
    assert publish_delivery(service, objects, THREAD, original) == first
    assert service.snapshot(THREAD).session_title == title
    assert service.submit_command(rename(THREAD, revision=title.revision, text=title.text)).status == 'accepted'
    locked = service.snapshot(THREAD).session_title
    revised = publish_delivery(service, objects, THREAD, request(attempt,
        command_id='cmd_new_report', idempotency_key='idem_new_report', expected_revision=1, title='A later report'))
    assert revised.status == 'accepted'
    assert service.snapshot(THREAD).session_title == locked


def test_work_bound_delivery_retains_actual_work_and_does_not_change_its_state(execution_store):
    from test_thread_work_execution import save_work, command
    service, thread_id = execution_store
    work = save_work(service, thread_id)
    start = service.submit_command(command(service, thread_id, 'start_work', 'delivery_start',
        work_id=work['work_id'], revision=work['revision']))
    assert start.status == 'accepted'
    claim = service.claim_attempt('worker', 30)
    service.finish_attempt(claim, phase='completed', payload={'answer': 'saved work'})
    before = service.snapshot(thread_id)
    value = request(claim.attempt.attempt_id, work_id=work['work_id'])
    objects = MemoryObjectStore()
    receipt = publish_delivery(service, objects, thread_id, value)
    assert receipt.target['delivery']['work_id'] == work['work_id']
    assert service.snapshot(thread_id).works == before.works
    assert service.snapshot(thread_id).run.state == 'open'
    service.set_archived(thread_id, True)
    assert publish_delivery(service, objects, thread_id, value) == receipt
    assert read_delivery_content(service, objects, thread_id, receipt.target['delivery']['artifact_id'], 1)
    rejected = publish_delivery(service, objects, thread_id, request(claim.attempt.attempt_id,
        work_id=work['work_id'], command_id='cmd_archived', idempotency_key='idem_archived', expected_revision=1))
    assert rejected.rejection == 'thread_archived'


def native_file(service, thread_id, data, *, status='completed', name='report.pdf'):
    from hashlib import sha256
    from types import SimpleNamespace
    from capstone_agent.thread_commands import ThreadCommandFactory
    from capstone_agent.native_artifact_projection import project_native_artifacts
    snapshot = service.snapshot(thread_id)
    message = ThreadCommandFactory(thread_id).send_auto('Generate a file',
        expected_event_seq=snapshot.last_event_seq, command_id=f'cmd_file_{snapshot.last_event_seq}', idempotency_key=f'idem_file_{snapshot.last_event_seq}')
    assert service.submit_command(message).status == 'accepted'
    claim = service.claim_attempt('worker', 30)
    identity = {'engine': 'pi', 'config_revision': 'delivery-fixture'}
    task_id = 'child-' + sha256(claim.attempt.attempt_id.encode()).hexdigest()[:16]
    host_id = 'file-' + sha256(name.encode()).hexdigest()[:16] + '-' + sha256(data).hexdigest()
    result = SimpleNamespace(to_document=lambda: {'task_id': task_id,
        'parent_attempt_id': claim.attempt.attempt_id, 'executor_identity': identity,
        'status': status, 'artifacts': [{'artifact_id': host_id, 'task_id': task_id,
            'parent_attempt_id': claim.attempt.attempt_id, 'kind': 'workspace_file',
            'metadata': {'path': name, 'sha256': sha256(data).hexdigest(), 'size_bytes': len(data)}}]})
    descriptor, = project_native_artifacts(claim, result)
    service.append_runtime_event(claim, event_type='native_artifact_published', payload={'artifact': descriptor})
    service.finish_attempt(claim, phase=status, payload={'answer': 'file saved'} if status == 'completed' else {})
    class Executor:
        calls = 0
        def read_artifact(self, task_id, artifact_id, **kwargs):
            self.calls += 1
            assert task_id == result.to_document()['task_id'] and artifact_id == host_id
            return data
    executor = Executor()
    executor.identity = identity
    return descriptor, executor


@pytest.mark.parametrize('status', ['completed', 'failed', 'cancelled'])
def test_explicit_native_file_adoption_copies_real_bytes_and_retains_status(status):
    service, objects = _service(), MemoryObjectStore()
    data = b'%PDF-1.7\nactual generated bytes\x00\xff'
    file, executor = native_file(service, THREAD, data, status=status, name='报告.pdf')
    body = request(file['attempt_id'], format='native-file', source_artifact={
        'attempt_id': file['attempt_id'], 'artifact_id': file['artifact_id']})
    assert delivery_page(service, THREAD)['deliveries'] == []
    receipt = publish_delivery(service, objects, THREAD, body, native_artifact_executor=executor)
    item = receipt.target['delivery']
    assert item['file_name'] == '报告.pdf' and item['media_type'] == 'application/pdf'
    assert item['source_status'] == status and item['generation_status'] == status
    assert item['source_artifact']['artifact_id'] == file['artifact_id']
    assert read_delivery_content(service, objects, THREAD, item['artifact_id'], 1) == data
    assert publish_delivery(service, objects, THREAD, body, native_artifact_executor=None) == receipt
    assert executor.calls == 1


def test_native_file_adoption_above_markdown_limit_has_typed_download():
    from fastapi.testclient import TestClient
    from test_thread_http_api import _auth
    service, objects = _service(), MemoryObjectStore()
    data = b'%PDF-' + b'x' * 2_100_000
    file, executor = native_file(service, THREAD, data)
    body = request(file['attempt_id'], format='native-file', source_artifact={
        'attempt_id': file['attempt_id'], 'artifact_id': file['artifact_id']})
    with TestClient(delivery_app(service, objects, executor), base_url='http://localhost') as client:
        response = client.post(f'/api/v1/threads/{THREAD}/deliveries', json=body, headers=_auth())
        assert response.status_code == 201
        item = response.json()['target']['delivery']
        path = f'/api/v1/threads/{THREAD}/deliveries/{item["artifact_id"]}/revisions/1/content'
        download = client.get(path, headers=_auth())
        assert download.status_code == 200 and download.content == data
        assert download.headers['Content-Type'].startswith('application/pdf')
        assert 'filename*=' in download.headers['Content-Disposition']


def test_postgres_native_adoption_survives_host_expiry_and_preserves_file_revisions(postgres_thread_service):
    from capstone_agent.thread_service import PostgresThreadService
    from test_thread_postgres import _snapshot
    service, thread_id = postgres_thread_service
    service.create_thread(_snapshot(thread_id))
    objects = MemoryObjectStore()
    file, executor = native_file(service, thread_id, b'first file')
    body = request(file['attempt_id'], format='native-file', source_artifact={
        'attempt_id': file['attempt_id'], 'artifact_id': file['artifact_id']})
    first = publish_delivery(service, objects, thread_id, body, native_artifact_executor=executor)
    assert first.status == 'accepted'
    reopened = PostgresThreadService(service.dsn)
    assert publish_delivery(reopened, objects, thread_id, body) == first
    assert read_delivery_content(reopened, objects, thread_id, first.target['delivery']['artifact_id'], 1) == b'first file'
    file2, executor2 = native_file(reopened, thread_id, b'new partial file', status='failed', name='partial.txt')
    second = publish_delivery(reopened, objects, thread_id, request(file2['attempt_id'],
        format='native-file', source_artifact={'attempt_id': file2['attempt_id'], 'artifact_id': file2['artifact_id']},
        expected_revision=1, command_id='cmd_adopt_2', idempotency_key='idem_adopt_2'), native_artifact_executor=executor2)
    item = second.target['delivery']
    assert item['revision'] == 2 and item['generation_status'] == 'failed'
    assert item['artifact_id'] == first.target['delivery']['artifact_id']
    assert read_delivery_content(reopened, objects, thread_id, item['artifact_id'], 2) == b'new partial file'
    assert read_delivery_content(reopened, objects, thread_id, item['artifact_id'], 1) == b'first file'


@pytest.mark.parametrize('tamper', ['other_file', 'other_attempt', 'work', 'corrupt'])
def test_native_adoption_rejects_unbound_or_corrupt_files_without_publication(tamper):
    service, objects = _service(), MemoryObjectStore()
    file, executor = native_file(service, THREAD, b'original')
    body = request(file['attempt_id'], format='native-file', source_artifact={
        'attempt_id': file['attempt_id'], 'artifact_id': file['artifact_id']})
    if tamper == 'other_file':
        body['source_artifact']['artifact_id'] = 'file_missing'
    elif tamper == 'other_attempt':
        body['source_artifact']['attempt_id'] = 'attempt_other'
    elif tamper == 'work':
        body['work_id'] = 'work_other'
    else:
        executor.read_artifact = lambda *args, **kwargs: b'changed'
    with pytest.raises((KeyError, ValueError, OSError)):
        publish_delivery(service, objects, THREAD, body, native_artifact_executor=executor)
    assert not objects.contents and delivery_page(service, THREAD)['deliveries'] == []
