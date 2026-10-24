from capstone_agent.thread_service import InMemoryThreadService, ThreadCreator
from capstone_agent.thread_protocol import ThreadSnapshot
from test_thread_postgres import postgres_thread_service
import pytest


def test_model_free_creation_and_work_cas():
    class Catalog:
        def resolve(self, *args):
            raise AssertionError('no model may be resolved')

    class Store:
        def create_thread(self, snapshot):
            return snapshot

    snapshot = ThreadCreator(Store(), Catalog()).create(model_free=True)
    assert snapshot.active_model_context is None
    assert ThreadSnapshot.from_document(snapshot.to_document()) == snapshot
    store = InMemoryThreadService(snapshot)
    command = {'schema': 'capstone-command/2', 'command_id': 'cmd_a',
               'idempotency_key': 'key_a', 'thread_id': snapshot.thread_id,
               'kind': 'work_message', 'target': {'kind': 'work', 'id': 'new', 'expected_revision': 0},
               'payload': {'text': 'Inspect the supplied materials'}}
    receipt = store.submit_command(command)
    assert receipt.status == 'accepted'
    assert store.submit_command(command) == receipt
    work = store.snapshot(snapshot.thread_id).to_document()['works'][0]
    assert work['status'] == 'blocked'
    assert work['task_context']['model_contexts'] == []
    assert store.claim_attempt('worker', 30) is None
    assert store.submit_command({**command, 'command_id': 'cmd_other', 'idempotency_key': 'key_other'}).status == 'accepted'
    assert store.snapshot(snapshot.thread_id).last_event_seq != work['revision']
    revise = {**command, 'command_id': 'cmd_b', 'idempotency_key': 'key_b',
              'kind': 'revise_goal', 'target': {'kind': 'work', 'id': work['work_id'], 'expected_revision': 1},
              'payload': {'text': 'Inspect the updated materials'}}
    assert store.submit_command(revise).status == 'accepted'
    assert store.submit_command({**revise, 'command_id': 'cmd_c', 'idempotency_key': 'key_c'}).rejection == 'revision_conflict'
    persisted = store.snapshot(snapshot.thread_id)
    assert ThreadSnapshot.from_document(persisted.to_document()) == persisted
    persisted.works[0]['goal'] = 'caller mutation'
    assert store.snapshot(snapshot.thread_id).works[0]['goal'] == 'Inspect the updated materials'


def test_upgrade_preserves_original_v1_retry_and_shared_history():
    from test_thread_http_api import _service, _app, _auth
    from capstone_agent.thread_commands import ThreadCommandFactory
    from fastapi.testclient import TestClient
    service = _service()
    command = ThreadCommandFactory('thr_demo_39').switch_runtime('pi_reference', expected_event_seq=0,
        command_id='cmd_before', idempotency_key='key_before')
    original = service.submit_command(command)
    with TestClient(_app(service), base_url='http://localhost') as client:
        work = {'schema': 'capstone-command/2', 'command_id': 'cmd_upgrade', 'idempotency_key': 'key_upgrade',
                'thread_id': 'thr_demo_39', 'kind': 'work_message',
                'target': {'kind': 'work', 'id': 'new', 'expected_revision': 0}, 'payload': {'text': 'Review materials'}}
        assert client.post('/api/v1/threads/thr_demo_39/commands', json=work,
                           headers={**_auth(), 'Capstone-Thread-Version': '2'}).status_code == 202
        assert client.get('/api/v1/threads/thr_demo_39', headers=_auth()).status_code == 409
        assert client.get('/api/v1/threads/thr_demo_39/events', headers=_auth()).status_code == 409
        retry = client.post('/api/v1/threads/thr_demo_39/commands', json=command, headers=_auth())
        assert retry.json() == original.to_document()
        events = client.get('/api/v1/threads/thr_demo_39/events',
                            headers={**_auth(), 'Capstone-Thread-Version': '2'}).json()['events']
        assert [event['event_seq'] for event in events] == list(range(1, len(events) + 1))


