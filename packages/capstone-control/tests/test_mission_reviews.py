from copy import deepcopy
import pytest

from capstone_control.service import InvalidTransition
from test_missions import service, create, command, task


def plan(control):
    mission = create(control, acceptance_criteria=['Inspect the saved result'])
    mission = command(control,mission,'prepare_task',{'task':task()},'prepare')
    return command(control,mission,'ready',{},'ready')


def complete_task(control,mission,number=1,**delivery_fields):
    mission = command(control,mission,'delegate_next',{},'dispatch_'+str(number))
    current = next(t for t in mission['tasks'] if t['state']=='dispatching')
    control.deliver('team',mission['mission_id'],current['delegation']['delegation_id'],
        {'thread_id':'task_thread_'+str(number),'work_id':'task_work_'+str(number)},
        dict(answer_ref='answer_'+str(number),products=[],status='completed',**delivery_fields))
    goal = control.read('team',mission['mission_id'])
    control.command('team',dict(schema='capstone-control-command/1',operation_id='verify_'+str(number),
        goal_id=mission['mission_id'],expected_revision=goal['revision'],kind='verify_task',
        payload=dict(task_id=current['task_id'],delivery_revision=1,checks=[dict(name='Saved answer checked',passed=True)])))
    return control.read_mission('team',mission['mission_id'])


def test_verified_authority_source_reaches_review_and_declared_dependent():
    control = service()
    source = dict(thread_id='task_thread_1', work_id='task_work_1',
                  attempt_id='attempt_1', answer_ref='answer_1')
    mission = complete_task(control, plan(control), authority_source=source, gateway_source=source)
    intent = control.pending_mission_reviews('team')[0]
    reserved = control.reserve_mission_review('team', mission['mission_id'], intent['review_id'])
    assert reserved['boundary']['tasks'][0]['delivery']['authority_source'] == source
    assert reserved['boundary']['tasks'][0]['delivery']['gateway_source'] == source
    control.acknowledge_mission_review('team', mission['mission_id'], intent['review_id'],
        dict(thread_id='thread_1', work_id='origin_work', attempt_id='review_1'))
    mission = control.read_mission('team', mission['mission_id'])
    second = task('task_2')
    second['depends_on'] = ['task_1']
    mission = command(control, mission, 'prepare_task', {'task': second}, 'second')
    mission = command(control, mission, 'ready', {}, 'ready_second')
    control.finish_mission_review('team', mission['mission_id'], intent['review_id'],
                                  attempt_id='review_1', phase='completed')
    mission = control.read_mission('team', mission['mission_id'])
    mission = command(control, mission, 'delegate_next', {}, 'dispatch_2')
    delegated = mission['tasks'][1]['delegation']['delegation_id']
    request = control.delegation_request('team', mission['mission_id'], delegated)
    assert request['context_authority_sources'] == [source]
    assert request['context_gateway_sources'] == [source]


def test_two_phase_organizer_uses_boundaries_and_explicit_plan_conclusion():
    control = service()
    mission = complete_task(control,plan(control))
    assert mission['state']=='waiting_review'
    assert mission['plan_concluded'] is False
    intent = control.pending_mission_reviews('team')[0]
    reserved = control.reserve_mission_review('team',mission['mission_id'],intent['review_id'])
    assert reserved==control.reserve_mission_review('team',mission['mission_id'],intent['review_id'])
    binding=dict(thread_id='thread_1',work_id='origin_work',attempt_id='review_attempt_1')
    control.acknowledge_mission_review('team',mission['mission_id'],intent['review_id'],binding)
    mission=control.read_mission('team',mission['mission_id'])
    second=task('task_2');second['depends_on']=['task_1']
    mission=command(control,mission,'prepare_task',{'task':second},'second')
    mission=command(control,mission,'ready',{},'ready_second')
    control.finish_mission_review('team',mission['mission_id'],intent['review_id'],attempt_id='review_attempt_1',phase='completed')
    mission=control.read_mission('team',mission['mission_id'])
    mission=complete_task(control,mission,2)
    assert mission['state']=='waiting_review' and len(control.pending_mission_reviews('team'))==1
    mission=command(control,mission,'conclude_plan',{'plan_revision':mission['plan_revision'],'summary':'The inspected saved results meet the current objective.','criteria_verdicts':[dict(criterion_index=0,status='met',explanation='Inspected the saved Task answer.',evidence=[dict(kind='answer',task_id='task_2',answer_ref='answer_2')])]},'conclude')
    assert mission['state']=='delivered' and mission['plan_concluded'] is True
    assert mission['plan_conclusion']['plan_revision']==mission['plan_revision']


