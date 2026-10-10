from copy import deepcopy

import pytest

from capstone_agent.thread_service import InMemoryThreadService
from test_intent_runtime import claim
from capstone_agent.intent_runtime import intent_request_for_claim, context_selection_request_for_claim
from capstone_agent.context_selection import ContextSelectionDecision, selected_business_context
from capstone_agent.request_intent import IntentDecision
from dataclasses import replace


def command(service, **payload):
    snapshot = service.snapshot('thr_intent')
    return {'schema': 'capstone-command/1', 'command_id': 'cmd_input',
            'idempotency_key': 'idem_input', 'thread_id': snapshot.thread_id,
            'kind': 'send_auto', 'expected_event_seq': snapshot.last_event_seq,
            'payload': {'text': 'Use this method', **payload}}


def idle_service():
    service, current = claim()
    service.finish_attempt(current, phase='failed', payload={})
    return service


def test_professional_private_selection_is_server_owned_and_frozen_on_retry():
    import hashlib
    import json
    from capstone_agent.thread_input_catalog import input_catalog_document, public_input_catalog
    service = idle_service()
    private = {'schema': 'capstone-harness-selection/1', 'profile_revision': 'a' * 64,
        'skill_id': 'powerskills-pandapower', 'skill_version': 'v1', 'binding_id': 'grid',
        'native_loaded_identity': 'c' * 64, 'backend_descriptor_sha256': 'd' * 64,
        'guide': {'resource_id': 'powerskills-pandapower-adapter', 'title': 'Guide',
                  'text': 'private accepted guide', 'sha256': hashlib.sha256(b'private accepted guide').hexdigest()},
        'installation_id': 'installs/' + 'a' * 32}
    profile = {'revision': 'a' * 64, 'resources': [{'id': 'powerskills-pandapower', 'version': 'v1',
        'kind': 'skill', 'ready': True}], '_professional_selection': private}
    service.set_input_catalog_provider(lambda snapshot: input_catalog_document(snapshot, {'harness_engine': profile}, []))
    submitted = command(service, input={'kind': 'skill_invocation', 'text': 'Use this method',
        'skill_id': 'powerskills-pandapower', 'skill_version': 'v1'},
        resource_profile={'profile_id': 'harness_engine', 'revision': 'a' * 64})
    forged = deepcopy(submitted)
    forged.update(command_id='cmd_forged', idempotency_key='idem_forged')
    forged['payload']['professional_resource'] = private
    assert service.submit_command(forged).status == 'rejected'
    assert service.submit_command(submitted).status == 'accepted'
    profile['revision'] = 'B'
    profile['_professional_selection'] = {**private, 'profile_revision': 'B'}
    current = service.claim_attempt('worker_test', 30)
    assert current.submission['professional_resource'] == private
    assert '_professional_selection' not in current.submission['resource_profiles']['harness_engine']
    assert 'private accepted guide' not in str(public_input_catalog(service.input_catalog('thr_intent')))
    assert 'private accepted guide' not in json.dumps(service.snapshot('thr_intent').to_document())
    assert 'private accepted guide' not in json.dumps(service.read_events('thr_intent', 0).to_document())
    assert 'private accepted guide' not in json.dumps(service.read_history('thr_intent'))
    assert 'private accepted guide' not in json.dumps(intent_request_for_claim(current).to_document())
    from capstone_agent.turn_router import TurnPlan
    details = TurnPlan(current.attempt.turn_id, current.attempt.attempt_id, 'professional', 'fixture', '1', None, {},
        intent_request=intent_request_for_claim(current), intent_resources={'submission': current.submission}).to_payload()
    assert 'private accepted guide' not in json.dumps(details)
    service.finish_attempt(current, phase='failed', payload={})
    retry = command(service)
    retry.update(command_id='cmd_retry', idempotency_key='idem_retry', kind='retry_new_attempt',
                 payload={'attempt_id': current.attempt.attempt_id})
    assert service.submit_command(retry).status == 'accepted'
    assert service.claim_attempt('worker_test', 30).submission['professional_resource'] == private


