from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
import pytest
from capability_agent.runtime.execution_queue import ExecutionQueue


def test_sixteen_calls_fill_eight_and_refill_without_wave_barrier():
    queue = ExecutionQueue(capacity=8)
    gates = [Event() for _ in range(16)]
    entered, lock = [], Lock()
    filled, refilled = Event(), Event()
    def run(i):
        receipt = queue.receipt(task_id='task', call_id=str(i))
        with queue.acquire(receipt, resource='shared', read_only=True):
            with lock:
                entered.append(i)
                if len(entered) == 8: filled.set()
                if len(entered) == 9: refilled.set()
            assert gates[i].wait(5)
        return receipt
    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = [pool.submit(run, i) for i in range(16)]
        try:
            assert filled.wait(3)
            assert len(entered) == 8
            gates[entered[0]].set()
            assert refilled.wait(3)
        finally:
            for gate in gates: gate.set()
        receipts = [f.result() for f in futures]
    assert all([e['phase'] for e in r['events']] == ['submitted','queued','acquired','released'] for r in receipts)


def test_error_releases_lease_and_unknown_effect_is_exclusive():
    queue = ExecutionQueue(capacity=8)
    receipt = queue.receipt(task_id='task', call_id='one')
    with pytest.raises(RuntimeError):
        with queue.acquire(receipt, resource='shared', read_only=False):
            raise RuntimeError('failure')
    with queue.acquire(queue.receipt(task_id='task', call_id='two'), resource='shared', read_only=False):
        pass
    assert receipt['events'][-1]['phase'] == 'released'


def test_queued_cancellation_does_not_acquire_or_release_capacity():
    queue = ExecutionQueue(capacity=1)
    cancel = Event()
    cancel.set()
    receipt = queue.receipt(task_id='task', call_id='cancelled')
    from concurrent.futures import CancelledError
    with pytest.raises(CancelledError):
        with queue.acquire(receipt, resource='shared', cancel=cancel):
            pytest.fail('cancelled work started')
    assert [e['phase'] for e in receipt['events']] == ['submitted','queued','cancellation_requested']


def test_conflicting_write_waits_for_read_and_blocks_later_read():
    queue = ExecutionQueue(capacity=8)
    writer, reader = Event(), Event()
    def call(flag, read_only):
        with queue.acquire(queue.receipt(task_id='task', call_id=str(read_only)), resource='shared', read_only=read_only):
            flag.set()
    with ThreadPoolExecutor(max_workers=2) as pool:
        with queue.acquire(queue.receipt(task_id='task', call_id='held'), resource='shared', read_only=True):
            write = pool.submit(call, writer, False)
            # Wait for admission to the pending queue without a timing assumption.
            from time import monotonic, sleep
            limit = monotonic() + 2
            while not queue._pending and monotonic() < limit: sleep(.001)
            read = pool.submit(call, reader, True)
            assert not writer.wait(.03)
            assert not reader.is_set()
        write.result()
        read.result()
    assert writer.is_set() and reader.is_set()
