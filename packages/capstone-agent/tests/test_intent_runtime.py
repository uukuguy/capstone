from dataclasses import replace
from types import SimpleNamespace
import time

import pytest

from capstone_agent.intent_runtime import IntentRuntimeFactory, intent_request_for_claim
from capstone_agent.request_intent import IntentDecision, IntentEngineIdentity, NodeControl
from capstone_agent.thread_service import InMemoryThreadService
from capstone_agent.thread_worker import run_pending_attempt


def claim():
    service = InMemoryThreadService.from_document({
        'schema': 'capstone-thread-snapshot/1', 'thread_id': 'thr_intent',
        'run': {'run_id': 'run_intent', 'state': 'open'},
        'active_model_context': {'id': 'ctx_test', 'model_id': 'ieee39',
            'model_revision': 'rev_1', 'implementation_family': 'pandapower',
            'selection_revision': 'sel_1'},
        'active_grid_page_id': 'page_test', 'current_attempt': None,
        'last_event_seq': 0, 'base_event_seq': 0,
    })
    service.submit_command({'schema': 'capstone-command/1', 'command_id': 'cmd_test',
        'idempotency_key': 'idem_test', 'thread_id': 'thr_intent', 'run_id': 'run_intent',
        'kind': 'send_auto', 'expected_event_seq': 0,
        'payload': {'text': '解释刚才的结论，然后翻译成英文'}})
    return service, service.claim_attempt('worker_test', 30)


class Recognizer:
    identity = IntentEngineIdentity('fixture', 'model', 'config_1')

    def recognize(self, request, control):
        control.checkpoint()
        doc = request.to_document()
        return IntentDecision.from_document({
            'schema': 'capstone-intent-decision/1', 'attempt_id': doc['attempt_id'],
            'history_cutoff': doc['history_cutoff'], 'relationship': 'continuation',
            'goals': [{'goal_id': 'g1', 'description': 'Translate previous answer',
                       'operation': 'rewrite', 'message_refs': [], 'object_refs': [],
                       'capability_refs': [], 'missing_requirements': []}],
            'clarification': None,
        }, request)


def test_hosted_intent_input_identifies_current_message_without_history():
    _, current = claim()
    assert current is not None
    document = intent_request_for_claim(current).to_document()
    assert document['messages'] == []
    assert document['instruction_message_id'] == current.attempt.attempt_id + ':user'


def test_retry_rebinds_current_message_identity_with_frozen_history():
    _, current = claim()
    assert current is not None
    frozen = []
    factory = IntentRuntimeFactory(lambda _: SimpleNamespace(), lambda: Recognizer(),
                                   lambda attempt, decision: SimpleNamespace())
    control = NodeControl(lambda: None, time.monotonic() + 5)
    factory.plan_intent(current, control, lambda claim, document: frozen.append(document) or document)
    retry = replace(current, attempt=replace(current.attempt, attempt_id='attempt_retry'))
    plan = factory.plan_intent(retry, control, lambda claim, document: frozen[0])
    document = plan.intent_request.to_document()
    assert document['attempt_id'] == 'attempt_retry'
    assert document['instruction_message_id'] == 'attempt_retry:user'
    assert document['messages'] == frozen[0]['request']['messages']
    assert frozen[0]['request']['instruction_message_id'] != 'attempt_retry:user'


def test_ordinary_semantics_bypass_domain_preparation_and_keep_model():
    service, current = claim()
    assert current is not None
    ordinary = []
    factory = IntentRuntimeFactory(
        lambda _: pytest.fail('ordinary request prepared a Domain Pack'),
        lambda: Recognizer(),
        lambda attempt, decision: ordinary.append((attempt, decision)) or SimpleNamespace(),
    )
    plan = factory.plan_intent(current, NodeControl(lambda: None, time.monotonic() + 5),
                               service.freeze_attempt_input)
    assert plan.route == 'ordinary'
    assert plan.intent_decision.to_document()['relationship'] == 'continuation'
    factory(replace(current, turn_plan=plan))
    assert ordinary[0][0].model_context == current.model_context


def test_intent_fault_never_falls_back_to_keywords():
    service, current = claim()
    assert current is not None
    class Broken(Recognizer):
        def recognize(self, request, control):
            raise RuntimeError('model unavailable')
    factory = IntentRuntimeFactory(lambda _: pytest.fail('executed'), lambda: Broken(),
                                   lambda *_: pytest.fail('executed'))
    with pytest.raises(RuntimeError, match='model unavailable'):
        factory.plan_intent(current, NodeControl(lambda: None, time.monotonic() + 5),
                            service.freeze_attempt_input)


