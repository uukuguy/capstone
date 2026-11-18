"""An open model stays management context on the enterprise main chain."""
from dataclasses import replace
import json
import threading
import time

import pytest

from capstone_agent.native_hosted_worker import native_runtime_factory
from capstone_agent.request_intent import NodeControl
from capstone_agent.structural_context import checked_structural_context, structural_context_for
from capstone_agent.thread_protocol import ModelContextSnapshot
from capstone_agent.thread_service import _attempt_family_predicate
from capstone_agent.thread_worker import run_pending_attempt
from capstone_agent.worker_wake import create_wake_app, wake_token
from test_unscoped_research_intent import governed_executor, open_store, publish_domain
from test_thread_work_execution import command
from test_thread_postgres import postgres_thread_service


def _model():
    return ModelContextSnapshot(
        'ctx_ieee39', 'ieee39', 'revision:sha256:' + 'a' * 64, 'pandapower', 'sel_ieee39',
        enabled_profiles=(('pandapower-static-analysis', '1.0.0'),))


def _store(executor, session_type):
    store = open_store(executor, session_type=session_type)
    store._snapshot = replace(store._snapshot, active_model_context=_model(), active_grid_page_id='page_ieee39')
    publish_domain(store, families=('pandapower', 'pypsa'))
    receipt = store.submit_command(command(
        store, 'thr_unscoped', 'send_message', session_type,
        payload={'text': '数据网关的业务数据情况'}))
    assert receipt.status == 'accepted', receipt.rejection
    return store


def test_general_pi_image_carries_the_structural_context_module():
    from pathlib import Path
    root = Path(__file__).resolve().parents[3]
    image = (root / 'deploy/general-pi.Dockerfile').read_text()
    assert 'packages/capstone-agent/src/capstone_agent/structural_context.py' in image
    server = (root / 'packages/capstone-agent/src/capstone_agent/general_pi_server.py').read_text()
    assert "'pi_delegation.py', 'structural_context.py'" in server


def test_structural_context_names_refs_and_rejects_tool_payloads():
    from types import SimpleNamespace
    claim = SimpleNamespace(
        model_context=_model(),
        prior_results=(SimpleNamespace(
            result_ref='result:sha256:' + 'b' * 64,
            evidence_refs=('evidence:sha256:' + 'c' * 64, '{"bus": 1, "vn_kv": 345}'),
        ),))
    document = structural_context_for(claim)
    assert document['schema'] == 'capstone-structural-context/1'
    assert document['model']['model_id'] == 'ieee39'
    assert document['handles'] == [
        {'kind': 'result_ref', 'ref': 'result:sha256:' + 'b' * 64},
        {'kind': 'evidence_ref', 'ref': 'evidence:sha256:' + 'c' * 64},
    ]
    encoded = json.dumps(document)
    assert 'vn_kv' not in encoded and 'bus' not in encoded
    with pytest.raises(ValueError, match='structural context'):
        checked_structural_context({**document, 'model': {**document['model'], 'buses': []}})


def test_model_free_scope_uses_frozen_work_run_and_thread():
    from types import SimpleNamespace

    from capstone_agent.structural_context import management_for, management_note

    def binding(thread='thr_one', run='run_one', work='work_one', attempt='attempt_one'):
        claim = SimpleNamespace(thread_id=thread, run_id=run, model_context=None,
            task_context=SimpleNamespace(binding=SimpleNamespace(work_id=work)), attempt=attempt)
        structural = structural_context_for(claim)
        management = management_for(structural)
        assert 'work_scope' not in management_note(structural)
        return management

    original = binding()
    assert original == binding(attempt='attempt_two')
    assert original != binding(thread='thr_two')
    assert original != binding(run='run_two')
    assert original != binding(work='work_two')


def test_family_predicate_keeps_native_execution_ahead_of_the_open_model():
    sql = _attempt_family_predicate('a.')
    assert sql.count('%s') == 5
    assert '{{' not in sql
    assert "a.submission_snapshot ? '_native_execution'" in sql
    assert "a.submission_snapshot #>> '{_domain_execution,implementation_family}'" in sql


