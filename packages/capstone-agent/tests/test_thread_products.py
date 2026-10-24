"""Common product references retain owning contracts and exact versions."""
from copy import deepcopy

import pytest

from capstone_agent.artifacts import MemoryObjectStore
from capstone_agent.thread_products import product_index, resolve_product
from test_thread_deliveries import native_file, request
from capstone_agent.thread_deliveries import publish_delivery
from test_thread_http_api import _service
from test_enterprise_normal_chat import chat_store, native_executor
from test_thread_postgres import postgres_thread_service
from test_thread_work_execution import command


def test_product_selection_preserves_four_uploaded_inputs():
    from dataclasses import replace
    from capstone_agent.thread_products import freeze_product_selection
    service = _service()
    _, executor = native_file(service, 'thr_demo_39', b'<html>Report</html>', name='report.html')
    executor.capability = native_executor().capability
    service.set_native_executor(executor)
    entry = next(item for item in product_index(service, 'thr_demo_39')['products'] if item['ref']['origin'] == 'native_file')
    snapshot = replace(service.snapshot('thr_demo_39'), active_model_context=None,
        minimum_protocol_version=2, active_grid_page_id=None, current_attempt=None)
    uploaded = [{'size_bytes': 1024 * 1024} for _ in range(4)]
    frozen, reason = freeze_product_selection(service, snapshot,
        {'context_product_refs': [{'ref': entry['ref'], 'purpose': 'historical-context'}]},
        {'_materials': uploaded})
    assert reason is None
    assert frozen['_materials'][:4] == uploaded
    assert frozen['_materials'][4]['file_name'] == 'report.html'


@pytest.mark.parametrize('name,media', [('report.html', 'text/html'), ('chart.svg', 'image/svg+xml'), ('metrics.json', 'application/json')])
def test_generated_text_documents_can_be_selected_without_execution(name, media):
    service = _service()
    source, executor = native_file(service, 'thr_demo_39', b'<text>Saved content</text>', name=name)
    entry = next(item for item in product_index(service, 'thr_demo_39')['products'] if item['ref']['origin'] == 'native_file')
    assert entry['media_type'] == media
    assert entry['capabilities']['select'] is True
    resolved = resolve_product(service, MemoryObjectStore(), 'thr_demo_39', entry['ref'], executor=executor)
    import base64
    assert base64.b64decode(resolved['content_base64']) == b'<text>Saved content</text>'


def test_old_octet_html_product_uses_filename_without_changing_saved_identity():
    service = _service()
    source, executor = native_file(service, 'thr_demo_39', b'<html>Existing report</html>', name='existing.html')
    event = next(event for event in service._events if event.event_type == 'native_artifact_published')
    event.payload['artifact']['media_type'] = 'application/octet-stream'
    entry = next(item for item in product_index(service, 'thr_demo_39')['products'] if item['ref']['origin'] == 'native_file')
    assert entry['media_type'] == 'text/html' and entry['capabilities']['select'] is True
    assert entry['source']['media_type'] == 'application/octet-stream'
    assert entry['ref']['digest'] == source['sha256']
    resolved = resolve_product(service, MemoryObjectStore(), 'thr_demo_39', entry['ref'], executor=executor)
    import base64
    assert base64.b64decode(resolved['content_base64']) == b'<html>Existing report</html>'


def test_native_product_survives_executor_upgrade_then_host_retention_expiry():
    service, objects = _service(), MemoryObjectStore()
    source, executor = native_file(service, 'thr_demo_39', b'<html>Original saved report</html>', name='report.html')
    executor.identity = {**executor.identity, 'config_revision': 'next-image'}
    entry = next(item for item in product_index(service, 'thr_demo_39')['products'] if item['ref']['origin'] == 'native_file')
    first = resolve_product(service, objects, 'thr_demo_39', entry['ref'], executor=executor)
    def expired(*args, **kwargs):
        raise OSError('host retention expired')
    executor.read_artifact = expired
    second = resolve_product(service, objects, 'thr_demo_39', entry['ref'], executor=executor)
    assert first['content_base64'] == second['content_base64']
    assert objects.contents


