import pytest
from fastapi.testclient import TestClient
from capstone_agent.host_api import create_host_app
from test_harness import _thread_service
from test_thread_http_api import _Ledger, WorkerRegistry
from test_attempt_records import completed_task


def test_diagnosis_executes_pi_without_submitting_a_thread_command(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setenv('CAPSTONE_DEPLOYMENT_STAGE', 'local')
    monkeypatch.setenv('CAPSTONE_DEBUG_COMMANDS', '1')
    service, claim = completed_task()
    calls = []
    interrupted = False
    from capstone_agent import debug_investigations
    register = debug_investigations.InvestigationRegister(service)
    monkeypatch.setattr(debug_investigations, 'InvestigationRegister', lambda service: register)

    class Executor:
        identity = {'service_id': 'pi-local', 'instance_id': 'pi-test', 'revision': 'test'}

        def execute(self, request, control, on_event):
            calls.append(request)
            if interrupted:
                raise OSError('lost response')
            return SimpleNamespace(status='completed', answer='输入检查失败。')

        def observe_terminal_task(self, task_id, parent_attempt_id, executor_identity):
            assert (task_id, parent_attempt_id, executor_identity) == (
                calls[-1].task_id, calls[-1].parent_attempt_id, self.identity)
            return SimpleNamespace(status='completed', answer='已找回原诊断结果。')

        def cancel(self, task_id):
            assert task_id == calls[-1].task_id
            return SimpleNamespace(task_id=task_id, parent_attempt_id=calls[-1].parent_attempt_id,
                                   status='cancelled', answer='')

    executor = Executor()
    app = create_host_app(_Ledger(), WorkerRegistry(()), operator_token='hosted-secret',
                          allowed_hosts={'localhost'}, allowed_origins={'http://localhost:5173'},
                          thread_open_access=True, thread_service=service, native_artifact_executor=executor)
    path = f'/api/v1/threads/{claim.thread_id}/debug'
    before = service.snapshot(claim.thread_id).last_event_seq
    with TestClient(app, base_url='http://localhost') as client:
        receipt = client.post(path + '/investigations', headers={'Idempotency-Key': 'direct-debug'},
                              json={'objective': '检查失败', 'attempt_id': claim.attempt.attempt_id})
        identity = receipt.json()['investigation_id']
        response = client.post(f'{path}/investigations/{identity}/diagnose')
        assert response.status_code == 200, response.text
        assert response.json()['status'] == 'queued'
        assert not calls
        assert response.json()['attempt_id'] == claim.attempt.attempt_id
        assert client.post(f'{path}/investigations/{identity}/diagnose').json() == response.json()
        register.diagnose(claim.workspace_name, claim.thread_id, identity, executor)
        assert calls[0].entrypoint == 'direct'
        assert len(calls) == 1
        assert service.snapshot(claim.thread_id).last_event_seq == before
        interrupted = True
        second = client.post(path + '/investigations', headers={'Idempotency-Key': 'recover-debug'},
                             json={'objective': '恢复结果', 'attempt_id': claim.attempt.attempt_id})
        url = f"{path}/investigations/{second.json()['investigation_id']}/diagnose"
        assert client.post(url).json()['status'] == 'queued'
        assert register.diagnose(claim.workspace_name, claim.thread_id,
                                 second.json()['investigation_id'], executor)['status'] == 'unknown'
        restored = client.get(url).json()
        assert restored['status'] == 'completed'
        assert restored['answer'] == '已找回原诊断结果。'
        assert client.post(url).json() == restored
        assert len(calls) == 2
        history = client.get(path + '/investigations').json()['investigations']
        assert [row['investigation_id'] for row in history] == [second.json()['investigation_id'], identity]
        assert client.get(f'{path}/investigations/{identity}/diagnose').json()['answer'] == '输入检查失败。'
        third = client.post(path + '/investigations', headers={'Idempotency-Key': 'stop-debug'},
                            json={'objective': '停止诊断', 'attempt_id': claim.attempt.attempt_id})
        url = f"{path}/investigations/{third.json()['investigation_id']}/diagnose"
        assert client.post(url).json()['status'] == 'queued'
        assert client.delete(url).json()['status'] == 'cancelled'
        assert len(calls) == 2
        assert client.get(url).json()['status'] == 'cancelled'
        assert service.snapshot(claim.thread_id).last_event_seq == before


def test_debug_diagnosis_reads_a_tool_failure_beyond_the_first_page():
    from types import SimpleNamespace
    from capstone_agent.debug_investigations import InvestigationRegister
    from test_attempt_failure_delivery import claim_attempt

    service = _thread_service()
    claim = claim_attempt(service)
    for index in range(15):
        service.append_runtime_event(claim, event_type='runtime_event', visibility='public',
            payload={'native_type': 'tool_execution_end', 'tool_name': f'read_{index}',
                     'is_error': index == 14,
                     'activity': {'output_excerpt': 'selected source remained ambiguous' if index == 14 else ''}})
    service.finish_attempt(claim, phase='completed', payload={'answer': 'Done'})
    register = InvestigationRegister(service)
    investigation = register.start(claim.workspace_name, claim.thread_id, 'late-error', 'Find failure',
                                   claim.attempt.attempt_id)
    failure_seq = investigation['observation']['first_failure']['seq']

    def execute(request, control, on_event):
        assert 'selected source remained ambiguous' in request.instruction
        return SimpleNamespace(status='completed', answer='Failure found')

    executor = SimpleNamespace(identity={'service_id': 'pi-local', 'instance_id': 'pi-test', 'revision': 'test'},
                               execute=execute)
    diagnosis = register.diagnose(claim.workspace_name, claim.thread_id, investigation['investigation_id'], executor)
    assert failure_seq in diagnosis['evidence_event_seqs']


def test_export_requires_permission_and_excludes_event_payloads(monkeypatch):
    monkeypatch.setenv('CAPSTONE_DEPLOYMENT_STAGE', 'local')
    monkeypatch.setenv('CAPSTONE_DEBUG_COMMANDS', '1')
    monkeypatch.setenv('CAPSTONE_DEBUG_TIMELINE_EXPORT', '0')
    service, claim = completed_task()
    app = create_host_app(_Ledger(), WorkerRegistry(()), operator_token='hosted-secret',
                          allowed_hosts={'localhost'}, allowed_origins={'http://localhost:5173'},
                          thread_open_access=True, thread_service=service)
    path = f'/api/v1/threads/{claim.thread_id}/debug/attempts/{claim.attempt.attempt_id}/timeline'
    with TestClient(app, base_url='http://localhost') as client:
        assert client.get(path).status_code == 403
        monkeypatch.setenv('CAPSTONE_DEBUG_TIMELINE_EXPORT', '1')
        response = client.get(path)
        assert response.status_code == 200
        page = response.json()
        assert page['events']
        assert all(set(event) == {'seq', 'type', 'occurred_at'} for event in page['events'])
        assert 'unverified_answer_recorded' not in response.text
        assert 'Input check failed' not in response.text
        debug = f'/api/v1/threads/{claim.thread_id}/debug'
        start = client.post(debug+'/investigations', headers={'Idempotency-Key':'saved-finding'},
                            json={'objective':'定位失败', 'attempt_id':claim.attempt.attempt_id})
        assert start.status_code == 200
        finding = start.json()['observation']
        records = debug + '/investigations/' + start.json()['investigation_id'] + '/records'
        evidence = records.removesuffix('/records') + '/evidence'
        exported = client.get(evidence)
        assert exported.status_code == 200
        assert exported.json()['observation'] == finding
        assert exported.json()['data_gateway']['status'] == 'export_unavailable'
        assert 'Input check failed' not in exported.text
        monkeypatch.setenv('CAPSTONE_DEBUG_TIMELINE_EXPORT', '0')
        assert client.get(evidence).status_code == 403
        monkeypatch.setenv('CAPSTONE_DEBUG_TIMELINE_EXPORT', '1')
        scoped = client.get(records)
        assert scoped.status_code == 200
        assert scoped.json()['attempt_id'] == claim.attempt.attempt_id
        assert 'Input check failed' in scoped.text
        assert 'Unverified product' not in scoped.text
        assert client.get(records, params={'after': finding['through'] + 1}).status_code == 422
        assert finding['attempt_id'] == claim.attempt.attempt_id
        assert finding['first_failure']['type'] == 'validation_observation'
        assert any(event['seq'] == finding['first_failure']['seq'] for event in page['events'])
        assert client.get(debug+'/status').json()['investigation']['observation'] == finding
        assert client.post(debug+'/investigations', headers={'Idempotency-Key':'outside'},
                           json={'objective':'定位失败','attempt_id':'unknown'}).status_code == 404
        assert client.get(path.replace(claim.attempt.attempt_id, 'unknown')).status_code == 404
        monkeypatch.setenv('CAPSTONE_DEBUG_COMMANDS', '0')
        assert client.get(path).status_code == 403


@pytest.mark.parametrize('text', ['/debug 检查运行记录', '/debug 检查失败调用'])
def test_open_development_access_and_release_block(monkeypatch, text):
    monkeypatch.setenv('CAPSTONE_DEPLOYMENT_STAGE', 'local')
    monkeypatch.delenv('CAPSTONE_DEBUG_COMMANDS', raising=False)
    from dataclasses import replace
    from capstone_agent.thread_service import InMemoryThreadService
    from test_enterprise_normal_chat import native_executor
    snapshot = _thread_service().snapshot('thr_harness')
    service = InMemoryThreadService(replace(snapshot, active_model_context=None,
                                    active_grid_page_id=None, minimum_protocol_version=2))
    service.set_native_executor(native_executor())
    app = create_host_app(_Ledger(), WorkerRegistry(()), operator_token='hosted-secret',
                          allowed_hosts={'localhost'}, allowed_origins={'http://localhost:5173'},
                          thread_open_access=True, thread_service=service)
    path = '/api/v1/threads/thr_harness'
    with TestClient(app, base_url='http://localhost') as client:
        client.headers.update({"Capstone-Thread-Version": "2"})
        assert client.get(path + '/debug/status').json()['enabled'] is True
        headers = {'Idempotency-Key': 'test-start'}
        start_path = path + '/debug/investigations'
        first = client.post(start_path, headers=headers, json={'objective':'检查失败调用'})
        assert first.status_code == 200
        assert client.post(start_path, headers=headers, json={'objective':'检查失败调用'}).json() == first.json()
        assert client.get(path + '/debug/status').json()['investigation'] == first.json()
        assert client.post(start_path, headers=headers, json={'objective':'不同目标'}).status_code == 409
        from test_thread_work_execution import command as work_command
        run = work_command(service, 'thr_harness', 'send_message', 'debug_run',
                           payload={'text': text,
                                    'debug_investigation_id': first.json()['investigation_id']})
        version = {'Capstone-Thread-Version': '2'}
        missing = {**run, 'payload': {**run['payload'], 'debug_investigation_id': 'inv_missing'}}
        assert client.post(path + '/commands', headers=version, json=missing).status_code == 404
        response = client.post(path + '/commands', headers=version, json=run)
        assert response.status_code == 202, response.text
        assert response.json()['status'] == 'accepted'
        monkeypatch.setenv('CAPSTONE_DEPLOYMENT_STAGE', 'user-trial')
        assert client.post(start_path, headers=headers, json={'objective':'检查失败调用'}).status_code == 403
        assert client.get(path + '/debug/status').status_code == 403
        command = {'thread_id': 'thr_harness', 'kind': 'send_message',
                   'payload': {'text': '/debug start test'}}
        assert client.post(path + '/commands', json=command).status_code == 403


def test_debug_source_query_syncs_bound_revision_only_on_cache_miss(monkeypatch, tmp_path):
    import json
    from capstone_agent import debug_sources
    resolve = debug_sources.resolve_sources
    library = tmp_path/'library'
    monkeypatch.setattr(debug_sources, 'resolve_sources', lambda publication: resolve(publication, tmp_path, library))
    monkeypatch.setenv('CAPSTONE_DEPLOYMENT_STAGE', 'local')
    monkeypatch.setenv('CAPSTONE_DEBUG_COMMANDS', '1')
    calls = []
    revision = 'a' * 64

    class Executor:
        def thread_gateway_publication(self, binding, *, refresh):
            assert refresh
            return {'available': True, 'connection_id': 'selected', 'catalog': {
                'instance': {'instance_id': 'live', 'source_sha256': revision}}}

        def sync_debug_source(self, connection_id, instance_id, digest):
            calls.append((connection_id, instance_id, digest))
            directory = library/digest
            directory.mkdir(parents=True)
            filename = f'data-gateway-{digest}.zip'
            (directory/filename).touch()
            (directory/'manifest.json').write_text(json.dumps({'sources': [
                {'repository': 'data-gateway', 'revision': digest, 'archive': filename}]}))

    app = create_host_app(_Ledger(), WorkerRegistry(()), operator_token='hosted-secret',
        allowed_hosts={'localhost'}, allowed_origins={'http://localhost:5173'}, thread_open_access=True,
        thread_service=_thread_service(), native_artifact_executor=Executor())
    with TestClient(app, base_url='http://localhost') as client:
        for _ in range(2):
            response = client.get('/api/v1/threads/thr_harness/debug/sources')
            assert response.json()['status'] == 'matched'
    assert calls == [('selected', 'live', revision)]
