"""Typed Mission reviews reuse native execution without manufacturing user input."""
from copy import deepcopy
from dataclasses import replace
from uuid import uuid4
import pytest

from capstone_agent.request_intent import IntentRequest
from test_request_intent import request_document
from test_thread_postgres import postgres_thread_service, _snapshot
from test_enterprise_normal_chat import native_executor
from test_thread_work_execution import command
from capstone_agent.control_host import configure_control
from capstone_agent.thread_service import InMemoryThreadService, PostgresThreadService
from capstone_agent.thread_protocol import ThreadProtocolError
from capstone_agent.mission_continuation import drain_mission_reviews, find_review


@pytest.fixture(params=['memory', 'postgres'])
def review_store(request):
    workspace = 'review_' + uuid4().hex[:16]
    if request.param == 'memory':
        thread_id = 'thr_review'
        snapshot = replace(_snapshot(thread_id), active_model_context=None,
            active_grid_page_id=None, minimum_protocol_version=2)
        service = InMemoryThreadService(snapshot, workspace_name=workspace)
    else:
        service, thread_id = request.getfixturevalue('postgres_thread_service')
        service.create_thread(replace(_snapshot(thread_id), active_model_context=None,
            active_grid_page_id=None, minimum_protocol_version=2), workspace_name=workspace)
    executor = native_executor()
    executor.capability['mission_schemas'] = ['capstone-native-mission/1']
    executor.capability['instruction_schemas'] = ['capstone-native-instruction/1']
    executor.capability['execution_authority_schemas'] = ['capstone-execution-authority/1']
    executor.capability['instruction_limit'] = 128
    service.set_native_executor(executor)
    return service, thread_id, workspace, executor


def reserved_review(review_store, *, complete_origin=True, products=None, reserve=True, authority=None, gateway=None):
    service, thread_id, workspace, executor = review_store
    host = configure_control(service)
    mission = host.create_mission(workspace, {'schema': 'capstone-control-mission-create/1',
        'operation_id': 'create', 'objective': 'Inspect results and refine the plan.',
        'origin': {'thread_id': thread_id}})
    assert service.submit_command(command(service, thread_id, 'send_message', 'original',
        payload={'text': 'Inspect results and keep the report in Chinese.'})).status == 'accepted'
    original = service.claim_attempt('original_planner', 30)
    assert original.thread_id == thread_id
    delivery_authority = {}
    if complete_origin:
        payload = {'answer': 'The first task is planned.'}
        if gateway is not None:
            service.append_runtime_event(original, event_type='runtime_event', visibility='diagnostic',
                                         payload={'gateway_operations': gateway})
        if authority is not None:
            from capstone_agent.structural_context import structural_context_for
            service.freeze_attempt_input(original, {'resources': {'structural_context': structural_context_for(original)}})
            payload.update(authority_references=[authority], result_refs=authority['result_refs'],
                           evidence_refs=authority['evidence_refs'])
        service.finish_attempt(original, phase='completed', payload=payload)
        if authority is not None or gateway is not None:
            terminal = next(event for event in service.read_events(thread_id, 0).events
                            if event.event_type == 'attempt_completed')
            coordinates = {'thread_id': thread_id,
                'work_id': original.task_context.binding.work_id, 'attempt_id': original.attempt.attempt_id,
                'answer_ref': terminal.event_id}
            if authority is not None:
                delivery_authority['authority_source'] = coordinates
            if gateway is not None:
                delivery_authority['gateway_source'] = coordinates
    task = dict(task_id='inspect', objective='Inspect the registered material',
        delivery_requirements=['Return a saved answer'], depends_on=[], agent_id='capstone',
        mode='single', max_attempts=1)
    for kind, revision, payload in [('update_plan', 1, {'acceptance_criteria': ['Review findings'], 'tasks': [task]}),
                                    ('ready', 2, {}), ('delegate_next', 3, {})]:
        host.command_mission(workspace, dict(schema='capstone-control-mission-command/1',
            operation_id=kind, mission_id=mission['mission_id'], expected_revision=revision,
            kind=kind, payload=payload))
    goal = host.service.read(workspace, mission['mission_id'])
    delegation = goal['tasks'][0]['delegation']
    product_binding = ({'thread_id': products[0]['thread_id'], 'work_id': products[0]['work_id']}
                       if products else {'thread_id': 'thr_fixture_child', 'work_id': 'work_fixture_child'})
    source = delivery_authority.get('authority_source', delivery_authority.get('gateway_source'))
    if source:
        product_binding = {key: source[key] for key in ('thread_id', 'work_id')}
    host.service.deliver(workspace, mission['mission_id'], delegation['delegation_id'],
        product_binding, {'answer_ref': source['answer_ref'] if source else 'answer_fixture',
                          'products': products or [], 'status': 'completed', **delivery_authority})
    goal = host.service.read(workspace, mission['mission_id'])
    host.service.command(workspace, dict(schema='capstone-control-command/1', operation_id='verify',
        goal_id=mission['mission_id'], expected_revision=goal['revision'], kind='verify_task',
        payload={'task_id': 'inspect', 'delivery_revision': 1,
                 'checks': [{'name': 'Saved test answer checked', 'passed': True}]}))
    pending = host.service.pending_mission_reviews(workspace)[0]
    intent = (host.service.reserve_mission_review(workspace, mission['mission_id'], pending['review_id'])
              if reserve else pending)
    return host, mission, intent, original