def test_native_and_delivery_keep_scope_versions_and_provenance():
    service, objects = _service(), MemoryObjectStore()
    source, executor = native_file(service, 'thr_demo_39', b'# Actual report\n', name='report.md')
    receipt = publish_delivery(service, objects, 'thr_demo_39', request(source['attempt_id'],
        format='native-file', source_artifact={'attempt_id': source['attempt_id'], 'artifact_id': source['artifact_id']}),
        native_artifact_executor=executor)
    page = product_index(service, 'thr_demo_39')
    assert {entry['ref']['origin'] for entry in page['products']} == {'native_file', 'task_delivery', 'process_record'}
    file = next(item for item in page['products'] if item['ref']['origin'] == 'native_file')
    delivery = next(item for item in page['products'] if item['ref']['origin'] == 'task_delivery')
    assert file['ref']['revision'] is None and file['ref']['scope'] == 'instruction'
    assert delivery['ref']['revision'] == 1 and delivery['ref']['scope'] == 'task'
    assert delivery['dependencies'] == [file['ref']]
    assert delivery['ref']['work_id'] is None
    resolved = resolve_product(service, objects, 'thr_demo_39', delivery['ref'], executor=executor)
    import base64
    assert base64.b64decode(resolved['content_base64']) == b'# Actual report\n'
    assert resolved['entry']['source']['artifact_id'] == receipt.target['delivery']['artifact_id']
    bad = deepcopy(file['ref']); bad['digest'] = '0' * 64
    with pytest.raises(ValueError):
        resolve_product(service, objects, 'thr_demo_39', bad, executor=executor)
    with pytest.raises(ValueError):
        resolve_product(service, objects, 'other_thread', file['ref'], executor=executor)


def test_paging_does_not_drop_products_from_one_event():
    service = _service()
    native_file(service, 'thr_demo_39', b'# Original\n', name='report.md')
    cursor, products = None, []
    for _ in range(10):
        page = product_index(service, 'thr_demo_39', cursor=cursor, limit=1)
        products += page['products']
        if not page['has_more']:
            assert page['next_cursor'] is None
            break
        assert page['next_cursor'] != cursor
        cursor = page['next_cursor']
    assert len(products) == 2
    assert len({item['ref']['product_id'] for item in products}) == 2


def test_admitted_domain_projection_is_historical_and_not_a_fake_file():
    from test_thread_result_projection import _service as projection_service, _claim_and_projection, RESULT_ONE, EVIDENCE_ONE
    service = projection_service()
    claim, projection = _claim_and_projection(service, 1, RESULT_ONE, EVIDENCE_ONE)
    service.finish_attempt(claim, phase='completed', payload={'answer': 'saved', 'result_projections': [projection],
        'result_refs': [RESULT_ONE], 'evidence_refs': [EVIDENCE_ONE],
        'admission': {'mode': 'authority_backed', 'assurance': 'lineage_verified'}})
    page = product_index(service, claim.thread_id)
    entry = next(item for item in page['products'] if item['ref']['origin'] == 'domain_result')
    assert entry['historical_only'] is True
    assert entry['download_url'] is None
    assert entry['source']['result_ref'] == RESULT_ONE
    result = resolve_product(service, MemoryObjectStore(), claim.thread_id, entry['ref'])
    assert result['content_base64'] is None
    assert result['projection'] == projection
    assert entry['ref']['revision'] is None
    first = product_index(service, claim.thread_id, limit=1)
    second = product_index(service, claim.thread_id, cursor=first['next_cursor'], limit=1)
    assert first['products'][0]['ref']['event_seq'] == second['products'][0]['ref']['event_seq']
    assert first['products'][0]['ref']['product_id'] != second['products'][0]['ref']['product_id']
    assert second['has_more'] is False


def generated_native_file(store, thread_id):
    from hashlib import sha256
    from types import SimpleNamespace
    from capstone_agent.native_artifact_projection import project_native_artifacts
    executor = native_executor()
    store.set_native_executor(executor)
    data = b'# Actual original bytes\n'
    executor.read_artifact = lambda *args, **kwargs: data
    assert store.submit_command(command(store, thread_id, 'send_message', 'source_file', payload={'text': 'Create file'})).status == 'accepted'
    claim = store.claim_attempt('products', 30, 'native')
    task = 'product-task'
    result = SimpleNamespace(to_document=lambda: {'task_id': task, 'parent_attempt_id': claim.attempt.attempt_id,
        'executor_identity': executor.identity, 'status': 'completed', 'artifacts': [{
            'artifact_id': 'file-' + sha256(b'report.md').hexdigest()[:16] + '-' + sha256(data).hexdigest(),
            'task_id': task, 'parent_attempt_id': claim.attempt.attempt_id, 'kind': 'workspace_file',
            'metadata': {'path': 'report.md', 'sha256': sha256(data).hexdigest(), 'size_bytes': len(data)}}]})
    descriptor, = project_native_artifacts(claim, result)
    store.append_runtime_event(claim, event_type='native_artifact_published', payload={'artifact': descriptor})
    store.finish_attempt(claim, phase='completed', payload={'answer': 'Saved file'})
    return data, executor