def test_interrupted_review_can_settle_recovered_delivery_under_original_binding():
    control = service()
    mission = complete_task(control, plan(control))
    mission_id = mission['mission_id']
    intent = control.pending_mission_reviews('team')[0]
    review_id = intent['review_id']
    control.reserve_mission_review('team', mission_id, review_id)
    binding = dict(thread_id=intent['origin']['thread_id'], work_id='work_review',
                   attempt_id='review_attempt_1')
    control.acknowledge_mission_review('team', mission_id, review_id, binding)
    control.finish_mission_review('team', mission_id, review_id,
                                  attempt_id=binding['attempt_id'], phase='interrupted')
    assert control.pending_mission_reviews('team') == [intent]
    recovered = control.finish_mission_review('team', mission_id, review_id,
        attempt_id=binding['attempt_id'], phase='completed', recovered=True)
    assert recovered['state'] == 'no_progress'
    assert control.pending_mission_reviews('team') == []
    assert control.finish_mission_review('team', mission_id, review_id,
        attempt_id=binding['attempt_id'], phase='completed', recovered=True) == recovered


def test_review_restart_budget_no_progress_and_stops_are_durable():
    control=service()
    mission=complete_task(control,plan(control))
    intent=control.pending_mission_reviews('team')[0]
    reserved=control.reserve_mission_review('team',mission['mission_id'],intent['review_id'])
    from capstone_control.service import ControlService
    restarted=ControlService(control.store,now=control.now)
    assert restarted.read_mission_review('team',mission['mission_id'],intent['review_id'])==reserved
    binding=dict(thread_id='thread_1',work_id='origin_work',attempt_id='review_attempt_1')
    restarted.acknowledge_mission_review('team',mission['mission_id'],intent['review_id'],binding)
    result=restarted.finish_mission_review('team',mission['mission_id'],intent['review_id'],attempt_id='review_attempt_1',phase='completed')
    assert result['state']=='no_progress'
    assert restarted.pending_mission_reviews('team')==[]
    assert restarted.finish_mission_review('team',mission['mission_id'],intent['review_id'],attempt_id='review_attempt_1',phase='completed')==result
    assert restarted.read_mission('team',mission['mission_id'])['organizer']['reviews_admitted']==1


def test_plan_conclusion_cannot_certify_empty_or_unverified_tasks():
    control=service();mission=create(control)
    with pytest.raises(InvalidTransition):
        command(control,mission,'conclude_plan',{'plan_revision':mission['plan_revision'],'summary':'Done','criteria_verdicts':[]},'empty')
    mission=command(control,mission,'prepare_task',{'task':task()},'prepare')
    with pytest.raises(InvalidTransition):
        command(control,mission,'conclude_plan',{'plan_revision':mission['plan_revision'],'summary':'Done','criteria_verdicts':[]},'unverified')


