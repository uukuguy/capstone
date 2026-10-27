"""Selected UTF-8 session materials reach the actual native task input."""
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from capstone_agent.artifacts import MemoryObjectStore
from capstone_agent.thread_materials import upload_material, remove_material, material_page, register_material_routes
from test_enterprise_normal_chat import chat_store, native_executor
from test_thread_postgres import postgres_thread_service
from test_thread_work_execution import command


def test_multi_megabyte_csvs_reach_native_context_without_truncation(chat_store):
    import base64
    from capstone_agent.native_task_context import native_context_for
    store, thread_id = chat_store
    objects = MemoryObjectStore()
    store.set_native_executor(native_executor())
    store.set_material_store(objects)
    data = b'time,value\n' + b'2026-08-01T00:00,42\n' * 100000
    for index in range(3):
        upload_material(store, objects, thread_id, f'data-{index}.csv', data)
    receipt = store.submit_command(command(store, thread_id, 'send_message', 'large_materials',
        payload={'text': 'Analyze these time series'}))
    assert receipt.status == 'accepted'
    claim = store.claim_attempt('large_materials', 30, 'native')
    context = native_context_for(claim, claim.submission['_native_execution'])
    assert len(context['materials']) == 3
    assert all(base64.b64decode(item['content_base64']) == data for item in context['materials'])