def test_mission_review_freezes_authority_inputs_from_reserved_delivery(review_store):
    from capstone_agent.structural_context import structural_context_for

    service, thread_id, _workspace, _executor = review_store
    receipt = {'authority_id': 'registered', 'capability_id': 'calculate',
               'result_refs': ['result:sha256:' + 'a' * 64],
               'evidence_refs': ['evidence:sha256:' + 'b' * 64],
               'context_refs': ['context:sha256:' + 'c' * 64]}
    operation = {'binding': {'connection_id': 'conn_x', 'instance_id': 'instance_x', 'catalog_revision': 'revision_x'},
                 'operations': [{'kind': 'preparation_ref', 'ref': 'issued-job'},
                                {'kind': 'view_ref', 'ref': 'issued-view',
                                 'view_identity': {'model_ref': 'model:one', 'model_revision': 'revision-one'}}]}
    _host, _mission, intent, original = reserved_review(review_store, authority=receipt, gateway=operation)
    assert service.submit_mission_review(intent)['thread_id'] == thread_id
    review = service.claim_attempt('reviewer', 30)
    assert review is not None
    context = structural_context_for(review)
    assert context['authority_inputs'] == [{
        'owner': {'work_scope': structural_context_for(original)['work_scope']}, **receipt}]
    assert {'kind': 'context_ref', 'ref': receipt['context_refs'][0]} in context['handles']
    assert review.submission['_gateway_operation_inputs'] == [operation]


def test_review_instruction_has_a_typed_identity_and_no_user_history_record():
    document = request_document()
    original_history = deepcopy(document['messages'])
    document.update(instruction_message_id=document['attempt_id'] + ':mission_review',
        instruction_source={'schema': 'capstone-mission-review-source/1',
            'mission_id': 'goal_review', 'review_id': 'review_one', 'boundary_digest': 'a' * 64})
    request = IntentRequest.from_document(document)
    assert request.to_document()['messages'] == original_history
    assert request.to_document()['instruction_source'] == document['instruction_source']
    document['instruction_message_id'] = document['attempt_id'] + ':user'
    with pytest.raises(ValueError):
        IntentRequest.from_document(document)
    document.pop('instruction_source')
    document['instruction_message_id'] = document['attempt_id'] + ':mission_review'
    with pytest.raises(ValueError):
        IntentRequest.from_document(document)


def test_review_admission_preserves_user_work_and_exact_retry(review_store):
    service, thread_id, workspace, _ = review_store
    host, mission, intent, original = reserved_review(review_store)
    before = service.snapshot(thread_id).works[0]
    binding = service.submit_mission_review(intent)
    assert binding == service.submit_mission_review(intent)
    after = service.snapshot(thread_id).works[0]
    for key in ('goal', 'goal_revision', 'messages', 'consumed_message_count', 'instruction_queue'):
        assert after.get(key) == before.get(key)
    assert binding['work_id'] == before['work_id']
    claim = service.claim_attempt('review_planner', 30)
    assert claim.kind == 'send_auto'
    assert claim.submission['_mission_review'] == intent
    assert claim.submission['_native_execution'] == original.submission['_native_execution']
    assert claim.instruction != before['goal']
    events = service.read_events(thread_id, 0).events
    own = [event for event in events if event.attempt_id == binding['attempt_id']]
    assert len([event for event in own if event.event_type == 'mission_review_requested']) == 1
    assert not any(event.event_type == 'command_accepted' for event in own)
    assert sum(item['content'].count('Inspect results and keep the report in Chinese.')
               for item in claim.conversation_context.messages if item['role'] == 'user') == 1


@pytest.mark.parametrize('grants_changed', [False, True])
def test_mission_review_rebinds_executor_implementation_only(review_store, grants_changed):
    service, thread_id, _workspace, executor = review_store
    executor.identity = {**executor.identity, 'executor_revision': 'a' * 64}
    executor.capability['executor_identity'] = deepcopy(executor.identity)
    service.set_native_executor(executor)
    _host, _mission, intent, original = reserved_review(review_store)

    executor.identity = {**executor.identity, 'executor_revision': 'b' * 64}
    executor.capability['executor_identity'] = deepcopy(executor.identity)
    if grants_changed:
        executor.capability['native_builtin_tools'] = ['read', 'bash', 'write']
    service.set_native_executor(executor)

    if grants_changed:
        with pytest.raises(ThreadProtocolError, match='registered grants changed'):
            service.submit_mission_review(intent)
        assert find_review(service, intent) is None
        return
    assert service.submit_mission_review(intent)['thread_id'] == thread_id
    review = service.claim_attempt('review_after_rebuild', 30)
    assert review.submission['_native_execution']['identity'] == executor.identity
    assert review.submission['_native_execution']['capability']['executor_identity'] == executor.identity
    assert original.submission['_native_execution']['identity']['executor_revision'] == 'a' * 64


def test_resumed_mission_review_can_follow_a_failed_organizer_attempt(review_store):
    service, thread_id, workspace, _ = review_store
    host, mission, intent, _ = reserved_review(review_store)
    mission_id = mission['mission_id']
    binding = service.submit_mission_review(intent)
    host.service.acknowledge_mission_review(workspace, mission_id, intent['review_id'], binding)
    review = service.claim_attempt('original_review', 30)
    assert review.thread_id == thread_id
    service.finish_attempt(review, phase='failed', payload={'answer': 'Answer rendering failed.'})
    host.service.finish_mission_review(workspace, mission_id, intent['review_id'],
                                       attempt_id=review.attempt.attempt_id, phase='failed')
    mission = host.service.read_mission(workspace, mission_id)
    host.command_mission(workspace, {'schema': 'capstone-control-mission-command/1',
        'operation_id': 'resume_review', 'mission_id': mission_id,
        'expected_revision': mission['revision'], 'kind': 'resume', 'payload': {}})
    assert drain_mission_reviews(service, workspace=workspace) == 1
    next_review = service.claim_attempt('resumed_review', 30)
    assert next_review.thread_id == thread_id
    assert next_review.attempt.attempt_id != review.attempt.attempt_id
    assert next_review.submission['_mission_review']['mission_id'] == mission_id