def test_running_observation_sequences_do_not_schedule_more_reviews():
    control=service();mission=complete_task(control,plan(control))
    intent=control.pending_mission_reviews('team')[0]
    control.reserve_mission_review('team',mission['mission_id'],intent['review_id'])
    control.acknowledge_mission_review('team',mission['mission_id'],intent['review_id'],dict(thread_id='thread_1',work_id='origin_work',attempt_id='review_1'))
    mission=control.read_mission('team',mission['mission_id'])
    mission=command(control,mission,'prepare_task',{'task':task('task_2')},'second')
    mission=command(control,mission,'ready',{},'second_ready')
    control.finish_mission_review('team',mission['mission_id'],intent['review_id'],attempt_id='review_1',phase='completed')
    mission=control.read_mission('team',mission['mission_id'])
    mission=command(control,mission,'delegate_next',{},'dispatch_2')
    delegated=mission['tasks'][1]['delegation']
    control.bind('team',mission['mission_id'],delegated['delegation_id'],dict(thread_id='task_thread_2',work_id='task_work_2'))
    for sequence in range(20):
        control.observe('team',mission['mission_id'],delegated['delegation_id'],dict(sequence=sequence,state='running',summary='Live progress '+str(sequence),delivery=None))
        assert control.pending_mission_reviews('team')==[]
    assert control.read_mission('team',mission['mission_id'])['organizer']['reviews_admitted']==1


def test_pending_boundaries_coalesce_and_budget_blocks_new_model_admission():
    control=service();mission=create(control,max_organizer_reviews=1,acceptance_criteria=['Saved'])
    mission=command(control,mission,'prepare_task',{'task':task()},'prepare')
    mission=command(control,mission,'ready',{},'ready')
    mission=complete_task(control,mission)
    intent=control.pending_mission_reviews('team')[0]
    assert intent['boundary']['tasks'][0]['state']=='verified'
    control.reserve_mission_review('team',mission['mission_id'],intent['review_id'])
    control.acknowledge_mission_review('team',mission['mission_id'],intent['review_id'],dict(thread_id='thread_1',work_id='origin_work',attempt_id='review_1'))
    mission=control.read_mission('team',mission['mission_id'])
    mission=command(control,mission,'prepare_task',{'task':task('task_2')},'second')
    mission=command(control,mission,'ready',{},'second_ready')
    control.finish_mission_review('team',mission['mission_id'],intent['review_id'],attempt_id='review_1',phase='completed')
    mission=complete_task(control,control.read_mission('team',mission['mission_id']),2)
    second=control.pending_mission_reviews('team')[0]
    assert second['review_id']!=intent['review_id']
    assert control.reserve_mission_review('team',mission['mission_id'],second['review_id']) is None
    assert control.read_mission('team',mission['mission_id'])['organizer']['reviews_admitted']==1


def test_explicit_pause_and_expired_deadline_prevent_review_admission():
    control=service();mission=complete_task(control,plan(control))
    intent=control.pending_mission_reviews('team')[0]
    reserved=control.reserve_mission_review('team',mission['mission_id'],intent['review_id'])
    mission=control.read_mission('team',mission['mission_id'])
    command(control,mission,'pause',{},'pause')
    with pytest.raises(InvalidTransition):
        control.read_mission_review('team',mission['mission_id'],reserved['review_id'])
    assert control.reserve_mission_review('team',mission['mission_id'],reserved['review_id']) is None
    binding=dict(thread_id='thread_1',work_id='origin_work',attempt_id='review_1')
    control.acknowledge_mission_review('team',mission['mission_id'],reserved['review_id'],binding)
    control.finish_mission_review('team',mission['mission_id'],reserved['review_id'],attempt_id='review_1',phase='cancelled')
    assert control.pending_mission_reviews('team')==[]
    control=service();mission=complete_task(control,plan(control));intent=control.pending_mission_reviews('team')[0]
    from datetime import timedelta
    current=control.now();control.now=lambda:current+timedelta(days=2)
    assert control.reserve_mission_review('team',mission['mission_id'],intent['review_id']) is None


