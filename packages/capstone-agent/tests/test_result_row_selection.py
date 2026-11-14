from dataclasses import replace
import pytest
from capstone_agent.artifacts import MemoryObjectStore
from capstone_agent.result_projection import ResultTablePagination
from capstone_agent.result_table_store import ResultTableStore
from capstone_agent.result_row_selection import prepare_selection, selected_document, checked_row_selection
from test_result_table_store import projection, pages


def test_exact_cross_page_null_and_unit_selection():
    store = ResultTableStore(MemoryObjectStore())
    parent = projection()
    manifest = store.publish(parent, 'res_line', pages())
    parent = replace(parent, tables=(replace(parent.tables[0], pagination=ResultTablePagination(manifest, 133, 128)),))
    ref = {'origin': 'domain_result', 'digest': 'a'*64}
    selection = prepare_selection(parent, ref, 'res_line', ['row_132','row_0'], ['value'], store)
    assert selection['row_ids'] == ['row_0','row_132']
    data = selected_document(parent, selection, store)
    assert data['columns'][0]['unit'] == '%'
    assert data['rows'][1]['cells'] == {'value': None}
    with pytest.raises(ValueError):
        selected_document(parent, {**selection, 'digest': 'f'*64}, store)
    with pytest.raises(ValueError):
        prepare_selection(parent, ref, 'res_line', ['row_0','row_0'], ['value'], store)
    with pytest.raises(ValueError):
        prepare_selection(parent, ref, 'res_line', ['missing'], ['value'], store)


def test_checked_selection_supports_distinct_rows_and_rejects_mixed_modes():
    from capstone_agent.thread_products import checked_selections
    ref = {'schema':'capstone-product-ref/1','thread_id':'thr_one','product_id':'result_one','origin':'domain_result','scope':'task','event_seq':1,'revision':None,'digest':'a'*64,'work_id':None,'attempt_id':'attempt_one','producer_attempt_id':'attempt_one'}
    p = replace(projection(),tables=(replace(projection().tables[0],rows=()),))
    # A syntactically exact host selection is distinct from its full parent.
    selection = {'schema':'capstone-result-row-selection/1','parent_ref':ref,'table_id':'res_line','table_version':'b'*64,'row_ids':['row_1'],'column_ids':['value'],'digest':'c'*64}
    item = {'ref':ref,'purpose':'historical-context','row_selection':selection}
    assert checked_selections([item, {'ref':ref,'purpose':'historical-context'}])[0] == item
    with pytest.raises(ValueError):
        checked_selections([{**item,'excerpt':{'max_bytes':1}}])

from test_thread_postgres import postgres_thread_service


