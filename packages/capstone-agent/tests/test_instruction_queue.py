import pytest
from capstone_agent.instruction_queue import submit, withdraw, admit


def test_retry_preserves_identity_and_order():
    queue = submit([], 'one', 'First', 'attempt')
    assert submit(queue, 'one', 'First', 'attempt') == queue
    with pytest.raises(ValueError):
        submit(queue, 'one', 'Changed', 'attempt')
    assert submit(queue, 'two', 'Next', 'attempt')[1]['sequence'] == 2


def test_withdraw_and_admission_have_one_outcome():
    queue = submit([], 'one', 'First', 'attempt')
    cancelled = withdraw(queue, 'one')
    assert admit(cancelled, 'attempt', 'lease')[1] is None
    accepted, item = admit(queue, 'attempt', 'lease')
    assert item['state'] == 'admitted'
    with pytest.raises(ValueError):
        withdraw(accepted, 'one')
    assert admit(accepted, 'attempt', 'other')[1] is None


def test_stop_and_other_attempt_cannot_consume_pending_text():
    queue = submit([], 'one', 'First', 'attempt')
    assert admit(queue, 'attempt', 'lease', stopped=True) == (queue, None)
    assert admit(queue, 'different', 'lease') == (queue, None)
    assert queue[0]['state'] == 'pending'


def test_active_work_saves_and_withdraws_supplement_without_replacing_attempt():
    from dataclasses import replace
    from capstone_agent.thread_protocol import ThreadSnapshot, RunSnapshot, AttemptSnapshot
    from capstone_agent.thread_service import InMemoryThreadService
    snapshot = ThreadSnapshot('thr_queue', RunSnapshot('run_queue', 'open'), None, None, None, 0, 0,
                              minimum_protocol_version=2)
    service = InMemoryThreadService(snapshot)
    command = dict(schema='capstone-command/2', command_id='first', idempotency_key='first',
                   thread_id='thr_queue', kind='work_message',
                   target=dict(kind='work', id='new', expected_revision=0), payload=dict(text='Initial'))
    assert service.submit_command(command).status == 'accepted'
    snapshot = service.snapshot('thr_queue')
    work = {**snapshot.works[0], 'status':'running', 'latest_attempt_id':'attempt_one'}
    current = AttemptSnapshot('turn_one', 'attempt_one', 'running', None, 'capstone')
    service = InMemoryThreadService(replace(snapshot, works=(work,), current_attempt=current))
    service._attempts[current.attempt_id] = {'attempt': current, 'submission': {'_native_execution': {
        'capability': {'instruction_schemas': ['capstone-native-instruction/1'],
                       'instruction_limit': 128,
                       'execution_authority_schemas': ['capstone-execution-authority/1']}}}}
    command.update(command_id='supplement', idempotency_key='supplement', kind='queue_instruction',
                   target=dict(kind='work', id=work['work_id'], expected_revision=work['revision']),
                   payload=dict(text='Change direction'))
    receipt = service.submit_command(command)
    assert receipt.status == 'accepted'
    assert service.submit_command(command) == receipt
    saved = service.snapshot('thr_queue')
    assert saved.current_attempt == current
    assert saved.works[0]['messages'] == ['Initial']
    assert saved.works[0]['instruction_queue'][0]['state'] == 'pending'
    command.update(command_id='withdraw', idempotency_key='withdraw', kind='withdraw_instruction',
                   target=dict(kind='work', id=work['work_id'], expected_revision=saved.works[0]['revision']),
                   payload=dict(instruction_id='supplement'))
    assert service.submit_command(command).status == 'accepted'
    assert service.snapshot('thr_queue').works[0]['instruction_queue'][0]['state'] == 'withdrawn'


