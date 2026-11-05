"""A governed research turn with no model still gets one intent decision."""
from dataclasses import replace
import time

import pytest

from capstone_agent.harness import AdmittedAttemptAnswer
from capstone_agent.intent_runtime import (
    DOMAIN_EXECUTOR_UNAVAILABLE, DOMAIN_EXECUTOR_UNREGISTERED, UNSCOPED_DOMAIN_GAP)
from capstone_agent.native_hosted_worker import native_runtime_factory
from capstone_agent.request_intent import IntentDecision, IntentEngineIdentity, NodeControl
from capstone_agent.thread_service import InMemoryThreadService
from capstone_agent.thread_worker import run_pending_attempt
from test_enterprise_normal_chat import native_executor
from test_thread_postgres import _snapshot
from test_thread_work_execution import command

INSTRUCTION = '建立潮流算法基准平台并复现病态11节点算例'
DOMAIN_CAPABILITY = 'pandapower-static-analysis@1.0.0'
PYPSA_CAPABILITY = 'pypsa-dispatch@1.0.0'


def governed_executor():
    from capstone_agent.native_task_context import research_policy_capabilities
    executor = native_executor()
    executor.capability.update({
        'research_bridge_schemas': ['capstone-research-bridge/1'],
        'delivery_review_schemas': ['capstone-delivery-review/1'],
        'research_graph_schemas': ['capstone-enterprise-graph/2'],
        'research_policy_profiles': research_policy_capabilities(),
    })
    executor.execute_with_research = lambda request, control, emit, bridge: executor.execute(request, control, emit)
    return executor


def open_store(executor, *, session_type=None):
    snapshot = replace(_snapshot('thr_unscoped'), active_model_context=None, active_grid_page_id=None,
                       minimum_protocol_version=2)
    store = InMemoryThreadService(snapshot)
    if session_type is not None:
        store._snapshot = replace(store._snapshot, session_type=session_type)
    store.set_native_executor(executor)
    return store


def goal(goal_id, operation, excerpt=None, refs=('general-pi',)):
    document = {'goal_id': goal_id, 'description': 'Untrusted plan prose', 'operation': operation,
                'message_refs': [], 'object_refs': [], 'capability_refs': list(refs),
                'missing_requirements': [], 'depends_on': []}
    if excerpt is not None:
        document['instruction_excerpt'] = excerpt
    return document


class Gate:
    def __init__(self, goals):
        self.goals = goals
        self.recognitions = 0
        self.requests = []
        self.identity = IntentEngineIdentity('fixture', 'model', 'config_1')

    def recognize(self, request, control):
        control.checkpoint()
        self.recognitions += 1
        document = request.to_document()
        self.requests.append(document)
        return IntentDecision.from_document({
            'schema': 'capstone-intent-decision/1', 'attempt_id': document['attempt_id'],
            'history_cutoff': document['history_cutoff'], 'relationship': 'independent',
            'goals': self.goals, 'clarification': None,
        }, request)


def publish_domain(store, *, available=True, families=('pandapower',)):
    models, profiles = [], []
    for family in families:
        models.append({
            'model_id': family + '-case', 'authority_model_ref': family + ':case',
            'display_name': family, 'diagram_provider_id': family,
            'implementation_family': family, 'available': available if family == 'pandapower' else True,
        })
        profile_id = 'pandapower-static-analysis' if family == 'pandapower' else 'pypsa-dispatch'
        profiles.append({
            'profile_id': profile_id, 'profile_version': '1.0.0', 'display_name': family,
            'implementation_families': [family],
        })
    store.set_catalog_context({
        'schema': 'capstone-thread-catalog/1', 'models': models, 'profiles': profiles,
    })


class DomainRuntime:
    """A domain executor that does not require an open model."""

    def __init__(self):
        self.claims = []

    def __call__(self, claim):
        self.claims.append(claim)
        return self

    def start(self):
        return None

    def stop(self):
        return None

    def prompt(self, question, *, on_event, correlation_id=None, on_heartbeat=None):
        on_event({
            'event_type': 'tool_completed', 'runtime_mode': 'capstone', 'visibility': 'public',
            'payload': {'tool_name': 'powerflow', 'tool_call_id': 'call-1', 'ok': True,
                        'evidence_refs': ['evidence-domain-1']},
        })
        return 'domain-result'

    def admit_attempt(self, claim, answer, result_refs, evidence_refs, events):
        del claim, answer, result_refs, events
        return AdmittedAttemptAnswer('domain-result', 'authority_backed', 'lineage_verified', (), ('evidence-domain-1',))


