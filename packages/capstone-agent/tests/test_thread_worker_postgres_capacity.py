"""Use an isolated PostgreSQL database, never an application data ledger."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Thread

import psycopg
import pytest

from capstone_agent.thread_worker import serve_thread_attempts
from capstone_agent.thread_protocol import ThreadSnapshot
from test_thread_postgres import _command, _snapshot, postgres_thread_service


def _capacity_command(thread_id):
    return {**_command(thread_id), 'run_id': thread_id + '_run'}


@pytest.fixture
def pending_threads(postgres_thread_service):
    service, prefix = postgres_thread_service
    ids = [prefix + suffix for suffix in ('_a', '_b', '_c')]
    try:
        for thread_id in ids:
            document = _snapshot(thread_id).to_document()
            document['run']['run_id'] = thread_id + '_run'
            service.create_thread(ThreadSnapshot.from_document(document))
            assert service.submit_command(_capacity_command(thread_id)).status == 'accepted'
        yield service, ids
    finally:
        with psycopg.connect(service.dsn) as connection:
            connection.execute('DELETE FROM capstone_threads WHERE thread_id = ANY(%s)', (ids,))


def test_postgres_two_slots_leave_third_unleased_and_cancelled_queue_never_executes(pending_threads):
    service, ids = pending_threads
    stop, wake = Event(), Event()
    started = {thread_id: Event() for thread_id in ids}
    release = {thread_id: Event() for thread_id in ids}
    closed = {thread_id: Event() for thread_id in ids}

    class Runtime:
        def __init__(self, thread_id):
            self.thread_id = thread_id
        def start(self):
            pass
        def prompt(self, question, *, on_event, correlation_id=None, on_heartbeat=None):
            started[self.thread_id].set()
            assert release[self.thread_id].wait(8)
            return self.thread_id
        def stop(self):
            closed[self.thread_id].set()

    worker = Thread(target=serve_thread_attempts, kwargs=dict(
        service=service, runtime_factory=lambda claim: Runtime(claim.thread_id),
        max_concurrent_attempts=2, wake_event=wake, stop_event=stop, poll_seconds=0.01))
    worker.start()
    try:
        assert started[ids[0]].wait(5)
        assert started[ids[1]].wait(5)
        assert not started[ids[2]].is_set()
        snapshot = service.snapshot(ids[2])
        assert snapshot.current_attempt.phase == 'accepted'
        with psycopg.connect(service.dsn) as connection:
            row = connection.execute('SELECT lease_token FROM capstone_thread_attempts WHERE thread_id = %s', (ids[2],)).fetchone()
            assert row[0] is None
        cancel = {**_capacity_command(ids[2]), 'command_id': 'cancel_queue', 'idempotency_key': 'cancel_queue',
                  'expected_event_seq': snapshot.last_event_seq, 'kind': 'cancel_live_attempt',
                  'payload': {'attempt_id': snapshot.current_attempt.attempt_id}}
        assert service.submit_command(cancel).status == 'accepted'
        assert service.snapshot(ids[2]).current_attempt is None
        assert service.snapshot(ids[0]).current_attempt.phase == 'running'
        assert service.snapshot(ids[1]).current_attempt.phase == 'running'
    finally:
        stop.set()
        wake.set()
        for event in release.values():
            event.set()
        worker.join(8)
    assert not worker.is_alive()
    assert closed[ids[0]].is_set() and closed[ids[1]].is_set()
    assert not started[ids[2]].is_set()
    assert service.claim_attempt('after-cancel', 30) is None


def test_postgres_competing_workers_claim_each_attempt_once(pending_threads):
    service, ids = pending_threads
    with ThreadPoolExecutor(max_workers=6) as pool:
        claims = list(pool.map(lambda i: service.claim_attempt(f'worker-{i}', 30), range(6)))
    admitted = [claim for claim in claims if claim is not None]
    assert len(admitted) == len(ids)
    assert {claim.thread_id for claim in admitted} == set(ids)
    assert len({claim.attempt.attempt_id for claim in admitted}) == len(ids)
    for thread_id in ids:
        snapshot = service.snapshot(thread_id)
        duplicate = {**_capacity_command(thread_id), 'command_id': 'another', 'idempotency_key': 'another',
                     'expected_event_seq': snapshot.last_event_seq}
        assert service.submit_command(duplicate).status == 'rejected'


def test_claim_skips_a_thread_locked_by_an_admission_or_cancel_command(pending_threads):
    service, ids = pending_threads
    with ThreadPoolExecutor(max_workers=1) as pool:
        with psycopg.connect(service.dsn) as connection:
            connection.execute('SELECT thread_id FROM capstone_threads WHERE thread_id=%s FOR UPDATE', (ids[0],))
            claims = [pool.submit(service.claim_attempt, 'unblocked-slot', 30).result(timeout=3)
                      for _ in range(3)]
            assert {claim.thread_id for claim in claims if claim is not None} == set(ids[1:])
            assert claims[-1] is None
        claim = service.claim_attempt('released-thread', 30)
        assert claim is not None and claim.thread_id == ids[0]
