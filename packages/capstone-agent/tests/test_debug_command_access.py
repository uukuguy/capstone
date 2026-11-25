import pytest
from fastapi.testclient import TestClient
from capstone_agent.host_api import create_host_app
from test_harness import _thread_service
from test_thread_http_api import _Ledger, WorkerRegistry
from test_attempt_records import completed_task


def test_independent_debug_reads_logs_for_a_bound_failed_call(monkeypatch):
    from types import SimpleNamespace
    from capstone_agent.debug_investigations import InvestigationRegister

    service, claim = completed_task()
    register = InvestigationRegister(service)
    binding = {'instance_id': 'fixture'}
    monkeypatch.setattr(register, 'historical_gateway', lambda *scope: binding)
    calls = []

    def read(actual_binding, workspace, investigation_id, operation, query):
        assert (actual_binding, workspace, investigation_id) == (binding, claim.workspace_name, 'inv_fixture')
        calls.append((operation, query))
        if operation == 'list':
            return {'receipts': [{'client_call_id': 'ok-call', 'state': 'observed', 'observed_status': 'ok'},
                                 {'client_call_id': 'failed-call', 'state': 'observed', 'observed_status': 'error'}]}
        return {'records': [{'stage': 'database.read', 'event': 'finished', 'severity': 'error',
                             'message': '查询超时', 'private': 'excluded'}],
                'log_read_status': 'retained', 'next_cursor': 'continue'}

    evidence = register._diagnosis_gateway_evidence(claim.workspace_name, claim.thread_id, 'inv_fixture',
                                                    SimpleNamespace(debug_observation=read))
    assert calls == [('list', {'limit': 4}), ('logs', {'client_call_id': 'failed-call', 'limit': 8})]
    assert evidence['logs'] == {'status': 'retained', 'client_call_id': 'failed-call', 'truncated': True,
                                'records': [{'stage': 'database.read', 'event': 'finished', 'severity': 'error',
                                             'message': '查询超时'}]}


def test_debug_historical_sources_check_each_admitted_revision(monkeypatch):
    from zipfile import BadZipFile
    from capstone_agent import debug_sources
    from capstone_agent.debug_investigations import InvestigationRegister

    service, _ = completed_task()
    register = InvestigationRegister(service)
    capstone, gateway = 'a' * 40, 'b' * 64
    binding = {'instance_id': 'historical', 'source_sha256': gateway}
    monkeypatch.setattr(register, 'get', lambda *scope: {'observation': {'capstone_revision': capstone}})
    monkeypatch.setattr(register, 'historical_gateway', lambda *scope: binding)

    def read_capstone(revision):
        assert revision == capstone

    def read_gateway(instance):
        assert instance == binding
        raise BadZipFile('invalid archive')

    monkeypatch.setattr(debug_sources, 'read_historical_capstone_source', read_capstone)
    monkeypatch.setattr(debug_sources, 'read_historical_gateway_source', read_gateway)
    assert register.historical_sources('local', 'thr_example', 'inv_example') == {
        'capstone': {'status': 'archive_verified', 'revision': capstone},
        'data-gateway': {'status': 'archive_unavailable', 'revision': gateway},
    }


