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
        assert client.get('/api/v1/control/missions', headers=_auth()).json()['schema'] == 'capstone-control-missions/1'
        assert client.get('/api/v1/control/missions/' + mission['mission_id'], headers=_auth()).json() == mission
        bad = {**_auth(), 'Capstone-Workspace': 'other'}
        assert client.get('/api/v1/control/missions/' + mission['mission_id'], headers=bad).status_code == 404
        assert client.post('/api/v1/control/missions', headers=bad, json=request(thread_id, 'foreign')).status_code == 404
        assert client.post('/api/v1/control/missions', headers=_auth(), json=request(thread_id, 'bad_work', work_id='missing')).status_code == 422


def test_partial_cross_store_creation_retries_repair_association(chat_store, monkeypatch):
    threads, thread_id = chat_store
    host = configure_control(threads)
    import capstone_agent.mission_origin as origins
    original = origins._reference
    def failed(*args, **kwargs):
        raise OSError('association write interrupted')
    monkeypatch.setattr(origins, '_reference', failed)
    with pytest.raises(OSError):
        host.create_mission('enterprise', request(thread_id))
    records = host.service.store.list('enterprise')
    records = [row for row in records if row.get('_mission', {}).get('origin', {}).get('thread_id') == thread_id]
    assert len(records) == 1 and records[0]['state'] == 'planning'
    assert not threads.snapshot(thread_id).mission_refs
    from capstone_agent.mission_origin import ActiveMissionConflict
    with pytest.raises(ActiveMissionConflict):
        host.create_mission('enterprise', request(thread_id, 'cannot_bypass_partial_create'))
    with pytest.raises(ValueError):
        host.command_mission('enterprise', dict(schema='capstone-control-mission-command/1',
            operation_id='orphan_cannot_run', mission_id=records[0]['goal_id'], expected_revision=1,
            kind='update_plan', payload={'acceptance_criteria': ['No orphan execution'], 'tasks': []}))
    monkeypatch.setattr(origins, '_reference', original)
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
    paused = host.mission_operation(claim, 'agent_mission_control',
        {'expected_revision': 2, 'action': 'pause'}, operation_id='model_pause')
    assert paused['mission']['state'] == 'paused'
    work = threads.snapshot(thread_id).works[0]
    assert threads.submit_command(command(threads, thread_id, 'cancel_work', 'stop_planner',
        work_id=work['work_id'], revision=work['revision'])).status == 'accepted'
    with pytest.raises(ThreadExecutionError):
        host.mission_operation(claim, 'agent_mission_read', {}, operation_id='stopping')
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


def test_legacy_goal_list_preserves_mixed_planning_mission_identity(chat_store):
    from test_control_host import goal_request
    threads, thread_id = chat_store
    with TestClient(_app(threads), base_url='http://localhost') as client:
        old_request = {**goal_request(), 'operation_id': 'legacy_' + thread_id}
        legacy = client.post('/api/v1/control/goals', headers=_auth(), json=old_request).json()
        mission = client.post('/api/v1/control/missions', headers=_auth(),
            json=request(thread_id, 'mixed')).json()
        found, cursor = {}, None
        while True:
            path = '/api/v1/control/goals?limit=64' + ('' if cursor is None else '&after=' + cursor)
            page = client.get(path, headers=_auth()).json()
            for row in page['goals']:
                assert row['goal_id'] not in found
                found[row['goal_id']] = row
            cursor = page['next_cursor']
            if cursor is None:
                break
        assert found[legacy['goal_id']] == legacy
        projected = found[mission['mission_id']]
        assert projected['schema'] == 'capstone-control-goal/1'
        assert projected['application_kind'] == 'mission'
        assert projected['mission_id'] == projected['goal_id'] == mission['mission_id']
        assert projected['origin'] == {'thread_id': thread_id}
        assert projected['state'] == 'planning' and projected['tasks'] == []
        assert projected['plan_complete'] is False and projected['plan_revision'] == 1
        assert 'application_kind' not in legacy


def test_concurrent_creates_admit_one_active_mission_per_thread(chat_store):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from capstone_control.service import Conflict
    threads, thread_id = chat_store
    host = configure_control(threads)
    gate = Barrier(2)
    def create(name):
        gate.wait()
        try:
            return host.create_mission('enterprise', request(thread_id, name))
        except Conflict as error:
            return str(error)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(create, ('first_concurrent', 'second_concurrent')))
    accepted = [result for result in results if isinstance(result, dict)]
    assert len(accepted) == 1
    assert any(isinstance(result, str) and 'already has an active Mission' in result for result in results)
    assert len(threads.snapshot(thread_id).mission_refs) == 1
    missions = [goal for goal in host.service.store.list('enterprise', limit=10000)
                if goal.get('_mission', {}).get('origin', {}).get('thread_id') == thread_id]
    assert len(missions) == 1
    first = accepted[0]
    host.command_mission('enterprise', dict(schema='capstone-control-mission-command/1',
        operation_id='end_previous', mission_id=first['mission_id'], expected_revision=1,
        kind='cancel', payload={}))
    following = host.create_mission('enterprise', request(thread_id, 'following_terminal'))
    assert following['mission_id'] != first['mission_id']
    assert len(threads.snapshot(thread_id).mission_refs) == 2


def test_conflicting_create_retains_same_operation_retry(chat_store):
    threads, thread_id = chat_store
    with TestClient(_app(threads), base_url='http://localhost') as client:
        original = request(thread_id, 'active')
        mission = client.post('/api/v1/control/missions', headers=_auth(), json=original).json()
        conflict = client.post('/api/v1/control/missions', headers=_auth(), json=request(thread_id, 'second'))
        assert conflict.status_code == 409
        assert conflict.json()['detail']['code'] == 'mission_already_active'
        assert conflict.json()['detail']['mission_id'] == mission['mission_id']
        assert client.post('/api/v1/control/missions', headers=_auth(), json=original).json() == mission