def test_postgres_rows_freeze_retry_scope_and_atomic_rejection(postgres_thread_service,monkeypatch):
    import json
    from capstone_agent.thread_products import product_index,resolve_row_request
    from capstone_agent.thread_service import PostgresThreadService
    from test_thread_work_execution import professional_snapshot
    from test_result_projection import valid_projection
    store,thread_id=postgres_thread_service
    store._material_objects=MemoryObjectStore()
    store.create_thread(professional_snapshot(thread_id))
    def command(name,refs=None):
        snapshot=store.snapshot(thread_id)
        return {'schema':'capstone-command/1','command_id':'cmd_'+name,'idempotency_key':'idem_'+name,
            'thread_id':thread_id,'run_id':snapshot.run.run_id,'kind':'send_professional',
            'expected_event_seq':snapshot.last_event_seq,'payload':{'text':'Analyze historical rows',
                **({'context_product_refs':refs} if refs is not None else {})}}
    assert store.submit_command(command('source')).status=='accepted'
    claim=store.claim_attempt('rows',30)
    table=list(pages())[1]['table']
    document={**valid_projection(),'thread_id':thread_id,'run_id':claim.run_id,
        'turn_id':claim.attempt.turn_id,'attempt_id':claim.attempt.attempt_id,
        'model_context_id':claim.model_context.id,'model_id':claim.model_context.model_id,
        'model_revision':claim.model_context.model_revision,'tables':[table],'element_refs':[],'overlay':None}
    store.finish_attempt(claim,phase='completed',payload={'answer':'saved','result_projections':[document],
        'result_refs':[document['result_ref']],'evidence_refs':document['evidence_refs'],
        'admission':{'mode':'authority_backed','assurance':'lineage_verified'}})
    ref=next(e['ref'] for e in product_index(store,thread_id)['products'] if e['ref']['origin']=='domain_result')
    selection=resolve_row_request(store,store._material_objects,thread_id,
        {'ref':ref,'table_id':'res_line','row_ids':['row_132','row_128'],'column_ids':['value']})
    page=resolve_row_request(store,store._material_objects,thread_id,
        {'ref':ref,'table_id':'res_line','offset':2,'limit':2},page=True)
    assert page['table']['rows'][0]['row_id']=='row_130'
    assert any(b'capstone-result-table-inline-page/1' in v for v in store._material_objects.contents.values())
    before=store.snapshot(thread_id)
    for name,bad in [('digest',{**selection,'digest':'f'*64}),('thread',{**selection,'parent_ref':{**ref,'thread_id':'thr_forged'}}),
                     ('row',{**selection,'row_ids':['row_forged']}),('column',{**selection,'column_ids':['forged']})]:
        receipt=store.submit_command(command('bad_'+name,[{'ref':ref,'purpose':'historical-context','row_selection':bad}]))
        assert receipt.status=='rejected'
        assert store.snapshot(thread_id)==before
    send=command('selected',[{'ref':ref,'purpose':'historical-context','row_selection':selection}])
    receipt=store.submit_command(send)
    assert receipt.status=='accepted'
    reopened=PostgresThreadService(store.dsn)
    import capstone_agent.thread_products as products
    def unavailable(*args,**kwargs):
        raise OSError('source disappeared')
    monkeypatch.setattr(products,'resolve_product',unavailable)
    assert reopened.submit_command(send)==receipt
    frozen=reopened.claim_attempt('rows',30).submission['_product_context'][0]
    assert frozen['historical_only'] is True
    assert frozen['row_selection']==selection
    data=json.loads(frozen['content'])
    assert data['rows'][1]['cells']=={'value':None}
    assert data['columns'][0]['unit']=='%'


def test_inline_page_read_preserves_original_and_selection_version():
    from capstone_agent.result_projection import ResultRow
    from capstone_agent.result_row_selection import read_table_page
    p=projection()
    p=replace(p,tables=(replace(p.tables[0],rows=tuple(ResultRow('row_'+str(i),{'value':i}) for i in range(5))),))
    original=p.to_document()
    store=ResultTableStore(MemoryObjectStore())
    ref={'origin':'domain_result'}
    first=read_table_page(p,ref,'res_line',store,limit=2)
    second=read_table_page(p,ref,'res_line',store,offset=2,limit=2)
    assert len(first['table']['rows'])==2 and first['next_offset']==2
    assert second['table']['rows'][0]['row_id']=='row_2'
    assert first['table_version']==second['table_version']
    assert original==p.to_document()
    a=prepare_selection(p,ref,'res_line',['row_0'],['value'],store)
    b=prepare_selection(p,ref,'res_line',['row_1'],['value'],store)
    assert a['digest']!=b['digest']


def test_row_endpoint_requires_auth_and_rejects_forged_source():
    from fastapi.testclient import TestClient
    from test_thread_deliveries import delivery_app
    from test_thread_http_api import _service,_auth
    service=_service()
    with TestClient(delivery_app(service,MemoryObjectStore(),None),base_url='http://localhost') as client:
        for suffix in ('table-page','row-selection'):
            url='/api/v1/threads/thr_demo_39/product-index/'+suffix
            assert client.post(url,json={}).status_code==401
            assert client.post(url,json={},headers=_auth()).status_code==422
            assert client.post(url,json={'ref':{},'table_id':'res_line','manifest_ref':'forged'},headers=_auth()).status_code==422