def test_debug_pi_cannot_select_another_source_revision(monkeypatch):
    from capstone_agent import debug_sources

    revision = 'a' * 40
    scope = {'capstone_revision': revision, 'gateway': None, 'workspace': 'local',
             'gateway_investigation': 'inv_' + 'b' * 32}
    monkeypatch.setattr(debug_sources, 'read_historical_capstone_source',
                        lambda revision, **query: {'revision': revision, **query})
    debug_sources.checked_debug_scope(scope)
    query = {'repository': 'capstone', 'path': 'src/file.py', 'line': 10}
    assert debug_sources.read_debug_source(scope, 'source_lines', query) == {
        'revision': revision, 'path': 'src/file.py', 'line': 10}
    with pytest.raises(ValueError):
        debug_sources.read_debug_source(scope, 'source_lines', {**query, 'revision': 'c' * 40})


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
            on_event({'event_id': 'event-1', 'type': 'tool_execution_start',
                      'tool_name': 'agent_debug_observe', 'arguments': {'private': 'do not copy'}})
            running = register.get(claim.workspace_name, claim.thread_id, request.parent_attempt_id)['diagnosis']
            assert running['progress'] == [{'seq': 1, 'stage': 'tool_started', 'tool': 'agent_debug_observe'}]
            on_event({'event_id': 'event-2', 'type': 'tool_execution_end',
                      'tool_name': 'agent_debug_observe', 'is_error': True, 'result': 'private result'})
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
        source_path = f'{path}/investigations/{identity}/sources'
        assert client.get(source_path).json() == {
            'capstone': {'status': 'revision_unavailable'}, 'data_gateway': {'status': 'revision_unavailable'}}
        response = client.post(f'{path}/investigations/{identity}/diagnose')
        assert response.status_code == 200, response.text
        assert response.json()['status'] == 'queued'
        queued_snapshot = register.export_timeline(claim.workspace_name, claim.thread_id, identity)['snapshot_id']
        assert not calls
        assert response.json()['attempt_id'] == claim.attempt.attempt_id
        assert client.post(f'{path}/investigations/{identity}/diagnose').json() == response.json()
        register.diagnose(claim.workspace_name, claim.thread_id, identity, executor)
        assert calls[0].entrypoint == 'direct'
        assert '_gateway_snapshot' in register.get(claim.workspace_name, claim.thread_id, identity)['diagnosis']
        assert '_gateway_snapshot' not in client.get(f'{path}/investigations/{identity}/diagnose').json()
        evidence = register.export_timeline(claim.workspace_name, claim.thread_id, identity)
        assert evidence['snapshot_id'] != queued_snapshot
        assert register.export_timeline(claim.workspace_name, claim.thread_id, identity)['snapshot_id'] == evidence['snapshot_id']
        monkeypatch.setenv('CAPSTONE_DEBUG_TIMELINE_EXPORT', '1')
        exported = client.get(f'{path}/investigations/{identity}/evidence').json()
        assert exported['snapshot_id'] == evidence['snapshot_id']
        assert exported['data_gateway']['scope'] == 'download_time'
        assert exported['integrity']['digest'] == debug_investigations.evidence_digest(
            {key: value for key, value in exported.items() if key != 'integrity'})
        assert evidence['diagnosis']['source_evidence'] == {
            'capstone': {'status': 'revision_unavailable'}, 'data-gateway': {'status': 'revision_unavailable'}}
        assert evidence['diagnosis']['progress'] == [
            {'seq': 1, 'stage': 'tool_started', 'tool': 'agent_debug_observe'},
            {'seq': 2, 'stage': 'tool_failed', 'tool': 'agent_debug_observe'}]
        assert client.post(path + '/investigations', headers={'Idempotency-Key': 'direct-debug'},
                           json={'objective': '检查失败', 'attempt_id': claim.attempt.attempt_id}).json() == receipt.json()
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
        assert restored['progress'] == evidence['diagnosis']['progress']
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
        native = request.to_document()['native_context']
        assert native['policy']['allowed_tools'] == ['agent_task_records_read', 'agent_debug_observe']
        assert native['debug_scope']['gateway_investigation'] == investigation['investigation_id']
        assert native['selected_task_source']['attempt_id'] == claim.attempt.attempt_id
        assert all(event['event_seq'] <= investigation['observation']['through']
                   for page in native['selected_task_records'] for event in page['events'])
        assert any(event['event_seq'] == failure_seq
                   for page in native['selected_task_records'] for event in page['events'])
        return SimpleNamespace(status='completed', answer='Failure found')

    executor = SimpleNamespace(identity={'service_id': 'pi-local', 'instance_id': 'pi-test', 'revision': 'test'},
                               capability={'resource_profiles': {'direct_pi': {'revision': 'debug-profile'}}},
                               execute=execute)
    diagnosis = register.diagnose(claim.workspace_name, claim.thread_id, investigation['investigation_id'], executor)
    assert failure_seq in diagnosis['evidence_event_seqs']


def test_debug_probe_retry_reads_the_original_call(monkeypatch):
    from capstone_agent.debug_investigations import InvestigationRegister

    monkeypatch.setenv('CAPSTONE_DEPLOYMENT_STAGE', 'local')
    monkeypatch.setenv('CAPSTONE_DEBUG_COMMANDS', '1')
    service, claim = completed_task()
    binding = {'connection_id': 'recorded', 'instance_id': 'instance-original'}
    monkeypatch.setattr(InvestigationRegister, 'historical_gateway', lambda *_: binding)
    operations = []

    class Executor:
        def debug_observation(self, selected, workspace, investigation_id, operation, query):
            assert selected == binding
            operations.append((operation, query))
            if operation == 'probe':
                raise OSError('response lost after dispatch')
            return {'state': 'observed', 'client_call_id': query['client_call_id']}

    app = create_host_app(_Ledger(), WorkerRegistry(()), operator_token='hosted-secret',
                          allowed_hosts={'localhost'}, allowed_origins={'http://localhost:5173'},
                          thread_open_access=True, thread_service=service, native_artifact_executor=Executor())
    path = f'/api/v1/threads/{claim.thread_id}/debug/investigations'
    with TestClient(app, base_url='http://localhost') as client:
        created = client.post(path, headers={'Idempotency-Key': 'probe-investigation'},
                              json={'objective': '复验', 'attempt_id': claim.attempt.attempt_id}).json()
        url = f"{path}/{created['investigation_id']}/probe"
        headers = {'Idempotency-Key': 'probe-choice'}
        body = {'tool': 'data_gateway_read', 'arguments': {'limit': 1}}
        assert client.post(url, headers=headers, json=body).status_code == 409
        assert client.post(url, headers=headers, json=body).json()['state'] == 'observed'
        assert client.post(url, headers=headers, json={**body, 'arguments': {'limit': 2}}).status_code == 409
        assert [operation for operation, _ in operations] == ['probe', 'read']
        assert operations[0][1]['client_call_id'] == operations[1][1]['client_call_id']
        automatic = {'tool': 'data_gateway_read', 'arguments': {'limit': 1, 'kind': 'grid'}}
        assert client.post(url, json=automatic).status_code == 409
        reordered = {'arguments': {'kind': 'grid', 'limit': 1}, 'tool': 'data_gateway_read'}
        assert client.post(url, json=reordered).json()['state'] == 'observed'
        assert [operation for operation, _ in operations] == ['probe', 'read', 'probe', 'read']
        assert operations[2][1]['client_call_id'] == operations[3][1]['client_call_id']


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
        before = service.snapshot('thr_harness')
        response = client.post(path + '/commands', headers=version, json=run)
        assert response.status_code == 422, response.text
        assert service.snapshot('thr_harness') == before
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
