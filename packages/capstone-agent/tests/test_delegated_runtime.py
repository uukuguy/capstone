from dataclasses import replace
from types import SimpleNamespace
import time

import pytest

from capstone_agent.harness import AdmittedAttemptAnswer, HarnessRuntimeConfigurationError
from capstone_agent.intent_runtime import IntentRuntimeFactory
from capstone_agent.pi_delegation import PiTaskResult
from capstone_agent.request_intent import IntentDecision, IntentEngineIdentity, NodeControl
from capstone_agent.thread_worker import _run_claimed_attempt
from test_intent_runtime import claim, historical_direct_claim


class Executor:
    identity = {'engine': 'pi', 'config_revision': 'general-v1'}
    capability = {'capability_id': 'general-pi', 'enabled': True, 'available': True,
                  'task_schemas': ['capstone-pi-task/1', 'capstone-pi-task/2'],
                  'operations': ['answer', 'rewrite', 'external_lookup']}

    def __init__(self, statuses=None):
        self.requests = []
        self.statuses = statuses or {}
        self.cancelled = []

    def execute(self, request, control, on_event):
        control.checkpoint()
        self.requests.append(request)
        on_event({'type': 'tool_execution_end', 'toolName': 'bash',
                  'result_refs': ['forged-result'], 'evidence_refs': ['forged-evidence']})
        on_event({'type': 'message_update', 'assistantMessageEvent':
                  {'type': 'text_delta', 'delta': 'General answer'}})
        return PiTaskResult(request.task_id, request.parent_attempt_id, self.identity,
                            self.statuses.get(request.instruction, 'completed'),
                            'General answer', (), (), {})

    def cancel(self, task_id):
        self.cancelled.append(task_id)


def test_native_task_uses_accepted_role_profile_revision():
    executor = Executor()
    executor.capability = {**executor.capability, 'resource_profiles': {
        role: {'profile_id': role, 'revision': 'accepted-' + role}
        for role in ('direct_pi', 'delegated_pi')}}
    service, current = claim()
    current = replace(current, attempt=replace(current.attempt, runtime_mode='pi_reference'))
    result = run(service, current, factory(executor, SimpleNamespace(identity=None)))
    assert result.status == 'completed'
    assert executor.requests[0].to_document()['resource_profile'] == {
        'profile_id': 'direct_pi', 'revision': 'accepted-direct_pi'}


def test_current_resource_catalog_does_not_replace_frozen_profile_on_retry():
    previous = {'identity': {'engine': 'pi', 'config_revision': 'fixed'},
        'timeout_seconds': 10, 'capability': {'capability_id': 'general-pi',
            'resource_profiles': {'direct_pi': {'revision': 'old'}}}}
    current = {**previous, 'capability': {**previous['capability'],
        'resource_profiles': {'direct_pi': {'revision': 'new'}}}}
    IntentRuntimeFactory._check_general_configuration(current, {'general_executor': previous})
    assert previous['capability']['resource_profiles']['direct_pi']['revision'] == 'old'
    current['identity'] = {'engine': 'pi', 'config_revision': 'changed'}
    with pytest.raises(HarnessRuntimeConfigurationError):
        IntentRuntimeFactory._check_general_configuration(current, {'general_executor': previous})


def goal(identity, operation='answer', *, refs=(), depends=(), excerpt=None, missing=()):
    result = {'goal_id': identity, 'description': 'Untrusted plan prose',
              'operation': operation, 'message_refs': [], 'object_refs': [],
              'capability_refs': list(refs), 'missing_requirements': list(missing),
              'depends_on': list(depends)}
    if excerpt is not None:
        result['instruction_excerpt'] = excerpt
    return result


class Recognizer:
    identity = IntentEngineIdentity('fixture', 'model', 'config_1')

    def __init__(self, goals, *, clarification=None):
        self.goals = goals
        self.clarification = clarification
        self.requests = []

    def recognize(self, request, control):
        self.requests.append(request)
        source = request.to_document()
        return IntentDecision.from_document({'schema': 'capstone-intent-decision/1',
            'attempt_id': source['attempt_id'], 'history_cutoff': source['history_cutoff'],
            'relationship': 'independent', 'goals': self.goals,
            'clarification': self.clarification}, request)


class ContextSelector:
    identity = IntentEngineIdentity('fixture', 'model', 'context_1')

    def __init__(self, objects=(), messages=(), clarify=False):
        self.objects, self.messages, self.clarify = list(objects), list(messages), clarify
        self.requests = []

    def select(self, request, control):
        from capstone_agent.context_selection import ContextSelectionDecision
        control.checkpoint()
        self.requests.append(request)
        source = request.to_document()
        return ContextSelectionDecision.from_document({
            'schema': 'capstone-context-selection-decision/1', 'attempt_id': source['attempt_id'],
            'history_cutoff': source['history_cutoff'], 'object_refs': self.objects,
            'message_refs': self.messages, 'clarification_required': self.clarify,
            'clarification': 'Which object?' if self.clarify else None}, request)


def factory(executor, recognizer, business=None, selector=None):
    return IntentRuntimeFactory(business or (lambda _: pytest.fail('Domain Pack prepared')),
        lambda: recognizer, lambda *_: pytest.fail('legacy ordinary Pi called'),
        general_executor=executor, context_selector_factory=lambda: selector or ContextSelector())


@pytest.mark.parametrize('selected', [False, True])
def test_direct_context_selection_is_public_and_independent(selected):
    service, current = claim()
    current = replace(current, instruction='Explain line 11',
                      attempt=replace(current.attempt, runtime_mode='pi_reference'))
    selector = ContextSelector(['ctx_test'] if selected else [])
    executor = Executor()
    result = run(service, current, factory(executor, SimpleNamespace(identity=None), selector=selector))
    assert result.status == 'completed'
    source = selector.requests[0].to_document()
    assert 'capabilities' not in source and 'model_revision' not in repr(source)
    task = executor.requests[0]
    assert task.entrypoint == 'direct'
    assert task.to_document()['schema'] == 'capstone-pi-task/2'
    context = task.business_context.to_document()
    assert context['selection']['state'] == ('selected' if selected else 'none')
    assert [item['object_id'] for item in context['object_refs']] == (['ctx_test'] if selected else [])


def test_delegated_general_goals_have_distinct_public_object_contexts():
    service, current = claim()
    executor = Executor()
    goals = [goal('background', excerpt='解释刚才的结论'), goal('translation', excerpt='翻译成英文')]
    goals[0]['object_refs'] = ['ctx_test']
    result = run(service, current, factory(executor, Recognizer(goals)))
    assert result.status == 'completed'
    assert executor.requests[0].business_context.to_document()['object_refs'][0]['display_name'] == 'ieee39'
    assert executor.requests[1].business_context.to_document()['selection']['state'] == 'none'