def test_material_total_budget_still_rejects_before_persistence(chat_store):
    from capstone_agent.application_capacity import limits
    store, thread_id = chat_store
    objects = MemoryObjectStore()
    data = b'x' * (limits.inline_material_bytes // 2 + 1)
    upload_material(store, objects, thread_id, 'first.csv', data)
    before = dict(objects.contents)
    with pytest.raises(ValueError, match='capacity_exceeded'):
        upload_material(store, objects, thread_id, 'second.csv', data)
    assert objects.contents == before
    assert len(material_page(store, thread_id)['materials']) == 1


def test_missing_durable_adoption_uses_real_store_backend_without_memory_attributes(chat_store):
    from capstone_agent.thread_materials import _adopted_file_bytes
    store, thread_id = chat_store
    with pytest.raises(OSError, match='no verified durable adoption'):
        _adopted_file_bytes(store, store.snapshot(thread_id),
            {'attempt_id': 'attempt_missing', 'artifact_id': 'file_missing'}, None, objects=MemoryObjectStore())


@pytest.mark.parametrize('phase', ['failed', 'cancelled', 'completed'])
@pytest.mark.parametrize('large_automatic', [False, True])
def test_terminal_work_files_remain_available_beyond_inline_material_slots(chat_store, phase, large_automatic, monkeypatch):
    from hashlib import sha256
    from types import SimpleNamespace
    from capstone_agent.native_artifact_projection import project_native_artifacts
    from capstone_agent.native_task_context import native_context_for
    store, thread_id = chat_store
    objects, executor = MemoryObjectStore(), native_executor()
    store.set_native_executor(executor)
    store.set_material_store(objects)
    assert store.submit_command(command(store, thread_id, 'send_message', 'partial_files',
        payload={'text': 'Analyze the sources'})).status == 'accepted'
    claim = store.claim_attempt('materials', 30, 'native')
    task_id = 'partial-files-task'
    from dataclasses import replace
    from capstone_agent import application_capacity
    if large_automatic:
        monkeypatch.setattr(application_capacity, '_current', replace(application_capacity.current_capacity(), mode='debug'))
    data = b'x,y\n1,2\n' if not large_automatic else b'1,2\n' * (application_capacity.limits.inline_material_bytes // 4 + 1)
    files = [('metrics.csv', data)] + [(f'chart-{i}.png', b'PNG' + bytes([i])) for i in range(6)]
    by_id = {}
    entries = []
    for name, data in files:
        identity = 'file-' + sha256(name.encode()).hexdigest()[:16] + '-' + sha256(data).hexdigest()
        by_id[identity] = data
        entries.append({'artifact_id': identity, 'task_id': task_id,
            'parent_attempt_id': claim.attempt.attempt_id, 'kind': 'workspace_file',
            'metadata': {'path': name, 'sha256': sha256(data).hexdigest(), 'size_bytes': len(data)}})
    executor.read_artifact = lambda task, identity, **kwargs: by_id[identity]
    result = SimpleNamespace(to_document=lambda: {'task_id': task_id, 'parent_attempt_id': claim.attempt.attempt_id,
        'executor_identity': executor.identity, 'status': phase, 'artifacts': entries})
    for source in project_native_artifacts(claim, result):
        store.append_runtime_event(claim, event_type='native_artifact_published', payload={'artifact': source})
    store.finish_attempt(claim, phase=phase, payload={'error_code': 'fixture_interrupted'} if phase != 'completed' else {'answer': 'Files saved'})
    work = store.snapshot(thread_id).works[0]
    assert store.submit_command(command(store, thread_id, 'send_message', 'resume_partial',
        work_id=work['work_id'], revision=work['revision'],
        payload={'text': 'Please finish the report', **({} if large_automatic else {'material_refs': []})})).status == 'accepted'
    resumed = store.claim_attempt('materials', 30, 'native')
    assert resumed.submission['_materials'] == []
    assert len(resumed.submission['_continuation_artifacts']) == 7
    context = native_context_for(resumed, resumed.submission['_native_execution'])
    assert {item['file_name'] for item in context['resource_manifests']} == {name for name, _ in files}
    assert len(context['resource_origins']) == 7
    assert {item['source_status'] for item in context['resource_origins']} == {phase}
    assert all('content_base64' not in item for item in context['resource_manifests'])
    from capstone_agent.continuation_resources import resource_reader_for
    reader = resource_reader_for(store, resumed)
    expected = dict(files)
    for resource in context['resource_manifests']:
        assert b''.join(reader(resource)) == expected[resource['file_name']]
    with pytest.raises(ValueError, match='not admitted'):
        list(reader({**context['resource_manifests'][0], 'sha256': '0' * 64}))
    from dataclasses import replace
    foreign = [{**dict(item), 'work_id': 'work_other'} for item in resumed.submission['_continuation_artifacts']]
    foreign_reader = resource_reader_for(store, replace(resumed,
        submission={**resumed.submission, '_continuation_artifacts': foreign}))
    with pytest.raises(ValueError, match='outside this Work'):
        list(foreign_reader(context['resource_manifests'][0]))


def test_continuation_reuses_latest_file_versions_across_terminal_attempts(chat_store):
    from hashlib import sha256
    from types import SimpleNamespace
    from capstone_agent.native_artifact_projection import project_native_artifacts
    from capstone_agent.continuation_resources import resource_reader_for
    store, thread_id = chat_store
    executor = native_executor()
    store.set_native_executor(executor)
    store.set_material_store(MemoryObjectStore())
    saved = {}
    executor.read_artifact = lambda task, identity, **kwargs: saved[identity]
    work = None
    for index, files in enumerate([
        [('chart.png', b'old-chart'), ('metrics.csv', b'old-metrics')],
        [('analysis.py', b'print(42)'), ('metrics.csv', b'new-metrics')],
    ]):
        arguments = {} if work is None else {'work_id': work['work_id'], 'revision': work['revision']}
        assert store.submit_command(command(store, thread_id, 'send_message', f'round_{index}',
            payload={'text': 'Continue', 'material_refs': []}, **arguments)).status == 'accepted'
        claim = store.claim_attempt('materials', 30, 'native')
        entries = []
        for name, data in files:
            identity = 'file-' + sha256(name.encode()).hexdigest()[:16] + '-' + sha256(data).hexdigest()
            saved[identity] = data
            entries.append({'artifact_id': identity, 'task_id': f'task-round-{index}',
                'parent_attempt_id': claim.attempt.attempt_id, 'kind': 'workspace_file',
                'metadata': {'path': name, 'sha256': sha256(data).hexdigest(), 'size_bytes': len(data)}})
        result = SimpleNamespace(to_document=lambda: {'task_id': f'task-round-{index}',
            'parent_attempt_id': claim.attempt.attempt_id, 'executor_identity': executor.identity,
            'status': 'failed', 'artifacts': entries})
        for source in project_native_artifacts(claim, result):
            store.append_runtime_event(claim, event_type='native_artifact_published', payload={'artifact': source})
        store.finish_attempt(claim, phase='failed', payload={'error_code': 'fixture_interrupted'})
        work = store.snapshot(thread_id).works[0]
    assert store.submit_command(command(store, thread_id, 'send_message', 'finish_all',
        work_id=work['work_id'], revision=work['revision'],
        payload={'text': 'Finish the report', 'material_refs': []})).status == 'accepted'
    resumed = store.claim_attempt('materials', 30, 'native')
    resources = resumed.submission['_resource_manifests']
    reader = resource_reader_for(store, resumed)
    assert {item['file_name']: b''.join(reader(item)) for item in resources} == {
        'chart.png': b'old-chart', 'metrics.csv': b'new-metrics', 'analysis.py': b'print(42)'}


@pytest.mark.parametrize('name,media', [('report.html', 'text/html'), ('chart.svg', 'image/svg+xml'), ('metrics.json', 'application/json')])
def test_utf8_generated_document_is_frozen_as_readonly_material(chat_store, name, media):
    store, thread_id = chat_store
    objects = MemoryObjectStore()
    store.set_native_executor(native_executor())
    store.set_material_store(objects)
    item = upload_material(store, objects, thread_id, name, b'<text>Actual saved bytes</text>')
    assert item['media_type'] == media
    receipt = store.submit_command(command(store, thread_id, 'send_message', 'text_document', payload={'text': 'Read this document'}))
    assert receipt.status == 'accepted'
    claim = store.claim_attempt('documents', 30, 'native')
    import base64
    assert base64.b64decode(claim.submission['_materials'][0]['content_base64']) == b'<text>Actual saved bytes</text>'
    from capstone_agent.native_task_context import native_context_for
    context = native_context_for(claim, claim.submission['_native_execution'])
    assert context['materials'] == list(claim.submission['_materials'])


def test_material_is_persistent_default_input_and_removal_preserves_frozen_claim(chat_store):
    store, thread_id = chat_store
    objects = MemoryObjectStore()
    store.set_native_executor(native_executor())
    store.set_material_store(objects)
    material = upload_material(store, objects, thread_id, 'facts.csv', b'item,value\nA,42\n')
    assert 'content' not in material
    assert upload_material(store, objects, thread_id, 'facts.csv', b'item,value\nA,42\n') == material
    assert store.input_catalog(thread_id)['materials'][0]['material_id'] == material['material_id']
    receipt = store.submit_command(command(store, thread_id, 'send_message', 'material_send', payload={'text': 'Read the uploaded CSV'}))
    assert receipt.status == 'accepted'
    claim = store.claim_attempt('materials', 30, 'native')
    assert claim is not None
    accepted = claim.submission['_materials']
    assert accepted[0]['material_id'] == material['material_id']
    remove_material(store, thread_id, material['material_id'])
    assert material_page(store, thread_id)['materials'] == []
    assert claim.submission['_materials'] == accepted
    store.finish_attempt(claim, phase='failed', payload={'error_code': 'fixture_done'})
    work = store.snapshot(thread_id).works[0]
    assert store.submit_command(command(store, thread_id, 'send_message', 'material_next',
        work_id=work['work_id'], revision=work['revision'], payload={'text': 'Continue'})).status == 'accepted'
    next_claim = store.claim_attempt('materials', 30, 'native')
    assert next_claim.submission['_materials'] == []


@pytest.mark.parametrize('filename,data', [('report.pdf', b'not pdf'), ('bad.txt', b'\xff'), ('../secret.txt', b'text')])
def test_unsupported_material_never_enters_thread_or_store(chat_store, filename, data):
    store, thread_id = chat_store
    objects = MemoryObjectStore()
    with pytest.raises(ValueError):
        upload_material(store, objects, thread_id, filename, data)
    assert objects.contents == {}
    assert material_page(store, thread_id)['materials'] == []


def test_private_http_upload_list_and_remove_use_same_thread_objects(chat_store):
    store, thread_id = chat_store
    objects = MemoryObjectStore()
    app = FastAPI()
    def authorize(request):
        if request.headers.get('authorization') != 'Bearer operator':
            raise HTTPException(401)
    register_material_routes(app, service=store, objects=objects, authorize=authorize)
    client = TestClient(app)
    url = f'/api/v1/threads/{thread_id}/materials'
    assert client.post(url + '?filename=notes.txt', content=b'Private facts').status_code == 401
    headers = {'authorization': 'Bearer operator'}
    response = client.post(url + '?filename=notes.txt', content=b'Private facts', headers=headers)
    assert response.status_code == 201
    item = response.json()
    assert client.get(url, headers=headers).json()['materials'] == [item]
    assert client.post(url + '?filename=scan.pdf', content=b'PDF', headers=headers).status_code == 422
    assert client.delete(url + '/' + item['material_id'], headers=headers).status_code == 200
    assert client.get(url, headers=headers).json()['materials'] == []


def test_foreign_material_ref_rejects_before_work_or_pending_selection_changes(chat_store):
    store, thread_id = chat_store
    store.set_native_executor(native_executor())
    before = store.snapshot(thread_id)
    receipt = store.submit_command(command(store, thread_id, 'send_message', 'foreign_material',
        payload={'text': 'Read', 'material_refs': ['material_' + 'f' * 32]}))
    assert receipt.status == 'rejected'
    assert receipt.rejection == 'material_unavailable'
    assert store.snapshot(thread_id).works == before.works
    assert store.snapshot(thread_id).current_attempt is None


@pytest.mark.parametrize('corrupt', [False, True])
def test_adopted_prior_file_survives_pi_expiry_without_trusting_corrupt_copy(chat_store, corrupt):
    from hashlib import sha256
    from types import SimpleNamespace
    import base64
    from capstone_agent.native_artifact_projection import project_native_artifacts
    from capstone_agent.thread_deliveries import publish_delivery
    from test_thread_deliveries import request
    store, thread_id = chat_store
    objects = MemoryObjectStore()
    executor = native_executor()
    store.set_native_executor(executor)
    store.set_material_store(objects)
    data = b'# Original private report\n\nUnique original content.\n'
    executor.read_artifact = lambda *args, **kwargs: data
    assert store.submit_command(command(store, thread_id, 'send_message', 'prior_file', payload={'text': 'Create a report'})).status == 'accepted'
    claim = store.claim_attempt('materials', 30, 'native')
    task_id = 'prior-file-task'
    result = SimpleNamespace(to_document=lambda: {'task_id': task_id,
        'parent_attempt_id': claim.attempt.attempt_id, 'executor_identity': executor.identity,
        'status': 'completed', 'artifacts': [{'artifact_id': 'file-' + sha256(b'review.md').hexdigest()[:16] + '-' + sha256(data).hexdigest(),
            'task_id': task_id, 'parent_attempt_id': claim.attempt.attempt_id, 'kind': 'workspace_file',
            'metadata': {'path': 'review.md', 'sha256': sha256(data).hexdigest(), 'size_bytes': len(data)}}]})
    source, = project_native_artifacts(claim, result)
    store.append_runtime_event(claim, event_type='native_artifact_published', payload={'artifact': source})
    store.finish_attempt(claim, phase='completed', payload={'answer': 'Report saved'})
    work = store.snapshot(thread_id).works[0]
    adopted = publish_delivery(store, objects, thread_id, request(claim.attempt.attempt_id,
        work_id=work['work_id'], format='native-file', source_artifact={'attempt_id': claim.attempt.attempt_id,
        'artifact_id': source['artifact_id']}), native_artifact_executor=executor)
    assert adopted.status == 'accepted'
    # Exercise the legacy adoption fallback without a separate durable process
    # copy. A valid process copy can legitimately survive a damaged delivery.
    for key in list(objects.contents):
        if key.startswith('native-process-artifacts/'):
            del objects.contents[key]
    if corrupt:
        key = next(key for key in objects.contents if key.startswith('thread-deliveries/'))
        objects.contents[key] = b'corrupted'
    def expired(*args, **kwargs):
        raise OSError('Pi retention expired')
    executor.read_artifact = expired
    assert store.submit_command(command(store, thread_id, 'send_message', 'revise_file',
        work_id=work['work_id'], revision=work['revision'], payload={'text': 'Read the prior report and append a section'})).status == 'accepted'
    next_claim = store.claim_attempt('materials', 30, 'native')
    materials = next_claim.submission['_materials']
    if corrupt:
        assert materials == []
        assert next_claim.submission['_material_notices']
    else:
        assert len(materials) == 1
        assert base64.b64decode(materials[0]['content_base64']) == data
        assert materials[0]['source_artifact'] == source
        assert next_claim.submission['_material_notices'] == []