def test_same_parent_distinct_row_materials_keep_independent_identity():
    from test_thread_result_projection import _service,_claim_and_projection,RESULT_ONE,EVIDENCE_ONE
    from capstone_agent.thread_products import product_index,resolve_row_request,freeze_product_selection
    store=_service()
    store._material_objects=MemoryObjectStore()
    claim,document=_claim_and_projection(store,1,RESULT_ONE,EVIDENCE_ONE)
    document={**document,'tables':[list(pages())[1]['table']]}
    store.finish_attempt(claim,phase='completed',payload={'answer':'saved','result_projections':[document],
        'result_refs':[RESULT_ONE],'evidence_refs':[EVIDENCE_ONE],
        'admission':{'mode':'authority_backed','assurance':'lineage_verified'}})
    ref=next(e['ref'] for e in product_index(store,claim.thread_id)['products'] if e['ref']['origin']=='domain_result')
    selected=[{'ref':ref,'purpose':'historical-context','row_selection':resolve_row_request(store,
        store._material_objects,claim.thread_id,{'ref':ref,'table_id':'res_line','row_ids':[row],'column_ids':['value']})}
        for row in ['row_128','row_132']]
    snapshot=replace(store.snapshot(claim.thread_id),active_model_context=None,
        minimum_protocol_version=2,active_grid_page_id=None,current_attempt=None)
    frozen,reason=freeze_product_selection(store,snapshot,{'context_product_refs':selected},{})
    assert reason is None
    assert len({m['material_id'] for m in frozen['_materials']})==2
    assert [m['source_product']['row_selection'] for m in frozen['_materials']]==[s['row_selection'] for s in selected]


def test_row_request_stream_limit_and_duplicate_fields():
    from fastapi.testclient import TestClient
    from test_thread_deliveries import delivery_app
    from test_thread_http_api import _service,_auth
    with TestClient(delivery_app(_service(),MemoryObjectStore(),None),base_url='http://localhost') as client:
        url='/api/v1/threads/thr_demo_39/product-index/row-selection'
        assert client.post(url,content=b'x'*17000).status_code==401
        response=client.post(url,content=b'x'*17000,headers=_auth())
        assert response.status_code==413
        response=client.post(url,content=b'{"ref":{},"ref":{},"table_id":"res_line"}',headers=_auth())
        assert response.status_code==422
        assert response.json()['detail']['code']=='invalid_result_row_request'


def test_row_source_failure_returns_recoverable_error(monkeypatch):
    from fastapi.testclient import TestClient
    from test_thread_deliveries import delivery_app
    from test_thread_http_api import _service,_auth
    import capstone_agent.thread_products as products
    def unavailable(*args,**kwargs):
        raise FileNotFoundError('private object path must not reach client')
    monkeypatch.setattr(products,'resolve_row_request',unavailable)
    with TestClient(delivery_app(_service(),MemoryObjectStore(),None),base_url='http://localhost') as client:
        result=client.post('/api/v1/threads/thr_demo_39/product-index/row-selection',json={},headers=_auth())
        assert result.status_code==410
        assert result.json()['detail']['code']=='result_row_source_unavailable'
        assert 'private object path' not in result.text


def test_inline_page_publishes_only_requested_rows():
    from capstone_agent.result_projection import ResultRow
    from capstone_agent.result_row_selection import read_table_page
    p=projection()
    p=replace(p,tables=(replace(p.tables[0],rows=tuple(ResultRow('row_'+str(i),{'value':i}) for i in range(10000))),))
    objects=MemoryObjectStore()
    page=read_table_page(p,{'origin':'domain_result'},'res_line',ResultTableStore(objects),limit=1)
    assert len(objects.contents)==1
    assert len(page['table']['rows'])==1