def test_review_source_spoof_and_paused_or_busy_origin_are_not_admitted(review_store):
    service, thread_id, workspace, _ = review_store
    host, mission, intent, original = reserved_review(review_store, complete_origin=False)
    fake = deepcopy(intent)
    fake['boundary']['digest'] = '0' * 64
    with pytest.raises(ThreadProtocolError):
        service.submit_mission_review(fake)
    assert service.submit_mission_review(intent) is None
    assert find_review(service, intent) is None
    current = host.service.read_mission(workspace, mission['mission_id'])
    host.command_mission(workspace, dict(schema='capstone-control-mission-command/1',
        operation_id='pause', mission_id=mission['mission_id'], expected_revision=current['revision'],
        kind='pause', payload={}))
    service.finish_attempt(original, phase='completed', payload={'answer': 'Origin is idle.'})
    with pytest.raises(ValueError):
        service.submit_mission_review(intent)
    assert find_review(service, intent) is None


def test_review_runs_through_real_native_factory_and_frozen_task_request(review_store, tmp_path):
    from capstone_agent.intent_runtime import IntentRuntimeFactory
    from capstone_agent.thread_worker import run_pending_attempt
    from capstone_agent.native_task_context import checked_native_context
    service, thread_id, workspace, executor = review_store
    host, mission, intent, original = reserved_review(review_store)
    binding = service.submit_mission_review(intent)
    host.service.acknowledge_mission_review(workspace, mission['mission_id'], intent['review_id'], binding)
    def forbidden(*args):
        raise AssertionError('Mission continuation cannot start a business runtime')
    factory = IntentRuntimeFactory(forbidden, forbidden, forbidden, general_executor=executor,
                                   native_research_root=tmp_path)
    result = run_pending_attempt(service, factory, worker_id='native_review', implementation_family='native')
    assert result.status == 'completed', [(event.event_type, dict(event.payload)) for event in
        service.read_events(thread_id, 0).events if event.event_type in {'attempt_failed', 'attempt_cancelled'}]
    assert len(executor.requests) == 1
    # Exercise the actual immutable PiTaskRequest boundary, then normalize once.
    request = executor.requests[0]
    document = request.to_document()
    assert document['native_context']['mission_review'] == intent
    assert checked_native_context(document['native_context'])['mission_review'] == intent
    assert document['parent_attempt_id'] == binding['attempt_id']
    if hasattr(service, '_attempts'):
        frozen = service._attempts[binding['attempt_id']]['intent_input_snapshot']
    else:
        with service._connect() as connection:
            frozen = connection.execute('SELECT intent_input_snapshot FROM capstone_thread_attempts WHERE attempt_id=%s',
                (binding['attempt_id'],)).fetchone()['intent_input_snapshot']
    assert frozen['request']['instruction_message_id'] == binding['attempt_id'] + ':mission_review'
    assert frozen['request']['instruction_source']['review_id'] == intent['review_id']


def test_real_user_supplement_during_review_survives_next_human_turn(review_store):
    service, thread_id, workspace, _ = review_store
    host, mission, intent, original = reserved_review(review_store)
    service.submit_mission_review(intent)
    claim = service.claim_attempt('review_with_input', 30)
    work = service.snapshot(thread_id).works[0]
    direction = 'Also retain the exact file version in the next summary.'
    assert service.submit_command(command(service, thread_id, 'queue_instruction', 'during_review',
        work_id=work['work_id'], revision=work['revision'], payload={'text': direction})).status == 'accepted'
    assert service.reserve_instruction(claim, 'cmd_during_review') is not None
    assert service.acknowledge_instruction(claim, 'cmd_during_review')['state'] == 'admitted'
    service.finish_attempt(claim, phase='completed', payload={'answer': 'The reviewed result needs another task.'})
    work = service.snapshot(thread_id).works[0]
    service.submit_command(command(service, thread_id, 'send_message', 'next_human',
        work_id=work['work_id'], revision=work['revision'], payload={'text': 'Explain the reviewed direction.'}))
    followup = service.claim_attempt('human_followup', 30)
    users = [message['content'] for message in followup.conversation_context.messages if message['role'] == 'user']
    assert direction in users
    assert not any('application continuation' in text for text in users)
    assert any(message['content'] == 'The reviewed result needs another task.'
               for message in followup.conversation_context.messages if message['role'] == 'assistant')


def test_restart_and_lost_acknowledgement_do_not_duplicate_review_attempt(review_store, monkeypatch):
    service, thread_id, workspace, executor = review_store
    host, mission, intent, original = reserved_review(review_store)
    acknowledge = host.service.acknowledge_mission_review
    calls = []
    def lost_ack(*args, **kwargs):
        calls.append(1)
        acknowledge(*args, **kwargs)
        raise OSError('acknowledgement response was lost')
    monkeypatch.setattr(host.service, 'acknowledge_mission_review', lost_ack)
    assert drain_mission_reviews(service, workspace=workspace) == 1
    binding, phase = find_review(service, intent)
    monkeypatch.setattr(host.service, 'acknowledge_mission_review', acknowledge)
    if isinstance(service, PostgresThreadService):
        service = PostgresThreadService(service.dsn)
        service.set_native_executor(executor)
        host = configure_control(service)
    assert drain_mission_reviews(service, workspace=workspace) == 0
    assert find_review(service, intent)[0] == binding
    claim = service.claim_attempt('restarted_review', 30)
    service.finish_attempt(claim, phase='completed', payload={'answer': 'Review complete with no plan changes.'})
    assert drain_mission_reviews(service, workspace=workspace) == 0
    assert host.service.pending_mission_reviews(workspace) == []
    assert host.service.read_mission(workspace, mission['mission_id'])['organizer']['reviews_admitted'] == 1