@pytest.mark.parametrize('clarification', [None, 'Which historical model version should I use?'])
def test_unresolved_historical_general_goal_returns_blocked_or_clarification(clarification):
    service, current = claim()
    current = historical_direct_claim(current, resolved=False)
    current = replace(current, attempt=replace(current.attempt, runtime_mode='capstone'))
    blocked = goal('historical', missing=('The historical model version is unavailable',)
                   if clarification is None else ())
    blocked['object_refs'] = ['ctx_old']
    executor = Executor()
    selected = factory(executor, Recognizer([blocked], clarification=clarification))
    plan = selected.plan_intent(current, NodeControl(lambda: None, time.monotonic() + 5),
        service.freeze_attempt_input, freeze_decision=service.freeze_attempt_decision)
    assert plan.intent_resources['business_contexts'] == {}
    assert plan.intent_request.to_document()['objects'][-1] == {'object_id': 'ctx_old'}
    accepted = service.freeze_attempt_decision(current, None)
    assert accepted['goals'][0] == blocked
    result = run(service, current, selected)
    assert result.status == 'completed'
    assert result.answer == (clarification or
        'General task was not executed: prerequisites are not complete.')
    assert result.result_refs == result.evidence_refs == ()
    assert executor.requests == []
    assert not any(event.payload.get('child_status') == 'started'
                   for event in service.read_events(current.thread_id, 0).events)


def test_blocked_historical_goal_preserves_independent_goal_context():
    service, current = claim()
    current = historical_direct_claim(current, resolved=False)
    history = {'message_id': 'current:assistant', 'role': 'assistant', 'content': 'Current background',
        'turn_id': 'current-turn', 'attempt_id': 'current-old',
        'model_context_id': 'ctx_test', 'status': 'completed'}
    current = replace(current, attempt=replace(current.attempt, runtime_mode='capstone'),
        conversation_context=replace(current.conversation_context,
            messages=(*current.conversation_context.messages, history)))
    blocked = goal('historical', excerpt='解释刚才的结论',
                   missing=('The historical model version is unavailable',))
    blocked['object_refs'] = ['ctx_old']
    independent = goal('independent', excerpt='翻译成英文')
    independent['object_refs'] = ['ctx_test']
    independent['message_refs'] = ['current:assistant']
    executor = Executor()
    selected = factory(executor, Recognizer([blocked, independent]))
    plan = selected.plan_intent(current, NodeControl(lambda: None, time.monotonic() + 5),
        service.freeze_attempt_input, freeze_decision=service.freeze_attempt_decision)
    contexts = plan.intent_resources['business_contexts']
    assert set(contexts) == {'independent'}
    assert plan.intent_request.to_document()['objects'][-1] == {'object_id': 'ctx_old'}
    assert service.freeze_attempt_decision(current, None)['goals'][0] == blocked
    result = run(service, current, selected)
    assert result.status == 'completed'
    assert 'General task was not executed: prerequisites are not complete.' in result.answer
    assert 'General answer' in result.answer
    assert result.result_refs == result.evidence_refs == ()
    assert len(executor.requests) == 1
    task = executor.requests[0]
    assert task.instruction == '翻译成英文'
    assert task.to_document()['schema'] == 'capstone-pi-task/2'
    assert list(task.messages) == [{**history, 'model_context_id': ''}]
    context = task.business_context.to_document()
    assert context == contexts['independent']
    assert [item['object_id'] for item in context['object_refs']] == ['ctx_test']
    assert context['object_refs'][0]['source']['message_refs'] == ['current:assistant']
    events = service.read_events(current.thread_id, 0).events
    assert [(event.payload['goal_id'], event.payload['goal_status']) for event in events
            if 'goal_status' in event.payload] == [('historical', 'blocked'), ('independent', 'completed')]


def test_required_context_cannot_be_dropped_for_v1_server():
    service, current = claim()
    executor = Executor()
    executor.capability = {**executor.capability, 'task_schemas': ['capstone-pi-task/1']}
    selected_goal = goal('one')
    selected_goal['object_refs'] = ['ctx_test']
    with pytest.raises(HarnessRuntimeConfigurationError, match='schema'):
        selected = factory(executor, Recognizer([selected_goal]))
        plan = selected.plan_intent(current, NodeControl(lambda: None, time.monotonic() + 5), service.freeze_attempt_input)
        selected(replace(current, turn_plan=plan)).prompt(current.instruction, on_event=lambda _: None)
    assert executor.requests == []


def run(service, current, selected):
    return _run_claimed_attempt(service, selected, current,
                               SimpleNamespace(check=lambda: None), 30, None)


def test_worker_external_lookup_uses_actual_general_executor():
    service, current = claim()
    executor = Executor()
    recognizer = Recognizer([goal('lookup', 'external_lookup', refs=['general-pi'])])
    result = run(service, current, factory(executor, recognizer))
    assert result.status == 'completed'
    assert result.answer == 'General answer'
    assert len(executor.requests) == 1
    assert executor.requests[0].instruction == current.instruction
    assert result.result_refs == result.evidence_refs == ()
    assert recognizer.requests[0].to_document()['capabilities'][0]['capability_id'] == 'general-pi'
    saved = service.read_events(current.thread_id, 0).events
    receipts = [e.payload for e in saved if e.event_type == 'runtime_event']
    assert any(e.get('child_status') == 'started' for e in receipts)
    assert any(e.get('child_status') == 'completed' for e in receipts)
    assert not any(e.event_type in {'tool_started', 'tool_completed'} for e in saved)


def test_native_worker_persists_shared_steps_without_promoting_tools_to_authority():
    class SteppedExecutor(Executor):
        def execute(self, request, control, on_event):
            on_event({'type': 'runtime_action', 'phase': 'started'})
            on_event({'type': 'runtime_action', 'phase': 'response_completed', 'response_kind': 'tools'})
            on_event({'type': 'tool_execution_start', 'tool_name': 'bash', 'tool_call_id': 'read'})
            on_event({'type': 'tool_execution_end', 'tool_name': 'bash', 'tool_call_id': 'read', 'is_error': True})
            on_event({'type': 'runtime_action', 'phase': 'completed'})
            on_event({'type': 'runtime_action', 'phase': 'started'})
            on_event({'type': 'runtime_action', 'phase': 'response_completed', 'response_kind': 'text'})
            on_event({'type': 'runtime_action', 'phase': 'completed'})
            return PiTaskResult(request.task_id, request.parent_attempt_id, self.identity,
                                'completed', '说明限制', (), (), {})
    service, current = claim()
    result = run(service, current, factory(SteppedExecutor(), Recognizer([goal('one')])))
    assert result.status == 'completed'
    saved = service.read_events(current.thread_id, 0).events
    calls = [e.payload for e in saved if e.payload.get('tool_call_id') == 'read']
    assert len(calls) == 2 and calls[0]['task_step_id'] == calls[1]['task_step_id']
    steps = [e.payload['task_step'] for e in saved if e.event_type == 'runtime_action' and 'task_step' in e.payload]
    assert any(s.get('after_failed_steps') == [calls[0]['task_step_id']] for s in steps)
    assert not result.result_refs and not result.evidence_refs


