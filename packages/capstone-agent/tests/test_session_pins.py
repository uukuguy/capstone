import os
import uuid
import pytest
from capstone_agent.session_pins import MemorySessionPins


def test_pin_import_cannot_resurrect_explicit_unpin():
    store = MemorySessionPins()
    assert store.update('enterprise', ['a', 'b'], imported=True)['pins'] == ['a', 'b']
    removed = store.update('enterprise', ['a'], pinned=False)
    restored = store.update('enterprise', ['a', 'c'], imported=True)
    assert restored['pins'] == ['b', 'c']
    assert restored['revision'] > removed['revision']


def test_workspace_isolation_and_revision_survives_empty_list():
    store = MemorySessionPins()
    first = store.update('one', ['a'])
    assert store.read('two')['pins'] == []
    empty = store.update('one', ['a'], pinned=False)
    assert empty['pins'] == []
    assert empty['revision'] > first['revision']
    assert store.read('one') == empty


def test_http_pins_are_workspace_scoped_and_validate_operations():
    from fastapi.testclient import TestClient
    from test_thread_http_api import _app, _auth, _service
    service = _service()
    with TestClient(_app(service), base_url='http://localhost') as client:
        path = '/api/v1/workspace/session-pins'
        response = client.put(path, headers=_auth(), json={'thread_id':'thr_demo_39', 'pinned':True})
        assert response.status_code == 200
        assert response.json()['pins'] == ['thr_demo_39']
        assert response.headers['Capstone-Workspace'] == 'enterprise'
        assert client.get(path, headers=_auth()).json() == response.json()
        other = {**_auth(), 'Capstone-Workspace':'other'}
        assert client.get(path, headers=other).json()['pins'] == []
        assert client.put(path, headers=other, json={'thread_id':'thr_demo_39','pinned':True}).status_code == 404
        assert client.put(path, headers=_auth(), json={'thread_id':'thr_demo_39','pinned':'false'}).status_code == 422
        assert client.delete(path+'/cleanup/thr_demo_39',headers=_auth()).status_code == 409
        assert client.get('/api/v1/threads/thr_demo_39',headers=_auth()).status_code == 200


def test_postgres_pins_survive_new_service_and_concurrent_clients():
    import psycopg
    from psycopg import sql
    from dataclasses import replace
    from concurrent.futures import ThreadPoolExecutor
    from capstone_agent.thread_service import PostgresThreadService
    from capstone_agent.session_pins import PostgresSessionPins
    from test_thread_http_api import _service
    dsn = os.environ.get('CAPSTONE_TEST_DATABASE_URL')
    if not dsn:
        pytest.skip('CAPSTONE_TEST_DATABASE_URL is required')
    schema = 'pins_test_' + uuid.uuid4().hex
    with psycopg.connect(dsn) as connection:
        connection.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    scoped = psycopg.conninfo.make_conninfo(dsn, options='-c search_path='+schema)
    try:
        service = PostgresThreadService(scoped)
        service.initialize()
        original = _service().snapshot('thr_demo_39')
        ids = ['thr_pin_'+str(index) for index in range(8)]
        for key in ids:
            service.create_thread(replace(original,thread_id=key,run=replace(original.run,run_id='run_'+key)))
        store = PostgresSessionPins(service)
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda key: store.update('enterprise',[key]),ids))
        recovered = PostgresSessionPins(PostgresThreadService(scoped))
        assert set(recovered.read('enterprise')['pins']) == set(ids)
        assert recovered.read('other')['pins'] == []
        removed = recovered.update('enterprise',[ids[0]],pinned=False)
        assert ids[0] not in store.update('enterprise',ids,imported=True)['pins']
        assert store.read('enterprise')['revision'] == removed['revision']
        for key in ids:
            service.delete_thread(key)
        empty = recovered.read('enterprise')
        assert empty['pins'] == []
        assert empty['revision'] == removed['revision']
    finally:
        with psycopg.connect(dsn) as connection:
            connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