def test_http_model_free_creation_skips_professional_preparation():
    from capstone_agent.host_api import create_host_app
    from capstone_agent.thread_protocol import RunSnapshot
    from capstone_agent.session import WorkerRegistry
    from test_thread_http_api import _Ledger, _auth
    from fastapi.testclient import TestClient
    snapshot = ThreadSnapshot('thr_work', RunSnapshot('run_work', 'open'), None, None, None, 0, 0,
                              minimum_protocol_version=2)
    store = InMemoryThreadService(snapshot)
    calls = []
    from capstone_agent.thread_input_catalog import catalog_provider
    store.set_input_catalog_provider(catalog_provider(store, lambda snapshot: {}, family_available=lambda family: True))
    class Creator:
        def create(self, *, model_free):
            assert model_free is True
            return snapshot
    app = create_host_app(_Ledger(), WorkerRegistry(()), operator_token='hosted-secret',
        allowed_hosts={'localhost'}, allowed_origins={'http://localhost:5173'}, thread_service=store,
        thread_creator=Creator(), prepare_model=lambda *args: calls.append(args))
    with TestClient(app, base_url='http://localhost') as client:
        headers = {**_auth(), 'Capstone-Thread-Version': '2'}
        response = client.post('/api/v1/threads', json={}, headers=headers)
        assert response.status_code == 201
        assert response.json()['active_model_context'] is None
        assert client.get('/api/v1/threads', headers=headers).json()['threads'][0]['model_id'] is None
        assert client.get('/api/v1/threads/thr_work/models', headers=headers).status_code == 409
        catalog = client.get('/api/v1/threads/thr_work/input-catalog', headers=headers)
        assert catalog.status_code == 200
        assert catalog.json()['context_id'] is None
        assert catalog.json()['objects'] == []
        assert catalog.json()['resource_profiles'] == {}
        assert not next(item for item in catalog.json()['operations'] if item['operation_id'] == 'view_topology')['available']
    assert calls == []


def test_legacy_application_transition_cannot_mutate_upgraded_thread():
    from test_thread_http_api import _service
    from capstone_agent.thread_application_transition import ThreadApplicationTransition
    store = _service()
    command = {'schema': 'capstone-command/1', 'command_id': 'cmd_app', 'idempotency_key': 'key_app',
        'thread_id': 'thr_demo_39', 'kind': 'application_update', 'expected_event_seq': 0, 'payload': {}}
    transition = ThreadApplicationTransition(command, {}, ())
    original = store.apply_application_transition(transition)
    work = {'schema': 'capstone-command/2', 'command_id': 'cmd_work', 'idempotency_key': 'key_work',
        'thread_id': 'thr_demo_39', 'kind': 'work_message',
        'target': {'kind': 'work', 'id': 'new', 'expected_revision': 0}, 'payload': {'text': 'Review'}}
    assert store.submit_command(work).status == 'accepted'
    assert store.apply_application_transition(transition) == original
    fresh = ThreadApplicationTransition({**command, 'command_id': 'cmd_fresh', 'idempotency_key': 'key_fresh',
                                         'expected_event_seq': store.snapshot('thr_demo_39').last_event_seq}, {'unsafe': True}, ())
    assert store.apply_application_transition(fresh).rejection == 'protocol_upgrade_required'


@pytest.mark.parametrize('state', ['created', 'closing', 'closed', 'failed'])
def test_work_rejects_non_open_run(state):
    from capstone_agent.thread_protocol import RunSnapshot
    store = InMemoryThreadService(ThreadSnapshot('thr_closed', RunSnapshot('run_closed', state),
                                                 None, None, None, 0, 0, minimum_protocol_version=2))
    receipt = store.submit_command({'schema': 'capstone-command/2', 'command_id': 'cmd_closed',
        'idempotency_key': 'key_closed', 'thread_id': 'thr_closed', 'kind': 'work_message',
        'target': {'kind': 'work', 'id': 'new', 'expected_revision': 0}, 'payload': {'text': 'Review'}})
    assert receipt.rejection == 'run_not_open'
    assert store.snapshot('thr_closed').last_event_seq == 0


def test_work_upgrade_preserves_active_legacy_application_boundary():
    from dataclasses import replace
    from test_thread_http_api import _service
    store = _service()
    store._snapshot = replace(store._snapshot, application_state={
        'case_execution': {'status': 'waiting_step'}, 'context_locked': True})
    receipt = store.submit_command({'schema': 'capstone-command/2', 'command_id': 'cmd_case_boundary',
        'idempotency_key': 'key_case_boundary', 'thread_id': 'thr_demo_39', 'kind': 'work_message',
        'target': {'kind': 'work', 'id': 'new', 'expected_revision': 0}, 'payload': {'text': 'Review'}})
    assert receipt.rejection == 'case_context_locked'
    assert store.snapshot('thr_demo_39').minimum_protocol_version == 1