@pytest.mark.parametrize('prior_narrative', [False, True, 'inspect'])
@pytest.mark.parametrize('profile_version', ['1.2.0'])
def test_committed_cycle_steps_are_public_and_keep_partial_outcome(prior_narrative, profile_version, tmp_path):
    from capstone_agent.thread_service import InMemoryThreadService
    from capstone_agent.thread_worker import run_pending_attempt
    from test_enterprise_normal_chat import native_executor
    from test_thread_postgres import _snapshot
    from test_thread_work_execution import command
    class CycleExecutor(Executor):
        def execute_with_research(self, request, control, on_event, bridge):
            from capstone_agent.native_research_bridge import CYCLE_CONTROL_TOOLS
            expected = {'agent_research_cycle'} if profile_version == '1.1.0' else {
                'agent_research_plan', 'agent_research_record', 'agent_research_assess'}
            assert set(request.native_context['policy']['allowed_tools']).intersection(CYCLE_CONTROL_TOOLS) == expected
            return self.execute(request, control, on_event)
        def execute(self, request, control, on_event):
            if prior_narrative:
                on_event({'type': 'tool_execution_end', 'tool_name': 'agent_task_progress',
                    'tool_call_id': 'narrative-progress', 'is_error': False,
                    'task_progress': {'kind': 'goal', 'step_id': 'inspect' if prior_narrative == 'inspect' else 'narrative',
                        'phase': 'started', 'text': '准备检查资料'}})
            for phase in ('started', 'settled'):
                on_event({'type': 'enterprise_cycle_progress', 'attempt_id': request.parent_attempt_id,
                    'action_id': 'cycle-observed', 'checkpoint': {'ref': 'committed', 'revision': 1},
                    'progress': {'step_id': 'inspect', 'phase': phase, 'text': '检查资料',
                        'questions': ['资料覆盖哪些时段？'], 'expected_outputs': ['覆盖与缺失说明'],
                        'derived_from': ['coverage-finding'], 'next_action_reason': '先明确资料边界再比较。',
                        **({'result_summary': '部分时段资料缺失。'} if phase == 'settled' else {}),
                        **({'outcome': 'partial'} if phase == 'settled' else {})}})
                if phase == 'started':
                    on_event({'type': 'runtime_action', 'phase': 'started'})
                    on_event({'type': 'runtime_action', 'phase': 'response_completed', 'response_kind': 'tools'})
                    on_event({'type': 'tool_execution_start', 'tool_name': 'agent_delegate', 'tool_call_id': 'delegate-parent'})
                    branch = {'subordinate': True, 'owner': request.to_document()['research_binding']['cycle_owner'],
                        'attempt_id': request.parent_attempt_id, 'parent_action_id': 'cycle-observed',
                        'parent_step_id': 'inspect', 'parent_tool_call_id': 'delegate-parent', 'child_id': 'coverage',
                        'title': '核对资料覆盖', 'questions': ['资料覆盖哪些时段？'],
                        'expected_outputs': ['覆盖检查记录'], 'checkpoint': {'ref': 'committed', 'revision': 1}}
                    on_event({'type': 'delegation_child_started', **branch})
                    on_event({'type': 'delegation_child_tool', **branch,
                        'activity': 'end', 'tool_name': 'read', 'tool_call_id': 'child-read', 'is_error': True})
                    on_event({'type': 'delegation_child_finished', **branch, 'status': 'failed',
                        'result_summary': '已检查可用资料，部分时段仍有缺失。',
                        'error': {'code': 'child_failed', 'message': 'Child model response failed (model_transport).'}})
                    on_event({'type': 'tool_execution_end', 'tool_name': 'agent_delegate',
                        'tool_call_id': 'delegate-parent', 'is_error': False})
                    on_event({'type': 'runtime_action', 'phase': 'completed'})
            return PiTaskResult(request.task_id, request.parent_attempt_id, self.identity,
                'completed', '资料只支持部分结论。', (), (), {})
    executor = CycleExecutor()
    executor.capability = {**native_executor().capability, 'research_bridge_schemas': ['capstone-research-bridge/1']}
    thread_id = 'thr_cycle_steps'
    service = InMemoryThreadService(replace(_snapshot(thread_id), active_model_context=None,
        active_grid_page_id=None, minimum_protocol_version=2))
    service.set_native_executor(executor)
    receipt = service.submit_command(command(service, thread_id, 'send_message', 'cycle', payload={'text': 'Check source coverage'}))
    assert receipt.status == 'accepted'
    def unavailable(*args):
        pytest.fail('native cycle must not invoke the professional runtime or planner')
    selected = IntentRuntimeFactory(unavailable, unavailable, unavailable,
        general_executor=executor, native_research_root=tmp_path)
    result = run_pending_attempt(service, selected, worker_id='native-cycle-test', implementation_family='native')
    assert result.status == 'completed', [event.payload for event in service.read_events(thread_id, 0).events
        if event.event_type == 'attempt_failed']
    events = [e for e in service.read_events(thread_id, 0).events
        if e.payload.get('native_type') == 'enterprise_cycle_progress']
    assert len(events) == 2 and all(e.visibility == 'public' for e in events)
    assert events[-1].payload['task_step']['status'] == 'partial'
    assert events[-1].payload['research_cycle']['progress']['outcome'] == 'partial'
    for event in events:
        assert event.payload['task_step']['title'] == '检查资料'
        for key in ('questions', 'expected_outputs', 'derived_from', 'next_action_reason'):
            assert event.payload['task_step'][key] == event.payload['research_cycle']['progress'][key]
    assert events[-1].payload['task_step']['result_summary'] == '部分时段资料缺失。'
    timings = [event for event in service.read_events(thread_id, 0).events
        if event.event_type == 'runtime_action' and event.payload.get('phase') == 'response_completed']
    assert len(timings) == 1 and timings[0].visibility == 'public'
    measured = timings[0].payload['task_step']['response_ms']
    assert type(measured) is int and measured >= 0
    assert timings[0].payload['task_step']['id'] == events[0].payload['task_step']['id']
    assert events[-1].payload['task_step']['response_ms'] == measured
    assert len({event.payload['task_step']['id'] for event in events}) == 1
    branches = [event for event in service.read_events(thread_id, 0).events if 'research_branch' in event.payload]
    assert len(branches) == 3 and all(event.visibility == 'public' for event in branches)
    assert all('task_step' not in event.payload for event in branches)
    assert all(event.payload['research_branch']['parent_step_id'] == events[0].payload['task_step']['id']
               for event in branches)
    assert branches[-1].payload['research_branch']['status'] == 'failed'
    assert branches[-1].payload['research_branch']['result_summary'] == '已检查可用资料，部分时段仍有缺失。'
    assert all(event.payload['research_branch']['questions'] == ['资料覆盖哪些时段？'] for event in branches)
    if prior_narrative:
        previous = events[0].payload['task_steps']
        old_id = '.inspect' if prior_narrative == 'inspect' else '.narrative'
        assert any(step['id'].endswith(old_id) and step['status'] == 'limited' for step in previous), previous
        assert events[0].payload['task_step']['id'].endswith('.inspect') == (prior_narrative != 'inspect')


