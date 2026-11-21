from copy import deepcopy

import pytest

from capstone_control.contracts import ContractError
from capstone_control.service import Conflict, InvalidTransition
from test_missions import service, create, command, task


PRODUCT = dict(artifact_id='file_original', version=1, sha256='a' * 64)


def verified(control, criteria=None, products=None):
    mission = create(control, acceptance_criteria=criteria or ['Original saved'])
    mission = command(control, mission, 'prepare_task', {'task': task()}, 'prepare')
    mission = command(control, mission, 'ready', {}, 'ready')
    mission = command(control, mission, 'delegate_next', {}, 'dispatch')
    delegation = mission['tasks'][0]['delegation']['delegation_id']
    control.deliver('team', mission['mission_id'], delegation,
        {'thread_id': 'child_thread', 'work_id': 'child_work'},
        dict(answer_ref='answer_saved', products=[deepcopy(PRODUCT)] if products is None else products, status='completed'))
    goal = control.read('team', mission['mission_id'])
    control.command('team', dict(schema='capstone-control-command/1', operation_id='verify',
        goal_id=goal['goal_id'], expected_revision=goal['revision'], kind='verify_task',
        payload=dict(task_id='task_1', delivery_revision=1, checks=[dict(name='Saved bytes verified', passed=True)])))
    return control.read_mission('team', mission['mission_id'])


def verdict(index=0, status='met', evidence=None):
    return dict(criterion_index=index, status=status, explanation='Observed the current saved result.',
        evidence=([dict(kind='product', task_id='task_1', artifact_id='file_original', sha256='a' * 64)]
                  if evidence is None and status == 'met' else evidence or []))


def conclusion(mission, verdicts):
    return dict(plan_revision=mission['plan_revision'], summary='Actual acceptance assessment.', criteria_verdicts=verdicts)


def accept(control, mission, operation='accept'):
    return control.command('team', dict(schema='capstone-control-command/1', operation_id=operation,
        goal_id=mission['mission_id'], expected_revision=mission['revision'], kind='accept', payload={'products': [product for task in mission['tasks'] for product in task['delivery']['products']]}))


def test_partial_conclusion_delivers_saved_work_and_can_be_replanned():
    control = service(); mission = verified(control, ['Original saved', 'Report actually verified'])
    partial = [verdict(), verdict(1, 'not_met')]
    mission = command(control, mission, 'conclude_plan', conclusion(mission, partial), 'partial')
    assert mission['state'] == 'delivered' and mission['reason'] == 'partial_delivery'
    assert mission['plan_concluded'] is False
    assert mission['plan_conclusion']['criteria_verdicts'] == partial
    assert mission['organizer']['suspended'] is True
    assert control.pending_mission_reviews('team') == []
    assert control.store.active_missions_for_thread('team', mission['origin']['thread_id']) == []
    with pytest.raises(InvalidTransition):
        accept(control, mission)
    mission = command(control, mission, 'update_plan', {'acceptance_criteria': ['Original saved'], 'tasks': []}, 'user_adjustment')
    mission = command(control, mission, 'conclude_plan', conclusion(mission, [verdict()]), 'reassess')
    assert mission['state'] == 'delivered' and mission['plan_concluded'] is True
    assert accept(control, mission, 'user_accept')['goal']['state'] == 'accepted'


@pytest.mark.parametrize('bad', [[], [verdict(), verdict()], [verdict(1)], [verdict(True)],
    [{**verdict(), 'explanation': ' '}], [{**verdict(), 'status': []}], [verdict(evidence=[])],
    [verdict(evidence=[dict(kind='product', task_id='task_1', artifact_id='forged', sha256='a'*64)])],
    [verdict(evidence=[dict(kind='product', task_id='task_1', artifact_id='file_original', sha256='b'*64)])],
    [verdict(evidence=[dict(kind='answer', task_id='task_1', answer_ref='forged')])]])
def test_uncovered_duplicate_and_forged_conclusions_are_rejected_without_state_change(bad):
    control = service(); mission = verified(control)
    with pytest.raises((ContractError, Conflict, InvalidTransition)):
        command(control, mission, 'conclude_plan', conclusion(mission, bad), 'bad')
    assert control.read_mission('team', mission['mission_id']) == mission


def test_unknown_is_not_satisfied_and_exact_saved_answer_can_support_a_later_assessment():
    control = service(); mission = verified(control, products=[])
    mission = command(control, mission, 'conclude_plan', conclusion(mission, [verdict(status='unknown')]), 'unknown')
    assert mission['state'] == 'delivered' and mission['reason'] == 'partial_delivery' and not mission['plan_concluded']
    mission = command(control, mission, 'update_plan', {'acceptance_criteria': ['Original saved'], 'tasks': []}, 'reopen')
    proof = dict(kind='answer', task_id='task_1', answer_ref='answer_saved')
    mission = command(control, mission, 'conclude_plan', conclusion(mission, [verdict(evidence=[proof])]), 'answer_assessed')
    assert mission['plan_concluded'] and mission['state'] == 'delivered'


def test_stale_revision_and_legacy_opaque_conclusion_cannot_authorize_acceptance():
    control = service(); mission = verified(control)
    payload = conclusion(mission, [verdict()]); payload['plan_revision'] -= 1
    with pytest.raises((ContractError, Conflict)):
        command(control, mission, 'conclude_plan', payload, 'stale')
    def old_record(goal):
        goal['_mission']['plan_conclusion'] = dict(plan_revision=goal['_mission']['plan_revision'], summary='Old opaque done', actor='agent:old')
        goal['state'] = 'delivered'
        return goal, None
    control.store.transact('team', mission['mission_id'], old_record)
    legacy = control.read_mission('team', mission['mission_id'])
    assert legacy['plan_concluded'] is False
    assert legacy['plan_conclusion']['summary'] == 'Old opaque done'
    with pytest.raises(InvalidTransition):
        accept(control, legacy)


def test_partial_conclusion_cannot_hide_a_child_that_is_still_waiting():
    control = service(); mission = create(control, acceptance_criteria=['Saved result'])
    mission = command(control, mission, 'prepare_task', {'task': task()}, 'prepare')
    mission = command(control, mission, 'ready', {}, 'ready')
    mission = command(control, mission, 'delegate_next', {}, 'dispatch')
    delegation = mission['tasks'][0]['delegation']['delegation_id']
    control.bind('team', mission['mission_id'], delegation, {'thread_id': 'child_thread', 'work_id': 'child_work'})
    control.observe('team', mission['mission_id'], delegation,
        dict(sequence=1, state='waiting', summary='Input is required by the active child.', delivery=None))
    mission = control.read_mission('team', mission['mission_id'])
    with pytest.raises(InvalidTransition):
        command(control, mission, 'conclude_plan', conclusion(mission, [verdict(status='unknown')]), 'partial')
    assert control.read_mission('team', mission['mission_id']) == mission