def test_enterprise_research_keeps_an_open_model_on_the_main_chain():
    executor = governed_executor()
    executor.capability['data_gateway'] = {
        'available': True,
        'catalog': {'tools': ['data_gateway_discover_data_inventory']},
    }
    store = _store(executor, 'enterprise-research')
    assert store.claim_attempt('grid', 30, 'pandapower') is None
    claim = store.claim_attempt('native', 30, 'native')
    assert claim is not None
    assert isinstance(claim.submission['_native_execution']['identity'], dict)
    model_object = claim.submission['objects'][0]
    assert model_object['object_id'] == 'ctx_ieee39'
    assert model_object['model_revision'].startswith('revision:sha256:')
    assert 'bus' not in json.dumps(model_object)
    plan = native_runtime_factory(executor, recognizer_factory=lambda: pytest.fail('main chain must not classify')).plan_intent(
        claim, NodeControl(lambda: None, time.monotonic() + 30),
        store.freeze_attempt_input, freeze_decision=store.freeze_attempt_decision)
    assert plan.source == 'native_conversation'
    assert plan.context_snapshot['model_id'] == 'ieee39'
    structural = plan.intent_resources['structural_context']
    assert structural['schema'] == 'capstone-structural-context/1'
    assert structural['model']['model_context_id'] == 'ctx_ieee39'
    assert 'vn_kv' not in json.dumps(structural)
    assert plan.intent_decision.to_document()['goals'][0]['object_refs'] == ['ctx_ieee39']


def test_open_model_main_chain_carries_management_context_and_both_tool_grants():
    executor = governed_executor()
    executor.capability['data_gateway'] = {
        'available': True,
        'catalog': {'tools': ['data_gateway_discover_data_inventory']},
    }
    store = _store(executor, 'enterprise-research')
    result = run_pending_attempt(store, native_runtime_factory(executor),
        worker_id='native', implementation_family='native')
    assert result.status == 'completed', [event.payload for event in store.read_events('thr_unscoped', 0).events
                                          if event.event_type == 'attempt_failed']
    request = executor.requests[0]
    document = request.to_document()
    assert document['structural_context']['model']['model_id'] == 'ieee39'
    assert 'vn_kv' not in json.dumps(document['structural_context'])
    assert {item['implementation_family'] for item in request.domain_tools['profiles']} == {'pandapower'}
    assert 'data_gateway_discover_data_inventory' in request.native_context['policy']['allowed_tools']


def test_native_plan_freezes_only_visible_admitted_prior_results():
    from capstone_agent.conversation_context import ConversationContext
    from capstone_agent.thread_service import PriorResultReference

    executor = governed_executor()
    store = _store(executor, 'enterprise-research')
    claim = store.claim_attempt('native', 30, 'native')
    assert claim is not None
    ref = 'result:sha256:' + 'a' * 64
    evidence = 'evidence:sha256:' + 'b' * 64
    message = {'message_id': 'msg_old', 'role': 'assistant', 'content': '先前结果',
        'turn_id': 'turn_old', 'attempt_id': 'attempt_old', 'model_context_id': _model().id,
        'status': 'completed'}
    claim = replace(claim, conversation_context=ConversationContext(messages=(message,)), prior_results=(
        PriorResultReference(ref, (evidence,), 'capability.example', 'attempt_old'),
        PriorResultReference('result:sha256:' + 'c' * 64, (), 'capability.example', 'attempt_hidden'),
    ))
    plan = native_runtime_factory(executor).plan_intent(claim, NodeControl(lambda: None, time.monotonic() + 30),
        store.freeze_attempt_input, freeze_decision=store.freeze_attempt_decision)
    resources = plan.intent_resources
    assert [item['result_ref'] for item in resources['prior_results']] == [ref]
    assert resources['structural_context']['handles'] == [
        {'kind': 'result_ref', 'ref': ref}, {'kind': 'evidence_ref', 'ref': evidence}]