@pytest.mark.parametrize('stop_action', [None, 'pause', 'cancel'])
def test_late_organizer_receipt_uses_original_control_binding(review_store, stop_action):
    from concurrent.futures import ThreadPoolExecutor
    from hashlib import sha256
    from types import SimpleNamespace

    from capstone_agent.native_owner_recovery import recover_exited_native_deliveries
    from capstone_agent.pi_delegation import PiTaskResult

    service, _, workspace, _ = review_store
    if not isinstance(service, PostgresThreadService):
        pytest.skip('native receipt recovery uses the PostgreSQL ledger')
    host, mission, intent, _ = reserved_review(review_store)
    mission_id = mission['mission_id']
    assert drain_mission_reviews(service, workspace=workspace) == 1
    binding, _ = find_review(service, intent)
    claim = service.claim_attempt('organizer_worker', 30)
    attempt_id = binding['attempt_id']
    assert claim.attempt.attempt_id == attempt_id
    task_id = 'pi-' + sha256((attempt_id + '\0conversation').encode()).hexdigest()
    identity = {'engine': 'pi'}
    service.append_runtime_event(claim, event_type='runtime_event', payload={
        'task_id': task_id, 'parent_attempt_id': attempt_id, 'entrypoint': 'delegated',
        'goal_id': 'conversation', 'child_status': 'started', 'executor_identity': identity,
        'route_source': 'native_conversation', 'delivery_recovery_format': 'plain',
    }, visibility='diagnostic')
    service.append_runtime_event(claim, event_type='attempt_worker_diagnostic',
                                 payload={'error_code': 'worker_execution_failed'}, visibility='diagnostic')
    assert service.interrupt_expired_attempts() == 1
    assert drain_mission_reviews(service, workspace=workspace) == 0
    if stop_action:
        goal = host.service.read(workspace, mission_id)
        host.command_mission(workspace, dict(schema='capstone-control-mission-command/1',
            operation_id=stop_action, mission_id=mission_id, expected_revision=goal['revision'],
            kind=stop_action, payload={}))

    reply = PiTaskResult(task_id, attempt_id, identity, 'completed', 'Saved review', (), (), {})
    assert recover_exited_native_deliveries(service, SimpleNamespace(observe_terminal_task=lambda *_: reply)) == 1
    with ThreadPoolExecutor(max_workers=2) as pool:
        attempts = [pool.submit(drain_mission_reviews, service, workspace=workspace) for _ in range(2)]
        assert [attempt.result(timeout=8) for attempt in attempts] == [0, 0]
    assert drain_mission_reviews(service, workspace=workspace) == 0
    goal = host.service.store.read(workspace, mission_id)
    organizer = goal['_mission']['organizer']
    record, = organizer['records']
    assert record['binding'] == binding and organizer['reviews_admitted'] == 1
    if stop_action:
        assert record['finish']['phase'] == 'interrupted'
        assert goal['state'] in {'paused', 'pausing', 'cancelled', 'cancelling'}
    else:
        assert record['interruption']['phase'] == 'interrupted'
        assert record['finish']['phase'] == 'completed'


def test_review_cancelled_before_claim_never_calls_native_model(review_store, tmp_path):
    from capstone_agent.intent_runtime import IntentRuntimeFactory
    from capstone_agent.thread_worker import run_pending_attempt
    service, thread_id, workspace, executor = review_store
    host, mission, intent, original = reserved_review(review_store)
    binding = service.submit_mission_review(intent)
    current = host.service.read_mission(workspace, mission['mission_id'])
    host.command_mission(workspace, dict(schema='capstone-control-mission-command/1', operation_id='cancel',
        mission_id=mission['mission_id'], expected_revision=current['revision'], kind='cancel', payload={}))
    def forbidden(*args):
        raise AssertionError('Canceled review cannot prepare a runtime')
    factory = IntentRuntimeFactory(forbidden, forbidden, forbidden, general_executor=executor,
                                   native_research_root=tmp_path)
    result = run_pending_attempt(service, factory, worker_id='stopped_review')
    assert result.status == 'cancelled'
    assert executor.requests == []
    assert drain_mission_reviews(service, workspace=workspace) == 0
    assert host.service.read_mission(workspace, mission['mission_id'])['organizer']['reviews_admitted'] == 1


def test_concurrent_review_admission_is_idempotent_and_public_spoof_is_rejected(review_store):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    service, thread_id, workspace, _ = review_store
    host, mission, intent, original = reserved_review(review_store)
    work = service.snapshot(thread_id).works[0]
    spoof = command(service, thread_id, 'continue_mission_review', 'untrusted_review',
        work_id=work['work_id'], revision=work['revision'], payload=deepcopy(intent))
    assert service.submit_command(spoof).status == 'rejected'
    assert find_review(service, intent) is None
    gate = Barrier(2)
    def admit():
        gate.wait()
        return service.submit_mission_review(deepcopy(intent))
    with ThreadPoolExecutor(max_workers=2) as pool:
        one, two = pool.submit(admit), pool.submit(admit)
        assert one.result() == two.result()
    requested = [event for event in service.read_events(thread_id, 0).events
                 if event.event_type == 'mission_review_requested']
    assert len(requested) == 1