def test_acceptance_preserves_typed_literal_and_context_on_retry():
    service = idle_service()
    payload = {'input': {'kind': 'text', 'text': '/unknown literal'},
               'context_selection': {'include_refs': ['ctx_test'], 'exclude_refs': ['ctx_test']}}
    submitted = command(service, text='/unknown literal', **payload)
    receipt = service.submit_command(submitted)
    assert receipt.status == 'accepted'
    current = service.claim_attempt('worker_test', 30)
    assert current.submission['input'] == payload['input']
    assert current.submission['context_selection'] == payload['context_selection']
    assert service.submit_command(submitted) == receipt
    altered = deepcopy(submitted)
    altered['payload']['context_selection']['exclude_refs'] = []
    assert service.submit_command(altered).rejection == 'idempotency_conflict'
    service.finish_attempt(current, phase='failed', payload={})
    retry = command(service)
    retry.update(command_id='cmd_retry', idempotency_key='idem_retry', kind='retry_new_attempt',
                 payload={'attempt_id': current.attempt.attempt_id})
    assert service.submit_command(retry).status == 'accepted'
    assert service.claim_attempt('worker_test', 30).submission == current.submission


@pytest.mark.parametrize('extra', [
    {'input': {'kind': 'text', 'text': 'different'}},
    {'input': {'kind': 'shell', 'text': 'Use this method'}},
    {'input': {'kind': 'text', 'text': 'Use this method', 'selection': {}}},
    {'context_selection': {'include_refs': ['missing'], 'exclude_refs': []}},
    {'context_selection': {'include_refs': [], 'exclude_refs': [], 'endpoint': 'private'}},
])
def test_invalid_or_unavailable_input_is_rejected_before_attempt(extra):
    service = idle_service()
    assert service.submit_command(command(service, **extra)).status == 'rejected'
    assert service.claim_attempt('worker_test', 30) is None


def test_skill_without_current_server_catalog_is_rejected():
    service = idle_service()
    receipt = service.submit_command(command(service,
        input={'kind': 'skill_invocation', 'text': 'Use this method', 'skill_id': 'fake', 'skill_version': '1'},
        resource_profile={'profile_id': 'delegated_pi', 'revision': 'sha256:' + 'a' * 64}))
    assert receipt.rejection == 'resource_unavailable'


def test_explicit_context_reaches_both_selectors_and_exclusion_wins():
    _, current = claim()
    choices = {'include_refs': ['ctx_test'], 'exclude_refs': ['ctx_test']}
    current = replace(current, submission={'context_selection': choices,
        'input': {'kind': 'text', 'text': current.instruction},
        'objects': intent_request_for_claim(current).to_document()['objects']})
    request = intent_request_for_claim(current)
    assert request.to_document()['context_selection'] == choices
    direct = context_selection_request_for_claim(current)
    assert direct.to_document()['context_selection'] == choices
    doc = {'schema': 'capstone-context-selection-decision/1',
           'attempt_id': current.attempt.attempt_id, 'history_cutoff': 0,
           'object_refs': ['ctx_test'], 'message_refs': [],
           'clarification_required': False, 'clarification': None}
    with pytest.raises(ValueError, match='excluded'):
        ContextSelectionDecision(doc, direct)
    doc['object_refs'] = []
    assert selected_business_context(direct, ContextSelectionDecision(doc, direct)).to_document()['object_refs'] == []
    business = {'schema': 'capstone-intent-decision/1', 'attempt_id': current.attempt.attempt_id,
        'history_cutoff': 0, 'relationship': 'independent', 'clarification': None,
        'goals': [{'goal_id': 'g1', 'description': 'read', 'operation': 'answer',
                   'object_refs': ['ctx_test'], 'message_refs': [], 'capability_refs': [], 'missing_requirements': []}]}
    with pytest.raises(ValueError, match='excluded'):
        IntentDecision(business, request)


