import pytest
from capstone_agent.artifacts import MemoryObjectStore
from capstone_agent.native_artifact_projection import artifact_object_key
from capstone_agent.product_index_jobs import ProductIndexJobs
from capstone_agent.product_index_service import ProductIndexService
from capstone_agent.thread_products import product_index
from test_thread_postgres import postgres_thread_service, _snapshot
from test_thread_deliveries import native_file


def test_service_runs_retained_product_through_real_database_and_child(postgres_thread_service):
    threads, thread = postgres_thread_service
    threads.create_thread(_snapshot(thread))
    data = b'First paragraph.\n\nSecond paragraph.\n'
    source, _ = native_file(threads, thread, data, name='report.md')
    ref = next(e['ref'] for e in product_index(threads, thread)['products'] if e['ref']['origin']=='native_file')
    class Store(MemoryObjectStore):
        reads = 0
        def get(self, key, limit):
            self.reads += 1
            return super().get(key, limit)
    objects = Store(); objects.put(artifact_object_key(source), data, 'text/markdown')
    jobs = ProductIndexJobs(threads.dsn); jobs.initialize()
    budgets = dict(max_input_bytes=1024, max_blocks=10, max_output_bytes=8192,
        wall_seconds=10, cpu_seconds=5, max_rss_bytes=512*1024*1024, lease_seconds=60, max_attempts=2)
    service = ProductIndexService(threads, objects, jobs, budgets=budgets)
    created = service.request(thread, ref)
    assert created['state']=='queued' and objects.reads==0
    assert service.request(thread, ref)['job_id']==created['job_id']
    assert service.run_once('worker')=='ready'
    restored = ProductIndexService(threads, objects, ProductIndexJobs(threads.dsn), budgets=budgets)
    page = restored.blocks(thread, created['job_id'], offset=0, limit=1)
    assert len(page['blocks'])==1 and page['next_offset']==1
    block = page['blocks'][0]
    selection = {'schema': 'capstone-local-product-selection/1', 'parent_ref': ref,
        'index_ref': page['index_ref'], 'block_id': block['block_id'],
        'content_digest': block['content_digest'], 'purpose': 'historical-context'}
    resolved = restored.resolve_selection(thread, selection)
    assert resolved['content'] == b'First paragraph.\n'
    assert resolved['dependencies'] == []
    assert 'receipt' not in resolved
    from dataclasses import replace
    from capstone_agent.thread_products import freeze_product_selection, checked_selections
    threads.set_product_index_service(restored)
    second_block = restored.blocks(thread, created['job_id'], offset=1, limit=1)['blocks'][0]
    second = {**selection, 'block_id': second_block['block_id'], 'content_digest': second_block['content_digest']}
    selected = [{'ref': ref, 'purpose': 'historical-context', 'local_selection': item}
                for item in (selection, second)]
    snapshot = replace(threads.snapshot(thread), active_model_context=None,
                       minimum_protocol_version=2, active_grid_page_id=None, current_attempt=None)
    frozen, reason = freeze_product_selection(threads, snapshot, {'context_product_refs': selected}, {})
    assert reason is None
    import base64
    assert [base64.b64decode(item['content_base64']) for item in frozen['_materials']] == [b'First paragraph.\n', b'Second paragraph.\n']
    assert len({item['material_id'] for item in frozen['_materials']}) == 2
    assert all('source_artifact' not in item for item in frozen['_materials'])
    assert frozen['_materials'][0]['source_product']['local_selection'] == selection
    professional, reason = freeze_product_selection(threads, threads.snapshot(thread),
        {'context_product_refs': selected}, {})
    assert reason is None
    assert [item['content'] for item in professional['_product_context']] == ['First paragraph.\n', 'Second paragraph.\n']
    unchanged = {'_materials': []}
    rejected, reason = freeze_product_selection(threads, snapshot,
        {'context_product_refs': [{**selected[0], 'local_selection': {**selection, 'index_ref': '0'*64}}]}, unchanged)
    assert reason == 'product_context_unavailable' and rejected == unchanged
    with pytest.raises(ValueError):
        checked_selections([selected[0], selected[0]])
    with pytest.raises(ValueError):
        checked_selections([{**selected[0], 'excerpt': {'max_bytes': 1}}])
    for invalid in ({**selection, 'index_ref': '0'*64},
                    {**selection, 'content_digest': '0'*64}):
        with pytest.raises((ValueError, KeyError)):
            restored.resolve_selection(thread, invalid)
    with pytest.raises(ValueError):
        restored.resolve_selection('other-thread', selection)
    assert restored.blocks(thread, created['job_id'], offset=1, limit=1)['next_offset'] is None
    assert 'receipt' not in restored.status(thread, created['job_id'])
    with pytest.raises(KeyError):
        restored.blocks('other-thread', created['job_id'], offset=0, limit=1)
    with pytest.raises(ValueError):
        restored.blocks(thread, created['job_id'], offset=3, limit=1)

    from fastapi.testclient import TestClient
    from capstone_agent.host_api import create_host_app
    from capstone_agent.ledger import Ledger
    from capstone_agent.session import WorkerRegistry
    from capstone_agent.artifacts import ArtifactService
    from capstone_agent.workspace_scope import WORKSPACE_HEADER
    from pathlib import Path
    ledger = Ledger(threads.dsn); ledger.initialize()
    app = create_host_app(ledger, WorkerRegistry(()), operator_token='test-private-token',
        allowed_hosts={'localhost'}, allowed_origins={'http://localhost'},
        artifacts=ArtifactService(ledger, objects, Path('/tmp/capstone-index-test-unused')),
        thread_service=threads, product_index_service=restored)
    with TestClient(app, base_url='http://localhost') as client:
        path = f'/api/v1/threads/{thread}/product-block-indexes'
        headers = {'Authorization': 'Bearer test-private-token', 'Capstone-Thread-Version': '2'}
        assert client.get(path+'/'+created['job_id']).status_code == 401
        assert client.get(path+'/'+created['job_id'], headers={**headers, WORKSPACE_HEADER: 'other'}).status_code == 404
        assert client.post(path, headers=headers, json={'ref': ref}).status_code == 202
        assert client.get(path+'/'+created['job_id'], headers=headers).json()['state'] == 'ready'
        assert client.get(path+'/'+created['job_id']+'/blocks', headers=headers).status_code == 200