def test_autonomous_review_does_not_admit_suspended_pending_user_input(review_store):
    service, thread_id, workspace, _ = review_store
    host, mission, intent, original = reserved_review(review_store, complete_origin=False)
    work = service.snapshot(thread_id).works[0]
    service.submit_command(command(service, thread_id, 'queue_instruction', 'left_pending',
        work_id=work['work_id'], revision=work['revision'], payload={'text': 'Keep this pending until explicit continuation.'}))
    service.finish_attempt(original, phase='completed', payload={'answer': 'Initial planning complete.'})
    service.submit_mission_review(intent)
    claim = service.claim_attempt('review_not_user_resume', 30)
    assert service.peek_instructions(claim) == ()
    pending = service.snapshot(thread_id).works[0]['instruction_queue'][0]
    assert pending['state'] == 'pending' and pending['attempt_id'] == original.attempt.attempt_id


@pytest.mark.parametrize('count,reason', [(0, 'organizer_work_unavailable'), (2, 'organizer_work_ambiguous')])
def test_missing_or_ambiguous_organizer_work_is_explicitly_blocked(review_store, count, reason):
    from psycopg.types.json import Jsonb
    from capstone_agent.enterprise_context import TaskContext, WorkBinding
    service, thread_id, workspace, _ = review_store
    host, mission, intent, original = reserved_review(review_store)
    snapshot = service.snapshot(thread_id)
    works = []
    if count:
        first = deepcopy(snapshot.works[0])
        second = deepcopy(first)
        second['work_id'] = 'work_second_organizer'
        context = TaskContext.from_document(second['task_context'])
        second['task_context'] = replace(context,
            binding=WorkBinding(thread_id, second['work_id'], 'research-second-organizer')).to_document()
        works = [first, second]
    if hasattr(service, '_lock'):
        with service._lock:
            service._snapshot = replace(snapshot, works=tuple(works))
    else:
        with service._connect() as connection:
            connection.execute('UPDATE capstone_threads SET works=%s WHERE thread_id=%s',
                (Jsonb(works), thread_id))
    assert drain_mission_reviews(service, workspace=workspace) == 0
    assert find_review(service, intent) is None
    organizer = host.service.read_mission(workspace, mission['mission_id'])['organizer']
    assert organizer['state'] == 'blocked' and organizer['reason'] == reason


def test_busy_origin_is_not_reserved_and_does_not_spend_review_budget(review_store):
    service, thread_id, workspace, _ = review_store
    host, mission, intent, original = reserved_review(review_store, complete_origin=False, reserve=False)
    assert drain_mission_reviews(service, workspace=workspace) == 0
    organizer = host.service.read_mission(workspace, mission['mission_id'])['organizer']
    assert organizer['state'] == 'pending' and organizer['reviews_admitted'] == 0
    service.finish_attempt(original, phase='completed', payload={'answer': 'Origin is idle.'})
    assert drain_mission_reviews(service, workspace=workspace) == 1
    assert host.service.read_mission(workspace, mission['mission_id'])['organizer']['reviews_admitted'] == 1


@pytest.mark.parametrize('typed_source_error', [False, True])
def test_pause_between_reservation_and_admission_releases_only_unexecuted_budget(review_store, monkeypatch, typed_source_error):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    service, thread_id, workspace, _ = review_store
    host, mission, intent, original = reserved_review(review_store, reserve=False)
    reached, paused = Event(), Event()
    actual_submit = service.submit_mission_review
    def pause_before_admission(source):
        reached.set()
        assert paused.wait(5), 'Concurrent pause did not complete before admission'
        if typed_source_error:
            raise ThreadProtocolError('Source validation failed after the concurrent pause')
        return actual_submit(source)
    monkeypatch.setattr(service, 'submit_mission_review', pause_before_admission)
    def user_pause():
        assert reached.wait(5), 'Drain did not reach reserved admission'
        current = host.service.read_mission(workspace, mission['mission_id'])
        host.command_mission(workspace, dict(schema='capstone-control-mission-command/1',
            operation_id='pause_before_admission', mission_id=mission['mission_id'],
            expected_revision=current['revision'], kind='pause', payload={}))
        paused.set()
    with ThreadPoolExecutor(max_workers=2) as pool:
        draining = pool.submit(drain_mission_reviews, service, workspace=workspace)
        pausing = pool.submit(user_pause)
        assert draining.result(timeout=8) == 0
        pausing.result(timeout=8)
    assert find_review(service, intent) is None
    current = host.service.read_mission(workspace, mission['mission_id'])
    assert current['organizer']['state'] == 'abandoned'
    assert current['organizer']['reviews_admitted'] == 0
    monkeypatch.setattr(service, 'submit_mission_review', actual_submit)
    host.command_mission(workspace, dict(schema='capstone-control-mission-command/1',
        operation_id='explicit_resume_after_release', mission_id=mission['mission_id'],
        expected_revision=current['revision'], kind='resume', payload={}))
    following = host.service.pending_mission_reviews(workspace)[0]
    assert following['review_id'] != intent['review_id']
    with pytest.raises(ValueError):
        service.submit_mission_review(intent)


