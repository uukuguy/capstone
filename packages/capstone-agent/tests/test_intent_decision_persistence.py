from dataclasses import replace
from types import SimpleNamespace
import time

import pytest

from capstone_agent.request_intent import NodeControl
from capstone_agent.thread_service import PostgresThreadService, ThreadExecutionError
from test_delegated_runtime import Executor, Recognizer, factory, goal, run
from test_intent_runtime import claim
from test_thread_postgres import postgres_thread_service, _snapshot, _command


def retry_command(service, current, suffix='retry'):
    return {'schema': 'capstone-command/1', 'command_id': 'cmd_' + suffix,
        'idempotency_key': 'idem_' + suffix, 'thread_id': current.thread_id,
        'run_id': current.run_id, 'kind': 'retry_new_attempt',
        'expected_event_seq': service.snapshot(current.thread_id).last_event_seq,
        'payload': {'attempt_id': current.attempt.attempt_id}}


def test_worker_retry_reuses_accepted_decision_without_recognition_or_new_task():
    service, current = claim()
    class Changing(Recognizer):
        def recognize(self, request, control):
            self.goals = [goal('first' if not self.requests else 'different')]
            return super().recognize(request, control)
    executor, recognizer = Executor(), Changing([])
    selected = factory(executor, recognizer)
    control = NodeControl(lambda: None, time.monotonic() + 10)
    plan = selected.plan_intent(current, control, service.freeze_attempt_input,
                               freeze_decision=service.freeze_attempt_decision)
    selected(replace(current, turn_plan=plan)).prompt(current.instruction, on_event=lambda _: None)
    service.finish_attempt(current, phase='failed', payload={'error_code': 'after_child'})
    assert service.submit_command(retry_command(service, current)).status == 'accepted'
    retry = service.claim_attempt('worker_retry', 30)
    assert service.freeze_attempt_decision(retry, None)['attempt_id'] == current.attempt.attempt_id
    result = run(service, retry, selected)
    assert result.status == 'completed'
    assert len(recognizer.requests) == 1
    assert executor.requests[0].to_document() == executor.requests[1].to_document()
    with pytest.raises(ThreadExecutionError):
        service.freeze_attempt_decision(current, None)


def test_memory_decision_snapshot_is_immutable_defensive_and_lease_checked():
    service, current = claim()
    assert service.freeze_attempt_decision(current, None) is None
    document = {'schema': 'capstone-intent-decision/1', 'attempt_id': current.attempt.attempt_id,
                'goals': [{'goal_id': 'first'}]}
    first = service.freeze_attempt_decision(current, document)
    first['goals'].clear()
    assert service.freeze_attempt_decision(current, {**document, 'goals': []}) == document
    with pytest.raises(Exception):
        service.freeze_attempt_decision(current, {'oversized': 'a' * 40000})


def test_postgres_retry_copies_accepted_decision_and_runtime_receipt(postgres_thread_service):
    service, thread_id = postgres_thread_service
    service.create_thread(_snapshot(thread_id))
    assert service.submit_command(_command(thread_id)).status == 'accepted'
    current = service.claim_attempt('decision-test', 30)
    document = {'schema': 'capstone-intent-decision/1', 'attempt_id': current.attempt.attempt_id,
                'goals': [{'goal_id': 'accepted'}]}
    assert service.freeze_attempt_decision(current, document) == document
    service.finish_attempt(current, phase='failed', payload={'error_code': 'test'})
    receipt = service.submit_command(retry_command(service, current))
    assert receipt.status == 'accepted'
    retry = service.claim_attempt('decision-test', 30)
    assert service.freeze_attempt_decision(retry, None) == document
    event = next(e for e in service.read_events(thread_id, 0).events
                 if e.event_type == 'command_accepted' and e.attempt_id == retry.attempt.attempt_id)
    assert event.payload['runtime_mode'] == current.attempt.runtime_mode
    with pytest.raises(ThreadExecutionError):
        service.freeze_attempt_decision(current, document)


def test_postgres_decision_storage_requires_live_lease_and_binds_copy():
    from unittest.mock import MagicMock
    connection = MagicMock()
    connection.__enter__.return_value = connection
    saved = {'schema': 'capstone-intent-decision/1', 'goals': [{'goal_id': 'one'}]}
    connection.execute.return_value.fetchone.return_value = {'intent_decision_snapshot': saved}
    service = PostgresThreadService('postgresql://unused')
    service._connect = lambda: connection
    current = SimpleNamespace(thread_id='thread', attempt=SimpleNamespace(attempt_id='attempt'),
                              lease_token='lease')
    result = service.freeze_attempt_decision(current, None)
    result['goals'].clear()
    assert saved['goals']
    query = connection.execute.call_args.args[0]
    assert 'FOR UPDATE' in query and 'lease_deadline > clock_timestamp()' in query
    connection.execute.return_value.fetchone.return_value = None
    with pytest.raises(ThreadExecutionError):
        service.freeze_attempt_decision(current, None)


def test_retry_accepted_event_records_original_runtime_mode():
    service, current = claim()
    service.finish_attempt(current, phase='failed', payload={})
    assert service.submit_command(retry_command(service, current)).status == 'accepted'
    retry = service.claim_attempt('retry', 30)
    event = next(e for e in service.read_events(current.thread_id, 0).events
                 if e.event_type == 'command_accepted' and e.attempt_id == retry.attempt.attempt_id)
    assert event.payload['runtime_mode'] == current.attempt.runtime_mode