def submit(store, name='powerflow'):
    receipt = store.submit_command(command(store, 'thr_unscoped', 'send_message', name,
                                            payload={'text': INSTRUCTION}))
    assert receipt.status == 'accepted'
    return receipt


def failed_detail(store):
    return [event.payload for event in store.read_events('thr_unscoped', 0).events
            if event.event_type == 'attempt_failed']


def test_external_lookup_runs_while_public_network_stays_closed(tmp_path):
    executor = governed_executor()
    store = open_store(executor)
    submit(store)
    gate = Gate([goal('news', 'external_lookup', refs=('general-pi',))])
    result = run_pending_attempt(store, native_runtime_factory(
        executor, research_root=tmp_path, recognizer_factory=lambda: gate, unscoped_intent=True),
        worker_id='native', implementation_family='native')
    assert result.status == 'completed', failed_detail(store)
    assert executor.requests[0].instruction == INSTRUCTION
    assert executor.requests[0].native_context['policy']['external_lookup_enabled'] is False
    decision = next(event.payload['intent_decision'] for event in store.read_events('thr_unscoped', 0).events
                    if event.event_type == 'turn_plan_created')
    assert decision['goals'][0]['operation'] == 'external_lookup'


def test_closed_native_factory_does_not_classify_a_governed_calculation(tmp_path):
    executor = governed_executor()
    store = open_store(executor)
    submit(store)
    gate = Gate([goal('calculation', 'business_execute', excerpt='复现病态11节点算例')])
    result = run_pending_attempt(store, native_runtime_factory(
        executor, research_root=tmp_path, recognizer_factory=lambda: gate, unscoped_intent=False),
        worker_id='native', implementation_family='native')
    assert result.status == 'completed', failed_detail(store)
    assert gate.recognitions == 0
    assert executor.requests[0].instruction == INSTRUCTION
    routes = [event.payload for event in store.read_events('thr_unscoped', 0).events
              if event.event_type == 'turn_route_selected']
    assert routes[-1]['source'] == 'native_conversation'


def test_governed_calculation_without_a_model_records_the_domain_gap(tmp_path):
    executor = governed_executor()
    store = open_store(executor)
    submit(store)
    gate = Gate([goal('calculation', 'business_execute', excerpt='复现病态11节点算例')])
    result = run_pending_attempt(store, native_runtime_factory(
        executor, research_root=tmp_path, recognizer_factory=lambda: gate, unscoped_intent=True),
        worker_id='native', implementation_family='native')
    assert result.status == 'completed', failed_detail(store)
    assert gate.recognitions == 2
    assert gate.requests[0]['messages'] == []
    assert gate.requests[-1]['mode_hint'] is None
    assert [request.instruction for request in executor.requests] == [INSTRUCTION]
    assert UNSCOPED_DOMAIN_GAP not in result.answer
    assert 'General answer' in result.answer


def test_independent_general_goal_still_runs_when_the_calculation_is_withheld(tmp_path):
    executor = governed_executor()
    store = open_store(executor)
    submit(store)
    gate = Gate([
        goal('platform', 'answer', excerpt='建立潮流算法基准平台'),
        goal('calculation', 'business_execute', excerpt='复现病态11节点算例'),
    ])
    result = run_pending_attempt(store, native_runtime_factory(
        executor, research_root=tmp_path, recognizer_factory=lambda: gate, unscoped_intent=True),
        worker_id='native', implementation_family='native')
    assert result.status == 'completed', failed_detail(store)
    assert [request.instruction for request in executor.requests] == [INSTRUCTION]
    assert UNSCOPED_DOMAIN_GAP not in result.answer
    assert 'General answer' in result.answer


def test_ordinary_instruction_stops_after_one_short_understanding(tmp_path):
    executor = governed_executor()
    store = open_store(executor)
    submit(store, name='news')

    class Recording(Gate):
        def recognize(self, request, control):
            self.levels.append(getattr(self, 'thinking_level', None))
            return super().recognize(request, control)

    gate = Recording([goal('news', 'external_lookup')])
    gate.levels = []
    result = run_pending_attempt(store, native_runtime_factory(
        executor, research_root=tmp_path, recognizer_factory=lambda: gate, unscoped_intent=True),
        worker_id='native', implementation_family='native')
    assert result.status == 'completed', failed_detail(store)
    assert gate.recognitions == 1
    assert gate.levels == ['low']
    assert gate.requests[0]['messages'] == []
    assert gate.requests[0]['objects'] == []
    assert gate.requests[0]['history_truncated'] is True