def test_admitted_attempt_never_refunds_after_pause_even_before_ack(review_store):
    from capstone_agent.mission_continuation import release_unadmitted_review
    service, thread_id, workspace, _ = review_store
    host, mission, intent, original = reserved_review(review_store)
    binding = service.submit_mission_review(intent)
    current = host.service.read_mission(workspace, mission['mission_id'])
    host.command_mission(workspace, dict(schema='capstone-control-mission-command/1',
        operation_id='pause_after_admission', mission_id=mission['mission_id'],
        expected_revision=current['revision'], kind='pause', payload={}))
    assert release_unadmitted_review(service, intent) is False
    assert find_review(service, intent)[0] == binding
    assert host.service.read_mission(workspace, mission['mission_id'])['organizer']['reviews_admitted'] == 1


def test_postgres_review_reads_original_child_product_and_plans_from_its_bytes(postgres_thread_service, tmp_path):
    import json
    from hashlib import sha256
    from capstone_agent.artifacts import MemoryObjectStore
    from capstone_agent.native_artifact_projection import artifact_object_key, project_native_artifact_capture
    from capstone_agent.native_product_roles import file_artifact_id
    from capstone_agent.pi_delegation import PiTaskRequest, PiTaskResult
    from capstone_agent.intent_runtime import IntentRuntimeFactory
    from capstone_agent.thread_worker import run_pending_attempt
    from capstone_agent.continuation_resources import resource_reader_for
    service, origin_thread = postgres_thread_service
    workspace = 'product_review_' + uuid4().hex[:12]
    native = native_executor()
    native.capability['mission_schemas'] = ['capstone-native-mission/1']
    service.set_native_executor(native)
    service.create_thread(replace(_snapshot(origin_thread), active_model_context=None,
        active_grid_page_id=None, minimum_protocol_version=2), workspace_name=workspace)
    objects = MemoryObjectStore()
    service.set_material_store(objects)
    child_thread = 'thr_saved_child_' + uuid4().hex[:12]
    from capstone_agent.thread_protocol import RunSnapshot
    service.create_thread(replace(_snapshot(child_thread), active_model_context=None,
        active_grid_page_id=None, minimum_protocol_version=2,
        run=RunSnapshot('run_' + uuid4().hex[:16], 'open')), workspace_name=workspace)
    try:
        service.submit_command(command(service, child_thread, 'send_message', 'save_first_product',
            payload={'text': 'Save the first task findings.'}))
        child = service.claim_attempt('saved_product_worker', 30)
        data = json.dumps({'followup': 'Compare the discrepancy found in the saved dataset.',
                           'needs_followup': True, 'unique': uuid4().hex}).encode()
        request = PiTaskRequest('task_saved_child', child.attempt.attempt_id, 'direct', 'Save findings',
            (), (), native.identity, 60)
        artifact = project_native_artifact_capture(child, request, {
            'type': 'native_artifact_captured', 'schema': 'capstone-pi-artifact-capture/1',
            'task_id': request.task_id, 'parent_attempt_id': request.parent_attempt_id,
            'executor_identity': dict(native.identity), 'artifact': {
                'artifact_id': file_artifact_id('findings.json', sha256(data).hexdigest()),
                'task_id': request.task_id, 'parent_attempt_id': request.parent_attempt_id,
                'kind': 'workspace_file', 'metadata': {'path': 'findings.json',
                    'sha256': sha256(data).hexdigest(), 'size_bytes': len(data)}}})[0]
        source = {**artifact, 'source_status': 'completed'}
        objects.put(artifact_object_key(source), data, 'application/json')
        service.append_runtime_event(child, event_type='native_artifact_published', payload={'artifact': source})
        service.finish_attempt(child, phase='completed', payload={'answer': 'Saved findings require content inspection.'})
        host, mission, intent, original = reserved_review((service, origin_thread, workspace, native), products=[source])
        binding = service.submit_mission_review(intent)
        host.service.acknowledge_mission_review(workspace, mission['mission_id'], intent['review_id'], binding)
        read_bytes = []
        def execute_with_references(request, control, on_event, reader, bridge):
            document = request.to_document()
            manifest, = document['native_context']['resource_manifests']
            assert 'content_base64' not in json.dumps(document)
            assert json.loads(data)['unique'] not in json.dumps(document)
            saved_bytes = b''.join(reader(manifest))
            reader.record_delivery(request.task_id, manifest)
            assert saved_bytes == data
            with pytest.raises(ValueError):
                b''.join(reader({**manifest, 'sha256': 'f' * 64}))
            read_bytes.append(saved_bytes)
            findings = json.loads(saved_bytes)
            current = control.mission_operation('agent_mission_read', {}, 'read_saved_results')
            if findings['needs_followup']:
                next_task = dict(task_id='compare_discrepancy', objective=findings['followup'],
                    delivery_requirements=['Save the discrepancy comparison'], depends_on=['inspect'],
                    agent_id='capstone', mode='single', max_attempts=1)
                control.mission_operation('agent_mission_prepare_task',
                    {'expected_revision': current['revision'], 'task': next_task}, 'prepare_from_saved_bytes')
            return PiTaskResult(request.task_id, request.parent_attempt_id, native.identity,
                'completed', 'The original saved findings require a discrepancy comparison.', (), (), {})
        native.execute_with_resource_references = execute_with_references
        def forbidden(*args):
            raise AssertionError('Review must use the existing native runtime')
        factory = IntentRuntimeFactory(forbidden, forbidden, forbidden, general_executor=native,
                                       native_research_root=tmp_path)
        result = run_pending_attempt(service, factory, worker_id='content_review', implementation_family='native')
        assert result.status == 'completed'
        assert read_bytes == [data]
        current = host.service.read_mission(workspace, mission['mission_id'])
        followup = next(task for task in current['tasks'] if task['task_id'] == 'compare_discrepancy')
        assert followup['objective'] == json.loads(data)['followup']
        assert json.loads(data)['followup'] not in str(intent)
        events = service.read_events(origin_thread, 0).events
        grants = [event for event in events if event.event_type == 'mission_review_resources_granted']
        assert len(grants) == 1 and grants[0].payload['delegation_id'] == intent['review_id']
        receipts = [event for event in events if event.event_type == 'delegation_input_delivered']
        assert len(receipts) == 1 and receipts[0].payload['source']['sha256'] == sha256(data).hexdigest()
    finally:
        service.delete_thread(child_thread)