def test_explicit_include_must_be_selected_or_clarified():
    _, current = claim()
    current = replace(current, submission={'context_selection': {'include_refs': ['ctx_test'], 'exclude_refs': []},
        'input': {'kind': 'text', 'text': current.instruction},
        'objects': intent_request_for_claim(current).to_document()['objects']})
    request = context_selection_request_for_claim(current)
    doc = {'schema': 'capstone-context-selection-decision/1',
           'attempt_id': current.attempt.attempt_id, 'history_cutoff': 0,
           'object_refs': [], 'message_refs': [], 'clarification_required': False, 'clarification': None}
    with pytest.raises(ValueError, match='included'):
        ContextSelectionDecision(doc, request)


@pytest.mark.parametrize('direct', [False, True])
def test_selected_native_skill_reaches_exactly_one_task_with_accepted_version(direct):
    from test_delegated_runtime import Executor, Recognizer, goal, factory, run
    service, current = claim()
    role = 'direct_pi' if direct else 'delegated_pi'
    selection = {'profile_id': role, 'revision': 'accepted-resource-version'}
    current = replace(current, instruction='first then second',
        attempt=replace(current.attempt, runtime_mode='pi_reference' if direct else 'capstone'),
        submission={'input': {'kind': 'skill_invocation', 'text': 'first then second',
                    'skill_id': 'selected-skill', 'skill_version': 'exact-version'},
                    'resource_profile': selection, 'context_selection': {'include_refs': [], 'exclude_refs': []},
                    'objects': intent_request_for_claim(current).to_document()['objects']})
    executor = Executor()
    recognizer = Recognizer([{**goal('first', excerpt='first'), 'uses_selected_skill': True},
                            goal('second', excerpt='second')])
    result = run(service, current, factory(executor, recognizer))
    assert result.status == 'completed'
    assert executor.requests[0].to_document()['input']['kind'] == 'skill_invocation'
    assert executor.requests[0].to_document()['input']['skill_version'] == 'exact-version'
    assert executor.requests[0].to_document()['resource_profile'] == selection
    if not direct:
        assert executor.requests[1].to_document()['input']['kind'] == 'text'
        assert recognizer.requests[0].to_document()['selected_skill']['profile_id'] == 'delegated_pi'


def test_intent_cannot_drop_or_duplicate_explicit_skill_step():
    from test_delegated_runtime import Recognizer, goal
    _, current = claim()
    current = replace(current, submission={'input': {'kind': 'skill_invocation', 'text': current.instruction,
        'skill_id': 'selected-skill', 'skill_version': 'exact-version'},
        'resource_profile': {'profile_id': 'delegated_pi', 'revision': 'accepted'},
        'context_selection': {'include_refs': [], 'exclude_refs': []},
        'objects': intent_request_for_claim(current).to_document()['objects']})
    request = intent_request_for_claim(current)
    for goals in ([goal('a')], [{**goal('a'), 'uses_selected_skill': True}, {**goal('b'), 'uses_selected_skill': True}]):
        with pytest.raises(ValueError, match='exactly one'):
            Recognizer(goals).recognize(request, type('Control', (), {})())