def test_answer_decision_is_not_rewritten_by_instruction_words(tmp_path):
    executor = governed_executor()
    store = open_store(executor)
    submit(store)
    gate = Gate([goal('whole', 'answer')])
    result = run_pending_attempt(store, native_runtime_factory(
        executor, research_root=tmp_path, recognizer_factory=lambda: gate, unscoped_intent=True),
        worker_id='native', implementation_family='native')
    assert result.status == 'completed', failed_detail(store)
    assert executor.requests[0].instruction == INSTRUCTION
    assert UNSCOPED_DOMAIN_GAP not in result.answer


@pytest.mark.parametrize('session_type', [None, 'general-chat'])
def test_installed_recognizer_does_not_treat_a_missing_model_as_an_ordinary_question(tmp_path, session_type):
    executor = native_executor()
    store = open_store(executor, session_type=session_type)
    submit(store, name='profile-' + (session_type or 'base'))
    gate = Gate([goal('calculation', 'business_execute', excerpt='复现病态11节点算例')])
    result = run_pending_attempt(store, native_runtime_factory(
        executor, research_root=tmp_path, recognizer_factory=lambda: gate, unscoped_intent=True),
        worker_id='native', implementation_family='native')
    assert result.status == 'completed', failed_detail(store)
    assert gate.recognitions == 2
    assert gate.requests[-1]['mode_hint'] is None
    assert [request.instruction for request in executor.requests] == [INSTRUCTION]
    assert UNSCOPED_DOMAIN_GAP not in result.answer


def test_frozen_synthetic_retry_does_not_call_the_recognizer():
    executor = governed_executor()
    store = open_store(executor)
    submit(store)
    claim = store.claim_attempt('native', 30, 'native')
    assert claim.submission['_native_execution']['application_profile'] == {
        'profile_id': 'enterprise-research', 'profile_version': '1.20.0'}
    control = NodeControl(lambda: None, time.monotonic() + 30)
    native_runtime_factory(executor, unscoped_intent=False).plan_intent(
        claim, control, store.freeze_attempt_input, freeze_decision=store.freeze_attempt_decision)
    gate = Gate([goal('calculation', 'business_execute', excerpt='复现病态11节点算例')])
    plan = native_runtime_factory(executor, unscoped_intent=True, recognizer_factory=lambda: gate).plan_intent(
        claim, control, store.freeze_attempt_input, freeze_decision=store.freeze_attempt_decision)
    assert plan.source == 'native_conversation'
    assert gate.recognitions == 0


def test_saved_unscoped_decision_is_reused_without_a_second_recognition():
    executor = governed_executor()
    store = open_store(executor)
    submit(store)
    claim = store.claim_attempt('native', 30, 'native')
    gate = Gate([goal('calculation', 'business_execute', excerpt='复现病态11节点算例')])
    factory = native_runtime_factory(executor, unscoped_intent=True, recognizer_factory=lambda: gate)
    control = NodeControl(lambda: None, time.monotonic() + 30)
    first = factory.plan_intent(claim, control, store.freeze_attempt_input,
                                freeze_decision=store.freeze_attempt_decision)
    second = factory.plan_intent(claim, control, store.freeze_attempt_input,
                                 freeze_decision=store.freeze_attempt_decision)
    assert gate.recognitions == 2
    assert first.source == second.source == 'fixture'
    assert second.intent_decision.to_document()['goals'][0]['operation'] == 'answer'
    assert second.intent_decision.to_document()['goals'][0]['capability_refs'] == ['general-pi']
    assert UNSCOPED_DOMAIN_GAP not in second.intent_decision.to_document()['goals'][0]['missing_requirements']