@pytest.mark.parametrize('review_store', ['postgres'], indirect=True)
def test_recovered_origin_delivery_releases_existing_mission_review_once(review_store):
    from hashlib import sha256
    from types import SimpleNamespace

    from capstone_agent.native_owner_recovery import recover_exited_native_deliveries
    from capstone_agent.pi_delegation import PiTaskResult

    service, thread_id, workspace, _ = review_store
    host, mission, intent, original = reserved_review(review_store, complete_origin=False, reserve=False)
    attempt_id = original.attempt.attempt_id
    task_id = 'pi-' + sha256((attempt_id + '\0conversation').encode()).hexdigest()
    identity = {'engine': 'pi'}
    service.append_runtime_event(original, event_type='runtime_event', payload={
        'task_id': task_id, 'parent_attempt_id': attempt_id, 'entrypoint': 'delegated',
        'goal_id': 'conversation', 'child_status': 'started', 'executor_identity': identity,
        'route_source': 'native_conversation', 'delivery_recovery_format': 'plain',
    }, visibility='diagnostic')
    service.append_runtime_event(original, event_type='attempt_worker_diagnostic',
                                 payload={'error_code': 'worker_execution_failed'}, visibility='diagnostic')
    assert service.interrupt_expired_attempts() == 1
    assert drain_mission_reviews(service, workspace=workspace) == 0

    reply = PiTaskResult(task_id, attempt_id, identity, 'completed', 'Initial plan filed', (), (), {})
    assert recover_exited_native_deliveries(service, SimpleNamespace(observe_terminal_task=lambda *_: reply)) == 1
    assert drain_mission_reviews(service, workspace=workspace) == 1
    assert drain_mission_reviews(service, workspace=workspace) == 0
    binding, phase = find_review(service, intent)
    review = service.claim_attempt('mission_reviewer', 30)
    assert phase == 'accepted' and review.attempt.attempt_id == binding['attempt_id']
    assert any(message['content'] == 'Initial plan filed' for message in review.conversation_context.messages)
    saved = host.service.read(workspace, mission['mission_id'])
    assert saved['organizer']['reviews_admitted'] == 1
    assert saved.get('acceptance') is None


@pytest.mark.parametrize('outcome', ['verified', 'pause', 'cancel', 'missing_authority'])
def test_mission_reconciles_child_delivery_after_observing_worker_exit(postgres_thread_service, outcome, monkeypatch):
    from hashlib import sha256
    from types import SimpleNamespace

    from capstone_control.reconcile import reconcile
    from capstone_agent.native_owner_recovery import recover_exited_native_deliveries
    from capstone_agent.pi_delegation import PiTaskResult

    service, thread_id = postgres_thread_service
    workspace = 'recover_child_' + uuid4().hex[:12]
    service.create_thread(replace(_snapshot(thread_id), active_model_context=None,
        active_grid_page_id=None, minimum_protocol_version=2), workspace_name=workspace)
    service.set_native_executor(native_executor())
    host = configure_control(service)
    list_goals = host.service.store.list
    monkeypatch.setattr(host.service.store, 'list', lambda **options: list_goals(workspace=workspace, **options))
    mission = host.create_mission(workspace, {'schema': 'capstone-control-mission-create/1',
        'operation_id': 'create', 'objective': 'Recover a child delivery', 'origin': {'thread_id': thread_id}})
    mission_id = mission['mission_id']
    task = dict(task_id='inspect', objective='Inspect the saved material',
        delivery_requirements=['Return a saved answer'], depends_on=[], agent_id='capstone',
        mode='single', max_attempts=1)
    if outcome == 'missing_authority':
        task['required_reference_sources'] = ['authority_source']
    for kind, payload in [('update_plan', {'acceptance_criteria': ['Inspect findings'], 'tasks': [task]}),
                          ('ready', {}), ('delegate_next', {})]:
        goal = host.service.read(workspace, mission_id)
        host.command_mission(workspace, {'schema': 'capstone-control-mission-command/1',
            'operation_id': kind, 'mission_id': mission_id, 'expected_revision': goal['revision'],
            'kind': kind, 'payload': payload})
    assert reconcile(host.service, host.agent, workspace=workspace, goal_id=mission_id)['errors'] == 0
    binding = host.service.read(workspace, mission_id)['tasks'][0]['delegation']['binding']
    try:
        claim = service.claim_attempt('child', 30)
        assert claim.thread_id == binding['thread_id']
        attempt_id = claim.attempt.attempt_id
        task_id = 'pi-' + sha256((attempt_id + '\0conversation').encode()).hexdigest()
        identity = {'engine': 'pi'}
        service.append_runtime_event(claim, event_type='runtime_event', payload={
            'task_id': task_id, 'parent_attempt_id': attempt_id, 'entrypoint': 'delegated',
            'goal_id': 'conversation', 'child_status': 'started', 'executor_identity': identity,
            'route_source': 'native_conversation', 'delivery_recovery_format': 'plain',
        }, visibility='diagnostic')
        service.append_runtime_event(claim, event_type='attempt_worker_diagnostic',
                                     payload={'error_code': 'worker_execution_failed'}, visibility='diagnostic')
        assert service.interrupt_expired_attempts() == 1
        assert reconcile(host.service, host.agent, workspace=workspace, goal_id=mission_id)['errors'] == 0
        assert host.service.read(workspace, mission_id)['tasks'][0]['state'] == 'blocked'
        if outcome in {'pause', 'cancel'}:
            goal = host.service.read(workspace, mission_id)
            host.command_mission(workspace, {'schema': 'capstone-control-mission-command/1',
                'operation_id': outcome, 'mission_id': mission_id, 'expected_revision': goal['revision'],
                'kind': outcome, 'payload': {}})

        reply = PiTaskResult(task_id, attempt_id, identity, 'completed', 'Recovered child findings', (), (), {})
        executor = SimpleNamespace(observe_terminal_task=lambda *_: reply)
        assert recover_exited_native_deliveries(service, executor) == 1
        host.tick()
        goal = host.service.read(workspace, mission_id)
        saved = goal['tasks'][0]
        assert saved['generation'] == 1 and saved['delegation']['binding'] == binding
        if outcome == 'verified':
            assert saved['state'] == 'verified' and goal['organizer']['state'] == 'pending'
        elif outcome == 'missing_authority':
            assert saved['state'] == 'failed' and saved['failure_reason'] == 'required_reference_receipt_missing'
        else:
            assert saved['delivery'] is None
        assert goal.get('acceptance') is None
        assert service.snapshot(binding['thread_id']).works[0]['latest_attempt_id'] == attempt_id
        assert reconcile(host.service, host.agent, workspace=workspace, goal_id=mission_id)['processed'] == 0
    finally:
        service.delete_thread(binding['thread_id'])