def test_explicit_cross_work_file_selection_freezes_bytes_and_exact_retry(chat_store):
    import base64
    store, thread_id = chat_store
    data, executor = generated_native_file(store, thread_id)
    ref = next(entry['ref'] for entry in product_index(store, thread_id)['products'] if entry['ref']['origin'] == 'native_file')
    first_work = store.snapshot(thread_id).works[0]
    assert store.submit_command(command(store, thread_id, 'work_message', 'other_work', payload={'text': 'Independent task'})).status == 'accepted'
    second_work = store.snapshot(thread_id).works[1]
    selected = [{'ref': ref, 'purpose': 'historical-context'}]
    send = command(store, thread_id, 'send_message', 'select_product', work_id=second_work['work_id'], revision=second_work['revision'],
        payload={'text': 'Read the exact previous file', 'context_product_refs': selected})
    receipt = store.submit_command(send)
    assert receipt.status == 'accepted'
    def unavailable(*args, **kwargs):
        raise OSError('Source disappeared after admission')
    executor.read_artifact = unavailable
    assert store.submit_command(send) == receipt
    claim = store.claim_attempt('products', 30, 'native')
    assert claim.task_context.binding.work_id != ref['work_id']
    assert claim.submission['context_product_refs'] == selected
    assert len(claim.submission['_materials']) == 1
    material = claim.submission['_materials'][0]
    assert base64.b64decode(material['content_base64']) == data
    assert material['source_product']['ref'] == ref
    assert claim.submission['_materials'][0]['source_artifact']['work_id'] == first_work['work_id']
    assert claim.prior_results == ()
    assert next(work for work in store.snapshot(thread_id).works if work['work_id'] == first_work['work_id']) == first_work


def test_explicit_bad_ref_rejects_atomically_but_unselected_products_do_not_gate(chat_store):
    store, thread_id = chat_store
    data, executor = generated_native_file(store, thread_id)
    page = product_index(store, thread_id)
    ref = next(entry['ref'] for entry in page['products'] if entry['ref']['origin'] == 'native_file')
    before = store.snapshot(thread_id)
    work = before.works[0]
    bad = {**ref, 'digest': '0' * 64}
    result = store.submit_command(command(store, thread_id, 'send_message', 'invalid_ref',
        work_id=work['work_id'], revision=work['revision'], payload={'text': 'Read', 'context_product_refs': [{'ref': bad, 'purpose': 'historical-context'}]}))
    assert result.rejection == 'product_context_unavailable'
    assert store.snapshot(thread_id) == before
    executor.read_artifact = lambda *args, **kwargs: b'wrong'
    result = store.submit_command(command(store, thread_id, 'send_message', 'ordinary_no_refs',
        work_id=work['work_id'], revision=work['revision'], payload={'text': 'Explain a general concept', 'material_refs': []}))
    assert result.status == 'accepted'


def test_native_selected_grid_projection_remains_historical_not_current_evidence():
    from dataclasses import replace
    import base64
    import json
    from test_thread_result_projection import _service as projection_service, _claim_and_projection, RESULT_ONE, EVIDENCE_ONE
    store = projection_service()
    claim, projection = _claim_and_projection(store, 1, RESULT_ONE, EVIDENCE_ONE)
    store.finish_attempt(claim, phase='completed', payload={'answer': 'saved', 'result_projections': [projection],
        'result_refs': [RESULT_ONE], 'evidence_refs': [EVIDENCE_ONE],
        'admission': {'mode': 'authority_backed', 'assurance': 'lineage_verified'}})
    ref = next(entry['ref'] for entry in product_index(store, claim.thread_id)['products'] if entry['ref']['origin'] == 'domain_result')
    # Fixture switches the Thread to its model-free execution boundary while
    # retaining the actual completed professional ledger, not fake Authority data.
    store._snapshot = replace(store._snapshot, active_model_context=None, active_grid_page_id=None, minimum_protocol_version=2)
    store.set_native_executor(native_executor())
    selected = [{'ref': ref, 'purpose': 'historical-context'}]
    receipt = store.submit_command(command(store, claim.thread_id, 'send_message', 'historical_grid',
        payload={'text': 'Explain the saved grid result historically', 'context_product_refs': selected}))
    assert receipt.status == 'accepted'
    native = store.claim_attempt('products', 30, 'native')
    assert native.model_context is None
    assert native.prior_results == ()
    assert native.submission['context_product_refs'] == selected
    frozen = native.submission['_materials'][0]
    assert json.loads(base64.b64decode(frozen['content_base64'])) == projection
    assert frozen['source_product']['historical_only'] is True