@pytest.mark.parametrize('summary', ['已完成计算，报告可查计算步骤。', '字' * 481])
def test_enterprise_main_chain_commits_model_summary_with_formal_answer(summary):
    executor = governed_executor()
    execute = executor.execute

    def answer(request, control, emit):
        return replace(execute(request, control, emit), answer=json.dumps({
            'answer': '正式回答：报告提供计算步骤。',
            'summary': summary,
        }, ensure_ascii=False))

    executor.execute = answer
    store = _store(executor, 'enterprise-research')
    result = run_pending_attempt(store, native_runtime_factory(executor),
        worker_id='native', implementation_family='native')
    assert result.status == 'completed'
    request = executor.requests[0]
    assert request.instruction == '数据网关的业务数据情况'
    assert type(request).from_document(request.to_document()).answer_format == 'formal-and-core/1'
    assert request.structural_context['model']['model_context_id'] == 'ctx_ieee39'
    assert request.structural_context['model']['model_revision'] == _model().model_revision
    assert request.structural_context['model']['selection_revision'] == _model().selection_revision
    assert request.structural_context['model']['enabled_profiles'][0]['profile_id'] == 'pandapower-static-analysis'
    completed = next(event for event in store.read_events('thr_unscoped', 0).events
                     if event.event_type == 'attempt_completed')
    assert completed.payload['answer'] == '正式回答：报告提供计算步骤。'
    assert completed.payload.get('answer_core_summary') == (summary if len(summary) <= 480 else None)


def test_core_reply_cannot_survive_a_changed_or_recovered_answer():
    from types import SimpleNamespace

    from capstone_agent.harness import _core_summary_payload

    runtime = SimpleNamespace(answer_core_bundle=('accepted', 'summary'))
    assert _core_summary_payload(runtime, 'accepted', 'accepted', False) == {'answer_core_summary': 'summary'}
    assert _core_summary_payload(runtime, 'accepted', 'rewritten', False) == {}
    assert _core_summary_payload(runtime, 'accepted', 'accepted', True) == {}


@pytest.mark.parametrize('backend', ('memory', 'postgres'))
def test_verified_native_receipt_reaches_same_work_without_text_refs(backend, request):
    from capstone_agent.structural_context import AUTHORITY_REFERENCE_SOURCE

    executor = governed_executor()
    execute = executor.execute
    ref = 'result:sha256:' + 'b' * 64
    evidence = 'evidence:sha256:' + 'c' * 64
    forged = 'result:sha256:' + 'd' * 64
    receipt = {'authority_id': 'example', 'capability_id': 'analysis.run',
               'result_refs': [ref], 'evidence_refs': [evidence]}

    def answer(request, control, emit):
        child = execute(request, control, emit)
        sources = ()
        if request.instruction == 'Calculate':
            sources = ({
                'source_id': 'authority-source', 'task_id': request.task_id,
                'parent_attempt_id': request.parent_attempt_id,
                'kind': AUTHORITY_REFERENCE_SOURCE, 'metadata': receipt,
            },)
        return replace(child, sources=sources, answer=json.dumps({
            'answer': 'Saved result. Text only: ' + forged, 'summary': 'Saved result.'}))

    executor.execute = answer
    if backend == 'memory':
        store = open_store(executor, session_type='enterprise-research')
        thread_id = 'thr_unscoped'
    else:
        from test_thread_postgres import _snapshot
        store, thread_id = request.getfixturevalue('postgres_thread_service')
        store.create_thread(replace(_snapshot(thread_id), active_model_context=None, active_grid_page_id=None,
            minimum_protocol_version=2, session_type='enterprise-research'))
        store.set_native_executor(executor)

    def send(name, instruction, **target):
        accepted = store.submit_command(command(store, thread_id, 'send_message', name,
            payload={'text': instruction}, **target))
        assert accepted.status == 'accepted', accepted.rejection
        outcome = run_pending_attempt(store, native_runtime_factory(executor),
            worker_id='native', implementation_family='native')
        assert outcome.status == 'completed', [event.payload for event in store.read_events(thread_id, 0).events
                                                if event.event_type == 'attempt_failed']

    send('calculate', 'Calculate')
    first = next(event.payload for event in store.read_events(thread_id, 0).events
                 if event.event_type == 'attempt_completed')
    assert first['result_refs'] == [ref]
    assert first['evidence_refs'] == [evidence]
    assert first['authority_references'] == [receipt]
    work = store.snapshot(thread_id).works[0]
    send('continue', 'Reuse', work_id=work['work_id'], revision=work['revision'])
    assert executor.requests[-1].to_document()['structural_context']['handles'] == [
        {'kind': 'result_ref', 'ref': ref}, {'kind': 'evidence_ref', 'ref': evidence}]


