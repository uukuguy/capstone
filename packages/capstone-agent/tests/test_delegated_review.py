from dataclasses import replace
import json
import threading
import time

import pytest

from capstone_agent.harness import AdmittedAttemptAnswer
from capstone_agent.pi_delegation import PiTaskResult
from capstone_agent.request_intent import NodeControl
from test_delegated_runtime import Executor, Recognizer, BusinessRuntime, business_claim, factory, goal, run
from test_intent_runtime import claim


def test_business_dependency_is_typed_current_attempt_input_with_admitted_refs():
    service, current = claim()
    current = business_claim(current)
    captured, admissions = [], []
    class Runtime(BusinessRuntime):
        def admit_attempt(self, scoped, answer, results, evidence, events):
            admissions.append((results, evidence, events))
            return super().admit_attempt(scoped, answer, results, evidence, events)
    def business(scoped):
        captured.append(scoped)
        return Runtime()
    result = run(service, current, factory(Executor(), Recognizer([
        goal('baseline', 'business_execute', refs=['grid@1'], excerpt='解释刚才的结论'),
        goal('compare', 'business_read', refs=['grid@1'], depends=['baseline'], excerpt='翻译成英文')]), business))
    assert result.status == 'completed'
    dependency = captured[1].turn_plan.intent_resources.get('business_goal_dependencies', ())
    assert len(dependency) == 1
    from capstone_agent.business_goal_dependency import AdmittedBusinessGoalDependency
    assert isinstance(dependency[0], AdmittedBusinessGoalDependency)
    document = dependency[0].to_document()
    assert document['attempt_id'] == current.attempt.attempt_id
    assert document['goal_id'] == 'baseline'
    assert document['answer'] == 'Authority answer'
    assert document['admission']['result_refs'] == ['result-current']
    assert document['admission']['evidence_refs'] == ['evidence-current']
    assert captured[1].prior_results == ()
    assert captured[1].turn_plan.intent_request.to_document()['messages'] == []
    assert 'result-current' in admissions[1][0]
    assert len(admissions[1][2]) == 2


@pytest.mark.parametrize('available', [True, False])
@pytest.mark.parametrize('count', [1, 2])
def test_business_projection_runs_before_child_stops_and_reaches_thread(available, count):
    from test_harness import _network_projection
    service, current = claim()
    current = business_claim(current)
    callbacks = []
    class Runtime(BusinessRuntime):
        network_projection_enabled = True
        network_projection_failure_code = 'projection_source_unavailable'
        stopped = False
        def network_projection(self, scoped, results, evidence, events):
            assert not self.stopped
            assert results == ('result-current',) and evidence == ('evidence-current',)
            callbacks.append(scoped.instruction)
            if not available:
                return None
            projection = _network_projection()
            projection['diagram']['model']['revision'] = scoped.model_context.model_revision
            return projection
        def stop(self):
            self.stopped = True
    goals = ([goal('calc', 'business_execute', refs=['grid@1'])] if count == 1 else [
        goal('calc', 'business_execute', refs=['grid@1'], excerpt='解释刚才的结论'),
        goal('read', 'business_read', refs=['grid@1'], excerpt='翻译成英文')])
    result = run(service, current, factory(Executor(), Recognizer(goals), lambda _: Runtime()))
    assert result.status == 'completed'
    assert callbacks == ([current.instruction] if count == 1 else ['解释刚才的结论', '翻译成英文'])
    events = service.read_events(current.thread_id, 0).events
    if available:
        assert any(event.event_type == 'network_diagram' for event in events)
        assert any(event.event_type == 'network_layer' for event in events)
    else:
        assert any(event.event_type == 'network_layer_unavailable'
                   and event.payload['code'] == 'projection_source_unavailable' for event in events)