def test_failed_record_visible_without_inventing_file_or_selection():
    from test_thread_deliveries import completed
    store = _service()
    completed(store, phase='failed')
    entry, = product_index(store, 'thr_demo_39')['products']
    assert entry['ref']['origin'] == 'process_record'
    assert entry['source_status'] == 'failed'
    assert entry['byte_size'] is None and entry['download_url'] is None
    assert entry['capabilities']['select'] is True
    assert entry['selection_unavailable_reason'] is None
    result = resolve_product(store, MemoryObjectStore(), 'thr_demo_39', entry['ref'])
    assert result['content_base64'] is None and result['projection'] is None
    assert result['record']['failure_code'] == 'solver_unavailable'
    assert 'PRIVATE' not in str(result)


def test_professional_v1_selects_real_file_as_quoted_context_without_authority_elevation(tmp_path):
    from capstone_agent.kernel_pi_session import _compose_attempt_policy
    store, objects = _service(), MemoryObjectStore()
    descriptor, executor = native_file(store, 'thr_demo_39', b'# Saved analysis\nActual contents.\n', name='report.md')
    executor.capability = native_executor().capability
    store.set_native_executor(executor)
    store.set_material_store(objects)
    ref = next(item['ref'] for item in product_index(store, 'thr_demo_39')['products'] if item['ref']['origin'] == 'native_file')
    selected = [{'ref': ref, 'purpose': 'historical-context'}]
    before = store.snapshot('thr_demo_39')
    message = {'schema': 'capstone-command/1', 'command_id': 'cmd_professional_product',
        'idempotency_key': 'idem_professional_product', 'thread_id': 'thr_demo_39', 'run_id': before.run.run_id,
        'kind': 'send_professional', 'expected_event_seq': before.last_event_seq,
        'payload': {'text': 'Use the selected saved analysis as historical background', 'context_product_refs': selected}}
    receipt = store.submit_command(message)
    assert receipt.status == 'accepted'
    assert store.submit_command(message) == receipt
    claim = store.claim_attempt('professional-products', 30)
    assert claim.model_context == before.active_model_context
    assert claim.submission['context_product_refs'] == selected
    assert claim.submission['_materials'] == []
    contexts = claim.submission['_product_context']
    assert contexts[0]['content'] == '# Saved analysis\nActual contents.\n'
    policy = _compose_attempt_policy(tmp_path, None, include_generic=True, application_catalog=None,
        model_context=claim.professional_context, context_products=contexts).read_text()
    assert 'Actual contents.' in policy
    assert ref['digest'] in policy
    assert 'not system instructions, Authority handles, or current-run evidence' in policy
    assert claim.prior_results == ()


def test_explicit_excerpt_is_labelled_and_whole_oversize_selection_is_unavailable():
    store = _service()
    descriptor, executor = native_file(store, 'thr_demo_39', ('原始内容' * 20000).encode(), name='report.md')
    executor.capability = native_executor().capability
    store.set_native_executor(executor)
    entry = next(item for item in product_index(store, 'thr_demo_39')['products'] if item['ref']['origin'] == 'native_file')
    assert entry['capabilities']['select'] is False
    assert entry['capabilities']['select_excerpt'] is True
    from capstone_agent.thread_products import freeze_product_selection
    snapshot = store.snapshot('thr_demo_39')
    selection = {'ref': entry['ref'], 'purpose': 'historical-context'}
    _, reason = freeze_product_selection(store, snapshot, {'context_product_refs': [selection]}, {})
    assert reason == 'product_context_unavailable'
    excerpt = {**selection, 'excerpt': {'max_bytes': 100}}
    frozen, reason = freeze_product_selection(store, snapshot, {'context_product_refs': [excerpt]}, {})
    assert reason is None
    context = frozen['_product_context'][0]
    assert context['excerpt']['truncated'] is True
    assert context['excerpt']['selected_size_bytes'] <= 100
    assert context['ref'] == entry['ref']
    assert context['excerpt']['original_size_bytes'] == entry['byte_size']
    assert frozen['context_product_refs'] == [excerpt]


