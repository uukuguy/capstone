"""Work commands use the existing Attempt ledger and professional runtime."""
from dataclasses import replace

import pytest

from capstone_agent.enterprise_context import TaskContext
from capstone_agent.thread_service import InMemoryThreadService
from test_thread_postgres import _snapshot, postgres_thread_service


@pytest.fixture(params=['memory', 'postgres'])
def execution_store(request):
    if request.param == 'memory':
        return InMemoryThreadService(professional_snapshot()), 'thr_work_exec'
    store, thread_id = request.getfixturevalue('postgres_thread_service')
    store.create_thread(professional_snapshot(thread_id))
    return store, thread_id


def professional_snapshot(thread_id='thr_work_exec'):
    snapshot = _snapshot(thread_id)
    return replace(snapshot, active_model_context=replace(snapshot.professional_context,
                   model_revision='revision:sha256:' + 'a' * 64,
                   enabled_profiles=(('pandapower-static-analysis', '1.0.1'),)))


def command(store, thread_id, kind, name, *, work_id='new', revision=0, payload=None):
    return {'schema': 'capstone-command/2', 'command_id': 'cmd_' + name, 'idempotency_key': 'key_' + name,
            'thread_id': thread_id, 'kind': kind, 'target': {'kind': 'work', 'id': work_id,
            'expected_revision': revision}, 'payload': {} if payload is None else payload}


def save_work(store, thread_id, name='save'):
    receipt = store.submit_command(command(store, thread_id, 'work_message', name, payload={'text': 'Inspect the model'}))
    assert receipt.status == 'accepted'
    return store.snapshot(thread_id).to_document()['works'][-1]


def test_start_work_claim_and_terminal_share_one_ledger():
    store = InMemoryThreadService(professional_snapshot())
    work = save_work(store, 'thr_work_exec')
    assert work['status'] == 'ready'
    assert work['start_available'] is True
    start = command(store, 'thr_work_exec', 'start_work', 'start', work_id=work['work_id'], revision=work['revision'])
    accepted = store.submit_command(start)
    assert accepted.status == 'accepted'
    assert store.submit_command(start) == accepted
    assert store.snapshot('thr_work_exec').works[0]['status'] == 'queued'
    claim = store.claim_attempt('worker', 30)
    assert claim is not None
    assert claim.task_context.binding.work_id == work['work_id']
    assert claim.task_context.model_contexts == (claim.model_context,)
    assert claim.model_context.enabled_profiles == (('pandapower-static-analysis', '1.0.1'),)
    assert claim.attempt.attempt_id == accepted.target['attempt_id']
    assert store.claim_attempt('other', 30) is None
    assert store.snapshot('thr_work_exec').works[0]['status'] == 'running'
    store.finish_attempt(claim, phase='failed', payload={'error_code': 'fixture_failure'})
    restored = store.snapshot('thr_work_exec').to_document()['works'][0]
    assert restored['status'] == 'failed'
    assert restored['latest_attempt_id'] == claim.attempt.attempt_id
    assert restored['start_available'] is True
    assert store.submit_command(start) == accepted
    events = store.read_events('thr_work_exec', 0).events
    assert [event.event_seq for event in events] == list(range(1, len(events) + 1))
    linked = [event for event in events if event.event_type in {'attempt_started', 'attempt_failed'}]
    assert all(event.payload['work_id'] == work['work_id'] for event in linked)
    assert all(event.payload['work']['latest_attempt_id'] == claim.attempt.attempt_id for event in linked)


@pytest.mark.parametrize('with_model', [False, True])
def test_start_without_model_or_profiles_never_queues(with_model):
    from capstone_agent.thread_protocol import ThreadSnapshot, RunSnapshot
    snapshot = (_snapshot('thr_work_exec') if with_model else
                ThreadSnapshot('thr_work_exec', RunSnapshot('run_free', 'open'), None, None, None, 0, 0,
                               minimum_protocol_version=2))
    store = InMemoryThreadService(snapshot)
    work = save_work(store, 'thr_work_exec')
    assert work['start_available'] is False
    start = command(store, 'thr_work_exec', 'start_work', 'start', work_id=work['work_id'], revision=work['revision'])
    assert store.submit_command(start).status == 'rejected'
    assert store.claim_attempt('worker', 30) is None


