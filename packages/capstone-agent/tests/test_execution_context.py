from copy import deepcopy
import json

import pytest

from capstone_agent.request_intent import IntentDecision, IntentRequest


def request(text='解释概念，然后翻译上一条回答'):
    return IntentRequest.from_document({
        'schema': 'capstone-intent-request/1', 'thread_id': 'thread_1',
        'turn_id': 'turn_1', 'attempt_id': 'attempt_1', 'instruction': text,
        'instruction_message_id': 'attempt_1:user', 'history_cutoff': 4,
        'messages': [{'message_id': 'previous_answer', 'role': 'assistant',
            'content': 'Previous committed text', 'turn_id': 'turn_0',
            'attempt_id': 'attempt_0', 'model_context_id': 'old_model', 'status': 'completed'}],
        'objects': [{'object_id': 'current_model'}, {'object_id': 'old_model'}],
        'capabilities': [{'capability_id': 'analysis', 'enabled': True, 'available': True}],
        'mode_hint': None,
    })


def goal(identity='g1', operation='answer', refs=None, dependencies=None, missing=None):
    return {'goal_id': identity, 'description': 'PRIVATE_DIAGNOSTIC prose',
        'operation': operation, 'message_refs': refs or ['attempt_1:user'],
        'object_refs': [], 'capability_refs': [], 'depends_on': dependencies or [],
        'missing_requirements': missing or []}


def decision(source, goals, clarification=None):
    return IntentDecision.from_document({'schema': 'capstone-intent-decision/1',
        'attempt_id': 'attempt_1', 'history_cutoff': 4, 'relationship': 'continuation',
        'goals': goals, 'clarification': clarification}, source)


@pytest.mark.parametrize('text,operation,refs,missing,clarification', [
    ('写一封邀请信', 'answer', ['attempt_1:user'], [], None),
    ('翻译上一条回答', 'rewrite', ['previous_answer'], [], None),
    ('解释这个专业概念', 'answer', ['attempt_1:user'], [], None),
    ('可用的功能有哪些', 'catalog_lookup', ['attempt_1:user'], [], None),
    ('查询最新外部信息', 'external_lookup', ['attempt_1:user'], ['PRIVATE_DIAGNOSTIC unavailable'], None),
    ('读取这个模型的结果', 'business_read', ['attempt_1:user'], [], None),
    ('运行当前模型的计算', 'business_execute', ['attempt_1:user'], [], None),
    ('比较前一个模型', 'answer', ['previous_answer'], [], 'PRIVATE_DIAGNOSTIC which comparison?'),
])
def test_general_scenario_projection_contains_only_execution_needs(text, operation, refs, missing, clarification):
    from capstone_agent.execution_context import execution_plan_for
    source = request(text)
    item = goal(operation=operation, refs=refs, missing=missing)
    item['instruction_excerpt'] = text
    plan = execution_plan_for(source, decision(source, [item], clarification))
    assert plan['schema'] == 'capstone-execution-plan/1'
    assert plan['goals'][0]['instruction_excerpt'] == text
    assert plan['goals'][0]['message_refs'] == refs
    assert plan['goals'][0]['operation'] == operation
    assert plan['goals'][0]['status'] == ('blocked' if missing or clarification else 'ready')
    assert 'PRIVATE_DIAGNOSTIC' not in json.dumps(plan)
    assert not {'description', 'missing_requirements', 'clarification'} & plan['goals'][0].keys()


def test_diagnostic_rewording_cannot_change_execution_input():
    from capstone_agent.execution_context import execution_plan_for
    source = request()
    first = goal(missing=['PRIVATE_DIAGNOSTIC first'])
    second = deepcopy(first)
    second.update(description='A different catalog dump', missing_requirements=['Another catalog dump'])
    assert execution_plan_for(source, decision(source, [first], 'First internal question')) == \
        execution_plan_for(source, decision(source, [second], 'Different internal question'))


def test_missing_input_blocks_dependents_but_preserves_independent_work():
    from capstone_agent.execution_context import execution_plan_for
    source = request('查询信息，用它计算，另外解释概念')
    lookup = goal('lookup', 'external_lookup', missing=['PRIVATE_DIAGNOSTIC no source'])
    dependent = goal('dependent', 'business_execute', dependencies=['lookup'])
    independent = goal('independent')
    lookup['instruction_excerpt'] = '查询信息'
    dependent['instruction_excerpt'] = '用它计算'
    independent['instruction_excerpt'] = '解释概念'
    plan = execution_plan_for(source, decision(source, [lookup, dependent, independent]))
    assert [item['status'] for item in plan['goals']] == ['blocked', 'blocked', 'ready']
    assert plan['executable_goal_ids'] == ['independent']
    assert plan['goals'][1]['blockers'] == [{'kind': 'dependency_not_ready', 'goal_ids': ['lookup']}]
    assert plan['goals'][0]['blockers'] == [{'kind': 'unresolved_requirement'}]
    dependent['depends_on'] = []
    assert execution_plan_for(source, decision(source, [lookup, dependent, independent])) != plan


def test_projection_preserves_source_and_model_references_without_granting_evidence():
    from capstone_agent.execution_context import execution_plan_for
    source = request()
    item = goal(refs=['previous_answer'])
    item['object_refs'] = ['old_model', 'current_model']
    plan = execution_plan_for(source, decision(source, [item]))
    assert plan['goals'][0]['object_refs'] == ['old_model', 'current_model']
    assert not {'results', 'result_refs', 'evidence_refs', 'messages'} & plan.keys()
    plan['goals'][0]['object_refs'].clear()
    assert execution_plan_for(source, decision(source, [item]))['goals'][0]['object_refs']


def test_projection_rejects_a_decision_bound_to_another_request():
    from capstone_agent.execution_context import execution_plan_for
    source = request()
    valid = decision(source, [goal()])
    changed = source.to_document()
    changed['history_cutoff'] = 5
    with pytest.raises(ValueError, match='identity and cutoff'):
        execution_plan_for(IntentRequest.from_document(changed), valid)


def test_task_excerpt_must_be_user_text_not_model_diagnostics():
    source = request()
    item = goal()
    item['instruction_excerpt'] = 'PRIVATE_DIAGNOSTIC inferred task'
    with pytest.raises(ValueError, match='instruction excerpt'):
        decision(source, [item])


def test_typed_clarification_state_does_not_depend_on_diagnostic_wording():
    from capstone_agent.execution_context import execution_plan_for
    source = request()
    document = decision(source, [goal()]).to_document()
    document.update(clarification_required=False, clarification='null')
    valid = IntentDecision.from_document(document, source)
    assert execution_plan_for(source, valid)['executable_goal_ids'] == ['g1']
    document.update(clarification_required=True, clarification=None)
    blocked = execution_plan_for(source, IntentDecision.from_document(document, source))
    assert blocked['goals'][0]['blockers'] == [{'kind': 'clarification_required'}]
    document['clarification_required'] = 'false'
    with pytest.raises(ValueError, match='clarification_required'):
        IntentDecision.from_document(document, source)