@pytest.mark.parametrize('direct', [False, True])
def test_real_host_delta_stream_reaches_worker_in_both_entries(tmp_path, direct):
    from capstone_agent.general_pi_server import GeneralPiHost, make_server
    from capstone_agent.general_executor_composition import configured_general_executor
    def execute(request, cancelled, emit):
        emit({'type': 'message_update', 'assistantMessageEvent': {'type': 'text_delta', 'delta': 'Streamed text'}})
        return 'Streamed text', {}
    host = GeneralPiHost(root=tmp_path, identity=Executor.identity, run_task=execute)
    server = make_server(host, control_token='fixture-control', address=('127.0.0.1', 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        executor = configured_general_executor({'CAPSTONE_GENERAL_EXECUTOR_ORIGIN':
            f'http://127.0.0.1:{server.server_port}', 'CAPSTONE_GENERAL_CONTROL_TOKEN': 'fixture-control'})
        service, current = claim()
        if direct:
            current = replace(current, attempt=replace(current.attempt, runtime_mode='pi_reference'))
        result = run(service, current, factory(executor, Recognizer([goal('one')])))
        assert result.status == 'completed'
        text = [event.payload['text'] for event in service.read_events(current.thread_id, 0).events
                if event.event_type == 'assistant_text_delta']
        assert text == ['Streamed text']
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize('text,multiple', [('a' * 40000, True), ('"' * 40000, False), ('电' * 20000, True)],
                         ids=['multiple_ascii', 'escaped_quotes', 'multibyte'])
def test_valid_large_child_answers_fit_parent_terminal_json_and_remain_complete(text, multiple):
    service, current = claim()
    class Large(Executor):
        def execute(self, request, control, on_event):
            self.requests.append(request)
            return PiTaskResult(request.task_id, request.parent_attempt_id, self.identity,
                                'completed', text, (), (), {})
    executor = Large()
    goals = ([goal('one', excerpt='解释刚才的结论'), goal('two', excerpt='翻译成英文')]
             if multiple else [goal('one')])
    result = run(service, current, factory(executor, Recognizer(goals)))
    assert result.status == 'completed'
    terminal = service.read_events(current.thread_id, 0).events[-1]
    assert len(json.dumps(dict(terminal.payload), ensure_ascii=False, sort_keys=True).encode()) <= 65536
    assert 'shortened' in result.answer
    assert result.result_refs == result.evidence_refs == ()


def test_general_shortening_preserves_full_professional_answer_and_refs():
    service, current = claim()
    current = business_claim(current)
    professional = 'Verified professional text. ' + ('x' * 12000)
    class Runtime(BusinessRuntime):
        def admit_attempt(self, *args):
            return AdmittedAttemptAnswer(professional, 'authority_backed', 'lineage_verified',
                                        ('result-current',), ('evidence-current',))
    class Large(Executor):
        def execute(self, request, control, on_event):
            return PiTaskResult(request.task_id, request.parent_attempt_id, self.identity,
                                'completed', '"' * 40000, (), (), {})
    result = run(service, current, factory(Large(), Recognizer([
        goal('one', excerpt='解释刚才的结论'),
        goal('calc', 'business_execute', refs=['grid@1'], excerpt='翻译成英文')]), lambda _: Runtime()))
    assert result.status == 'completed'
    assert professional in result.answer
    assert 'shortened' in result.answer
    assert result.result_refs == ('result-current',)
    assert result.evidence_refs == ('evidence-current',)


def test_executor_unavailable_is_safe_configuration_failure_and_preserves_model():
    service, current = claim()
    result = run(service, current, factory(None, Recognizer([goal('one')])))
    assert result.error_code == 'runtime_configuration_invalid'
    assert service.snapshot(current.thread_id).active_model_context == current.model_context


def test_executor_configuration_drift_is_safe_configuration_failure():
    service, current = claim()
    executor = Executor()
    selected = factory(executor, Recognizer([goal('one')]))
    selected.plan_intent(current, NodeControl(lambda: None, time.monotonic() + 10), service.freeze_attempt_input)
    executor.identity = {'engine': 'pi', 'config_revision': 'changed'}
    result = run(service, current, selected)
    assert result.error_code == 'runtime_configuration_invalid'


def projected_runtime(scoped, *, rows=32):
    from test_result_projection import valid_projection
    projection = valid_projection()
    result_ref, evidence_ref = projection['result_ref'], projection['evidence_refs'][0]
    projection.update(thread_id=scoped.thread_id, run_id=scoped.run_id,
        turn_id=scoped.attempt.turn_id, attempt_id=scoped.attempt.attempt_id,
        model_context_id=scoped.model_context_id, model_id=scoped.model_context.model_id,
        model_revision=scoped.model_context.model_revision)
    projection.update(element_refs=[], overlay=None)
    projection['tables'][0]['rows'] = [
        {'row_id': f'row_{index}', 'cells': {'line': '"' * 256, 'loading': 67.15}}
        for index in range(rows)]
    class Runtime(BusinessRuntime):
        def prompt(self, question, **kwargs):
            kwargs['on_event']({'event_type': 'tool_completed', 'runtime_mode': 'capstone',
                'visibility': 'public', 'payload': {'tool_name': 'grid_calc',
                    'result_refs': [result_ref], 'evidence_refs': [evidence_ref]}})
            return 'Verified professional facts.'
        def admit_attempt(self, scoped, answer, *args):
            return AdmittedAttemptAnswer(answer, 'authority_backed', 'lineage_verified',
                (result_ref,), (evidence_ref,), result_projections=(projection,))
    return Runtime(), projection


def test_answer_budget_reserves_exact_result_projection_and_admitted_refs():
    service, current = claim()
    current = business_claim(current)
    current = replace(current, model_context=replace(current.model_context,
        model_revision='revision:sha256:' + 'c' * 64))
    projections = []
    def business(scoped):
        runtime, projection = projected_runtime(scoped)
        projections.append(projection)
        return runtime
    class Large(Executor):
        def execute(self, request, control, on_event):
            return PiTaskResult(request.task_id, request.parent_attempt_id, self.identity,
                                'completed', '"' * 40000, (), (), {})
    result = run(service, current, factory(Large(), Recognizer([
        goal('one', excerpt='解释刚才的结论'),
        goal('calc', 'business_execute', refs=['grid@1'], excerpt='翻译成英文')]), business))
    assert result.status == 'completed'
    terminal = service.read_events(current.thread_id, 0).events[-1]
    assert len(json.dumps(dict(terminal.payload), ensure_ascii=False, sort_keys=True).encode()) <= 65536
    assert 'Verified professional facts.' in result.answer and 'shortened' in result.answer
    assert result.result_refs == (projections[0]['result_ref'],)
    assert result.evidence_refs == tuple(projections[0]['evidence_refs'])
    assert terminal.payload['result_projections'][0]['tables'] == projections[0]['tables']


@pytest.mark.parametrize('conflicting', [False, True])
def test_dependency_projection_reuse_is_deduplicated_only_when_identical(conflicting):
    service, current = claim()
    current = business_claim(current)
    current = replace(current, model_context=replace(current.model_context,
        model_revision='revision:sha256:' + 'c' * 64))
    prepared = []
    def business(scoped):
        runtime, projection = projected_runtime(scoped, rows=1)
        if prepared and conflicting:
            projection['summary'][0]['value'] = 99
        prepared.append(projection)
        return runtime
    result = run(service, current, factory(Executor(), Recognizer([
        goal('baseline', 'business_execute', refs=['grid@1'], excerpt='解释刚才的结论'),
        goal('compare', 'business_read', refs=['grid@1'], depends=['baseline'], excerpt='翻译成英文')]), business))
    if conflicting:
        assert result.status == 'failed'
        assert result.answer is None
    else:
        assert result.status == 'completed'
        assert len(service.snapshot(current.thread_id).result_projections) == 1


def test_oversized_professional_text_has_complete_admitted_receipt_before_excerpt():
    service, current = claim()
    current = business_claim(current)
    text = 'Verified professional text: ' + '"' * 40000
    class Runtime(BusinessRuntime):
        def admit_attempt(self, *args):
            return AdmittedAttemptAnswer(text, 'authority_backed', 'lineage_verified',
                ('result-current',), ('evidence-current',))
    result = run(service, current, factory(Executor(), Recognizer([
        goal('calc', 'business_execute', refs=['grid@1'])]), lambda _: Runtime()))
    assert result.status == 'completed'
    assert result.answer.startswith('Verified professional text: ') and 'shortened' in result.answer
    events = service.read_events(current.thread_id, 0).events
    chunks = [event.payload for event in events if event.payload.get('business_answer_receipt')]
    assert len(chunks) == chunks[0]['chunk_count']
    document = json.loads(''.join(item['content'] for item in sorted(chunks, key=lambda item: item['chunk_index'])))
    assert document['answer'] == text
    assert document['admission']['result_refs'] == list(result.result_refs)
    assert document['admission']['evidence_refs'] == list(result.evidence_refs)
    from hashlib import sha256
    assert sha256(json.dumps(document, ensure_ascii=False, sort_keys=True).encode()).hexdigest() == chunks[0]['business_answer_receipt']


def test_metadata_only_overflow_fails_without_discarding_authority_receipt():
    service, current = claim()
    original_model = service.snapshot(current.thread_id).active_model_context
    current = business_claim(current)
    references = tuple(f'result-{index:03}-' + 'r' * 501 for index in range(128))
    class Runtime(BusinessRuntime):
        def prompt(self, question, **kwargs):
            for offset in (0, 64):
                kwargs['on_event']({'event_type': 'tool_completed', 'runtime_mode': 'capstone',
                    'visibility': 'public', 'payload': {'tool_name': 'grid_calc',
                        'result_refs': references[offset:offset + 64], 'evidence_refs': ['evidence-current']}})
            return 'Verified answer'
        def admit_attempt(self, *args):
            return AdmittedAttemptAnswer('Verified answer', 'authority_backed', 'lineage_verified',
                references, ('evidence-current',))
    result = run(service, current, factory(Executor(), Recognizer([
        goal('calc', 'business_execute', refs=['grid@1'])]), lambda _: Runtime()))
    assert result.status == 'failed' and result.error_code == 'runtime_failed'
    assert result.answer is None
    events = service.read_events(current.thread_id, 0).events
    chunks = [event.payload for event in events if event.payload.get('business_answer_receipt')]
    document = json.loads(''.join(item['content'] for item in sorted(chunks, key=lambda item: item['chunk_index'])))
    assert document['admission']['result_refs'] == list(references)
    assert document['admission']['evidence_refs'] == ['evidence-current']
    assert service.snapshot(current.thread_id).active_model_context == original_model


@pytest.mark.parametrize('fault', ['attempt', 'goal', 'model', 'capability', 'raw'])
def test_business_dependency_rejects_foreign_or_untyped_scope(fault):
    from capstone_agent.business_goal_dependency import AdmittedBusinessGoalDependency, business_dependencies_for_claim
    service, current = claim()
    current = business_claim(current)
    captured = []
    def business(scoped):
        captured.append(scoped)
        return BusinessRuntime()
    assert run(service, current, factory(Executor(), Recognizer([
        goal('one', 'business_execute', refs=['grid@1'], excerpt='解释刚才的结论'),
        goal('two', 'business_read', refs=['grid@1'], depends=['one'], excerpt='翻译成英文')]), business)).status == 'completed'
    scoped = captured[1]
    resources = dict(scoped.turn_plan.intent_resources)
    admitted = AdmittedAttemptAnswer('Verified answer', 'authority_backed', 'lineage_verified',
                                     ('result-current',), ('evidence-current',))
    dependency = AdmittedBusinessGoalDependency(
        'foreign' if fault == 'attempt' else current.attempt.attempt_id,
        'foreign' if fault == 'goal' else 'one',
        'foreign' if fault == 'model' else current.model_context_id,
        ('foreign@1',) if fault == 'capability' else ('grid@1',), admitted, ())
    resources['business_goal_dependencies'] = (dependency.to_document() if fault == 'raw' else dependency,)
    scoped = replace(scoped, turn_plan=replace(scoped.turn_plan, intent_resources=resources))
    with pytest.raises(ValueError, match='scope|typed'):
        business_dependencies_for_claim(scoped)