def test_tiny_row_selection_admitted_when_parent_exceeds_full_context_budget():
    from test_thread_result_projection import _service,_claim_and_projection,RESULT_ONE,EVIDENCE_ONE
    from capstone_agent.thread_products import product_index,resolve_row_request,freeze_product_selection
    store=_service()
    store._material_objects=MemoryObjectStore()
    claim,document=_claim_and_projection(store,1,RESULT_ONE,EVIDENCE_ONE)
    table=list(pages())[1]['table']
    table={**table,'rows':[{'row_id':'row_'+str(i),'cells':{'value':None if i==0 else 'x'*2048}} for i in range(100)]}
    document={**document,'tables':[table]}
    store.finish_attempt(claim,phase='completed',payload={'answer':'saved','result_projections':[document],
        'result_refs':[RESULT_ONE],'evidence_refs':[EVIDENCE_ONE],
        'admission':{'mode':'authority_backed','assurance':'lineage_verified'}})
    entry=next(e for e in product_index(store,claim.thread_id)['products'] if e['ref']['origin']=='domain_result')
    assert entry['byte_size']>128*1024 and entry['capabilities']['select'] is False
    ref=entry['ref']
    selection=resolve_row_request(store,store._material_objects,claim.thread_id,
        {'ref':ref,'table_id':'res_line','row_ids':['row_0'],'column_ids':['value']})
    frozen,reason=freeze_product_selection(store,store.snapshot(claim.thread_id),
        {'context_product_refs':[{'ref':ref,'purpose':'historical-context','row_selection':selection}]},{})
    assert reason is None
    assert len(frozen['_product_context'][0]['content'])<2048


@pytest.mark.parametrize('storage',['memory','postgres'])
def test_postgres_professional_v2_work_save_start_rows(postgres_thread_service,monkeypatch,storage):
    from test_thread_work_execution import professional_snapshot,command,save_work
    from test_result_projection import valid_projection
    from capstone_agent.thread_products import product_index,resolve_row_request
    from capstone_agent.thread_service import PostgresThreadService
    store,thread_id=postgres_thread_service
    if storage == 'memory':
        from capstone_agent.thread_service import InMemoryThreadService
        store=InMemoryThreadService(professional_snapshot(thread_id))
    store._material_objects=MemoryObjectStore()
    if storage == 'postgres':
        store.create_thread(professional_snapshot(thread_id))
    work=save_work(store,thread_id)
    start=command(store,thread_id,'start_work','source',work_id=work['work_id'],revision=work['revision'])
    assert store.submit_command(start).status=='accepted'
    claim=store.claim_attempt('rows',30)
    projection={**valid_projection(),'thread_id':thread_id,'run_id':claim.run_id,
        'turn_id':claim.attempt.turn_id,'attempt_id':claim.attempt.attempt_id,
        'model_context_id':claim.model_context.id,'model_id':claim.model_context.model_id,
        'model_revision':claim.model_context.model_revision,'tables':[list(pages())[1]['table']],'element_refs':[],'overlay':None}
    store.finish_attempt(claim,phase='completed',payload={'answer':'saved','result_projections':[projection],
        'result_refs':[projection['result_ref']],'evidence_refs':projection['evidence_refs'],
        'admission':{'mode':'authority_backed','assurance':'lineage_verified'}})
    ref=next(e['ref'] for e in product_index(store,thread_id)['products'] if e['ref']['origin']=='domain_result')
    selection=resolve_row_request(store,store._material_objects,thread_id,
        {'ref':ref,'table_id':'res_line','row_ids':['row_132'],'column_ids':['value']})
    refs=[{'ref':ref,'purpose':'historical-context','row_selection':selection}]
    work=store.snapshot(thread_id).works[0]
    saved=command(store,thread_id,'work_message','save_rows',work_id=work['work_id'],revision=work['revision'],
        payload={'text':'Analyze this selected null row','context_product_refs':refs})
    assert store.submit_command(saved).status=='accepted'
    reopened=PostgresThreadService(store.dsn) if storage == 'postgres' else store
    reopened._material_objects=store._material_objects
    work=reopened.snapshot(thread_id).works[0]
    assert work['context_product_refs']==refs
    import capstone_agent.thread_products as products
    def missing(*args,**kwargs):
        raise OSError('source disappeared')
    before=reopened.snapshot(thread_id)
    bad_start=command(reopened,thread_id,'start_work','unavailable_rows',work_id=work['work_id'],revision=work['revision'])
    with monkeypatch.context() as patch:
        patch.setattr(products,'resolve_product',missing)
        assert reopened.submit_command(bad_start).rejection=='product_context_unavailable'
    assert reopened.snapshot(thread_id)==before
    start=command(reopened,thread_id,'start_work','selected_rows',work_id=work['work_id'],revision=work['revision'])
    receipt=reopened.submit_command(start)
    assert receipt.status=='accepted'
    monkeypatch.setattr(products,'resolve_product',missing)
    retry_store=PostgresThreadService(store.dsn) if storage == 'postgres' else store
    assert retry_store.submit_command(start)==receipt
    next_claim=reopened.claim_attempt('rows',30)
    assert next_claim.task_context.binding.work_id==work['work_id']
    assert next_claim.model_context==claim.model_context
    assert next_claim.submission['context_product_refs']==refs
    assert next_claim.submission['_product_context'][0]['row_selection']==selection
    assert next_claim.submission['_product_context'][0]['historical_only'] is True