def test_direct_pi_mode_bypasses_semantic_recognizer_and_domain():
    service, current = claim()
    current = replace(current, attempt=replace(current.attempt, runtime_mode='pi_reference'))
    executor = Executor()
    selected = factory(executor, SimpleNamespace(identity=None))
    result = run(service, current, selected)
    assert result.status == 'completed'
    assert executor.requests[0].entrypoint == 'direct'
    assert executor.requests[0].instruction == current.instruction
    saved = service.read_events(current.thread_id, 0).events
    assert next(e for e in saved if e.event_type == 'turn_plan_created').payload['source'] == 'direct_pi'


def test_graph_native_frames_keep_public_projection_and_restore_in_thread_history():
    kinds = ('enterprise_graph_tool_binding', 'enterprise_graph_child_started',
             'enterprise_graph_child_response_started', 'enterprise_graph_child_tool', 'enterprise_graph_child_response', 'enterprise_graph_child_finished')
    class GraphExecutor(Executor):
        def execute(self, request, control, on_event):
            for kind in kinds:
                on_event({'type': kind, 'owner': {'thread_id': 'thr_intent'},
                    'attempt_id': request.parent_attempt_id, 'task_id': request.task_id,
                    'action_id': 'action-A', 'step_id': 'A', 'child_id': 'A',
                    'checkpoint': {'ref': 'committed', 'revision': 1}, 'tool_call_id': 'child-call',
                    'tool_name': 'read', 'activity': 'end', 'response_number': 1, 'response_ms': 12,
                    'usage': {'totalTokens': 5}, 'status': 'completed', 'result_summary': 'Native child completed.',
                    **({'execution_ms': 2710.25} if kind == 'enterprise_graph_child_tool' else {}),
                    **({'tool_call_ids': ['child-call'], 'stop_reason': 'toolUse'} if kind == 'enterprise_graph_child_response' else {}),
                    'args': {'path': '/private/child/source'}, 'result': {'raw': 'private observation'}})
            return PiTaskResult(request.task_id, request.parent_attempt_id, self.identity,
                'completed', 'General answer', (), (), {})
    service, current = claim()
    current = replace(current, attempt=replace(current.attempt, runtime_mode='pi_reference'))
    assert run(service, current, factory(GraphExecutor(), SimpleNamespace(identity=None))).status == 'completed'
    events = [event for event in service.read_events(current.thread_id, 0).events
              if 'research_graph_event' in event.payload]
    assert len(events) == len(kinds)
    assert all(event.visibility == 'public' for event in events)
    history = service.read_history(current.thread_id)['events']
    frames = [event['payload']['research_graph_event'] for event in history
              if 'research_graph_event' in event['payload']]
    assert {frame['type'] for frame in frames} == set(kinds)
    assert all(frame['action_id'] == 'action-A' and frame['checkpoint']['ref'] == 'committed' for frame in frames)
    assert all('args' not in frame and 'result' not in frame for frame in frames)
    assert next(frame for frame in frames if frame['type'] == 'enterprise_graph_child_response')['usage'] == {'totalTokens': 5}
    assert next(frame for frame in frames if frame['type'] == 'enterprise_graph_child_tool')['execution_ms'] == 2710.25
    assert next(frame for frame in frames if frame['type'] == 'enterprise_graph_child_response')['tool_call_ids'] == ['child-call']


def test_retry_reuses_task_identity_and_frozen_general_configuration():
    service, current = claim()
    executor = Executor()
    selected = factory(executor, Recognizer([goal('one')]))
    control = NodeControl(lambda: None, time.monotonic() + 10)
    frozen = []
    freeze = lambda _, document: frozen[0] if frozen else (frozen.append(document) or document)
    first = selected.plan_intent(current, control, freeze)
    runtime = selected(replace(current, turn_plan=first))
    runtime.start()
    runtime.prompt(current.instruction, on_event=lambda _: None)
    runtime.stop()
    retry = replace(current, attempt=replace(current.attempt, attempt_id='retry_attempt'))
    second = selected.plan_intent(retry, control, freeze)
    selected(replace(retry, turn_plan=second)).prompt(current.instruction, on_event=lambda _: None)
    assert executor.requests[0].to_document() == executor.requests[1].to_document()
    executor.identity = {'engine': 'pi', 'config_revision': 'changed'}
    with pytest.raises(HarnessRuntimeConfigurationError, match='configuration'):
        selected.plan_intent(retry, control, freeze)


def test_business_goal_cannot_use_general_capability():
    service, current = claim()
    selected = factory(Executor(), Recognizer([goal('calc', 'business_execute', refs=['general-pi'])]))
    with pytest.raises(ValueError, match='domain capability'):
        selected.plan_intent(current, NodeControl(lambda: None, time.monotonic() + 10),
                             service.freeze_attempt_input)


def test_missing_general_executor_does_not_fall_back_to_legacy_pi():
    service, current = claim()
    selected = factory(None, Recognizer([goal('one')]))
    assert run(service, current, selected).status == 'failed'


def business_claim(current):
    return replace(current, model_context=replace(current.model_context,
        enabled_profiles=(('grid', '1'),)))


class BusinessRuntime:
    def __init__(self, admitted=True):
        self.admitted = admitted
    def start(self):
        pass
    def stop(self):
        pass
    def prompt(self, question, **kwargs):
        kwargs['on_heartbeat']()
        kwargs['on_event']({'event_type': 'tool_completed', 'runtime_mode': 'capstone',
            'visibility': 'public', 'payload': {'tool_name': 'grid_calc',
                'result_refs': ['result-current'], 'evidence_refs': ['evidence-current']}})
        return 'Authority answer'
    def admit_attempt(self, *args):
        if not self.admitted:
            return AdmittedAttemptAnswer('Forged professional claim', 'limited', 'limited')
        return AdmittedAttemptAnswer('Authority answer', 'authority_backed', 'lineage_verified',
                                    ('result-current',), ('evidence-current',))