def test_retry_refuses_changed_recognizer_configuration():
    service, current = claim()
    assert current is not None
    factory = IntentRuntimeFactory(lambda _: None, lambda: Recognizer(), lambda *_: None)
    control = NodeControl(lambda: None, time.monotonic() + 5)
    factory.plan_intent(current, control, service.freeze_attempt_input)
    class Changed(Recognizer):
        identity = IntentEngineIdentity('fixture', 'model', 'config_2')
    changed = IntentRuntimeFactory(lambda _: None, lambda: Changed(), lambda *_: None)
    with pytest.raises(ValueError, match='configuration'):
        changed.plan_intent(current, control, service.freeze_attempt_input)


def test_request_contains_shared_history_and_no_raw_model():
    _, current = claim()
    assert current is not None
    request = intent_request_for_claim(current).to_document()
    assert request['objects'][0]['object_id'] == 'ctx_test'
    assert request['instruction'] == current.instruction
    assert request['messages'] == []
    assert request['capabilities'] == []


def test_worker_records_semantics_before_ordinary_execution():
    service, current = claim()
    # Release this test's claimed Attempt by exercising the same worker body.
    from capstone_agent.thread_worker import _run_claimed_attempt
    from capstone_agent.harness import AdmittedAttemptAnswer
    events = []
    class Session:
        def start(self):
            events.append('execution')
        def prompt_and_wait(self, question, **kwargs):
            return '这是一段译文。'
        def stop(self):
            pass
        def admit_attempt(self, *args):
            return AdmittedAttemptAnswer('这是一段译文。', 'offline_information', 'general_knowledge')
    class Traced(Recognizer):
        def recognize(self, request, control):
            events.append('recognition')
            return super().recognize(request, control)
    factory = IntentRuntimeFactory(lambda _: pytest.fail('domain prepared'),
        lambda: Traced(), lambda *_: Session())
    result = _run_claimed_attempt(service, factory, current,
                                 SimpleNamespace(check=lambda: None), 30, None)
    assert result.status == 'completed'
    assert events == ['recognition', 'execution']
    saved = service.read_events('thr_intent', 0).events
    plan = next(event for event in saved if event.event_type == 'turn_plan_created')
    assert plan.payload['intent_decision']['goals'][0]['operation'] == 'rewrite'


def test_cancel_during_recognition_does_not_start_execution():
    service, current = claim()
    from capstone_agent.thread_worker import _run_claimed_attempt
    class Cancelled(Recognizer):
        def recognize(self, request, control):
            raise InterruptedError('cancelled')
    factory = IntentRuntimeFactory(lambda _: pytest.fail('business executed'),
        lambda: Cancelled(), lambda *_: pytest.fail('ordinary executed'))
    result = _run_claimed_attempt(service, factory, current,
                                 SimpleNamespace(check=lambda: None), 30, None)
    assert result.status == 'cancelled'


def test_result_resources_and_catalog_remain_at_original_cutoff():
    from capstone_agent.conversation_context import ConversationContext
    from capstone_agent.thread_service import PriorResultReference
    service, current = claim()
    history = ConversationContext.from_document({'history_cutoff': 0, 'truncated': False,
        'messages': [{'message_id': 'msg_old', 'role': 'assistant', 'content': 'Previous result',
                      'turn_id': 'turn_old', 'attempt_id': 'attempt_old',
                      'model_context_id': 'ctx_test', 'status': 'completed'}]})
    old = PriorResultReference('result:sha256:' + 'a' * 64, (), 'flow', 'attempt_old')
    later = PriorResultReference('result:sha256:' + 'b' * 64, (), 'flow', 'attempt_later')
    current = replace(current, conversation_context=history, prior_results=(old,),
                      application_catalog={'models': []})
    captured = []
    factory = IntentRuntimeFactory(lambda _: pytest.fail('domain'), lambda: Recognizer(),
                                   lambda attempt, _: captured.append(attempt) or SimpleNamespace())
    control = NodeControl(lambda: None, time.monotonic() + 5)
    factory.plan_intent(current, control, service.freeze_attempt_input)
    changed = replace(current, prior_results=(later,), application_catalog={'models': ['later']})
    plan = factory.plan_intent(changed, control, service.freeze_attempt_input)
    factory(replace(changed, turn_plan=plan))
    assert captured[0].prior_results == (old,)
    assert captured[0].application_catalog == {'models': []}


def test_wrapper_preserves_business_preparation_rollback_contract():
    class Business:
        rollback_selection_on_failure = True
        def __call__(self, claim):
            raise RuntimeError('preparation failed')
    assert IntentRuntimeFactory(Business(), lambda: Recognizer(), lambda *_: None).rollback_selection_on_failure
