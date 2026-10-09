from dataclasses import replace
from threading import Event

from fastapi.testclient import TestClient

from capstone_agent.thread_input_catalog import input_catalog_document
from capstone_agent.worker_wake import create_wake_app, wake_token
from test_intent_runtime import claim
import pytest


def test_standard_prepared_session_binds_harness_skill_server_side(monkeypatch):
    from types import SimpleNamespace
    from capstone_agent.kernel_pi_session import PreparedKernelPiSessionFactory
    from capstone_agent.model_capability_context import PreparedModelCapabilityContext
    from capstone_agent.turn_router import TurnPlan
    from capstone_agent.intent_runtime import intent_request_for_claim
    import capstone_agent.professional_resources as resources
    service, current = claim()
    source = intent_request_for_claim(current).to_document()
    source['selected_skill'] = {'profile_id': 'harness_engine', 'revision': 'accepted',
                               'skill_id': 'powerskills-pandapower', 'skill_version': 'v1'}
    from capstone_agent.request_intent import IntentRequest
    plan = TurnPlan(current.attempt.turn_id, current.attempt.attempt_id, 'professional',
                    'fixture', '1', None, {}, intent_request=IntentRequest(source), intent_resources={})
    current = replace(current, turn_plan=plan)
    typed = object()
    profile = object()
    monkeypatch.setattr(resources, 'resolve_harness_resource_profile', lambda root, bindings: profile)
    def bind(actual, **choice):
        assert actual is profile
        assert choice == {'profile_revision': 'accepted', 'skill_id': 'powerskills-pandapower', 'skill_version': 'v1'}
        return typed
    monkeypatch.setattr(resources, 'bind_harness_skill', bind)
    received = []
    def builder(scoped, context, profiles):
        received.append(scoped)
        return SimpleNamespace(start=lambda: None, prompt_and_wait=lambda: None, stop=lambda: None)
    context = PreparedModelCapabilityContext(current.thread_id, current.run_id, current.model_context, (), ())
    PreparedKernelPiSessionFactory(builder)(current, context)
    assert received[0].turn_plan.intent_resources['harness_skill_selection'] is typed


def test_common_operations_are_available_in_both_modes_but_cases_need_harness():
    service, _ = claim()
    snapshot = service.snapshot('thr_intent')
    for mode in ('capstone', 'pi_reference'):
        document = input_catalog_document(replace(snapshot, runtime_mode=mode), {}, [])
        operations = {item['operation_id']: item for item in document['operations']}
        assert operations['view_context']['available']
        assert operations['view_topology']['role'] == 'application'
        assert operations['start_case_execution']['available'] is False
        assert document['materials'] == []
        assert document['coverage']['full_model_tables'] is False


def test_resource_endpoint_uses_internal_auth_and_server_thread_identity():
    service, _ = claim()
    calls = []
    app = create_wake_app(Event(), 'operator-secret', implementation_family='pandapower',
        input_catalog=lambda thread_id: calls.append(thread_id) or {'implementation_family': 'pandapower', 'resource_profiles': {}})
    with TestClient(app) as client:
        route = '/threads/thr_intent/input-resources'
        assert client.get(route).status_code == 401
        response = client.get(route, headers={'Authorization': 'Bearer ' + wake_token('operator-secret')})
        assert response.status_code == 200
        assert response.json() == {'implementation_family': 'pandapower', 'resource_profiles': {}}
        assert calls == ['thr_intent']


def test_worker_rejects_catalog_for_another_registered_family():
    calls = []
    app = create_wake_app(Event(), 'secret', implementation_family='pandapower',
        thread_family=lambda thread_id: 'pypsa',
        input_catalog=lambda thread_id: calls.append(thread_id) or {'implementation_family': 'pypsa', 'resource_profiles': {}})
    with TestClient(app) as client:
        response = client.get('/threads/thr_other/input-resources',
            headers={'Authorization': 'Bearer ' + wake_token('secret')})
        assert response.status_code == 409
        assert calls == []


def test_catalog_cache_releases_its_own_pin_and_preserves_active_attempt(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from types import SimpleNamespace
    from test_model_capability_context import _owner, _claim
    from capstone_agent.thread_input_catalog import PreparedResourceCatalog
    from capstone_agent.thread_protocol import ThreadSnapshot, RunSnapshot
    import capstone_agent.thread_input_catalog as module
    import capstone_agent.professional_resources as resources
    owner, adapters = _owner([])
    current = _claim()
    active = owner.acquire(current)
    (tmp_path / 'agent-resources.json').write_text('{}')
    revision = ['source1']
    monkeypatch.setattr(module, 'resolve_resource_profile', lambda *args: SimpleNamespace(revision=revision[0]))
    calls = []
    def resolve(*args):
        calls.append(1)
        return SimpleNamespace(document_json='{"revision":"prepared","resources":[]}')
    monkeypatch.setattr(resources, 'resolve_harness_resource_profile', resolve)
    provider = PreparedResourceCatalog(owner, None, tmp_path)
    snapshot = ThreadSnapshot(current.thread_id, RunSnapshot(current.run_id, 'open'), current.model_context,
                              'page', None, 0, 0)
    with ThreadPoolExecutor(max_workers=4) as pool:
        documents = list(pool.map(provider, [snapshot] * 8))
    assert len(calls) == 1
    assert owner.resource_counts() == {'active': 1, 'retained': 1}
    assert not active.closed
    documents[0]['harness_engine']['revision'] = 'forged'
    assert provider(snapshot)['harness_engine']['revision'] == 'prepared'
    revision[0] = 'source2'
    provider(snapshot)
    assert len(calls) == 2
    owner.release(active)
    owner.close()
    revision[0] = 'source3'
    with pytest.raises(RuntimeError, match='closed'):
        provider(snapshot)


def test_real_http_api_to_registered_worker_resource_projection():
    import socket
    import threading
    import time
    import uvicorn
    from capstone_agent.thread_input_catalog import RemoteResourceCatalog, catalog_provider
    from test_thread_http_api import _app, _service, _auth
    worker_service = _service()
    worker_service.set_input_catalog_provider(catalog_provider(worker_service, lambda snapshot: {}, family_available=lambda family: True))
    app = create_wake_app(Event(), 'hosted-secret', implementation_family='pandapower', input_catalog=worker_service.input_catalog)
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    origin = f'http://127.0.0.1:{sock.getsockname()[1]}'
    server = uvicorn.Server(uvicorn.Config(app, log_level='error', access_log=False))
    thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started: break
            time.sleep(.01)
        assert server.started
        api_service = _service()
        reader = RemoteResourceCatalog('pandapower=' + origin, 'hosted-secret')
        api_service.set_input_catalog_provider(catalog_provider(api_service, reader, family_available=lambda family: True))
        with TestClient(_app(api_service), base_url='http://localhost') as client:
            response = client.get('/api/v1/threads/thr_demo_39/input-catalog', headers=_auth())
            assert response.status_code == 200
            doc = response.json()
            assert doc['objects'][0]['model_id'] == 'ieee39'
            assert doc['coverage']['full_model_tables'] is False
            assert origin not in response.text and 'secret' not in response.text
        assert RemoteResourceCatalog('pandapower=' + origin, 'wrong')(api_service.snapshot('thr_demo_39')) == {}
        with pytest.raises(ValueError):
            RemoteResourceCatalog('user-chosen=' + origin, 'hosted-secret')
    finally:
        server.should_exit = True
        thread.join(3)
        sock.close()