@pytest.mark.parametrize('backend', ['memory', 'postgres'])
@pytest.mark.parametrize('professional', [False, True])
def test_receipt_and_retry_keep_accepted_skill_when_catalog_changes(backend, professional):
    import hashlib
    import os
    import uuid
    import psycopg
    from capstone_agent.thread_service import PostgresThreadService
    template, _ = claim()
    thread_id = 'thr_input_' + uuid.uuid4().hex[:12]
    snapshot = replace(template.snapshot('thr_intent'), thread_id=thread_id, current_attempt=None, last_event_seq=0)
    if backend == 'postgres':
        dsn = os.environ.get('CAPSTONE_TEST_DATABASE_URL')
        if not dsn:
            pytest.skip('CAPSTONE_TEST_DATABASE_URL is required')
        service = PostgresThreadService(dsn)
        service.initialize()
        service.create_thread(snapshot)
    else:
        service = InMemoryThreadService(snapshot)
    role = 'harness_engine' if professional else 'delegated_pi'
    skill_id = 'powerskills-pandapower' if professional else 'skill-a'
    profiles = {role: {'revision': 'a' * 64, 'resources': [
        {'id': skill_id, 'version': '1', 'kind': 'skill', 'ready': True}]}}
    if professional:
        profiles[role]['_professional_selection'] = {'schema': 'capstone-harness-selection/1',
            'profile_revision': 'a' * 64, 'skill_id': skill_id, 'skill_version': '1', 'binding_id': 'grid',
            'native_loaded_identity': 'c' * 64, 'backend_descriptor_sha256': 'd' * 64,
            'installation_id': 'installs/' + 'a' * 32, 'guide': {'resource_id': 'powerskills-pandapower-adapter',
                'title': 'Guide', 'text': 'retained guide A', 'sha256': hashlib.sha256(b'retained guide A').hexdigest()}}
    service.set_input_catalog_provider(lambda snapshot: {'resource_profiles': profiles, 'objects': [
        {'object_id': 'ctx_test', 'model_id': 'ieee39', 'model_revision': 'rev_1', 'implementation_family': 'pandapower'}]})
    submitted = {'schema': 'capstone-command/1', 'thread_id': thread_id, 'kind': 'send_auto',
        'command_id': 'cmd_skill', 'idempotency_key': 'idem_skill', 'expected_event_seq': 0,
        'payload': {'text': 'task', 'input': {'kind': 'skill_invocation', 'text': 'task', 'skill_id': skill_id, 'skill_version': '1'},
                    'resource_profile': {'profile_id': role, 'revision': 'a' * 64},
                    'context_selection': {'include_refs': ['ctx_test'], 'exclude_refs': []}}}
    try:
        receipt = service.submit_command(submitted)
        assert receipt.status == 'accepted'
        profiles[role]['revision'] = 'b' * 64
        assert service.submit_command(submitted) == receipt
        if backend == 'postgres':
            # Recreate the service before first start. Only the database retains A.
            service = PostgresThreadService(dsn)
        current = service.claim_attempt('worker', 30)
        assert current.submission['resource_profile']['revision'] == 'a' * 64
        if professional:
            assert current.submission['professional_resource']['guide']['text'] == 'retained guide A'
            assert current.submission['professional_resource']['installation_id'] == 'installs/' + 'a' * 32
        service.finish_attempt(current, phase='failed', payload={})
        stale = {**submitted, 'command_id': 'cmd_stale', 'idempotency_key': 'idem_stale',
                 'expected_event_seq': service.snapshot(thread_id).last_event_seq}
        if backend == 'postgres':
            service.set_input_catalog_provider(lambda snapshot: {'resource_profiles': profiles, 'objects': [
                {'object_id': 'ctx_test', 'model_id': 'ieee39', 'model_revision': 'rev_1', 'implementation_family': 'pandapower'}]})
        assert service.submit_command(stale).rejection == 'resource_catalog_stale'
        retry = {**stale, 'command_id': 'cmd_retry', 'idempotency_key': 'idem_retry',
                 'kind': 'retry_new_attempt', 'payload': {'attempt_id': current.attempt.attempt_id}}
        assert service.submit_command(retry).status == 'accepted'
        if backend == 'postgres':
            service = PostgresThreadService(dsn)
        assert service.claim_attempt('worker', 30).submission == current.submission
    finally:
        if backend == 'postgres':
            with psycopg.connect(dsn) as connection:
                connection.execute('DELETE FROM capstone_threads WHERE thread_id = %s', (thread_id,))