@pytest.mark.parametrize('storage',['memory','postgres'])
def test_v2_work_http_invalid_refs_do_not_mutate(postgres_thread_service,storage):
    from fastapi.testclient import TestClient
    from test_thread_http_api import _app,_auth
    from test_thread_work_execution import professional_snapshot,command
    from capstone_agent.thread_service import InMemoryThreadService
    from capstone_agent.application_capacity import limits
    store,thread_id=postgres_thread_service
    if storage=='memory':
        store=InMemoryThreadService(professional_snapshot(thread_id))
    else:
        store.create_thread(professional_snapshot(thread_id))
    ref={'schema':'capstone-product-ref/1','thread_id':thread_id,'product_id':'result_one','origin':'domain_result','scope':'task','event_seq':1,'revision':None,'digest':'a'*64,'work_id':None,'attempt_id':'attempt_one','producer_attempt_id':'attempt_one'}
    item={'ref':ref,'purpose':'historical-context'}
    before=store.snapshot(thread_id)
    with TestClient(_app(store),base_url='http://localhost',raise_server_exceptions=False) as client:
        for name,refs in [('malformed',[{}]),('duplicate',[item,item]),('overflow',[{**item,'ref':{**ref,'product_id':'result_'+str(i)}} for i in range(limits.product_reference_count+1)])]:
            response=client.post('/api/v1/threads/'+thread_id+'/commands',headers={**_auth(),'Capstone-Thread-Version':'2'},
                json=command(store,thread_id,'work_message',name,payload={'text':'Save selection','context_product_refs':refs}))
            assert response.status_code==422, response.text
            assert store.snapshot(thread_id)==before
        refs=[{**item,'ref':{**ref,'product_id':'result_'+str(i)}} for i in range(limits.product_reference_count)]
        accepted=client.post('/api/v1/threads/'+thread_id+'/commands',headers={**_auth(),'Capstone-Thread-Version':'2'},
            json=command(store,thread_id,'work_message','save_limit',payload={'text':'Save selection','context_product_refs':refs}))
        assert accepted.status_code==202 and accepted.json()['status']=='accepted'
        before=store.snapshot(thread_id)
        work=before.works[0]
        overflow=client.post('/api/v1/threads/'+thread_id+'/commands',headers={**_auth(),'Capstone-Thread-Version':'2'},
            json=command(store,thread_id,'revise_goal','merged_overflow',work_id=work['work_id'],revision=work['revision'],
                payload={'text':'Revise with one more source','context_product_refs':[item]}))
        assert overflow.status_code==422
        assert store.snapshot(thread_id)==before