@pytest.mark.parametrize('channel', ('native_events', 'native_result'))
def test_only_typed_host_sources_can_carry_protected_refs(channel):
    from capstone_agent.pi_delegation import _json_document
    from capstone_agent.structural_context import AUTHORITY_REFERENCE_SOURCE

    receipt = {'authority_id': 'example', 'capability_id': 'analysis.run',
               'result_refs': ['result:sha256:' + 'b' * 64], 'evidence_refs': []}
    source = {'kind': AUTHORITY_REFERENCE_SOURCE, 'metadata': receipt}
    wrapped = {'result': {'sources': [source]}}
    assert _json_document(wrapped, **{channel: True}) == wrapped
    with pytest.raises(ValueError, match='protected fields'):
        _json_document(wrapped)
    with pytest.raises(ValueError, match='protected fields'):
        _json_document({'events': [source]}, **{channel: True})
    with pytest.raises(ValueError, match='authority references'):
        _json_document({'result': {'sources': [
            {**source, 'metadata': {**receipt, 'result_refs': ['unverified']}}]}}, **{channel: True})


def test_recent_result_without_evidence_does_not_hide_earlier_verified_evidence():
    from capstone_agent.thread_service import _with_native_prior_results

    def payload(capability, evidence):
        fields = {'result_refs': ['result:sha256:' + 'b' * 64], 'evidence_refs': evidence}
        return {**fields, 'authority_references': [{
            'capability_id': capability, 'authority_id': 'example', **fields}]}

    evidence = 'evidence:sha256:' + 'c' * 64
    (candidate,) = _with_native_prior_results((), (
        ('attempt_read', payload('read', [])),
        ('attempt_compute', payload('compute', [evidence])),
    ))
    assert candidate.attempt_id == 'attempt_compute'
    assert candidate.evidence_refs == (evidence,)


@pytest.mark.parametrize('backend', ('memory', 'postgres'))
@pytest.mark.parametrize('route', ('automatic', 'resume'))
def test_goal_continuation_keeps_the_published_catalog_and_selected_refs(backend, route, request):
    from capstone_agent.goal_continuation import drain_goal_continuations

    executor = governed_executor()
    if backend == 'memory':
        store = open_store(executor, session_type='enterprise-research')
        thread_id = 'thr_unscoped'
    else:
        from test_thread_postgres import _snapshot
        store, thread_id = request.getfixturevalue('postgres_thread_service')
        store.create_thread(replace(_snapshot(thread_id), active_model_context=None, active_grid_page_id=None,
            minimum_protocol_version=2, session_type='enterprise-research'))
        store.set_native_executor(executor)
    publish_domain(store, families=('pandapower',))
    assert store.submit_command(command(store, thread_id, 'work_message', 'save',
        payload={'text': 'Calculate then read a result'})).status == 'accepted'
    work = store.snapshot(thread_id).works[0]
    assert store.submit_command(command(store, thread_id, 'start_goal', 'calculate',
        work_id=work['work_id'], revision=work['revision'], payload={
            'objective': 'Calculate then read a result', 'max_attempts': 2,
            'deadline_at': '2099-01-01T00:00:00Z'})).status == 'accepted'
    first = store.claim_attempt('native', 30, 'native')
    assert first is not None and first.application_catalog is not None
    result = 'result:sha256:' + 'a' * 64
    proof = 'evidence:sha256:' + 'b' * 64
    decoy = 'evidence:sha256:' + 'c' * 64
    store.finish_attempt(first, phase='completed', payload={'answer': 'Saved the calculation',
        'result_refs': [result], 'evidence_refs': [proof, decoy],
        'authority_references': [{'authority_id': 'registered', 'capability_id': 'calculate',
                                 'result_refs': [result], 'evidence_refs': [proof, decoy]}],
        'goal_proposal': {'schema': 'capstone-work-goal-proposal/1', 'disposition': 'continue',
            'summary': 'Saved the calculation', 'next_instruction': 'Read the result',
            'waiting_reason': None, 'product_refs': [], 'authority_refs': [result, proof]}})
    store._catalog_context = None
    if route == 'automatic':
        assert drain_goal_continuations(store) == 1
    else:
        work = store.snapshot(thread_id).works[0]
        assert store.submit_command(command(store, thread_id, 'pause_goal', 'pause',
            work_id=work['work_id'], revision=work['revision'])).status == 'accepted'
        if backend == 'postgres':
            from capstone_agent.thread_service import PostgresThreadService
            store = PostgresThreadService(store.dsn)
            store.set_native_executor(executor)
        work = store.snapshot(thread_id).works[0]
        assert store.submit_command(command(store, thread_id, 'resume_goal', 'resume',
            work_id=work['work_id'], revision=work['revision'])).status == 'accepted'
    continuation = store.claim_attempt('native', 30, 'native')
    assert continuation is not None and continuation.application_catalog == first.application_catalog
    assert structural_context_for(continuation)['handles'] == [
        {'kind': 'result_ref', 'ref': result}, {'kind': 'evidence_ref', 'ref': proof}]


