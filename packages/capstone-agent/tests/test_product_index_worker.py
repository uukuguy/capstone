from hashlib import sha256
import psycopg

from capstone_agent.artifacts import MemoryObjectStore
from capstone_agent.product_block_store import ProductBlockStore
from capstone_agent.product_blocks import build_index
from capstone_agent.product_index_worker import run_index_once
from test_product_index_jobs import jobs
from test_thread_postgres import postgres_thread_service


def prepare(jobs):
    queue, parent = jobs
    content = b'First [source][a].\n\n[a]: https://example.invalid\n'
    parent = {**parent, 'digest': sha256(content).hexdigest()}
    index = build_index(parent, content, max_input_bytes=1024, max_blocks=10)
    key = queue.request(parent, parser_id=index['parser_id'], max_attempts=2)
    store = ProductBlockStore(MemoryObjectStore(), max_index_bytes=8192)
    return queue, parent, content, key, store


def test_worker_publishes_verified_index(jobs):
    queue, parent, content, key, store = prepare(jobs)
    calls = []
    def read(ref, limit):
        calls.append((ref, limit))
        return content
    assert run_index_once(queue, store, read, worker_id='test', lease_seconds=60,
                          max_input_bytes=1024, max_blocks=10) == 'ready'
    state = queue.status(parent['thread_id'], key)
    assert calls == [(parent, 1024)]
    assert store.read(parent['thread_id'], state['receipt'])['blocks'][0]['dependencies']


def test_changed_source_records_failure_without_publishing(jobs):
    queue, parent, content, key, store = prepare(jobs)
    assert run_index_once(queue, store, lambda *_: b'changed', worker_id='test',
                          lease_seconds=60, max_input_bytes=1024, max_blocks=10) == 'failed'
    assert queue.status(parent['thread_id'], key)['receipt'] is None
    assert store.objects.contents == {}


def test_expired_reader_cannot_publish(jobs):
    queue, parent, content, key, store = prepare(jobs)
    def read(*_):
        with psycopg.connect(queue.dsn) as c:
            c.execute("UPDATE capstone_product_index_jobs SET lease_until=clock_timestamp()-interval '1 second' WHERE job_id=%s", (key,))
        return content
    assert run_index_once(queue, store, read, worker_id='test', lease_seconds=60,
                          max_input_bytes=1024, max_blocks=10) == 'lease_lost'
    assert store.objects.contents == {}


def test_reader_cannot_exceed_budget(jobs):
    queue, parent, content, key, store = prepare(jobs)
    assert run_index_once(queue, store, lambda *_: b'x'*1025, worker_id='test',
                          lease_seconds=60, max_input_bytes=1024, max_blocks=10) == 'failed'
    assert store.objects.contents == {}


def test_publish_failure_cannot_mark_ready_or_leak_exception(jobs):
    queue, parent, content, key, store = prepare(jobs)
    class BrokenStore:
        def publish(self, _):
            raise OSError('private source detail must not be persisted')
    assert run_index_once(queue, BrokenStore(), lambda *_: content, worker_id='test',
                          lease_seconds=60, max_input_bytes=1024, max_blocks=10) == 'failed'
    state = queue.status(parent['thread_id'], key)
    assert state['error'] == 'object_publish_failed' and state['receipt'] is None


def test_lease_loss_after_object_write_does_not_publish_ready(jobs):
    queue, parent, content, key, store = prepare(jobs)
    class ExpiringStore:
        def publish(self, value):
            receipt = store.publish(value)
            with psycopg.connect(queue.dsn) as c:
                c.execute("UPDATE capstone_product_index_jobs SET lease_until=clock_timestamp()-interval '1 second' WHERE job_id=%s", (key,))
            return receipt
    assert run_index_once(queue, ExpiringStore(), lambda *_: content, worker_id='test',
                          lease_seconds=60, max_input_bytes=1024, max_blocks=10) == 'lease_lost'
    assert queue.status(parent['thread_id'], key)['receipt'] is None
