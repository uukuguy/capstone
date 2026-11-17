from datetime import datetime, timezone

import pytest

from capstone_control.contracts import ContractError
from capstone_control.service import ControlService, Conflict, InvalidTransition
from capstone_control.store import MemoryStore


def service(**kwargs):
    return ControlService(MemoryStore(), now=lambda: datetime(2026, 11, 18, tzinfo=timezone.utc), **kwargs)


def create(control, **fields):
    return control.create_mission('team', dict(schema='capstone-control-mission-create/1',
        operation_id='create', objective='Investigate the reported issue', origin={'thread_id': 'thread_1'}, **fields))


def command(control, mission, kind, payload, operation='update'):
    return control.command_mission('team', dict(schema='capstone-control-mission-command/1', operation_id=operation,
        mission_id=mission['mission_id'], expected_revision=mission['revision'], kind=kind, payload=payload))['mission']


def task(identity='task_1', **fields):
    return dict(task_id=identity, objective='Inspect the saved inputs', delivery_requirements=['Saved findings'],
                depends_on=[], agent_id='capstone', mode='single', max_attempts=1, **fields)


def test_intent_only_mission_uses_same_identity_and_needs_explicit_readiness():
    control = service()
    mission = create(control)
    assert mission['state'] == 'planning' and mission['tasks'] == []
    assert mission['mission_id'] == mission['goal_id']
    assert control.read('team', mission['mission_id'])['schema'] == 'capstone-control-goal/1'
    assert control.read_mission('team', mission['mission_id']) == mission
    assert create(control) == mission
    with pytest.raises(KeyError):
        control.read_mission('other', mission['mission_id'])
    with pytest.raises(InvalidTransition):
        command(control, mission, 'ready', {})
    mission = command(control, mission, 'update_plan', {'acceptance_criteria': ['Finding saved'], 'tasks': [task()]})
    assert mission['state'] == 'planning'
    mission = command(control, mission, 'ready', {}, 'ready')
    assert mission['state'] == 'ready'


def test_prepare_task_does_not_revoke_unrelated_execution_and_revisions_are_fenced():
    control = service()
    mission = create(control, acceptance_criteria=['Saved'])
    mission = command(control, mission, 'prepare_task', {'task': task()})
    mission = command(control, mission, 'ready', {}, 'ready')
    receipt = control.command('team', dict(schema='capstone-control-command/1',operation_id='dispatch',
        goal_id=mission['mission_id'], expected_revision=mission['revision'],kind='delegate_next',payload={}))
    running = control.read_mission('team', mission['mission_id'])
    mission = command(control, running, 'prepare_task', {'task': task('task_2')}, 'second')
    assert mission['tasks'][0] == running['tasks'][0]
    assert mission['state'] == 'running'
    with pytest.raises(InvalidTransition):
        command(control, mission, 'prepare_task', {'task': task()}, 'active_edit')
    with pytest.raises(Conflict):
        command(control, running, 'prepare_task', {'task': task('task_3')}, 'stale')


def test_equipment_is_a_registered_reference_not_a_permission_claim():
    ref = dict(schema='capstone-mission-equipment-reference/1', kind='capability', id='read_inputs', revision='v1')
    control = service()
    mission = create(control)
    mission = command(control, mission, 'prepare_task', {'task': task(equipment=[ref])})
    assert mission['state'] == 'planning'
    mission = command(control, mission, 'update_plan', {'acceptance_criteria': ['Saved'], 'tasks': []}, 'criteria')
    with pytest.raises(InvalidTransition):
        command(control, mission, 'ready', {}, 'unavailable')
    control = service(admit_mission_reference=lambda workspace, origin, reference: reference == ref)
    mission = create(control)
    mission = command(control, mission, 'prepare_task', {'task': task(equipment=[ref])})
    assert mission['tasks'][0]['equipment'] == [ref]
    with pytest.raises(ContractError):
        command(control, mission, 'prepare_task', {'task': task('other', equipment=[{**ref, 'permissions': ['shell']}])}, 'bad')
    with pytest.raises(ContractError):
        command(control, mission, 'prepare_task', {'task': task('other', equipment=[ref], restrictions=[ref])}, 'denied')


def test_existing_goal_projection_remains_unchanged_and_is_not_copied():
    control = service()
    original = control.create('team', dict(schema='capstone-control-goal-create/1',operation_id='legacy',
        objective='Legacy',acceptance_criteria=['Saved'], max_delegations=2,
        deadline_at='2026-11-20T00:00:00Z',tasks=[task()]))
    projected = control.read_mission('team', original['goal_id'])
    assert projected['mission_id'] == original['goal_id']
    assert control.read('team', original['goal_id']) == original
    assert len(control.store.list('team')) == 1