def test_enterprise_research_admits_an_attachment_while_a_model_is_open():
    from capstone_agent.artifacts import MemoryObjectStore
    from capstone_agent.thread_resources import ResourceUploads
    executor = governed_executor()
    store = open_store(executor, session_type='enterprise-research')
    store._snapshot = replace(store._snapshot, active_model_context=_model(), active_grid_page_id='page_ieee39')
    publish_domain(store, families=('pandapower', 'pypsa'))
    objects = MemoryObjectStore()
    store._material_objects = objects
    uploads = ResourceUploads(store, objects, chunk_bytes=4)
    uid = uploads.begin('thr_unscoped', '01-安装部署手册.pdf', 4, 'manual', True)['upload_id']
    uploads.part('thr_unscoped', uid, 0, b'abcd')
    resource = uploads.complete('thr_unscoped', uid)
    receipt = store.submit_command(command(
        store, 'thr_unscoped', 'send_message', 'install-steps',
        payload={'text': '简明安装步骤', 'attachment_refs': [resource['resource_id']]}))
    assert receipt.status == 'accepted', receipt.rejection
    assert uploads.resources('thr_unscoped', True) == []
    assert store.claim_attempt('grid', 30, 'pandapower') is None
    claim = store.claim_attempt('native', 30, 'native')
    assert claim is not None
    assert claim.submission['_materials'] == []
    manifest = claim.submission['_resource_manifests'][0]
    assert manifest['resource_id'] == resource['resource_id']
    assert manifest['file_name'] == '01-安装部署手册.pdf'
    assert 'YWJjZA==' not in json.dumps(claim.submission)


def test_grid_analysis_rejects_an_attachment_while_a_model_is_open():
    executor = governed_executor()
    store = open_store(executor, session_type='grid-analysis')
    store._snapshot = replace(store._snapshot, active_model_context=_model(), active_grid_page_id='page_ieee39')
    receipt = store.submit_command(command(
        store, 'thr_unscoped', 'send_message', 'install-steps',
        payload={'text': '简明安装步骤', 'attachment_refs': ['resource_' + 'ab' * 16]}))
    assert receipt.status == 'rejected'
    assert receipt.rejection == 'material_execution_unsupported'


def test_grid_analysis_with_an_open_model_stays_on_its_family_worker():
    executor = governed_executor()
    store = _store(executor, 'grid-analysis')
    assert store.claim_attempt('native', 30, 'native') is None
    claim = store.claim_attempt('grid', 30, 'pandapower')
    assert claim is not None
    assert '_native_execution' not in claim.submission


def test_domain_invoke_accepts_management_identity_and_rejects_a_payload():
    from fastapi.testclient import TestClient
    seen = []

    class Pack:
        def invoke(self, body):
            seen.append(body)
            return {'ok': True, 'result': {'tool': body['name']}}

    app = create_wake_app(threading.Event(), 'operator-secret', implementation_family='pandapower', domain_tools=Pack())
    auth = {'Authorization': f"Bearer {wake_token('operator-secret')}"}
    management = structural_context_for(type('Claim', (), {'model_context': _model(), 'prior_results': ()})())
    identity = {'schema': management['schema'], 'model': management['model']}
    with TestClient(app) as client:
        assert client.post('/domain-tools/invoke', headers=auth, json={
            'task_id': 'pi-1', 'call_id': 'call-1', 'name': 'grid_context_open',
            'arguments': {'model_id': 'ieee39'}, 'management': identity}).status_code == 200
        rejected = client.post('/domain-tools/invoke', headers=auth, json={
            'task_id': 'pi-1', 'call_id': 'call-1', 'name': 'grid_context_open',
            'arguments': {'model_id': 'ieee39'}, 'management': {**identity, 'buses': []}})
        assert rejected.status_code == 422
    assert seen[0]['management'] == identity
    assert 'buses' not in json.dumps(seen[0])