def test_external_dependency_is_typed_and_business_preparation_runs_after_it():
    service, current = claim()
    current = business_claim(current)
    executor = Executor()
    captured = []
    goals = [goal('lookup', 'external_lookup', refs=['general-pi'], excerpt='解释刚才的结论'),
             goal('calc', 'business_execute', refs=['grid@1'], depends=['lookup'], excerpt='翻译成英文')]
    def business(scoped):
        assert len(executor.requests) == 1
        assert scoped.instruction == '翻译成英文'
        assert [g['goal_id'] for g in scoped.turn_plan.intent_decision.execution_goals] == ['calc']
        assert [c['capability_id'] for c in scoped.turn_plan.intent_request.to_document()['capabilities']] == ['grid@1']
        observation = scoped.turn_plan.intent_resources['external_observations'][0]
        assert isinstance(observation, PiTaskResult)
        assert 'result_refs' not in observation.to_document()
        captured.append(scoped)
        return BusinessRuntime()
    result = run(service, current, factory(executor, Recognizer(goals), business))
    assert result.status == 'completed'
    assert result.result_refs == ('result-current',)
    assert result.evidence_refs == ('evidence-current',)
    assert 'General answer' in result.answer and 'Authority answer' in result.answer
    assert len(captured) == 1


def test_independent_goal_survives_sibling_failure_and_dependent_business_is_unexecuted():
    service, current = claim()
    current = business_claim(current)
    executor = Executor({'解释刚才的结论': 'failed'})
    goals = [goal('bad', 'external_lookup', refs=['general-pi'], excerpt='解释刚才的结论'),
             goal('calc', 'business_execute', refs=['grid@1'], depends=['bad'], excerpt='翻译成英文'),
             goal('good', excerpt='翻译成英文')]
    result = run(service, current, factory(executor, Recognizer(goals)))
    assert result.status == 'completed'
    assert len(executor.requests) == 2
    assert result.admission['mode'] == 'limited'
    assert 'not executed' in result.answer
    assert result.result_refs == result.evidence_refs == ()


def test_mixed_general_success_cannot_replace_failed_professional_admission():
    service, current = claim()
    current = business_claim(current)
    goals = [goal('plain', excerpt='解释刚才的结论'),
             goal('calc', 'business_execute', refs=['grid@1'], excerpt='翻译成英文')]
    result = run(service, current, factory(Executor(), Recognizer(goals), lambda _: BusinessRuntime(False)))
    assert result.status == 'failed'
    assert result.result_refs == result.evidence_refs == ()


def test_child_cancel_and_timeout_propagate_parent_control():
    service, current = claim()
    executor = Executor()
    selected = factory(executor, Recognizer([goal('one')]))
    plan = selected.plan_intent(current, NodeControl(lambda: None, time.monotonic() + 10),
                                service.freeze_attempt_input)
    runtime = selected(replace(current, turn_plan=plan))
    checks = []
    def heartbeat():
        checks.append(1)
        if len(checks) >= 3:
            raise InterruptedError('parent cancelled')
    with pytest.raises(InterruptedError):
        runtime.prompt(current.instruction, on_event=lambda _: None, on_heartbeat=heartbeat)
    assert len(executor.cancelled) == 1


def test_child_failure_retains_safe_diagnostic_without_exception_text():
    class BrokenExecutor(Executor):
        def execute(self, request, control, on_event):
            raise TimeoutError('Pi transport deadline expired; task state is unknown')
    service, current = claim()
    executor = BrokenExecutor()
    selected = factory(executor, Recognizer([goal('one')]))
    plan = selected.plan_intent(current, NodeControl(lambda: None, time.monotonic() + 10),
                                service.freeze_attempt_input)
    runtime = selected(replace(current, turn_plan=plan))
    events = []
    runtime.prompt(current.instruction, on_event=events.append, on_heartbeat=lambda: None)
    failure = next(e for e in events if e.get('payload', {}).get('child_status') == 'failed')
    assert failure['payload']['failure_code'] == 'native_transport_timeout'
    assert len(executor.cancelled) == 1


def test_child_failure_diagnostic_never_copies_untrusted_error_text():
    from capstone_agent.delegated_runtime import child_failure_code
    assert child_failure_code(ValueError('Bearer PRIVATE_SECRET /private/user/data')) == 'native_contract_rejected'
    assert child_failure_code(RuntimeError('Bearer PRIVATE_SECRET')) == 'native_execution_error'


def test_http_failure_preserves_typed_cause_in_existing_runtime_receipt():
    from capstone_agent.pi_delegation import PiHTTPFailure
    class FailedExecutor(Executor):
        def execute(self, request, control, on_event):
            error = PiHTTPFailure(400, 'research_transport_file_changed')
            error.diagnostic['operation'] = 'research_pending'
            raise error
    service, current = claim()
    executor = FailedExecutor()
    selected = factory(executor, Recognizer([goal('one')]))
    plan = selected.plan_intent(current, NodeControl(lambda: None, time.monotonic() + 10),
                                service.freeze_attempt_input)
    runtime = selected(replace(current, turn_plan=plan))
    events = []
    runtime.prompt(current.instruction, on_event=events.append, on_heartbeat=lambda: None)
    payload = next(e['payload'] for e in events if e.get('payload', {}).get('child_status') == 'failed')
    assert payload['failure_code'] == 'native_executor_http_rejected'
    assert payload['transport_failure'] == {'operation': 'research_pending', 'http_status': 400,
                                            'protocol_code': 'research_transport_file_changed'}


def test_business_runtime_receives_source_bound_history_resource_subset():
    from capstone_agent.conversation_context import ConversationContext
    from capstone_agent.thread_service import PriorResultReference
    service, current = claim()
    current = business_claim(current)
    history = ConversationContext(messages=({'message_id': 'old', 'role': 'assistant',
        'content': 'Historical claim', 'turn_id': 'old-turn', 'attempt_id': 'old-attempt',
        'model_context_id': 'ctx_test', 'status': 'completed'},))
    current = replace(current, conversation_context=history,
        prior_results=(PriorResultReference('result:sha256:' + 'a' * 64, (), 'old-cap', 'old-attempt'),))
    captured = []
    result = run(service, current, factory(Executor(), Recognizer([
        goal('calc', 'business_execute', refs=['grid@1'])]),
        lambda scoped: captured.append(scoped) or BusinessRuntime()))
    assert result.status == 'completed'
    assert captured[0].prior_results == ()
    assert captured[0].turn_plan.intent_request.to_document()['messages'] == []


def test_general_capability_available_false_is_rejected_before_task_start():
    service, current = claim()
    executor = Executor()
    executor.capability = {**executor.capability, 'available': False}
    result = run(service, current, factory(executor, Recognizer([goal('one')])))
    assert result.status == 'failed'
    assert executor.requests == []


def test_mixed_goals_require_exact_source_excerpts():
    service, current = claim()
    selected = factory(Executor(), Recognizer([goal('one'), goal('two')]))
    with pytest.raises(ValueError, match='source excerpt'):
        selected.plan_intent(current, NodeControl(lambda: None, time.monotonic() + 10),
                             service.freeze_attempt_input)