def test_settled_organizer_review_cannot_pause_itself(review_store):
    service, _, workspace, _ = review_store
    host, mission, intent, _ = reserved_review(review_store)
    assert service.submit_mission_review(intent) is not None
    claim = service.claim_attempt('reviewer', 30)
    current = host.read_mission(workspace, mission['mission_id'], claim=claim)
    with pytest.raises(ValueError, match='settled task'):
        host.mission_operation(claim, 'agent_mission_control',
            {'expected_revision': current['revision'], 'action': 'pause'}, operation_id='self_pause')
    assert host.read_mission(workspace, mission['mission_id'])['revision'] == current['revision']
    stopped = host.command_mission(workspace, {
        'schema': 'capstone-control-mission-command/1', 'operation_id': 'explicit_pause',
        'mission_id': mission['mission_id'], 'expected_revision': current['revision'],
        'kind': 'pause', 'payload': {}})
    assert stopped['mission']['state'] == 'paused'


def test_autonomous_mission_review_cannot_replace_acceptance_criteria(review_store):
    service, _, workspace, _ = review_store
    host, mission, intent, _ = reserved_review(review_store)
    assert service.submit_mission_review(intent) is not None
    claim = service.claim_attempt('reviewer', 30)
    current = host.read_mission(workspace, mission['mission_id'], claim=claim)
    assert current['acceptance_criteria']
    with pytest.raises(ValueError, match='preserve the current acceptance criteria'):
        host.mission_operation(claim, 'agent_mission_update_plan', {
            'expected_revision': current['revision'], 'tasks': [],
            'acceptance_criteria': ['Accept a different result'],
        }, operation_id='replace_criteria')
    assert host.read_mission(workspace, mission['mission_id'], claim=claim) == current


def test_autonomous_mission_cannot_suspend_for_user_input(review_store):
    service, _, workspace, _ = review_store
    host, mission, intent, _ = reserved_review(review_store)
    assert service.submit_mission_review(intent) is not None
    claim = service.claim_attempt('reviewer', 30)
    current = host.read_mission(workspace, mission['mission_id'], claim=claim)
    with pytest.raises(ValueError, match='partial delivery'):
        host.mission_operation(claim, 'agent_mission_wait', {
            'expected_revision': current['revision'], 'until': 'user',
            'reason': 'The source file is missing',
        }, operation_id='ask_user')
    assert host.read_mission(workspace, mission['mission_id'], claim=claim) == current


def test_review_plan_receipt_replays_after_user_changes_criteria(review_store):
    service, _, workspace, _ = review_store
    host, mission, intent, _ = reserved_review(review_store)
    assert service.submit_mission_review(intent) is not None
    claim = service.claim_attempt('reviewer', 30)
    mission_id = mission['mission_id']
    current = host.read_mission(workspace, mission_id, claim=claim)
    arguments = {'expected_revision': current['revision'], 'tasks': [],
                 'acceptance_criteria': current['acceptance_criteria']}
    operation = 'agent_mission_update_plan'
    original = host.mission_operation(claim, operation, arguments, operation_id='review_plan')
    updated = host.command_mission(workspace, {
        'schema': 'capstone-control-mission-command/1', 'operation_id': 'user_guidance',
        'mission_id': mission_id, 'expected_revision': original['mission']['revision'],
        'kind': 'update_plan', 'payload': {'tasks': [], 'acceptance_criteria': ['Check the updated result']},
    })
    assert host.mission_operation(claim, operation, arguments, operation_id='review_plan') == original
    assert host.read_mission(workspace, mission_id)['revision'] == updated['mission']['revision']
