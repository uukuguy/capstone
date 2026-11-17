"""Mission creation links the actual owning Thread and repairs partial writes."""
from dataclasses import replace
import pytest
from fastapi.testclient import TestClient

from capstone_agent.control_host import configure_control
from capstone_agent.thread_service import ThreadExecutionError
from capstone_agent.thread_protocol import ThreadSnapshot
from test_enterprise_normal_chat import chat_store, native_executor
from test_thread_postgres import postgres_thread_service
from test_thread_work_execution import command
from test_thread_http_api import _app, _auth


def request(thread_id, operation='mission_create', **origin):
    return {'schema': 'capstone-control-mission-create/1', 'operation_id': operation + '_' + thread_id,
            'objective': 'Study the options and refine a plan in this conversation.',
            'origin': {'thread_id': thread_id, **origin}}


def test_intent_creation_and_goal_alias_share_identity_and_thread_link(chat_store):
    threads, thread_id = chat_store
    with TestClient(_app(threads), base_url='http://localhost') as client:
        created = client.post('/api/v1/control/missions', headers=_auth(), json=request(thread_id))
        assert created.status_code == 201, created.text
        mission = created.json()
        assert mission['state'] == 'planning' and mission['tasks'] == []
        assert mission['acceptance'] is None and not mission['plan_complete']
        assert mission['mission_id'] == mission['goal_id']
        retried = client.post('/api/v1/control/missions', headers=_auth(), json=request(thread_id))
        assert retried.json() == mission
        snapshot = threads.snapshot(thread_id)
        assert snapshot.mission_refs == ({'mission_id': mission['mission_id']},)
        assert ThreadSnapshot.from_document(snapshot.to_document()).mission_refs == snapshot.mission_refs
        assert len([event for event in threads.read_events(thread_id, 0, protocol_version=2).events
                    if event.event_type == 'mission_associated']) == 1
        goal_path = '/api/v1/control/goals/' + mission['goal_id']
        assert client.get(goal_path, headers=_auth()).json()['goal_id'] == mission['mission_id']
        event_path = '/api/v1/control/missions/' + mission['mission_id'] + '/events'
        assert client.get(event_path, headers=_auth()).json() == client.get(goal_path + '/events', headers=_auth()).json()
        assert mission in client.get('/api/v1/control/missions', headers=_auth()).json()['missions']
        bad = {**_auth(), 'Capstone-Workspace': 'other'}
        assert client.get('/api/v1/control/missions/' + mission['mission_id'], headers=bad).status_code == 404
        assert client.post('/api/v1/control/missions', headers=bad, json=request(thread_id, 'foreign')).status_code == 404
        assert client.post('/api/v1/control/missions', headers=_auth(), json=request(thread_id, 'bad_work', work_id='missing')).status_code == 422


def test_partial_cross_store_creation_retries_repair_association(chat_store, monkeypatch):
    threads, thread_id = chat_store
    host = configure_control(threads)
    original = threads.attach_mission
    def failed(*args, **kwargs):
        raise OSError('association write interrupted')
    monkeypatch.setattr(threads, 'attach_mission', failed)
    with pytest.raises(OSError):
        host.create_mission('enterprise', request(thread_id))
    records = host.service.store.list('enterprise')
    records = [row for row in records if row.get('_mission', {}).get('origin', {}).get('thread_id') == thread_id]
    assert len(records) == 1 and records[0]['state'] == 'planning'
    assert not threads.snapshot(thread_id).mission_refs
    monkeypatch.setattr(threads, 'attach_mission', original)
    repaired = host.create_mission('enterprise', request(thread_id))
    assert repaired['mission_id'] == records[0]['goal_id']
    assert len([row for row in host.service.store.list('enterprise')
                if row.get('_mission', {}).get('origin', {}).get('thread_id') == thread_id]) == 1
    assert threads.snapshot(thread_id).mission_refs[0]['mission_id'] == repaired['mission_id']


def test_native_binding_origin_lease_cas_and_frozen_selection(chat_store):
    threads, thread_id = chat_store
    threads.set_native_executor(native_executor())
    host = configure_control(threads)
    mission = host.create_mission('enterprise', request(thread_id))
    assert threads.submit_command(command(threads, thread_id, 'send_message', 'planning_prompt',
        payload={'text': 'Consider the accepted Mission intent.'})).status == 'accepted'
    claim = threads.claim_attempt('mission_planner', 30)
    assert claim.submission['_mission'] == {
        'schema': 'capstone-native-mission/1', 'mission_id': mission['mission_id'], 'origin': {'thread_id': thread_id}}
    assert host.mission_operation(claim, 'agent_mission_read', {}, operation_id='read')['state'] == 'planning'
    update = {'expected_revision': 1, 'acceptance_criteria': ['Explain the selected direction'], 'tasks': []}
    receipt = host.mission_operation(claim, 'agent_mission_update_plan', update, operation_id='model_plan')
    assert host.mission_operation(claim, 'agent_mission_update_plan', update, operation_id='model_plan') == receipt
    with pytest.raises(ValueError):
        host.mission_operation(claim, 'agent_mission_update_plan', update, operation_id='stale_plan')
    with pytest.raises(ValueError):
        host.mission_operation(claim, 'agent_mission_read', {'mission_id': 'injected'}, operation_id='bad_read')
    with pytest.raises(ThreadExecutionError):
        host.mission_operation(replace(claim, lease_token='stale'), 'agent_mission_read', {}, operation_id='old_lease')
    with pytest.raises((ThreadExecutionError, KeyError)):
        host.mission_operation(replace(claim, workspace_name='other'), 'agent_mission_read', {}, operation_id='other_workspace')
    threads.finish_attempt(claim, phase='completed', payload={'answer': 'Initial options need refinement.'})
    with pytest.raises(ThreadExecutionError):
        host.mission_operation(claim, 'agent_mission_read', {}, operation_id='terminal')


def test_postgres_origin_link_survives_new_service(postgres_thread_service):
    from capstone_agent.thread_service import PostgresThreadService
    from test_thread_postgres import _snapshot
    threads, thread_id = postgres_thread_service
    threads.create_thread(replace(_snapshot(thread_id), active_model_context=None,
        active_grid_page_id=None, minimum_protocol_version=2))
    mission = configure_control(threads).create_mission('enterprise', request(thread_id))
    restarted = PostgresThreadService(threads.dsn)
    assert restarted.snapshot(thread_id).mission_refs == ({'mission_id': mission['mission_id']},)
    assert configure_control(restarted).read_mission('enterprise', mission['mission_id'])['goal_id'] == mission['goal_id']