def test_explicit_pending_removal_preserves_history_and_remaining_dependencies():
    control=service();mission=plan(control)
    mission=command(control,mission,'prepare_task',{'task':task('task_2')},'second')
    mission=command(control,mission,'update_plan',dict(acceptance_criteria=['Saved'],tasks=[],removed_task_ids=['task_2']),'remove')
    assert [t['task_id'] for t in mission['tasks']]==['task_1']
    assert mission['history'][-1]['tasks'][0]['task_id']=='task_2'
    with pytest.raises(InvalidTransition):
        command(control,mission,'prepare_task',{'task':task('task_2')},'reuse')
    third=task('task_3');third['depends_on']=['task_1']
    mission=command(control,mission,'prepare_task',{'task':third},'third')
    from capstone_control.contracts import ContractError
    with pytest.raises(ContractError):
        command(control,mission,'update_plan',dict(acceptance_criteria=['Saved'],tasks=[],removed_task_ids=['task_1']),'dangling')
    assert len(control.read_mission('team',mission['mission_id'])['tasks'])==2


def test_remove_racing_dispatch_has_one_atomic_outcome_and_no_retired_execution():
    from concurrent.futures import ThreadPoolExecutor
    from capstone_control.service import Conflict
    control=service();mission=plan(control)
    def act(kind):
        payload={} if kind=='delegate_next' else dict(acceptance_criteria=['Saved'],tasks=[],removed_task_ids=['task_1'])
        try:
            return command(control,mission,kind,payload,kind)
        except Conflict:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(act,['delegate_next','update_plan']))
    assert sum(result is not None for result in results)==1
    current=control.read_mission('team',mission['mission_id'])
    if not current['tasks']:
        assert current['state']=='planning' and control.pending('team')==[]
        with pytest.raises(InvalidTransition):
            command(control,current,'delegate_next',{},'after_removal')
    else:
        assert current['tasks'][0]['state']=='dispatching'


def test_explicit_resume_after_no_progress_creates_one_new_budgeted_review():
    control=service();mission=complete_task(control,plan(control))
    first=control.pending_mission_reviews('team')[0]
    control.reserve_mission_review('team',mission['mission_id'],first['review_id'])
    control.acknowledge_mission_review('team',mission['mission_id'],first['review_id'],dict(thread_id='thread_1',work_id='origin_work',attempt_id='review_1'))
    control.finish_mission_review('team',mission['mission_id'],first['review_id'],attempt_id='review_1',phase='completed')
    before=control.read_mission('team',mission['mission_id'])
    resumed=command(control,before,'resume',{},'explicit_resume')
    assert command(control,before,'resume',{},'explicit_resume')==resumed
    assert resumed['state']=='waiting_review'
    second,=control.pending_mission_reviews('team')
    assert second['review_id']!=first['review_id']
    assert second['boundary']['digest']==first['boundary']['digest']
    control.reserve_mission_review('team',mission['mission_id'],second['review_id'])
    assert control.read_mission('team',mission['mission_id'])['organizer']['reviews_admitted']==2
    assert control.reserve_mission_review('team',mission['mission_id'],second['review_id'])==second


def test_paused_without_pending_tasks_resumes_review_instead_of_empty_dispatch():
    control=service();mission=complete_task(control,plan(control))
    mission=command(control,mission,'pause',{},'pause')
    mission=command(control,mission,'resume',{},'resume')
    assert mission['state']=='waiting_review' and control.pending('team')==[]
    assert len(control.pending_mission_reviews('team'))==1


def test_ready_and_conclusion_reject_incomplete_or_nonexecutable_plan():
    control=service();mission=complete_task(control,plan(control))
    with pytest.raises(InvalidTransition,match='conclude'):
        command(control,mission,'ready',{},'no_work')
    mission=command(control,mission,'update_plan',dict(acceptance_criteria=[],tasks=[]),'clear_criteria')
    with pytest.raises(InvalidTransition):
        command(control,mission,'conclude_plan',dict(plan_revision=mission['plan_revision'],summary='Done',criteria_verdicts=[]),'missing_criteria')
    assert control.read_mission('team',mission['mission_id'])['state']=='waiting_review'


