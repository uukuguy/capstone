"""Terminal preparation is pure; both stores commit the same public outcome."""
import pytest

from capstone_agent.thread_service import ThreadExecutionError, _prepare_terminal_transition
from test_thread_work_execution import command, execution_store, save_work
from test_thread_postgres import postgres_thread_service


@pytest.mark.parametrize('phase', ['completed', 'failed', 'cancelled', 'interrupted'])
def test_terminal_transition_matches_both_stores_without_mutating_inputs(execution_store, phase):
    store, thread = execution_store
    work = save_work(store, thread)
    accepted = store.submit_command(command(store, thread, 'start_work', 'terminal',
        work_id=work['work_id'], revision=work['revision']))
    assert accepted.status == 'accepted'
    claim = store.claim_attempt('transition-check', 30)
    before = store.snapshot(thread)
    original = before.to_document()
    payload = {'answer': 'Saved outcome'}
    prepared, event_payload, parts = _prepare_terminal_transition(before, claim, phase, payload)
    assert before.to_document() == original
    assert payload == {'answer': 'Saved outcome'}
    assert prepared.current_attempt is None
    assert prepared.works[0]['status'] == phase
    assert prepared.works[0]['revision'] == before.works[0]['revision'] + 1
    assert prepared.works[0]['latest_attempt_id'] == claim.attempt.attempt_id
    assert event_payload['answer'] == 'Saved outcome'
    assert event_payload['work']['status'] == phase
    assert parts == ()
    finished = store.finish_attempt(claim, phase=phase, payload=payload)
    assert finished.current_attempt is None
    assert finished.works == prepared.works
    assert finished.result_projections == prepared.result_projections
    event = next(e for e in store.read_events(thread, before.last_event_seq).events
                 if e.event_type == 'attempt_' + phase)
    assert event.payload == event_payload
    assert finished.last_event_seq == event.event_seq
    with pytest.raises(ThreadExecutionError):
        store.finish_attempt(claim, phase=phase, payload=payload)
    restored = store.snapshot(thread)
    assert restored.current_attempt is None
    assert restored.works == finished.works
    assert restored.result_projections == finished.result_projections
    terminal_events = [e for e in store.read_events(thread, before.last_event_seq).events
                       if e.event_type == 'attempt_' + phase]
    assert len(terminal_events) == 1
