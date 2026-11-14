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