def test_trusted_release_refunds_only_unbound_reservation_and_resume_has_new_identity():
    control=service();mission=complete_task(control,plan(control))
    first=control.pending_mission_reviews('team')[0]
    control.reserve_mission_review('team',mission['mission_id'],first['review_id'])
    mission=control.read_mission('team',mission['mission_id'])
    command(control,mission,'pause',{},'pause')
    assert control.release_mission_review('team',mission['mission_id'],first['review_id'])==first
    assert control.release_mission_review('team',mission['mission_id'],first['review_id'])==first
    mission=control.read_mission('team',mission['mission_id'])
    assert mission['organizer']['reviews_admitted']==0
    with pytest.raises(InvalidTransition):
        control.read_mission_review('team',mission['mission_id'],first['review_id'])
    mission=command(control,mission,'resume',{},'explicit_resume')
    second,=control.pending_mission_reviews('team')
    assert second['review_id']!=first['review_id']
    control.reserve_mission_review('team',mission['mission_id'],second['review_id'])
    control.acknowledge_mission_review('team',mission['mission_id'],second['review_id'],dict(thread_id='thread_1',work_id='origin_work',attempt_id='real_review'))
    with pytest.raises(InvalidTransition):
        control.release_mission_review('team',mission['mission_id'],second['review_id'])
    assert control.read_mission('team',mission['mission_id'])['organizer']['reviews_admitted']==1


def test_missing_required_reference_reaches_review_as_failed_delivery():
    control = service()
    mission = create(control, acceptance_criteria=['Read the source operation'])
    producer = {**task(), 'required_reference_sources': ['gateway_source']}
    consumer = {**task('task_2'), 'depends_on': ['task_1']}
    mission = command(control, mission, 'update_plan',
        {'acceptance_criteria': ['Read the source operation'], 'tasks': [producer, consumer]}, 'plan')
    mission = command(control, mission, 'ready', {}, 'ready')
    mission = command(control, mission, 'delegate_next', {}, 'dispatch')
    delegation = mission['tasks'][0]['delegation']['delegation_id']
    binding = {'thread_id': 'task_thread', 'work_id': 'task_work'}
    answer = {'answer_ref': 'saved_answer', 'products': [], 'status': 'completed'}

    control.deliver('team', mission['mission_id'], delegation, binding, answer)
    control.deliver('team', mission['mission_id'], delegation, binding, answer)

    intent = control.pending_mission_reviews('team')[0]
    failed, pending = intent['boundary']['tasks']
    assert failed['state'] == 'failed'
    assert failed['failure_reason'] == 'required_reference_receipt_missing'
    assert failed['delivery']['answer_ref'] == 'saved_answer'
    assert pending['state'] == 'pending'


def test_partial_conclusion_preserves_dependency_ready_work_after_failure():
    control = service()
    mission = create(control, acceptance_criteria=['Read the source operation'])
    producer = {**task(), 'required_reference_sources': ['gateway_source']}
    consumer = {**task('task_2'), 'depends_on': ['task_1']}
    independent = task('task_3')
    mission = command(control, mission, 'update_plan',
        {'acceptance_criteria': ['Read the source operation'],
         'tasks': [producer, consumer, independent]}, 'plan')
    mission = command(control, mission, 'ready', {}, 'ready')
    mission = command(control, mission, 'delegate_next', {}, 'dispatch')
    delegation = mission['tasks'][0]['delegation']['delegation_id']
    control.deliver('team', mission['mission_id'], delegation,
        {'thread_id': 'task_thread', 'work_id': 'task_work'},
        {'answer_ref': 'saved_answer', 'products': [], 'status': 'completed'})
    mission = control.read_mission('team', mission['mission_id'])
    conclusion = {'plan_revision': mission['plan_revision'], 'summary': 'Source unavailable.',
                  'criteria_verdicts': [{'criterion_index': 0, 'status': 'not_met',
                                         'explanation': 'No source receipt.', 'evidence': []}]}
    with pytest.raises(InvalidTransition, match='dependency-ready'):
        command(control, mission, 'conclude_plan', conclusion, 'early_partial')
    mission = command(control, mission, 'ready', {}, 'ready_independent')
    mission = complete_task(control, mission, number=3)
    assert [t['state'] for t in mission['tasks']] == ['failed', 'pending', 'verified']
    mission = command(control, mission, 'conclude_plan', conclusion, 'final_partial')
    assert mission['state'] == 'delivered' and mission['reason'] == 'partial_delivery'


