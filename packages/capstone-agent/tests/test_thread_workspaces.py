from unittest.mock import MagicMock
from urllib.parse import quote
from dataclasses import replace
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from capstone_agent.thread_service import InMemoryThreadService, PostgresThreadService, ThreadNotFound, ThreadCreator
from capstone_agent.host_api import create_host_app
from capstone_agent.session import WorkerRegistry
from test_thread_http_api import _app, _auth, _service, _Ledger
from test_thread_creation import _Catalog


def test_memory_workspace_ownership_and_cursor_are_enforced():
    service = InMemoryThreadService(_service().snapshot('thr_demo_39'), workspace_name='研究')
    service.require_workspace('thr_demo_39', '研究')
    assert len(service.list_threads(workspace_name='研究')['threads']) == 1
    assert service.list_threads()['threads'] == []
    with pytest.raises(ThreadNotFound):
        service.require_workspace('thr_demo_39', 'enterprise')
    with pytest.raises(ThreadNotFound):
        service.list_threads(before='thr_demo_39', workspace_name='enterprise')
    with pytest.raises(ValueError, match='already exists'):
        service.create_thread(service.snapshot('thr_demo_39'), workspace_name='another')
    service.require_workspace('thr_demo_39', '研究')


def test_http_chinese_name_routes_to_its_space_and_missing_header_keeps_default():
    service = InMemoryThreadService(_service().snapshot('thr_demo_39'), workspace_name='电网研究')
    with TestClient(_app(service), base_url='http://localhost') as client:
        headers = {**_auth(), 'Capstone-Workspace': quote('电网研究')}
        assert client.get('/api/v1/threads/thr_demo_39', headers=headers).status_code == 200
        assert len(client.get('/api/v1/threads', headers=headers).json()['threads']) == 1
        assert client.get('/api/v1/threads/thr_demo_39', headers=_auth()).status_code == 404
        assert client.get('/api/v1/threads', headers=_auth()).json()['threads'] == []
        assert client.get('/api/v1/threads/thr_demo_39', headers={**_auth(),
            'Capstone-Workspace':'elsewhere', 'Capstone-Thread-Version':'999'}).status_code == 404


@pytest.mark.parametrize('selection,version', [({'session_type':'general-chat'}, '2'),
    ({'session_type':'enterprise-research'}, '2'), ({'model_id':'ieee39'}, '1')])
def test_http_creation_transfers_workspace_to_the_atomic_service_insert(selection, version):
    service = _service()
    service.create_thread = MagicMock(side_effect=lambda snapshot, **kwargs: snapshot)
    creator = ThreadCreator(service, _Catalog())
    app = create_host_app(_Ledger(), WorkerRegistry(()), operator_token='hosted-secret',
        allowed_hosts={'localhost'}, allowed_origins={'http://localhost:5173'},
        thread_service=service, thread_creator=creator)
    with TestClient(app, base_url='http://localhost') as client:
        response = client.post('/api/v1/threads', headers={**_auth(),
            'Capstone-Thread-Version':version, 'Capstone-Workspace':quote('研究')},
            json=selection)
    assert response.status_code == 201
    assert service.create_thread.call_args.kwargs == {'workspace_name':'研究'}


@pytest.mark.parametrize('model_free', [False, True])
def test_postgres_creation_binds_workspace_in_the_insert_not_a_later_update(model_free):
    service = PostgresThreadService('postgresql://unused')
    connection = MagicMock()
    connection.__enter__.return_value = connection
    service._connect = MagicMock(return_value=connection)
    snapshot = _service().snapshot('thr_demo_39')
    if model_free:
        snapshot = replace(snapshot, active_model_context=None, active_grid_page_id=None, minimum_protocol_version=2)
    service.create_thread(snapshot, workspace_name='研究')
    inserts = [call.args for call in connection.execute.call_args_list if 'INSERT INTO capstone_threads' in call.args[0]]
    assert len(inserts) == 1
    sql, parameters = inserts[0]
    assert 'workspace_name' in sql and parameters[-1] == '研究'
    assert not any('UPDATE capstone_threads SET workspace_name' in call.args[0] for call in connection.execute.call_args_list)


def test_postgres_list_filters_main_query_and_cursor_by_workspace():
    service = PostgresThreadService('postgresql://unused')
    connection = MagicMock()
    connection.__enter__.return_value = connection
    service._connect = MagicMock(return_value=connection)
    connection.execute.return_value.fetchone.return_value = {'created_at':datetime.now(timezone.utc), 'thread_id':'thr_cursor'}
    connection.execute.return_value.fetchall.return_value = []
    assert service.list_threads(before='thr_cursor', workspace_name='研究')['threads'] == []
    cursor, listing = [call.args for call in connection.execute.call_args_list]
    assert 'workspace_name = %s' in cursor[0] and cursor[1] == ('thr_cursor', '研究')
    assert 'workspace_name = %s' in listing[0] and listing[1][1] == '研究'


def test_postgres_rejects_foreign_cursor_before_listing_rows():
    service = PostgresThreadService('postgresql://unused')
    connection = MagicMock()
    connection.__enter__.return_value = connection
    service._connect = MagicMock(return_value=connection)
    connection.execute.return_value.fetchone.return_value = None
    with pytest.raises(ThreadNotFound):
        service.list_threads(before='thr_foreign', workspace_name='研究')
    assert connection.execute.call_count == 1


