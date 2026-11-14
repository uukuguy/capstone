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