def test_interrupt_replacement_uses_destination_state_instead_of_repeating_handoff():
    from dataclasses import replace
    from capstone_agent.instruction_queue import prepare_replacement
    from capstone_agent.thread_protocol import AttemptSnapshot, RunSnapshot, ThreadSnapshot
    from capstone_agent.thread_service import InMemoryThreadService
    from test_thread_work_execution import save_work

    snapshot = ThreadSnapshot('thr_queue', RunSnapshot('run_queue', 'open'), None, None, None, 0, 0,
                              minimum_protocol_version=2)
    store = InMemoryThreadService(snapshot)
    work = save_work(store, snapshot.thread_id)
    attempt = AttemptSnapshot('turn_source', 'attempt_destination', 'running', None, 'capstone')
    queue = submit([], 'next_instruction', 'Change direction', attempt.attempt_id, mode='interrupt')
    current = {**work, 'conversation_mode': True, 'status': 'running',
               'latest_attempt_id': attempt.attempt_id, 'instruction_queue': queue}
    before = replace(snapshot, works=(current,), current_attempt=attempt)
    settled = {**current, 'status': 'interrupted', 'task_state': {'revision_ref': attempt.attempt_id}}
    terminal = replace(snapshot, works=(settled,))
    _, _, context, submission, _ = prepare_replacement(
        before, terminal, attempt.attempt_id, {
            '_task_handoff': {'revision_ref': 'attempt_cross_session'},
            '_instruction_command_id': 'cmd_original',
        })
    assert context.task_state_ref == attempt.attempt_id
    assert '_task_handoff' not in submission
    assert submission['_instruction_command_id'] == 'next_instruction'


def test_pending_supplement_starts_after_completed_attempt_only():
    from dataclasses import replace
    from capstone_agent.instruction_queue import pending, prepare_replacement
    from capstone_agent.thread_protocol import AttemptSnapshot, RunSnapshot, ThreadSnapshot
    from capstone_agent.thread_service import InMemoryThreadService
    from test_thread_work_execution import save_work

    snapshot = ThreadSnapshot('thr_queue', RunSnapshot('run_queue', 'open'), None, None, None, 0, 0,
                              minimum_protocol_version=2)
    store = InMemoryThreadService(snapshot)
    work = save_work(store, snapshot.thread_id)
    attempt = AttemptSnapshot('turn_source', 'attempt_source', 'running', None, 'capstone')
    queue = submit([], 'next_instruction', 'Continue work', attempt.attempt_id)
    queue = submit(queue, 'deferred_instruction', 'Save the result', attempt.attempt_id, mode='after_attempt')
    assert [item['id'] for item in pending(queue, attempt.attempt_id)] == ['next_instruction']
    current = {**work, 'conversation_mode': True, 'status': 'running',
               'latest_attempt_id': attempt.attempt_id, 'instruction_queue': queue}
    before = replace(snapshot, works=(current,), current_attempt=attempt)
    terminal = replace(snapshot, works=({**current, 'status': 'completed'},))
    frozen = {'input': {'kind': 'text', 'text': 'Original'}, '_instruction_command_id': 'original'}
    assert prepare_replacement(before, terminal, attempt.attempt_id, frozen, phase='failed') is None
    successor, attempt_next, _, submission, event = prepare_replacement(
        before, terminal, attempt.attempt_id, frozen, phase='completed')
    assert attempt_next.attempt_id != attempt.attempt_id
    assert successor.works[0]['instruction_queue'][0]['state'] == 'admitted'
    assert submission['input']['text'] == 'Continue work'
    assert submission['_instruction_command_id'] == 'next_instruction'
    assert 'supersedes_attempt_id' not in event
    assert successor.works[0]['instruction_queue'][1]['attempt_id'] == attempt_next.attempt_id
    assert pending(successor.works[0]['instruction_queue'], attempt_next.attempt_id) == ()
    settled = replace(successor, current_attempt=None)
    _, _, _, deferred, _ = prepare_replacement(
        successor, settled, attempt_next.attempt_id, submission, phase='completed')
    assert deferred['input']['text'] == 'Save the result'