def test_missing_header_and_explicit_default_are_the_same_scope():
    with TestClient(_app(_service()), base_url='http://localhost') as client:
        implicit = client.get('/api/v1/threads', headers=_auth())
        explicit = client.get('/api/v1/threads', headers={**_auth(), 'Capstone-Workspace':'enterprise'})
        assert implicit.json() == explicit.json()
        assert 'capstone-workspace' in implicit.headers['Vary'].lower()
        assert implicit.headers['Capstone-Workspace'] == 'enterprise'


@pytest.mark.parametrize('name', ['enterprise', '中文研究', "scope!'()*"])
def test_thread_response_echoes_canonical_scope_and_exposes_it_on_cors_even_on_404(name):
    encoded = quote(name, safe='')
    service = InMemoryThreadService(_service().snapshot('thr_demo_39'), workspace_name=name)
    with TestClient(_app(service), base_url='http://localhost') as client:
        headers = {**_auth(), 'Capstone-Workspace':encoded}
        for path in ['/api/v1/threads', '/api/v1/threads/thr_missing']:
            response = client.get(path, headers=headers)
            assert response.status_code == (404 if path.endswith('thr_missing') else 200)
            assert response.headers['Capstone-Workspace'] == encoded
            exposed = {value.strip().lower() for value in response.headers['Access-Control-Expose-Headers'].split(',')}
            assert {'capstone-workspace', 'capstone-thread-version'} <= exposed
        invalid = client.get('/api/v1/threads', headers={**_auth(), 'Capstone-Workspace':'%FF'})
        assert invalid.status_code == 422
        assert 'Capstone-Workspace' not in invalid.headers


def test_unauthorized_request_cannot_probe_workspace_validation():
    with TestClient(_app(_service()), base_url='http://localhost') as client:
        response = client.get('/api/v1/threads/thr_demo_39', headers={'Capstone-Workspace':'%FF'})
    assert response.status_code == 401


@pytest.mark.parametrize('method,path', [
    ('GET', ''), ('GET', '/history'), ('GET', '/metadata'), ('GET', '/input-catalog'),
    ('GET', '/events?after=0'), ('GET', '/events/stream?after=0&follow=0'),
    ('POST', '/commands'), ('POST', '/archive'), ('DELETE', ''),
    ('GET', '/materials'), ('POST', '/materials'), ('GET', '/resources'),
    ('POST', '/resource-uploads'), ('PUT', '/resource-uploads/up_test/parts/0'),
    ('POST', '/resource-uploads/up_test/complete'), ('DELETE', '/resource-uploads/up_test'),
    ('GET', '/product-index'), ('POST', '/product-index/resolve'),
    ('GET', '/attempts/att_test/artifacts'), ('GET', '/attempts/att_test/artifacts/file_test'),
])
def test_cross_workspace_routes_refuse_before_protocol_or_payload_processing(method, path):
    service = _service()
    service.snapshot = MagicMock(side_effect=AssertionError('foreign snapshot must not be read'))
    with TestClient(_app(service), base_url='http://localhost') as client:
        response = client.request(method, '/api/v1/threads/thr_demo_39'+path,
            headers={**_auth(), 'Capstone-Workspace': quote('另一个空间')})
    assert response.status_code == 404
    service.snapshot.assert_not_called()


def test_http_catalog_is_scoped_and_foreign_cursor_is_not_accepted():
    with TestClient(_app(_service()), base_url='http://localhost') as client:
        assert len(client.get('/api/v1/threads', headers=_auth()).json()['threads']) == 1
        foreign = {**_auth(), 'Capstone-Workspace': 'another'}
        assert client.get('/api/v1/threads', headers=foreign).json()['threads'] == []
        assert client.get('/api/v1/threads?before=thr_demo_39', headers=foreign).status_code == 404
        assert client.get('/api/v1/threads', headers={**_auth(), 'Capstone-Workspace':'%FF'}).status_code == 422


def test_cors_allows_workspace_header():
    with TestClient(_app(_service()), base_url='http://localhost') as client:
        response = client.options('/api/v1/threads/thr_demo_39/resource-uploads/up_test/parts/0', headers={
            'Origin':'http://localhost:5173', 'Access-Control-Request-Method':'PUT',
            'Access-Control-Request-Headers':'Capstone-Workspace'})
    assert response.status_code == 204
    assert 'capstone-workspace' in response.headers['Access-Control-Allow-Headers'].lower()
    assert 'PUT' in {method.strip() for method in response.headers['Access-Control-Allow-Methods'].split(',')}


def test_cross_workspace_binary_upload_part_is_rejected_before_upload_processing():
    service = _service()
    service.snapshot = MagicMock(side_effect=AssertionError('foreign upload must not be processed'))
    with TestClient(_app(service), base_url='http://localhost') as client:
        response = client.put('/api/v1/threads/thr_demo_39/resource-uploads/up_test/parts/0',
            headers={**_auth(), 'Capstone-Workspace':quote('其他空间'),
                     'Content-Type':'application/octet-stream'}, content=b'upload-part')
    assert response.status_code == 404
    service.snapshot.assert_not_called()


def test_postgres_workspace_guard_filters_identity_without_reading_snapshot():
    service = PostgresThreadService('postgresql://unused')
    connection = MagicMock()
    service._connect = MagicMock(return_value=connection)
    connection.__enter__.return_value = connection
    connection.execute.return_value.fetchone.return_value = None
    with pytest.raises(ThreadNotFound):
        service.require_workspace('thr_foreign', 'another')
    sql, params = connection.execute.call_args.args
    assert 'workspace_name = %s' in sql
    assert params == ('thr_foreign', 'another')