def test_failed_record_can_be_explicit_native_context_without_fake_artifact():
    from dataclasses import replace
    import base64
    import json
    from test_thread_deliveries import completed
    store = _service()
    completed(store, phase='failed')
    ref = product_index(store, 'thr_demo_39')['products'][0]['ref']
    store._snapshot = replace(store._snapshot, active_model_context=None, active_grid_page_id=None, minimum_protocol_version=2)
    store.set_native_executor(native_executor())
    receipt = store.submit_command(command(store, 'thr_demo_39', 'send_message', 'failure_context',
        payload={'text': 'Explain the saved failure', 'context_product_refs': [{'ref': ref, 'purpose': 'historical-context'}]}))
    assert receipt.status == 'accepted'
    claim = store.claim_attempt('products', 30, 'native')
    material, = claim.submission['_materials']
    record = json.loads(base64.b64decode(material['content_base64']))
    assert record['status'] == 'failed' and record['failure_code'] == 'solver_unavailable'
    assert material['source_product']['ref']['origin'] == 'process_record'
    assert 'source_artifact' not in material


def test_professional_delegated_file_pipeline_is_published_and_selected_for_next_turn():
    from hashlib import sha256
    from capstone_agent.pi_delegation import PiTaskResult
    from capstone_agent.thread_worker import run_pending_attempt
    from test_delegated_runtime import Executor, Recognizer, factory, goal
    store = _service()
    data = b'# Report generated by actual delegated pipeline\n'
    class FileExecutor(Executor):
        def execute(self, request, control, on_event):
            self.requests.append(request)
            artifact = {'artifact_id': 'file-' + sha256(b'report.md').hexdigest()[:16] + '-' + sha256(data).hexdigest(),
                'task_id': request.task_id, 'parent_attempt_id': request.parent_attempt_id, 'kind': 'workspace_file',
                'metadata': {'path': 'report.md', 'sha256': sha256(data).hexdigest(), 'size_bytes': len(data)}}
            return PiTaskResult(request.task_id, request.parent_attempt_id, self.identity, 'completed',
                'Actual file generated', (), (artifact,), {})
        def read_artifact(self, *args, **kwargs):
            return data
    executor = FileExecutor()
    executor.capability = native_executor().capability
    def send(name, refs=None):
        snapshot = store.snapshot('thr_demo_39')
        return store.submit_command({'schema': 'capstone-command/1', 'command_id': 'cmd_' + name,
            'idempotency_key': 'idem_' + name, 'thread_id': snapshot.thread_id, 'run_id': snapshot.run.run_id,
            'kind': 'send_auto', 'expected_event_seq': snapshot.last_event_seq,
            'payload': {'text': 'Create report' if refs is None else 'Explain saved report',
                **({} if refs is None else {'context_product_refs': refs})}})
    runtime = factory(executor, Recognizer([goal('report')]))
    assert send('first').status == 'accepted'
    assert run_pending_attempt(store, runtime, worker_id='products').status == 'completed'
    entry = next(item for item in product_index(store, 'thr_demo_39')['products'] if item['ref']['origin'] == 'native_file')
    assert entry['ref']['work_id'] is None
    assert store.snapshot('thr_demo_39').active_model_context is not None
    store.set_native_executor(executor)
    selected = [{'ref': entry['ref'], 'purpose': 'historical-context'}]
    assert send('followup', selected).status == 'accepted'
    result = run_pending_attempt(store, runtime, worker_id='products')
    assert result.status == 'completed'
    assert any(data.decode() in item['content'] for item in executor.requests[-1].messages)
    assert result.result_refs == result.evidence_refs == ()


