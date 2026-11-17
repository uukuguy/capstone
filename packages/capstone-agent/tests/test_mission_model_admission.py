"""Model planning rejects unregistered equipment before mutating durable plans."""
from copy import deepcopy
import pytest

from capstone_control.contracts import ContractError
from capstone_control.service import InvalidTransition
from capstone_agent.control_host import configure_control
from test_enterprise_normal_chat import chat_store, native_executor
from test_thread_postgres import postgres_thread_service
from test_thread_work_execution import command
from test_mission_origin import request
from test_mission_continuation import review_store, reserved_review


def task(identity='next_task', **changes):
    return dict(task_id=identity, objective='Inspect the admitted dependency input.',
        delivery_requirements=['Save a bounded result'], depends_on=[], agent_id='capstone',
        mode='single', max_attempts=1, **changes)


@pytest.mark.parametrize('name', ['agent_mission_prepare_task', 'agent_mission_update_plan'])
@pytest.mark.parametrize('invalid', ['resource_kind', 'stale_revision', 'unknown_id', 'unknown_restriction'])
def test_model_invalid_equipment_never_enters_plan_or_changes_revision(chat_store, name, invalid):
    threads, thread_id = chat_store
    threads.set_native_executor(native_executor())
    host = configure_control(threads)
    mission = host.create_mission('enterprise', request(thread_id, 'model_validation'))
    threads.submit_command(command(threads, thread_id, 'send_message', 'model_planning',
        payload={'text': 'Prepare the Mission plan using the registered equipment.'}))
    claim = threads.claim_attempt('model_planner', 60)
    current = host.mission_operation(claim, 'agent_mission_read', {}, operation_id='read')
    registered = next(ref for ref in current['available_equipment'] if ref['kind'] == 'capability')
    ref = deepcopy(registered)
    if invalid == 'resource_kind':
        ref.update(kind='resource', id='resource_' + 'a' * 32, revision='1')
    elif invalid == 'stale_revision':
        ref['revision'] = 'stale'
    else:
        ref['id'] = 'not_registered'
    proposal = task(**{'restrictions' if invalid == 'unknown_restriction' else 'equipment': [ref]})
    payload = ({'task': proposal} if name == 'agent_mission_prepare_task'
               else {'acceptance_criteria': ['Inspect original results'], 'tasks': [proposal]})
    before = host.service.read_mission('enterprise', mission['mission_id'])
    events = host.service.read_events('enterprise', mission['mission_id'])
    callback = host.service.admit_mission_reference
    seen = []
    def admitted(workspace, origin, reference):
        seen.append((workspace, deepcopy(origin), deepcopy(reference)))
        return callback(workspace, origin, reference)
    host.service.admit_mission_reference = admitted
    with pytest.raises(ContractError):
        host.mission_operation(claim, name, {'expected_revision': before['revision'], **payload},
                               operation_id='invalid_model_proposal')
    assert seen == [('enterprise', claim.submission['_mission']['origin'], ref)]
    assert host.service.read_mission('enterprise', mission['mission_id']) == before
    assert host.service.read_events('enterprise', mission['mission_id']) == events


def test_valid_dependency_task_is_ready_and_unrelated_restrictions_are_preserved(review_store):
    threads, thread_id, workspace, _ = review_store
    host, mission, intent, original = reserved_review(review_store)
    binding = threads.submit_mission_review(intent)
    host.service.acknowledge_mission_review(workspace, mission['mission_id'], intent['review_id'], binding)
    claim = threads.claim_attempt('review_planner', 60)
    current = host.mission_operation(claim, 'agent_mission_read', {}, operation_id='read')
    read = next(ref for ref in current['available_equipment'] if ref['kind'] == 'capability' and ref['id'] == 'read')
    denied = next(ref for ref in current['available_equipment'] if ref['kind'] == 'capability' and ref['id'] == 'write')
    unrelated = task('unrelated', restrictions=[denied])
    current = host.mission_operation(claim, 'agent_mission_prepare_task',
        {'expected_revision': current['revision'], 'task': unrelated}, operation_id='keep_unrelated')['mission']
    old_tasks = deepcopy(current['tasks'])
    dependent = task('inspect_dependency', equipment=[read])
    dependent['depends_on'] = ['inspect']
    current = host.mission_operation(claim, 'agent_mission_prepare_task',
        {'expected_revision': current['revision'], 'task': dependent}, operation_id='prepare_dependency')['mission']
    assert current['tasks'][:2] == old_tasks
    assert current['tasks'][-1]['depends_on'] == ['inspect']
    current = host.mission_operation(claim, 'agent_mission_ready',
        {'expected_revision': current['revision']}, operation_id='ready_dependency')['mission']
    assert current['state'] == 'ready'
    before = deepcopy(current)
    with pytest.raises(InvalidTransition):
        host.mission_operation(claim, 'agent_mission_update_plan',
            {'expected_revision': current['revision'], 'acceptance_criteria': current['acceptance_criteria'],
             'tasks': [task('unrelated')]}, operation_id='cannot_relax_existing_restriction')
    assert host.service.read_mission(workspace, mission['mission_id']) == before


def test_raw_planning_api_keeps_future_draft_reference_semantics(chat_store):
    threads, thread_id = chat_store
    threads.set_native_executor(native_executor())
    host = configure_control(threads)
    mission = host.create_mission('enterprise', request(thread_id, 'future_draft'))
    reference = {'schema': 'capstone-mission-equipment-reference/1', 'kind': 'resource',
                 'id': 'future_resource', 'revision': '1'}
    saved = host.command_mission('enterprise', dict(schema='capstone-control-mission-command/1',
        operation_id='raw_draft', mission_id=mission['mission_id'], expected_revision=1,
        kind='prepare_task', payload={'task': task(equipment=[reference])}))['mission']
    assert saved['tasks'][0]['equipment'] == [reference]
    assert saved['state'] == 'planning'


@pytest.mark.parametrize('name', ['agent_mission_prepare_task', 'agent_mission_update_plan'])
def test_successful_model_operation_replays_before_changed_registry_validation(chat_store, name):
    threads, thread_id = chat_store
    threads.set_native_executor(native_executor())
    host = configure_control(threads)
    mission = host.create_mission('enterprise', request(thread_id, 'model_replay'))
    threads.submit_command(command(threads, thread_id, 'send_message', 'model_replay',
        payload={'text': 'Prepare a registered task.'}))
    claim = threads.claim_attempt('replay_planner', 60)
    current = host.mission_operation(claim, 'agent_mission_read', {}, operation_id='read')
    ref = next(ref for ref in current['available_equipment'] if ref['kind'] == 'capability')
    proposed = task(equipment=[ref])
    payload = ({'task': proposed} if name == 'agent_mission_prepare_task'
               else {'acceptance_criteria': ['Review the saved result'], 'tasks': [proposed]})
    arguments = {'expected_revision': current['revision'], **payload}
    accepted = host.mission_operation(claim, name, arguments, operation_id='accepted_model_operation')
    before = host.service.read_mission('enterprise', mission['mission_id'])
    checks = []
    def unavailable(*args):
        checks.append(args)
        return False
    host.service.admit_mission_reference = unavailable
    assert host.mission_operation(claim, name, arguments, operation_id='accepted_model_operation') == accepted
    assert checks == []
    # A new operation at the current revision must revalidate the registry.
    fresh = {**arguments, 'expected_revision': before['revision']}
    with pytest.raises(ContractError):
        host.mission_operation(claim, name, fresh, operation_id='new_invalid_operation')
    assert len(checks) == 1
    assert host.service.read_mission('enterprise', mission['mission_id']) == before