def test_wait_rejects_dependent_work_without_an_executable_predecessor():
    control = service()
    criteria = ['Read the source']
    mission = create(control, acceptance_criteria=criteria)
    producer = {**task(), 'required_reference_sources': ['gateway_source']}
    consumer = {**task('task_2'), 'depends_on': ['task_1']}
    mission = command(control, mission, 'update_plan',
                      {'acceptance_criteria': criteria, 'tasks': [producer, consumer, task('task_3')]}, 'plan')
    mission = command(control, mission, 'ready', {}, 'ready')
    mission = command(control, mission, 'delegate_next', {}, 'dispatch')
    control.deliver('team', mission['mission_id'], mission['tasks'][0]['delegation']['delegation_id'],
        {'thread_id': 'task_thread', 'work_id': 'task_work'},
        {'answer_ref': 'saved_answer', 'products': [], 'status': 'completed'})
    mission = control.read_mission('team', mission['mission_id'])
    mission = command(control, mission, 'ready', {}, 'ready_independent')
    mission = command(control, mission, 'update_plan',
                      {'acceptance_criteria': criteria, 'tasks': [], 'removed_task_ids': ['task_3']}, 'drop_independent')
    assert [item['state'] for item in mission['tasks']] == ['failed', 'pending']
    with pytest.raises(InvalidTransition, match='executable or active'):
        command(control, mission, 'wait', {'until': 'task_boundary', 'reason': 'Wait for the dependent'}, 'wait')
    conclusion = {'plan_revision': mission['plan_revision'], 'summary': 'The required source was unavailable.',
                  'criteria_verdicts': [{'criterion_index': 0, 'status': 'not_met',
                                         'explanation': 'Missing source receipt.', 'evidence': []}]}
    mission = command(control, mission, 'conclude_plan', conclusion, 'partial')
    assert mission['state'] == 'delivered' and mission['reason'] == 'partial_delivery'


def test_missing_required_file_is_a_saved_failure_and_queues_review():
    control = service()
    mission = create(control, acceptance_criteria=['Save the requested file'])
    mission = command(control, mission, 'prepare_task',
        {'task': task(required_products=['required.txt'])}, 'prepare')
    mission = command(control, mission, 'ready', {}, 'ready')
    mission = command(control, mission, 'delegate_next', {}, 'dispatch')
    delegation = mission['tasks'][0]['delegation']['delegation_id']
    control.deliver('team', mission['mission_id'], delegation,
        {'thread_id': 'task_thread', 'work_id': 'task_work'},
        {'answer_ref': 'saved_answer', 'products': [], 'status': 'completed'})
    intent = control.pending_mission_reviews('team')[0]
    saved = intent['boundary']['tasks'][0]
    assert saved['state'] == 'failed'
    assert saved['failure_reason'] == 'required_product_missing'
    assert saved['delivery']['answer_ref'] == 'saved_answer'



def test_partial_child_goal_keeps_saved_results_without_certifying_the_task():
    control = service()
    mission = create(control, acceptance_criteria=['Verify the child result'])
    child = {**task(), 'mode': 'goal', 'max_attempts': 4}
    mission = command(control, mission, 'prepare_task', {'task': child}, 'prepare')
    mission = command(control, mission, 'ready', {}, 'ready')
    mission = command(control, mission, 'delegate_next', {}, 'dispatch')
    delegation = mission['tasks'][0]['delegation']['delegation_id']
    control.deliver('team', mission['mission_id'], delegation,
        {'thread_id': 'task_thread', 'work_id': 'task_work'},
        {'answer_ref': 'saved_answer', 'products': [], 'status': 'completed', 'outcome': 'partial'})
    task_result = control.pending_mission_reviews('team')[0]['boundary']['tasks'][0]
    assert task_result['state'] == 'failed'
    assert task_result['failure_reason'] == 'child_goal_partial_delivery'
    assert task_result['delivery']['answer_ref'] == 'saved_answer'