def test_postgres_work_claim_survives_restart(postgres_thread_service):
    from capstone_agent.thread_service import PostgresThreadService
    store, thread_id = postgres_thread_service
    store.create_thread(professional_snapshot(thread_id))
    work = save_work(store, thread_id)
    start = command(store, thread_id, 'start_work', 'start', work_id=work['work_id'], revision=work['revision'])
    accepted = store.submit_command(start)
    assert accepted.status == 'accepted'
    restored = PostgresThreadService(store.dsn)
    assert restored.submit_command(start) == accepted
    claim = restored.claim_attempt('worker', 30)
    assert claim is not None
    assert isinstance(claim.task_context, TaskContext)
    assert claim.task_context.binding.research_id == work['task_context']['binding']['research_id']
    restored.finish_attempt(claim, phase='failed', payload={'error_code': 'fixture_failure'})
    assert store.snapshot(thread_id).works[0]['status'] == 'failed'


def test_expired_work_can_restart_and_old_claim_cannot_write():
    from capstone_agent.thread_service import ThreadExecutionError
    store = InMemoryThreadService(professional_snapshot())
    work = save_work(store, 'thr_work_exec')
    store.submit_command(command(store, 'thr_work_exec', 'start_work', 'first',
        work_id=work['work_id'], revision=work['revision']))
    claim = store.claim_attempt('worker', 30)
    store._attempts[claim.attempt.attempt_id]['lease_deadline'] = 0
    assert store.interrupt_expired_attempts() == 1
    after = store.snapshot('thr_work_exec').to_document()['works'][0]
    assert after['status'] == 'interrupted' and after['start_available']
    store.submit_command(command(store, 'thr_work_exec', 'start_work', 'second',
        work_id=work['work_id'], revision=after['revision']))
    new_claim = store.claim_attempt('worker', 30)
    with pytest.raises(ThreadExecutionError):
        store.finish_attempt(claim, phase='completed', payload={'answer': 'late'})
    assert store.snapshot('thr_work_exec').works[0]['latest_attempt_id'] == new_claim.attempt.attempt_id


def test_same_work_rebinds_current_model_on_a_new_explicit_start():
    store = InMemoryThreadService(professional_snapshot())
    work = save_work(store, 'thr_work_exec')
    store.submit_command(command(store, 'thr_work_exec', 'start_work', 'first',
        work_id=work['work_id'], revision=work['revision']))
    first = store.claim_attempt('worker', 30)
    store.finish_attempt(first, phase='failed', payload={'error_code': 'fixture_failure'})
    store._snapshot = replace(store._snapshot, active_model_context=replace(
        store._snapshot.professional_context, id='ctx_next', model_revision='next-revision'))
    work = store.snapshot('thr_work_exec').to_document()['works'][0]
    store.submit_command(command(store, 'thr_work_exec', 'start_work', 'second',
        work_id=work['work_id'], revision=work['revision']))
    second = store.claim_attempt('worker', 30)
    assert first.task_context.binding == second.task_context.binding
    assert first.task_context.goal_revision == second.task_context.goal_revision
    assert first.task_context.snapshot_id != second.task_context.snapshot_id
    assert first.model_context.model_revision != second.model_context.model_revision
    assert first.task_context.model_contexts == (first.model_context,)
    assert second.task_context.model_contexts == (second.model_context,)