def test_unavailable_domain_family_records_the_executor_gap(tmp_path):
    executor = governed_executor()
    store = open_store(executor)
    publish_domain(store, available=False)
    submit(store)
    store._catalog_context = None
    gate = Gate([goal('calculation', 'business_execute', excerpt='复现病态11节点算例', refs=(DOMAIN_CAPABILITY,))])
    result = run_pending_attempt(store, native_runtime_factory(
        executor, research_root=tmp_path, recognizer_factory=lambda: gate, unscoped_intent=True),
        worker_id='native', implementation_family='native')
    assert result.status == 'completed', failed_detail(store)
    seen = next(item for item in gate.requests[0]['capabilities'] if item['capability_id'] == DOMAIN_CAPABILITY)
    assert seen['enabled'] is True and seen['available'] is False
    assert gate.requests[0]['objects'] == []
    assert [request.instruction for request in executor.requests] == [INSTRUCTION]
    assert executor.requests[0].domain_tools is None
    assert DOMAIN_EXECUTOR_UNAVAILABLE not in result.answer
    assert UNSCOPED_DOMAIN_GAP not in result.answer
    assert not store.has_pending_attempts('pandapower')


def test_registered_domain_runtime_executes_without_an_open_model():
    executor = governed_executor()
    store = open_store(executor)
    publish_domain(store)
    submit(store)
    gate = Gate([goal('calculation', 'business_execute', excerpt='复现病态11节点算例', refs=(DOMAIN_CAPABILITY,))])
    domain = DomainRuntime()
    result = run_pending_attempt(store, native_runtime_factory(
        executor, recognizer_factory=lambda: gate, unscoped_intent=True, business_factory=domain),
        worker_id='native', implementation_family='native')
    assert result.status == 'completed', failed_detail(store)
    assert domain.claims == []
    assert [request.instruction for request in executor.requests] == [INSTRUCTION]
    assert [dict(item) for item in executor.requests[0].domain_tools['profiles']] == [{
        'profile_id': 'pandapower-static-analysis', 'profile_version': '1.0.0',
        'implementation_family': 'pandapower'}]
    assert 'General answer' in result.answer
    assert UNSCOPED_DOMAIN_GAP not in result.answer
    routes = [event.payload for event in store.read_events('thr_unscoped', 0).events
              if event.event_type == 'turn_route_selected']
    assert routes[-1]['route'] == 'ordinary'


def test_domain_tool_stays_inside_the_lightweight_attempt(tmp_path, monkeypatch):
    woken = []
    monkeypatch.setattr('capstone_agent.thread_worker._wake_released_family', woken.append)
    executor = governed_executor()
    store = open_store(executor)
    publish_domain(store)
    submit(store)
    store._catalog_context = None
    gate = Gate([goal('calculation', 'business_execute', excerpt='复现病态11节点算例', refs=(DOMAIN_CAPABILITY,))])
    domain = DomainRuntime()
    result = run_pending_attempt(store, native_runtime_factory(
        executor, research_root=tmp_path, recognizer_factory=lambda: gate, unscoped_intent=True,
        business_factory=domain),
        worker_id='native', implementation_family='native')
    assert result.status == 'completed', failed_detail(store)
    assert domain.claims == []
    assert executor.requests[0].domain_tools['profiles'][0]['implementation_family'] == 'pandapower'
    assert woken == []
    assert not store.has_pending_attempts('pandapower')


def test_available_domain_calculation_is_released_then_replayed_once(tmp_path):
    executor = governed_executor()
    store = open_store(executor)
    publish_domain(store)
    submit(store)
    store._catalog_context = None
    gate = Gate([
        goal('platform', 'answer', excerpt='建立潮流算法基准平台'),
        goal('calculation', 'business_execute', excerpt='复现病态11节点算例', refs=(DOMAIN_CAPABILITY,)),
    ])
    domain = DomainRuntime()
    result = run_pending_attempt(store, native_runtime_factory(
        executor, research_root=tmp_path, recognizer_factory=lambda: gate, unscoped_intent=True,
        business_factory=domain),
        worker_id='native', implementation_family='native')
    assert result.status == 'completed', failed_detail(store)
    assert gate.recognitions == 2
    assert domain.claims == []
    assert not store.has_pending_attempts('pandapower')
    assert [request.instruction for request in executor.requests] == [INSTRUCTION]
    assert executor.requests[0].domain_tools['profiles'][0]['profile_id'] == 'pandapower-static-analysis'
    assert 'General answer' in result.answer
    assert UNSCOPED_DOMAIN_GAP not in result.answer
    routes = [event.payload for event in store.read_events('thr_unscoped', 0).events
              if event.event_type == 'turn_route_selected']
    assert routes[-1]['route'] == 'ordinary'


