import pytest
from test_product_index_reader import prepare
from capstone_agent.product_series_service import ProductSeriesService
from test_thread_postgres import postgres_thread_service


def test_exact_retry_survives_source_loss_and_failed_adoption_rolls_back():
    threads, objects, ref, _ = prepare()
    service = ProductSeriesService(threads, objects)
    command = dict(schema='capstone-product-series-command/1', series_id='series_a',
        expected_revision=0, operation='register', product=ref,
        command_id='cmd_a', idempotency_key='idem_a')
    first = service.command(ref['thread_id'], command, actor='operator:private')
    assert service.discover(ref['thread_id'], ref)['series'] == first
    assert service.list(ref['thread_id'])['series'] == [first]
    objects.contents.clear()
    assert service.command(ref['thread_id'], command, actor='operator:private') == first
    with pytest.raises((ValueError, KeyError)):
        service.command(ref['thread_id'], {**command, 'operation':'adopt', 'expected_revision':1,
            'command_id':'cmd_b', 'idempotency_key':'idem_b'}, actor='operator:private')
    assert service.read(ref['thread_id'], 'series_a') == first
    with pytest.raises(ValueError):
        service.command(ref['thread_id'], {**command, 'actor':'client'}, actor='operator:private')


def test_postgres_exact_retained_source_and_http_recovery(postgres_thread_service):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from capstone_agent.product_series_http import register_product_series_routes
    threads, thread = postgres_thread_service
    memory, objects, ref, data = prepare()
    # Import actual published events and bytes; do not replace source validation.
    thread = ref['thread_id']
    threads.create_thread(memory._snapshot)
    try:
        with threads._connect() as c:
            for event in memory._events:
                threads._insert_event(c, event)
        service = ProductSeriesService(threads, objects)
        app = FastAPI()
        register_product_series_routes(app,service=service,authorize=lambda request:None,
            actor_provider=lambda request:'operator:test')
        command=dict(schema='capstone-product-series-command/1',series_id='series_real',
            expected_revision=0,operation='register',product=ref,command_id='cmd_real',idempotency_key='idem_real')
        path=f'/api/v1/threads/{thread}/product-series'
        with TestClient(app) as client:
            response=client.post(path+'/commands',json=command)
            assert response.status_code==200, response.text
            original=response.json()
            assert client.post(path+'/sources',json={'product':ref}).json()=={'sources':[]}
            objects.contents.clear()
            assert client.post(path+'/commands',json=command).json()==original
            adopt={**command,'expected_revision':1,'operation':'adopt','command_id':'cmd_adopt','idempotency_key':'idem_adopt'}
            assert client.post(path+'/commands',json=adopt).status_code in {404,422}
            assert client.get(path+'/series_real').json()==original
            assert client.post(path+'/commands',json={**adopt,'expected_revision':0}).status_code==409
            assert client.post(path+'/commands',json={**adopt,'product':{**ref,'thread_id':'other'}}).status_code==422
            assert ProductSeriesService(threads,objects).read(thread,'series_real')==original
    finally:
        with threads._connect() as c:
            c.execute('DELETE FROM capstone_threads WHERE thread_id=%s',(thread,))


def test_host_mount_requires_private_access_and_uses_scope_actor():
    from fastapi.testclient import TestClient
    from test_thread_http_api import _app, _auth
    threads,objects,ref,_=prepare()
    app=_app(threads)
    path=f"/api/v1/threads/{ref['thread_id']}/product-series"
    with TestClient(app,base_url='http://localhost') as client:
        assert client.get(path).status_code==401
        assert client.get(path,headers=_auth()).json()=={'series':[],'next_cursor':None}
        assert client.post(path+'/commands',headers=_auth(),json={'actor':'forged'}).status_code==422


def test_shared_memory_adapter_keeps_all_series_data_in_thread_scope():
    from dataclasses import replace
    from threading import RLock
    from test_thread_http_api import _service
    from test_thread_deliveries import native_file
    from capstone_agent.artifacts import MemoryObjectStore
    from capstone_agent.native_artifact_projection import artifact_object_key
    from capstone_agent.thread_products import product_index
    first, objects, ref, _ = prepare()
    second = _service()
    second._snapshot = replace(second._snapshot, thread_id='thr_other')
    data=b'Second source'
    source,_=native_file(second,'thr_other',data,name='second.md')
    objects.put(artifact_object_key(source),data,'text/markdown')
    other_ref=next(p['ref'] for p in product_index(second,'thr_other')['products'] if p['ref']['origin']=='native_file')
    class SharedMemory:
        _lock=RLock()
        active=first
        def _check_thread(self, thread):
            self.active={ref['thread_id']:first,'thr_other':second}[thread]
            self.active._check_thread(thread)
        def __getattr__(self,name):
            return getattr(self.active,name)
    shared=SharedMemory()
    service=ProductSeriesService(shared,objects)
    command=dict(schema='capstone-product-series-command/1',series_id='series_same',expected_revision=0,
        operation='register',product=ref,command_id='cmd_same',idempotency_key='idem_same')
    accepted=service.command(ref['thread_id'],command,actor='operator:test')
    assert service.list('thr_other')=={'series':[],'next_cursor':None}
    for operation in (service.read,service.members,service.history):
        with pytest.raises(KeyError): operation('thr_other','series_same')
    other=service.command('thr_other',{**command,'product':other_ref},actor='operator:test')
    assert other['thread_id']=='thr_other'
    assert service.command(ref['thread_id'],command,actor='operator:test')==accepted
    assert service.read(ref['thread_id'],'series_same')==accepted
    assert service.discover('thr_other',other_ref)['series']==other
    assert service.history('thr_other','series_same')['events'][0]['product']==other_ref


def test_adoption_accepts_large_binary_products_without_whole_object_reads():
    from test_thread_http_api import _service
    from test_thread_deliveries import native_file
    from capstone_agent.artifacts import MemoryObjectStore
    from capstone_agent.native_artifact_projection import artifact_object_key
    from capstone_agent.thread_products import product_index
    threads=_service()
    data=b'\x00\xff'*(3*1024*1024)
    source,_=native_file(threads,'thr_demo_39',data,name='report.pdf')
    class StreamingOnly(MemoryObjectStore):
        def get(self,*args): raise AssertionError('must stream retained bytes')
    objects=StreamingOnly()
    objects.put(artifact_object_key(source),data,'application/pdf')
    ref=next(p['ref'] for p in product_index(threads,'thr_demo_39')['products'] if p['ref']['origin']=='native_file')
    service=ProductSeriesService(threads,objects)
    command=dict(schema='capstone-product-series-command/1',series_id='series_binary',expected_revision=0,
        operation='register',product=ref,command_id='cmd_binary',idempotency_key='idem_binary')
    assert service.command(ref['thread_id'],command,actor='operator:test')['revision']==1
    adopted=service.command(ref['thread_id'],{**command,'operation':'adopt','expected_revision':1,
        'command_id':'cmd_adopt','idempotency_key':'idem_adopt'},actor='operator:test')
    assert adopted['adopted_ref']==ref