def test_product_routes_keep_private_auth_and_existing_process_endpoint():
    from fastapi.testclient import TestClient
    from test_thread_deliveries import delivery_app
    from test_thread_http_api import _auth
    store, objects = _service(), MemoryObjectStore()
    descriptor, executor = native_file(store, 'thr_demo_39', b'# Real\n', name='report.md')
    with TestClient(delivery_app(store, objects, executor), base_url='http://localhost') as client:
        url = '/api/v1/threads/thr_demo_39/product-index'
        assert client.get(url).status_code == 401
        response = client.get(url, headers=_auth())
        assert response.status_code == 200
        ref = next(item['ref'] for item in response.json()['products'] if item['ref']['origin'] == 'native_file')
        assert client.post(url + '/resolve', json={'ref': ref}).status_code == 401
        resolved = client.post(url + '/resolve', json={'ref': ref}, headers=_auth())
        assert resolved.status_code == 200
        assert resolved.json()['entry']['ref'] == ref
        assert client.get('/api/v1/threads/thr_demo_39/products', headers=_auth()).json()['schema'] == 'capstone-process-products/1'
        assert client.get(url + '?cursor=not-a-cursor', headers=_auth()).status_code == 422


def test_work_filter_is_applied_before_paging(chat_store):
    store, thread_id = chat_store
    generated_native_file(store, thread_id)
    work = store.snapshot(thread_id).works[0]
    assert product_index(store, thread_id, work_id=work['work_id'])['products']
    assert product_index(store, thread_id, work_id='work_not_present')['products'] == []
    assert product_index(store, thread_id, work_id='legacy')['products'] == []
    first = product_index(store, thread_id, work_id=work['work_id'], limit=1)
    with pytest.raises(ValueError):
        product_index(store, thread_id, work_id='legacy', cursor=first['next_cursor'])


def test_postgres_professional_result_selection_needs_no_native_executor(postgres_thread_service):
    from test_thread_work_execution import professional_snapshot
    from test_result_projection import valid_projection
    store, thread_id = postgres_thread_service
    store.create_thread(professional_snapshot(thread_id))
    def send(name, refs=None):
        snapshot = store.snapshot(thread_id)
        return store.submit_command({'schema': 'capstone-command/1', 'command_id': 'cmd_' + name,
            'idempotency_key': 'idem_' + name, 'thread_id': thread_id, 'run_id': snapshot.run.run_id,
            'kind': 'send_professional', 'expected_event_seq': snapshot.last_event_seq,
            'payload': {'text': 'Historical analysis', **({} if refs is None else {'context_product_refs': refs})}})
    assert send('calculate').status == 'accepted'
    claim = store.claim_attempt('products', 30)
    projection = {**valid_projection(), 'thread_id': thread_id, 'run_id': claim.run_id,
        'turn_id': claim.attempt.turn_id, 'attempt_id': claim.attempt.attempt_id,
        'model_context_id': claim.model_context.id, 'model_id': claim.model_context.model_id,
        'model_revision': claim.model_context.model_revision, 'tables': [], 'element_refs': [], 'overlay': None}
    store.finish_attempt(claim, phase='completed', payload={'answer': 'saved', 'result_projections': [projection],
        'result_refs': [projection['result_ref']], 'evidence_refs': projection['evidence_refs'],
        'admission': {'mode': 'authority_backed', 'assurance': 'lineage_verified'}})
    ref = next(entry['ref'] for entry in product_index(store, thread_id)['products'] if entry['ref']['origin'] == 'domain_result')
    assert send('historical', [{'ref': ref, 'purpose': 'historical-context'}]).status == 'accepted'
    next_claim = store.claim_attempt('products', 30)
    assert next_claim.submission['_product_context'][0]['ref'] == ref
    assert next_claim.model_context == claim.model_context
    assert next_claim.submission['_product_context'][0]['historical_only'] is True


def test_postgres_index_reuses_one_read_connection_for_the_whole_page(postgres_thread_service, monkeypatch):
    from test_thread_postgres import _snapshot
    store, thread_id = postgres_thread_service
    store.create_thread(_snapshot(thread_id))
    for index in range(5):
        native_file(store, thread_id, f'File {index}'.encode(), name='report.md')
    connect = store._connect
    calls = []
    def counted_connect():
        calls.append(True)
        return connect()
    monkeypatch.setattr(store, '_connect', counted_connect)
    page = product_index(store, thread_id, limit=32)
    assert len(page['products']) == 10
    # Existing public snapshot recovery/title reads plus one page transaction;
    # this count must not grow with the number of terminal or artifact entries.
    assert len(calls) <= 5