def test_pausing_a_plan_cannot_bypass_explicit_readiness():
    control = service()
    mission = create(control, acceptance_criteria=['Saved'])
    mission = command(control, mission, 'prepare_task', {'task': task()})
    mission = command(control, mission, 'pause', {}, 'pause')
    with pytest.raises(InvalidTransition):
        command(control, mission, 'resume', {}, 'resume')
    with pytest.raises(InvalidTransition):
        control.command('team', dict(schema='capstone-control-command/1', operation_id='legacy_resume',
            goal_id=mission['mission_id'], expected_revision=mission['revision'], kind='resume', payload={}))
    assert command(control, mission, 'ready', {}, 'explicit_ready')['state'] == 'ready'


def test_reference_availability_is_rechecked_at_dispatch_and_restrictions_cannot_relax():
    ref = dict(schema='capstone-mission-equipment-reference/1', kind='capability', id='read_inputs', revision='v1')
    admitted = [True]
    control = service(admit_mission_reference=lambda *_: admitted[0])
    mission = create(control, acceptance_criteria=['Saved'])
    mission = command(control, mission, 'prepare_task', {'task': task(restrictions=[ref])})
    with pytest.raises(InvalidTransition):
        command(control, mission, 'prepare_task', {'task': task()}, 'relax')
    mission = command(control, mission, 'ready', {}, 'ready')
    admitted[0] = False
    with pytest.raises(InvalidTransition):
        command(control, mission, 'delegate_next', {}, 'dispatch')
    assert control.read_mission('team', mission['mission_id']) == mission


def test_mission_plan_dependencies_and_command_identities_are_exact():
    control = service()
    mission = create(control)
    receipt = command(control, mission, 'prepare_task', {'task': task()})
    assert command(control, mission, 'prepare_task', {'task': task()}) == receipt
    with pytest.raises(Conflict):
        command(control, mission, 'prepare_task', {'task': task('different')})
    invalid = task('task_2')
    invalid['depends_on'] = ['missing']
    with pytest.raises(ContractError):
        command(control, receipt, 'prepare_task', {'task': invalid}, 'missing_dependency')
    assert control.read_mission('team', mission['mission_id']) == receipt
    assert control.store.list('team', active_only=True)[0]['state'] == 'planning'


def test_registered_references_do_not_claim_an_unimplemented_execution_grant():
    control = service(admit_mission_reference=lambda *_: True)
    mission = create(control, acceptance_criteria=['Saved'])
    ref = dict(schema='capstone-mission-equipment-reference/1',kind='skill',id='analyze',revision='v1')
    mission = command(control, mission, 'prepare_task', {'task': task(equipment=[ref])})
    mission = command(control, mission, 'ready', {}, 'ready')
    with pytest.raises(InvalidTransition, match='execution adapter'):
        command(control, mission, 'delegate_next', {}, 'dispatch')
    assert control.pending('team') == []


def test_mission_postgres_recovery_preserves_origin_plan_and_receipts():
    import os
    from uuid import uuid4
    from concurrent.futures import ThreadPoolExecutor
    from capstone_control.store import PostgresStore
    dsn = os.environ.get('CAPSTONE_TEST_DATABASE_URL')
    if not dsn:
        pytest.skip('disposable PostgreSQL database required')
    store = PostgresStore(dsn)
    store.initialize()
    workspace = 'mission_test_' + uuid4().hex
    try:
        control = ControlService(store)
        request = dict(schema='capstone-control-mission-create/1',operation_id='create',objective='Investigate',
            origin={'thread_id': 'thread_1','work_id':'work_1'},acceptance_criteria=['Saved'])
        mission = control.create_mission(workspace, request)
        change = dict(schema='capstone-control-mission-command/1',operation_id='prepare',mission_id=mission['mission_id'],
            expected_revision=mission['revision'],kind='prepare_task',payload={'task':task()})
        def apply(_):
            return ControlService(PostgresStore(dsn)).command_mission(workspace, change)
        with ThreadPoolExecutor(max_workers=4) as pool:
            receipts = list(pool.map(apply, range(4)))
        assert all(receipt == receipts[0] for receipt in receipts)
        restarted = ControlService(PostgresStore(dsn))
        assert restarted.create_mission(workspace, request) == mission
        restored = restarted.read_mission(workspace, mission['mission_id'])
        assert restored['origin'] == request['origin']
        assert restored['plan_revision'] == 2 and restored['state'] == 'planning'
        assert len(restored['tasks']) == 1
        assert len(restarted.store.list(workspace)) == 1
    finally:
        with store.connect() as connection:
            connection.execute('DELETE FROM capstone_control_goals WHERE workspace=%s', (workspace,))