def test_actual_snapshot_read_rechecks_version_after_middleware_race():
    from test_thread_http_api import _service, _app, _auth
    from fastapi.testclient import TestClient
    store = _service()
    original = store.snapshot
    first = True
    def racing_snapshot(thread_id):
        nonlocal first
        captured = original(thread_id)
        if first:
            first = False
            store.submit_command({'schema': 'capstone-command/2', 'command_id': 'cmd_race',
                'idempotency_key': 'key_race', 'thread_id': thread_id, 'kind': 'work_message',
                'target': {'kind': 'work', 'id': 'new', 'expected_revision': 0}, 'payload': {'text': 'Review'}})
        return captured
    store.snapshot = racing_snapshot
    with TestClient(_app(store), base_url='http://localhost') as client:
        response = client.get('/api/v1/threads/thr_demo_39', headers=_auth())
    assert response.status_code == 409
    assert response.json()['error'] == 'protocol_upgrade_required'


def test_open_legacy_stream_reports_upgrade_without_emitting_work_event():
    from test_thread_http_api import _service, _app, _auth
    from fastapi.testclient import TestClient
    store = _service()
    original = store.read_events
    first = True
    def racing_events(thread_id, after_event_seq, *, protocol_version=2):
        nonlocal first
        page = original(thread_id, after_event_seq, protocol_version=protocol_version)
        if first:
            first = False
            store.submit_command({'schema': 'capstone-command/2', 'command_id': 'cmd_stream',
                'idempotency_key': 'key_stream', 'thread_id': thread_id, 'kind': 'work_message',
                'target': {'kind': 'work', 'id': 'new', 'expected_revision': 0}, 'payload': {'text': 'Review'}})
        return page
    store.read_events = racing_events
    with TestClient(_app(store), base_url='http://localhost') as client:
        response = client.get('/api/v1/threads/thr_demo_39/events/stream?follow=true', headers=_auth())
    assert 'event: protocol_upgrade_required' in response.text
    assert 'command.applied' not in response.text
    assert 'id:' not in response.text


def test_legacy_archive_page_does_not_read_default_active_page():
    from test_thread_http_api import _service, _app, _auth
    from fastapi.testclient import TestClient
    store = _service()
    original = store.list_threads
    calls = []
    def requested_page(*, before=None, limit=20, archived=False):
        calls.append((before, limit, archived))
        page = original()
        if not archived:
            page['threads'][0]['minimum_protocol_version'] = 2
        return page
    store.list_threads = requested_page
    with TestClient(_app(store), base_url='http://localhost') as client:
        response = client.get('/api/v1/threads?archived=true&limit=5', headers=_auth())
    assert response.status_code == 200
    assert calls == [(None, 5, True)]


def test_postgres_application_transition_retry_precedes_upgrade_gate(postgres_thread_service):
    from test_thread_postgres import _snapshot
    from capstone_agent.thread_application_transition import ThreadApplicationTransition
    store, thread_id = postgres_thread_service
    store.create_thread(_snapshot(thread_id))
    command = {'schema': 'capstone-command/1', 'command_id': 'cmd_app', 'idempotency_key': 'key_app',
        'thread_id': thread_id, 'kind': 'application_update', 'expected_event_seq': 0, 'payload': {}}
    transition = ThreadApplicationTransition(command, {}, ())
    original = store.apply_application_transition(transition)
    work = {'schema': 'capstone-command/2', 'command_id': 'cmd_work', 'idempotency_key': 'key_work',
        'thread_id': thread_id, 'kind': 'work_message',
        'target': {'kind': 'work', 'id': 'new', 'expected_revision': 0}, 'payload': {'text': 'Review'}}
    assert store.submit_command(work).status == 'accepted'
    assert store.apply_application_transition(transition) == original
    fresh = ThreadApplicationTransition({**command, 'command_id': 'cmd_fresh', 'idempotency_key': 'key_fresh',
        'expected_event_seq': store.snapshot(thread_id).last_event_seq}, {'unsafe': True}, ())
    assert store.apply_application_transition(fresh).rejection == 'protocol_upgrade_required'


def test_postgres_model_free_work_survives_restart(postgres_thread_service):
    from capstone_agent.thread_protocol import RunSnapshot
    from capstone_agent.thread_service import PostgresThreadService
    service, thread_id = postgres_thread_service
    service.create_thread(ThreadSnapshot(thread_id, RunSnapshot('run_' + thread_id, 'open'),
                                        None, None, None, 0, 0, minimum_protocol_version=2))
    command = {'schema': 'capstone-command/2', 'command_id': 'cmd_a', 'idempotency_key': 'key_a',
               'thread_id': thread_id, 'kind': 'work_message',
               'target': {'kind': 'work', 'id': 'new', 'expected_revision': 0}, 'payload': {'text': 'Review'}}
    original = service.submit_command(command)
    restored = PostgresThreadService(service.dsn)
    assert restored.submit_command(command) == original
    assert restored.snapshot(thread_id).works == service.snapshot(thread_id).works
    assert restored.list_threads()['threads'][0]['model_id'] is None