def test_conflicting_domain_families_stay_on_this_worker_as_a_gap(tmp_path):
    executor = governed_executor()
    store = open_store(executor)
    publish_domain(store, families=('pandapower', 'pypsa'))
    submit(store)
    gate = Gate([goal('calculation', 'business_execute', excerpt='复现病态11节点算例',
                      refs=(DOMAIN_CAPABILITY, PYPSA_CAPABILITY))])
    result = run_pending_attempt(store, native_runtime_factory(
        executor, research_root=tmp_path, recognizer_factory=lambda: gate, unscoped_intent=True),
        worker_id='native', implementation_family='native')
    assert result.status == 'completed', failed_detail(store)
    assert [request.instruction for request in executor.requests] == [INSTRUCTION]
    assert {item['implementation_family'] for item in executor.requests[0].domain_tools['profiles']} == {'pandapower', 'pypsa'}
    assert DOMAIN_EXECUTOR_UNREGISTERED not in result.answer
    assert not store.has_pending_attempts('pandapower')


def test_unscoped_request_names_published_models_without_a_revision():
    executor = governed_executor()
    store = open_store(executor)
    publish_domain(store, families=('pandapower', 'pypsa'))
    submit(store)
    gate = Gate([goal('calculation', 'business_execute', excerpt='复现病态11节点算例')])
    claim = store.claim_attempt('native', 30, 'native')
    control = NodeControl(lambda: None, time.monotonic() + 30)
    native_runtime_factory(executor, unscoped_intent=True, recognizer_factory=lambda: gate).plan_intent(
        claim, control, store.freeze_attempt_input, freeze_decision=store.freeze_attempt_decision)
    assert gate.requests[0]['objects'] == []
    assert gate.recognitions == 2
    objects = {item['object_id']: item for item in gate.requests[-1]['objects']}
    assert set(objects) == {'pandapower-case', 'pypsa-case'}
    assert objects['pandapower-case']['implementation_family'] == 'pandapower'
    assert 'model_revision' not in objects['pandapower-case']


def test_clarification_does_not_withhold_a_ready_published_calculation(tmp_path):
    executor = governed_executor()
    store = open_store(executor)
    publish_domain(store)
    submit(store)
    store._catalog_context = None

    class Clarifying(Gate):
        def recognize(self, request, control):
            document = super().recognize(request, control).to_document()
            document['clarification'] = 'Confirm the comparison basis?'
            document['clarification_required'] = True
            return IntentDecision.from_document(document, request)

    gate = Clarifying([
        goal('platform', 'answer', excerpt='建立潮流算法基准平台'),
        goal('calculation', 'business_execute', excerpt='复现病态11节点算例', refs=(DOMAIN_CAPABILITY,)),
    ])
    domain = DomainRuntime()
    result = run_pending_attempt(store, native_runtime_factory(
        executor, research_root=tmp_path, recognizer_factory=lambda: gate, unscoped_intent=True,
        business_factory=domain),
        worker_id='native', implementation_family='native')
    assert result.status == 'completed', failed_detail(store)
    assert 'pandapower-case' in {item['object_id'] for item in gate.requests[-1]['objects']}
    assert domain.claims == []
    assert not store.has_pending_attempts('pandapower')
    assert executor.requests[0].domain_tools['profiles'][0]['profile_id'] == 'pandapower-static-analysis'
    assert [request.instruction for request in executor.requests] == [INSTRUCTION]


def test_answer_decision_stays_general_when_a_domain_capability_is_available(tmp_path):
    executor = governed_executor()
    store = open_store(executor)
    publish_domain(store)
    submit(store)
    gate = Gate([goal('whole', 'answer')])
    domain = DomainRuntime()
    result = run_pending_attempt(store, native_runtime_factory(
        executor, research_root=tmp_path, recognizer_factory=lambda: gate, unscoped_intent=True,
        business_factory=domain),
        worker_id='native', implementation_family='native')
    assert result.status == 'completed', failed_detail(store)
    assert executor.requests[0].instruction == INSTRUCTION
    assert domain.claims == []
    assert executor.requests[0].domain_tools['profiles'][0]['profile_id'] == 'pandapower-static-analysis'
    assert UNSCOPED_DOMAIN_GAP not in result.answer