def test_production_kernel_builder_opens_real_work_research(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from capability_agent.application.workspace import ApplicationWorkspace
    from capstone_agent.attempt_research import AttemptResearch
    import capstone_agent.kernel_pi_session as module
    store = InMemoryThreadService(professional_snapshot())
    work = save_work(store, 'thr_work_exec')
    store.submit_command(command(store, 'thr_work_exec', 'start_work', 'start',
        work_id=work['work_id'], revision=work['revision']))
    claim = store.claim_attempt('worker', 30)
    workspace = ApplicationWorkspace.create(tmp_path / 'contexts', binding_ids=('grid',))
    profile = SimpleNamespace(workspace=workspace, model_binding=SimpleNamespace(binding_id='grid'),
        profile=SimpleNamespace(reference_grants=()), prepared_application=SimpleNamespace(bindings={}))
    opened = []
    class ResearchOpened(Exception):
        pass
    def capture(*args, **kwargs):
        research = AttemptResearch(*args, **kwargs)
        opened.append(research)
        raise ResearchOpened()
    monkeypatch.setattr(module, 'AttemptResearch', capture)
    builder = object.__new__(module.PreparedKernelPiRpcSessionBuilder)
    builder._research_enabled = True
    builder._research_is_active = lambda selected: selected == claim
    with pytest.raises(ResearchOpened):
        builder(claim, None, (profile,))
    research = opened[0]
    assert research.task_context == claim.task_context
    assert research.model_context is None
    assert research.research_id == work['task_context']['binding']['research_id']
    assert research.identity_path.is_file()
    research.close(failed=True)


def test_postgres_expiry_restores_work_and_preserves_unconsumed_input(postgres_thread_service):
    import psycopg
    from capstone_agent.thread_service import ThreadExecutionError
    store, thread_id = postgres_thread_service
    store.create_thread(professional_snapshot(thread_id))
    work = save_work(store, thread_id)
    for index, text in enumerate(('supplement A', 'supplement B')):
        store.submit_command(command(store, thread_id, 'work_message', 'note' + str(index),
            work_id=work['work_id'], revision=work['revision'], payload={'text': text}))
        work = store.snapshot(thread_id).to_document()['works'][0]
    store.submit_command(command(store, thread_id, 'start_work', 'first',
        work_id=work['work_id'], revision=work['revision']))
    first = store.claim_attempt('worker', 30)
    assert 'supplement A' in first.instruction and 'supplement B' in first.instruction
    with psycopg.connect(store.dsn) as connection:
        connection.execute('UPDATE capstone_thread_attempts SET lease_deadline=now()-interval \'1 second\' WHERE attempt_id=%s',
                           (first.attempt.attempt_id,))
    assert store.interrupt_expired_attempts() == 1
    after = store.snapshot(thread_id).to_document()['works'][0]
    assert after['status'] == 'interrupted' and after['start_available']
    store.submit_command(command(store, thread_id, 'start_work', 'second',
        work_id=work['work_id'], revision=after['revision']))
    second = store.claim_attempt('worker', 30)
    assert first.instruction == second.instruction
    with pytest.raises(ThreadExecutionError):
        store.finish_attempt(first, phase='completed', payload={'answer': 'late'})
    assert store.snapshot(thread_id).works[0]['latest_attempt_id'] == second.attempt.attempt_id


@pytest.mark.parametrize('phase', ['queued', 'running'])
def test_cancel_work_uses_existing_attempt_cancel_guard(phase):
    store = InMemoryThreadService(professional_snapshot())
    work = save_work(store, 'thr_work_exec')
    store.submit_command(command(store, 'thr_work_exec', 'start_work', 'start',
        work_id=work['work_id'], revision=work['revision']))
    claim = store.claim_attempt('worker', 30) if phase == 'running' else None
    before = store.snapshot('thr_work_exec').to_document()['works'][0]
    cancel = command(store, 'thr_work_exec', 'cancel_work', 'cancel', work_id=work['work_id'], revision=before['revision'])
    receipt = store.submit_command(cancel)
    assert receipt.status == 'accepted'
    assert store.submit_command(cancel) == receipt
    after = store.snapshot('thr_work_exec').to_document()['works'][0]
    assert after['cancel_requested'] and after['status'] == phase
    claim = claim or store.claim_attempt('worker', 30)
    assert store.cancel_requested(claim)
    store.finish_attempt(claim, phase='cancelled', payload={})
    terminal = store.snapshot('thr_work_exec').to_document()['works'][0]
    assert terminal['status'] == 'cancelled' and terminal['cancel_requested'] is False


def test_runtime_factory_consumes_frozen_profile_reference():
    from types import SimpleNamespace
    from test_model_capability_context import _owner
    from capstone_agent.thread_application import PreparedApplicationPiRuntimeFactory
    snapshot = professional_snapshot()
    snapshot = replace(snapshot, active_model_context=replace(snapshot.professional_context,
                       enabled_profiles=(('static', '1.0.0'),)))
    store = InMemoryThreadService(snapshot)
    work = save_work(store, 'thr_work_exec')
    store.submit_command(command(store, 'thr_work_exec', 'start_work', 'start',
        work_id=work['work_id'], revision=work['revision']))
    claim = store.claim_attempt('worker', 30)
    log = []
    owner, adapters = _owner(log)
    seen = []
    def session_factory(selected, prepared):
        seen.append((selected.task_context, prepared.selected_profiles))
        return SimpleNamespace(stop=lambda: None)
    runtime = PreparedApplicationPiRuntimeFactory(owner, session_factory)(claim)
    assert seen == [(claim.task_context, claim.model_context.enabled_profiles)]
    assert adapters['static'].inputs[0][1] == claim.task_context.model_contexts[0]
    runtime.stop()
    store.finish_attempt(claim, phase='failed', payload={'error_code': 'fixture_failure'})
    store._snapshot = replace(store._snapshot, active_model_context=replace(
        store._snapshot.professional_context, id='ctx_new_revision', model_revision='next-revision'))
    work = store.snapshot('thr_work_exec').to_document()['works'][0]
    store.submit_command(command(store, 'thr_work_exec', 'start_work', 'next_revision',
        work_id=work['work_id'], revision=work['revision']))
    next_claim = store.claim_attempt('worker', 30)
    next_runtime = PreparedApplicationPiRuntimeFactory(owner, session_factory)(next_claim)
    assert next_claim.model_context.selection_revision == claim.model_context.selection_revision
    assert next_claim.task_context.binding == claim.task_context.binding
    assert adapters['static'].inputs[-1][1] == next_claim.model_context
    next_runtime.stop()
    owner.close()


def test_work_worker_runs_and_commits_terminal_state():
    from capstone_agent.thread_worker import run_pending_attempt
    store = InMemoryThreadService(professional_snapshot())
    work = save_work(store, 'thr_work_exec')
    store.submit_command(command(store, 'thr_work_exec', 'start_work', 'start',
        work_id=work['work_id'], revision=work['revision']))
    seen = []
    class Runtime:
        def start(self):
            pass
        def prompt(self, instruction, **kwargs):
            seen.append(instruction)
            return 'Ready to review supplied materials.'
        def stop(self):
            pass
    from capstone_agent.turn_router import FakeDecisionRouter
    result = run_pending_attempt(store, lambda claim: Runtime(), worker_id='worker',
                                 turn_router=FakeDecisionRouter('ordinary'))
    assert result.status == 'completed'
    assert seen == ['Inspect the model']
    completed = store.snapshot('thr_work_exec').to_document()['works'][0]
    assert completed['status'] == 'completed'
    assert completed['consumed_message_count'] == len(completed['messages'])


def test_unconsumed_supplements_survive_failure_and_completed_history_is_bounded(execution_store):
    store, thread_id = execution_store
    work = save_work(store, thread_id)
    for index, text in enumerate(('supplement A', 'supplement B')):
        store.submit_command(command(store, thread_id, 'work_message', 'note' + str(index),
            work_id=work['work_id'], revision=work['revision'], payload={'text': text}))
        work = store.snapshot(thread_id).to_document()['works'][0]
    instructions = []
    for name, phase in (('first', 'failed'), ('retry', 'completed')):
        work = store.snapshot(thread_id).to_document()['works'][0]
        store.submit_command(command(store, thread_id, 'start_work', name,
            work_id=work['work_id'], revision=work['revision']))
        claim = store.claim_attempt('worker', 30)
        instructions.append(claim.instruction)
        store.finish_attempt(claim, phase=phase, payload={'answer': 'fixture completion'} if phase == 'completed'
                             else {'error_code': 'fixture_failure'})
    assert instructions[0] == instructions[1]
    assert 'supplement A' in instructions[0] and 'supplement B' in instructions[0]
    work = store.snapshot(thread_id).to_document()['works'][0]
    assert work['consumed_message_count'] == len(work['messages'])
    store.submit_command(command(store, thread_id, 'work_message', 'new_note',
        work_id=work['work_id'], revision=work['revision'], payload={'text': 'supplement C'}))
    work = store.snapshot(thread_id).to_document()['works'][0]
    store.submit_command(command(store, thread_id, 'start_work', 'third',
        work_id=work['work_id'], revision=work['revision']))
    third = store.claim_attempt('worker', 30)
    assert 'supplement C' in third.instruction and 'supplement A' not in third.instruction
    assert third.previous_instruction.attempt_id == claim.attempt.attempt_id
    assert any('supplement A' in item['content'] for item in third.conversation_context.messages)
    from capstone_agent.task_record_reader import SelectedTaskRecordReader
    reader = SelectedTaskRecordReader(store, thread_id, third.previous_instruction.attempt_id)
    assert 'supplement A' in reader.read()['instruction']
    assert 'supplement B' in reader.read()['instruction']


def test_different_work_does_not_inherit_answers_or_result_refs(execution_store):
    store, thread_id = execution_store
    first = save_work(store, thread_id, 'first_work')
    store.submit_command(command(store, thread_id, 'start_work', 'first_start',
        work_id=first['work_id'], revision=first['revision']))
    first_claim = store.claim_attempt('worker', 30)
    result_ref, evidence_ref = 'result:sha256:' + 'b' * 64, 'evidence:sha256:' + 'c' * 64
    projection = {'schema': 'capstone-result-projection/1.0', 'result_id': 'projection_first',
        'result_ref': result_ref, 'evidence_refs': [evidence_ref], 'thread_id': thread_id,
        'run_id': first_claim.run_id, 'turn_id': first_claim.attempt.turn_id, 'attempt_id': first_claim.attempt.attempt_id,
        'model_context_id': first_claim.model_context.id, 'model_id': first_claim.model_context.model_id,
        'model_revision': first_claim.model_context.model_revision,
        'source': {'capability_id': 'analysis_fixture', 'domain_pack_id': 'pandapower-static-analysis', 'implementation_family': 'pandapower'},
        'status': 'completed', 'summary': [], 'tables': [], 'element_refs': [], 'overlay': None}
    store.finish_attempt(first_claim, phase='completed', payload={'answer': 'private answer for first Work',
        'result_refs': [result_ref], 'evidence_refs': [evidence_ref], 'result_projections': [projection]})
    second = save_work(store, thread_id, 'second_work')
    store.submit_command(command(store, thread_id, 'start_work', 'second_start',
        work_id=second['work_id'], revision=second['revision']))
    second_claim = store.claim_attempt('worker', 30)
    assert second_claim.previous_instruction is None
    assert second_claim.prior_results == ()
    assert second_claim.conversation_context.messages == ()
    assert first_claim.task_context.binding.research_id != second_claim.task_context.binding.research_id


def test_work_input_uses_existing_runtime_bound_without_new_16384_gate(execution_store):
    store, thread_id = execution_store
    long_goal = 'a' * 17000
    store.submit_command(command(store, thread_id, 'work_message', 'long_save', payload={'text': long_goal}))
    work = store.snapshot(thread_id).to_document()['works'][0]
    start = command(store, thread_id, 'start_work', 'start', work_id=work['work_id'], revision=work['revision'])
    assert store.submit_command(start).status == 'accepted'
    claim = store.claim_attempt('worker', 30)
    from capstone_agent.turn_router import routing_input_for_claim
    assert claim.instruction == long_goal
    assert len(routing_input_for_claim(claim).instruction) <= 16384


def test_work_over_existing_runtime_bound_is_rejected_idempotently(execution_store, request):
    from capstone_agent.application_capacity import current_capacity, initialize_capacity
    previous = current_capacity()
    request.addfinalizer(lambda: initialize_capacity(previous))
    initialize_capacity({'input_text_chars': 65536})
    store, thread_id = execution_store
    store.submit_command(command(store, thread_id, 'work_message', 'large_goal', payload={'text': 'g' * 33000}))
    work = store.snapshot(thread_id).to_document()['works'][0]
    store.submit_command(command(store, thread_id, 'work_message', 'large_note', work_id=work['work_id'],
        revision=work['revision'], payload={'text': 'n' * 33000}))
    work = store.snapshot(thread_id).to_document()['works'][0]
    assert work['start_available'] is False
    assert work['start_unavailable_reason'] == 'work_input_too_large'
    start = command(store, thread_id, 'start_work', 'start', work_id=work['work_id'], revision=work['revision'])
    rejected = store.submit_command(start)
    assert rejected.rejection == 'work_input_too_large'
    assert store.submit_command(start) == rejected
    assert store.claim_attempt('worker', 30) is None
    assert store.snapshot(thread_id).works[0]['messages'] == work['messages']


@pytest.mark.parametrize('claimed', [False, True])
def test_cancel_uses_same_ledger_in_both_adapters(execution_store, claimed):
    from capstone_agent.thread_worker import run_pending_attempt
    store, thread_id = execution_store
    work = save_work(store, thread_id)
    store.submit_command(command(store, thread_id, 'start_work', 'start',
        work_id=work['work_id'], revision=work['revision']))
    claim = store.claim_attempt('worker', 30) if claimed else None
    work = store.snapshot(thread_id).to_document()['works'][0]
    cancel = command(store, thread_id, 'cancel_work', 'cancel', work_id=work['work_id'], revision=work['revision'])
    accepted = store.submit_command(cancel)
    assert accepted.status == 'accepted' and store.submit_command(cancel) == accepted
    assert store.snapshot(thread_id).works[0]['status'] != 'cancelled'
    if claimed:
        assert store.cancel_requested(claim)
        store.finish_attempt(claim, phase='cancelled', payload={})
    else:
        def forbidden_runtime(claim):
            raise AssertionError('cancelled queued Work must not prepare resources or Provider')
        assert run_pending_attempt(store, forbidden_runtime, worker_id='worker').status == 'cancelled'
    terminal = store.snapshot(thread_id).to_document()['works'][0]
    assert terminal['status'] == 'cancelled' and terminal['cancel_requested'] is False
    assert store.submit_command(cancel) == accepted


def test_cancel_other_work_and_terminal_race_do_not_change_owner(execution_store):
    store, thread_id = execution_store
    other = save_work(store, thread_id, 'other')
    work = save_work(store, thread_id)
    store.submit_command(command(store, thread_id, 'start_work', 'start',
        work_id=work['work_id'], revision=work['revision']))
    claim = store.claim_attempt('worker', 30)
    bad = store.submit_command(command(store, thread_id, 'cancel_work', 'other_cancel',
        work_id=other['work_id'], revision=other['revision']))
    assert bad.rejection == 'attempt_target_mismatch'
    assert not store.cancel_requested(claim)
    work = store.snapshot(thread_id).to_document()['works'][1]
    cancel = command(store, thread_id, 'cancel_work', 'cancel', work_id=work['work_id'], revision=work['revision'])
    accepted = store.submit_command(cancel)
    store.finish_attempt(claim, phase='completed', payload={'answer': 'Completed before cancellation was observed.'})
    terminal = store.snapshot(thread_id).to_document()['works'][1]
    assert terminal['status'] == 'completed' and terminal['cancel_requested'] is False
    assert store.submit_command(cancel) == accepted
    late = store.submit_command(command(store, thread_id, 'cancel_work', 'late_cancel',
        work_id=work['work_id'], revision=terminal['revision']))
    assert late.rejection == 'attempt_target_mismatch'


def test_context_mismatch_interrupts_work_without_poisoning_new_start(execution_store):
    store, thread_id = execution_store
    work = save_work(store, thread_id)
    first = command(store, thread_id, 'start_work', 'first', work_id=work['work_id'], revision=work['revision'])
    accepted = store.submit_command(first)
    if isinstance(store, InMemoryThreadService):
        store._snapshot = replace(store._snapshot, active_model_context=replace(
            store._snapshot.professional_context, id='ctx_next', model_revision='next-revision'))
    else:
        import psycopg
        with psycopg.connect(store.dsn) as connection:
            connection.execute('UPDATE capstone_threads SET model_context_id=%s,model_revision=%s WHERE thread_id=%s',
                               ('ctx_next', 'next-revision', thread_id))
    assert store.claim_attempt('worker', 30) is None
    interrupted = store.snapshot(thread_id).to_document()['works'][0]
    assert interrupted['status'] == 'interrupted' and interrupted['start_available']
    assert store.read_events(thread_id, 0).events[-1].payload['work']['status'] == 'interrupted'
    assert store.submit_command(first) == accepted
    store.submit_command(command(store, thread_id, 'start_work', 'second',
        work_id=work['work_id'], revision=interrupted['revision']))
    current = store.claim_attempt('worker', 30)
    assert current.model_context.model_revision == 'next-revision'
    assert current.task_context.binding.research_id == work['task_context']['binding']['research_id']


def test_http_start_wakes_existing_worker_but_work_save_does_not():
    from fastapi.testclient import TestClient
    from test_thread_http_api import _app, _auth
    calls = []
    store = InMemoryThreadService(professional_snapshot())
    with TestClient(_app(store, wake_worker=lambda: calls.append('wake') or True), base_url='http://localhost') as client:
        headers = {**_auth(), 'Capstone-Thread-Version': '2'}
        save = command(store, 'thr_work_exec', 'work_message', 'save', payload={'text': 'a' * 17000})
        assert client.post('/api/v1/threads/thr_work_exec/commands', json=save, headers=headers).status_code == 202
        assert calls == []
        work = store.snapshot('thr_work_exec').to_document()['works'][0]
        start = command(store, 'thr_work_exec', 'start_work', 'start', work_id=work['work_id'], revision=work['revision'])
        response = client.post('/api/v1/threads/thr_work_exec/commands', json=start, headers=headers)
        assert response.status_code == 202 and response.json()['status'] == 'accepted'
        assert calls == ['wake']


@pytest.mark.parametrize('pending_kind', ['selection', 'model'])
def test_start_activates_pending_resources_atomically_after_admission(execution_store, pending_kind):
    from types import SimpleNamespace
    from capstone_agent.thread_service import ThreadModelDescriptor
    from capstone_model_capability_spi import ModelCapabilitySelection
    store, thread_id = execution_store
    selected = ModelCapabilitySelection((('pandapower-static-analysis', '1.0.1'),))
    store.set_capability_catalog(SimpleNamespace(resolve=lambda model, selection: selection or selected))
    if pending_kind == 'selection':
        # A normal empty active selection must not defeat a pending explicit enable.
        if isinstance(store, InMemoryThreadService):
            store._snapshot = replace(store._snapshot, active_model_context=replace(
                store._snapshot.professional_context, enabled_profiles=()))
        else:
            import psycopg
            with psycopg.connect(store.dsn) as connection:
                connection.execute("UPDATE capstone_threads SET enabled_profiles='[]'::jsonb WHERE thread_id=%s", (thread_id,))
        kind = 'replace_selection'
        payload = {'enabled_profiles': [{'profile_id': 'pandapower-static-analysis', 'profile_version': '1.0.1'}]}
    else:
        store.set_model_catalog(SimpleNamespace(resolve=lambda identity: ThreadModelDescriptor(
            identity, 'revision:sha256:' + 'd' * 64, 'pandapower')))
        kind, payload = 'switch_model', {'model_id': 'case14'}
    change = {'schema': 'capstone-command/1', 'command_id': 'cmd_select', 'idempotency_key': 'key_select',
        'thread_id': thread_id, 'kind': kind, 'expected_event_seq': 0, 'payload': payload}
    assert store.submit_command(change).status == 'accepted'
    work = save_work(store, thread_id)
    assert work['start_available'] is True
    before = store.snapshot(thread_id)
    bad = command(store, thread_id, 'start_work', 'bad_start', work_id=work['work_id'], revision=0)
    assert store.submit_command(bad).rejection == 'revision_conflict'
    assert store.snapshot(thread_id) == before
    store.set_available_families(frozenset())
    no_worker = command(store, thread_id, 'start_work', 'no_worker', work_id=work['work_id'], revision=work['revision'])
    assert store.submit_command(no_worker).rejection == 'worker_unavailable'
    assert store.snapshot(thread_id) == before
    store.set_available_families(None)
    accepted = store.submit_command(command(store, thread_id, 'start_work', 'start',
        work_id=work['work_id'], revision=work['revision']))
    assert accepted.status == 'accepted'
    claimed = store.claim_attempt('worker', 30)
    assert claimed.task_context.model_contexts == (claimed.model_context,)
    assert claimed.model_context.enabled_profiles == selected.enabled_profiles
    assert store.snapshot(thread_id).pending_selection is None
    assert store.snapshot(thread_id).pending_model_switch is None
    if pending_kind == 'model':
        assert claimed.model_context.model_id == 'case14'
    events = store.read_events(thread_id, 0).events
    activation = next(event for event in events if event.event_type in {'selection_activated', 'model_context_activated'})
    assert activation.event_seq < accepted.accepted_event_seq