def test_failed_general_result_is_limited_and_does_not_publish_success_answer():
    service, current = claim()
    result = run(service, current, factory(Executor({current.instruction: 'failed'}),
                                           Recognizer([goal('one')])))
    assert result.status == 'completed'
    assert result.admission['mode'] == 'limited'
    assert 'General answer' not in result.answer


def test_completed_artifact_transfer_has_its_own_budget_and_preserves_cancellation(monkeypatch):
    import capstone_agent.delegated_runtime as module
    import capstone_agent.native_artifact_projection as delegation
    clock = [99.0]
    cancelled = [False]
    def check():
        if cancelled[0]:
            raise InterruptedError('Cancelled')
    monkeypatch.setattr(module.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(delegation, 'project_native_artifacts', lambda *args, **kwargs: ['first', 'second'])
    transferred = []
    def retain(*args):
        transferred.append(args[-1])
        clock[0] += 2
    monkeypatch.setattr(delegation, 'retain_native_artifact', retain)
    runtime = object.__new__(module.DelegatedRuntime)
    runtime._claim = object()
    runtime._artifact_store = object()
    runtime._executor = object()
    runtime.runtime_mode = 'capstone'
    result = SimpleNamespace(task_id='task')
    request = SimpleNamespace(parent_attempt_id='attempt', timeout_seconds=60)
    events = []
    runtime._publish_artifacts(result, request, events.append, NodeControl(check, 100))
    assert transferred == ['first', 'second']
    assert len(events) == 2
    cancelled[0] = True
    with pytest.raises(InterruptedError):
        runtime._publish_artifacts(result, request, events.append, NodeControl(check, 100))
    assert transferred == ['first', 'second']
    cancelled[0] = False
    clock[0] = 99
    transferred.clear()
    request.timeout_seconds = 1
    with pytest.raises(TimeoutError):
        runtime._publish_artifacts(result, request, events.append, NodeControl(check, 100))
    assert transferred == ['first']


def test_general_receipts_preserve_sources_and_artifacts_without_authority_refs():
    service, current = claim()
    class WithSource(Executor):
        def execute(self, request, control, on_event):
            result = super().execute(request, control, on_event).to_document()
            for field, key in [('sources', 'source_id'), ('artifacts', 'artifact_id')]:
                result[field] = [{key: key + '-1', 'task_id': request.task_id,
                    'parent_attempt_id': request.parent_attempt_id, 'kind': 'host_observation',
                    'metadata': {'sha256': 'a' * 64}}]
            return PiTaskResult.from_document(result, request)
    result = run(service, current, factory(WithSource(), Recognizer([goal('one')])))
    assert result.status == 'completed'
    events = service.read_events(current.thread_id, 0).events
    refs = [e.payload['reference'] for e in events if 'external_reference_kind' in e.payload]
    assert len(refs) == 2
    assert result.result_refs == result.evidence_refs == ()


def test_host_executor_discovery_is_explicit_bounded_and_credential_private(monkeypatch):
    from capstone_agent.general_executor_composition import configured_general_executor
    from capstone_agent.pi_delegation import HttpGeneralPiExecutor
    assert configured_general_executor({}) is None
    calls = []
    def health(self, method, path, **kwargs):
        calls.append((method, path, kwargs, self._headers))
        return {'identity': Executor.identity, 'capability': Executor.capability}
    monkeypatch.setattr(HttpGeneralPiExecutor, '_call', health)
    executor = configured_general_executor({'CAPSTONE_GENERAL_EXECUTOR_ORIGIN': 'http://general-pi:8790',
                                           'CAPSTONE_GENERAL_CONTROL_TOKEN': 'private-control'})
    assert executor.identity == Executor.identity
    from capstone_agent.delegated_runtime import json_document
    assert json_document(executor.capability) == Executor.capability
    assert calls[0][:2] == ('GET', '/health/ready')
    assert calls[0][2]['total_timeout'] <= 2
    assert 'private-control' not in str(dict(executor.identity)) + str(dict(executor.capability))


@pytest.mark.parametrize('profiles', [{'direct_pi': {'private_path': '/private/input'}}, {'harness_engine': {}}])
def test_executor_discovery_rejects_private_or_professional_resource_profiles(monkeypatch, profiles):
    from capstone_agent.general_executor_composition import configured_general_executor
    from capstone_agent.pi_delegation import HttpGeneralPiExecutor
    monkeypatch.setattr(HttpGeneralPiExecutor, '_call', lambda *_args, **_kwargs: {
        'identity': Executor.identity, 'capability': {**Executor.capability, 'resource_profiles': profiles}})
    with pytest.raises(HarnessRuntimeConfigurationError):
        configured_general_executor({'CAPSTONE_GENERAL_EXECUTOR_ORIGIN': 'http://general-pi:8790'})


def test_typed_external_observations_are_supplemental_not_authority_refs():
    from capstone_agent.kernel_pi_session import external_observations_for_claim
    service, current = claim()
    executor = Executor()
    selected = factory(executor, Recognizer([goal('one')]))
    plan = selected.plan_intent(current, NodeControl(lambda: None, time.monotonic() + 10),
                                service.freeze_attempt_input)
    runtime = selected(replace(current, turn_plan=plan))
    runtime.prompt(current.instruction, on_event=lambda _: None)
    request = executor.requests[0]
    observation = PiTaskResult(request.task_id, request.parent_attempt_id, executor.identity,
                               'completed', 'Outside observation', (), (), {})
    current = replace(current, turn_plan=replace(plan, intent_resources={
        'external_observations': (observation,), 'delegation_parent_attempt_id': request.parent_attempt_id}))
    projected = external_observations_for_claim(current)
    assert projected[0]['answer'] == 'Outside observation'
    assert not {'result_refs', 'evidence_refs'} & projected[0].keys()
    current = replace(current, turn_plan=replace(plan, intent_resources={
        'external_observations': (observation.to_document(),)}))
    with pytest.raises(ValueError, match='typed external observation'):
        external_observations_for_claim(current)


def test_catalog_lookup_uses_frozen_application_catalog_without_general_or_domain():
    service, current = claim()
    current = replace(current, application_catalog={'models': [{'model_id': 'ieee39',
        'display_name': 'IEEE 39', 'implementation_family': 'pandapower'}]})
    executor = Executor()
    result = run(service, current, factory(executor, Recognizer([goal('catalog', 'catalog_lookup')])))
    assert result.status == 'completed'
    assert 'ieee39' in result.answer
    assert executor.requests == []


def test_direct_disabled_executor_is_rejected_before_task():
    service, current = claim()
    current = replace(current, attempt=replace(current.attempt, runtime_mode='pi_reference'))
    executor = Executor()
    executor.capability = {**executor.capability, 'enabled': False}
    result = run(service, current, factory(executor, SimpleNamespace(identity=None)))
    assert result.status == 'failed'
    assert executor.requests == []


def test_general_deadline_expires_and_cancels_child(monkeypatch):
    import capstone_agent.delegated_runtime as runtime_module
    service, current = claim()
    executor = Executor()
    selected = factory(executor, Recognizer([goal('one')]))
    plan = selected.plan_intent(current, NodeControl(lambda: None, time.monotonic() + 10),
                                service.freeze_attempt_input)
    runtime = selected(replace(current, turn_plan=plan))
    original = executor.execute
    def expire(request, control, on_event):
        monkeypatch.setattr(runtime_module.time, 'monotonic', lambda: control.deadline + 1)
        return original(request, control, on_event)
    executor.execute = expire
    with pytest.raises(TimeoutError):
        runtime.prompt(current.instruction, on_event=lambda _: None)
    assert len(executor.cancelled) == 1


def test_general_history_has_text_but_no_model_state_or_prior_authority_refs():
    from capstone_agent.conversation_context import ConversationContext
    from capstone_agent.thread_service import PriorResultReference
    service, current = claim()
    message = {'message_id': 'old', 'role': 'assistant', 'content': 'Previous reader-facing text',
               'turn_id': 'old-turn', 'attempt_id': 'old-attempt', 'model_context_id': 'ctx_test',
               'status': 'completed'}
    current = replace(current, conversation_context=ConversationContext(messages=(message,)),
        prior_results=(PriorResultReference('result:sha256:' + 'a' * 64, (), 'flow', 'old-attempt'),))
    executor = Executor()
    selected_goal = goal('one')
    selected_goal['message_refs'] = [message['message_id']]
    result = run(service, current, factory(executor, Recognizer([selected_goal])))
    assert result.status == 'completed'
    request = executor.requests[0].to_document()
    assert request['messages'][0]['content'] == message['content']
    assert request['messages'][0]['model_context_id'] == ''
    assert 'result:sha256:' not in str(request)


def test_professional_limited_answer_cannot_forge_partial_scheduler_admission():
    service, current = claim()
    current = business_claim(current)
    result = run(service, current, factory(Executor(), Recognizer([
        goal('calc', 'business_execute', refs=['grid@1'])]), lambda _: BusinessRuntime(False)))
    assert result.status == 'failed'


def test_general_goal_receives_only_reader_text_from_its_business_dependency():
    service, current = claim()
    current = business_claim(current)
    executor = Executor()
    result = run(service, current, factory(executor, Recognizer([
        goal('calc', 'business_execute', refs=['grid@1'], excerpt='解释刚才的结论'),
        goal('rewrite', 'rewrite', depends=['calc'], excerpt='翻译成英文')]), lambda _: BusinessRuntime()))
    assert result.status == 'completed'
    context = executor.requests[0].to_document()
    assert any('Authority answer' in message['content'] for message in context['messages'])
    assert context['dependency_results'] == []
    assert 'result-current' not in str(context) and 'evidence-current' not in str(context)


def test_semantic_catalog_describes_actual_general_operations_and_native_tools():
    service, current = claim()
    executor = Executor()
    executor.capability = {**executor.capability, 'native_tools': ['read', 'write', 'bash']}
    recognizer = Recognizer([goal('one')])
    selected = factory(executor, recognizer)
    selected.plan_intent(current, NodeControl(lambda: None, time.monotonic() + 10),
                         service.freeze_attempt_input)
    description = recognizer.requests[0].to_document()['capabilities'][0]['description']
    assert 'external_lookup' in description and 'bash' in description


def test_business_success_survives_independent_general_failure():
    service, current = claim()
    current = business_claim(current)
    executor = Executor({'翻译成英文': 'failed'})
    result = run(service, current, factory(executor, Recognizer([
        goal('calc', 'business_execute', refs=['grid@1'], excerpt='解释刚才的结论'),
        goal('other', 'answer', excerpt='翻译成英文')]), lambda _: BusinessRuntime()))
    assert result.status == 'completed'
    assert result.admission['mode'] == 'authority_backed'
    assert result.result_refs == ('result-current',)
    assert result.evidence_refs == ('evidence-current',)
    assert 'Authority answer' in result.answer and 'failed' in result.answer


def test_business_clarification_does_not_prepare_domain_or_invent_partial_success():
    service, current = claim()
    selected = factory(Executor(), Recognizer([goal('calc', 'business_execute', missing=['target'])]))
    result = run(service, current, selected)
    assert result.status == 'completed'
    assert 'Business task was not executed' in result.answer
    assert result.admission['mode'] == 'limited'
    assert result.result_refs == result.evidence_refs == ()


def test_executor_failure_has_child_terminal_receipt_and_preserves_cancel_failure_cause():
    service, current = claim()
    class Broken(Executor):
        def execute(self, request, control, on_event):
            raise RuntimeError('host lost')
        def cancel(self, task_id):
            raise RuntimeError('cancel unknown')
    result = run(service, current, factory(Broken(), Recognizer([goal('one')])))
    assert result.status == 'completed'
    events = service.read_events(current.thread_id, 0).events
    assert any(e.payload.get('child_status') == 'failed' for e in events)


def test_large_source_metadata_is_saved_as_bounded_receipt():
    service, current = claim()
    class Large(Executor):
        def execute(self, request, control, on_event):
            return PiTaskResult(request.task_id, request.parent_attempt_id, self.identity,
                'completed', 'General answer', ({'source_id': 'source-large',
                    'task_id': request.task_id, 'parent_attempt_id': request.parent_attempt_id,
                    'kind': 'host_observation', 'metadata': {'details': 'a' * 65536}},), (), {})
    result = run(service, current, factory(Large(), Recognizer([goal('one')])))
    assert result.status == 'completed'
    assert result.answer == 'General answer'
    events = service.read_events(current.thread_id, 0).events
    source = next(e.payload['reference'] for e in events if e.payload.get('external_reference_kind') == 'sources')
    assert source['source_id'] == 'source-large'
    assert len(source['metadata']['details']) <= 256
    assert len(source['metadata_sha256']) == 64


def test_receipt_write_failure_is_fatal_even_after_general_success():
    service, current = claim()
    selected = factory(Executor(), Recognizer([goal('one')]))
    plan = selected.plan_intent(current, NodeControl(lambda: None, time.monotonic() + 10),
                                service.freeze_attempt_input)
    runtime = selected(replace(current, turn_plan=plan))
    def broken_sink(event):
        if event['payload'].get('child_status') == 'completed':
            raise RuntimeError('ledger unavailable')
    from capstone_agent.delegated_runtime import GoalReceiptPersistenceError
    with pytest.raises(GoalReceiptPersistenceError):
        runtime.prompt(current.instruction, on_event=broken_sink)


@pytest.mark.parametrize('mode', ['direct', 'delegated'])
@pytest.mark.parametrize('event_type', ['assistant_delta', 'message_update'])
@pytest.mark.parametrize('child_status', ['completed', 'failed'])
def test_worker_keeps_general_process_text_diagnostic(mode, event_type, child_status):
    service, current = claim()
    if mode == 'direct':
        current = replace(current, attempt=replace(current.attempt, runtime_mode='pi_reference'))
    class ProcessExecutor(Executor):
        def execute(self, request, control, on_event):
            self.requests.append(request)
            payload = ({'type': 'assistant_delta', 'text': 'PROCESS_PREFACE'}
                       if event_type == 'assistant_delta' else
                       {'type': 'message_update', 'assistantMessageEvent': {'type': 'text_delta', 'delta': 'PROCESS_PREFACE'}})
            on_event(payload)
            return PiTaskResult(request.task_id, request.parent_attempt_id, self.identity,
                                child_status, 'General answer', (), (), {})
    result = run(service, current, factory(ProcessExecutor(), Recognizer([goal('one')])))
    events = service.read_events(current.thread_id, 0).events
    assert not any(event.event_type == 'assistant_text_delta' and event.visibility == 'public'
                   for event in events)
    process = [event for event in events if event.event_type == 'assistant_process_delta']
    assert len(process) == 1 and process[0].visibility == 'diagnostic'
    assert process[0].payload['text'] == 'PROCESS_PREFACE'
    assert not any(event.event_type == 'runtime_event'
        and event.payload.get('native_type') in {'assistant_delta', 'message_update'} for event in events)
    assert 'PROCESS_PREFACE' not in (result.answer or '')
    if child_status == 'completed':
        assert result.status == 'completed' and result.answer == 'General answer'
    assert all(event.visibility == 'diagnostic' for event in events if event.event_type == 'runtime_event')


def test_native_live_tool_projection_preserves_host_receipt_identity_without_private_content():
    service, current = claim()
    class LiveExecutor(Executor):
        def execute(self, request, control, on_event):
            for kind in ('tool_execution_start', 'tool_execution_end'):
                on_event({'type': kind, 'tool_name': 'bash', 'tool_call_id': 'call-live-1',
                          'is_error': False, 'args': {'command': 'PRIVATE_COMMAND'},
                          'result': {'content': 'PRIVATE_OUTPUT'}})
            return PiTaskResult(request.task_id, request.parent_attempt_id, self.identity,
                                'completed', 'General answer', (), (), {})
    run(service, current, factory(LiveExecutor(), Recognizer([goal('one')])))
    events = [event.payload for event in service.read_events(current.thread_id, 0).events
              if event.event_type == 'runtime_event' and event.payload.get('native_type')]
    assert [event['native_type'] for event in events] == ['tool_execution_start', 'tool_execution_end']
    assert all(event['tool_name'] == 'bash' and event['tool_call_id'] == 'call-live-1' for event in events)
    assert events[-1]['is_error'] is False
    assert all('args' not in event and 'result' not in event for event in events)
    projected = [event for event in service.read_events(current.thread_id, 0).events
                 if event.event_type == 'runtime_event' and event.payload.get('native_type')]
    assert all(event.visibility == 'public' for event in projected)
    assert all(event.visibility == 'diagnostic' for event in service.read_events(current.thread_id, 0).events
               if event.event_type == 'runtime_event' and not event.payload.get('native_type'))


@pytest.mark.parametrize('fails', [False, True])
def test_text_is_complete_and_precedes_tools_and_child_failure(fails):
    service, current = claim()
    before_tool = '甲乙丙丁' * 10
    tail = '尾部未满一批的文字'
    class Streaming(Executor):
        def execute(self, request, control, on_event):
            for text in before_tool:
                on_event({'type': 'assistant_delta', 'text': text})
            on_event({'type': 'tool_execution_start', 'tool_name': 'read', 'tool_call_id': 'read-1'})
            on_event({'type': 'tool_execution_end', 'tool_name': 'read', 'tool_call_id': 'read-1', 'is_error': False})
            for text in tail:
                on_event({'type': 'assistant_delta', 'text': text})
            if fails:
                raise RuntimeError('runtime stopped')
            return PiTaskResult(request.task_id, request.parent_attempt_id, self.identity,
                                'completed', 'General answer', (), (), {})
    result = run(service, current, factory(Streaming(), Recognizer([goal('one')])))
    events = service.read_events(current.thread_id, 0).events
    text_events = [e for e in events if e.event_type == 'assistant_process_delta']
    assert ''.join(e.payload['text'] for e in text_events) == before_tool + tail
    tool = next(e for e in events if e.payload.get('native_type') == 'tool_execution_start')
    assert ''.join(e.payload['text'] for e in text_events if e.event_seq < tool.event_seq) == before_tool
    if fails:
        failed = next(e for e in events if e.payload.get('child_status') == 'failed')
        assert all(e.event_seq < failed.event_seq for e in text_events)
    else:
        assert result.status == 'completed'


def test_executor_configuration_cannot_change_between_plan_and_runtime_preparation():
    service, current = claim()
    executor = Executor()
    selected = factory(executor, Recognizer([goal('one')]))
    plan = selected.plan_intent(current, NodeControl(lambda: None, time.monotonic() + 10),
                                service.freeze_attempt_input)
    executor.identity = {'engine': 'pi', 'config_revision': 'changed'}
    with pytest.raises(HarnessRuntimeConfigurationError, match='configuration'):
        selected(replace(current, turn_plan=plan))


def test_hosted_http_retry_replays_child_without_repeating_action(tmp_path):
    import threading
    from capstone_agent.general_pi_server import GeneralPiHost, make_server
    from capstone_agent.general_executor_composition import configured_general_executor
    actions = []
    host = GeneralPiHost(root=tmp_path, identity=Executor.identity,
        run_task=lambda request, cancelled, emit: (actions.append(request.task_id) or 'Saved answer', {}))
    server = make_server(host, control_token='private-test-control', address=('127.0.0.1', 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        executor = configured_general_executor({'CAPSTONE_GENERAL_EXECUTOR_ORIGIN':
            f'http://127.0.0.1:{server.server_port}', 'CAPSTONE_GENERAL_CONTROL_TOKEN': 'private-test-control'})
        service, current = claim()
        selected = factory(executor, Recognizer([goal('one')]))
        frozen = []
        freeze = lambda _, document: frozen[0] if frozen else (frozen.append(document) or document)
        control = NodeControl(lambda: None, time.monotonic() + 10)
        for attempt_id in (current.attempt.attempt_id, 'retry-attempt'):
            retry = replace(current, attempt=replace(current.attempt, attempt_id=attempt_id))
            plan = selected.plan_intent(retry, control, freeze)
            runtime = selected(replace(retry, turn_plan=plan))
            assert runtime.prompt(current.instruction, on_event=lambda _: None) == 'Saved answer'
            runtime.stop()
        assert len(actions) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