def test_accepted_context_projection_reports_actual_selection_and_material_gap():
    import time
    from capstone_agent.request_intent import NodeControl
    from test_delegated_runtime import Executor, ContextSelector, factory
    service, current = claim()
    current = replace(current, attempt=replace(current.attempt, runtime_mode='pi_reference'))
    runtime = factory(Executor(), None, selector=ContextSelector(['ctx_test']))
    plan = runtime.plan_intent(current, NodeControl(lambda: None, time.monotonic() + 10), service.freeze_attempt_input)
    context = plan.to_payload()['accepted_context']
    assert context['objects'][0]['object_id'] == 'ctx_test'
    assert context['materials'] == []
    assert context['full_model_tables'] is False


@pytest.mark.parametrize('backend', ['memory', 'postgres'])
@pytest.mark.parametrize('switch', [False, True])
@pytest.mark.parametrize('skill', [False, True])
def test_input_freezes_activated_context_and_refuses_old_harness_binding(backend, switch, skill):
    import os
    import uuid
    import psycopg
    from capstone_agent.thread_service import PostgresThreadService
    from test_thread_postgres import _snapshot, _command, _ToolsCatalog, _ToolsModelCatalog
    thread_id = 'thr_activation_' + uuid.uuid4().hex[:12]
    snapshot = _snapshot(thread_id)
    dsn = os.environ.get('CAPSTONE_TEST_DATABASE_URL')
    if backend == 'postgres':
        if not dsn: pytest.skip('CAPSTONE_TEST_DATABASE_URL is required')
        service = PostgresThreadService(dsn)
        service.initialize()
        service.create_thread(snapshot)
    else:
        service = InMemoryThreadService(snapshot)
    service.set_capability_catalog(_ToolsCatalog())
    service.set_model_catalog(_ToolsModelCatalog())
    service.set_input_catalog_provider(lambda state: {
        'objects': [{'object_id': state.active_model_context.id, 'model_id': state.active_model_context.model_id,
                     'model_revision': state.active_model_context.model_revision, 'implementation_family': state.active_model_context.implementation_family}],
        'resource_profiles': {'harness_engine': {'revision': 'old', 'resources': [
            {'id': 'guide', 'version': '1', 'kind': 'skill', 'ready': True}]}}})
    try:
        if switch:
            pending = {**_command(thread_id), 'command_id': 'cmd_switch', 'idempotency_key': 'idem_switch',
                       'kind': 'switch_model', 'payload': {'model_id': 'pypsa39'}}
            assert service.submit_command(pending).status == 'accepted'
        payload = {'text': 'inspect', 'input': {'kind': 'text', 'text': 'inspect'},
                   'enabled_profiles': [{'profile_id': 'operations' if switch else 'static-analysis', 'profile_version': '1.0.0'}]}
        if skill:
            payload['input'].update(kind='skill_invocation', skill_id='guide', skill_version='1')
            payload['resource_profile'] = {'profile_id': 'harness_engine', 'revision': 'old'}
        receipt = service.submit_command({**_command(thread_id), 'payload': payload,
            'expected_event_seq': service.snapshot(thread_id).last_event_seq})
        if skill:
            assert receipt.rejection == 'resource_catalog_stale'
            assert service.snapshot(thread_id).active_model_context == snapshot.active_model_context
        else:
            assert receipt.status == 'accepted'
            current = service.claim_attempt('activation', 30)
            assert current.submission['model_context'] == current.model_context.to_document()
            assert current.submission['objects'][0]['object_id'] == current.model_context.id
            assert current.submission['objects'][0]['model_id'] == ('pypsa39' if switch else 'ieee39')
            assert 'harness_engine' not in current.submission['resource_profiles']
            context_selection_request_for_claim(current)
    finally:
        if backend == 'postgres':
            with psycopg.connect(dsn) as connection:
                connection.execute('DELETE FROM capstone_threads WHERE thread_id = %s', (thread_id,))

