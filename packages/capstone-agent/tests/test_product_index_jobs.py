import pytest
import psycopg
from capstone_agent.product_index_jobs import ProductIndexJobs
from test_thread_postgres import postgres_thread_service, _snapshot
from test_product_block_identity import selection


@pytest.fixture
def jobs(postgres_thread_service):
    service, thread = postgres_thread_service
    service.create_thread(_snapshot(thread))
    jobs = ProductIndexJobs(service.dsn); jobs.initialize()
    parent = {**selection()['parent_ref'], 'thread_id': thread}
    return jobs, parent


def test_request_is_idempotent_and_claim_is_exclusive(jobs):
    queue, parent = jobs
    key = queue.request(parent, parser_id='test/1', max_attempts=2)
    assert queue.request(parent, parser_id='test/1', max_attempts=2) == key
    first = queue.claim('worker-a', lease_seconds=60)
    assert first['job_id'] == key
    assert queue.claim('worker-b', lease_seconds=60) is None
    assert queue.renew(key, first['generation'], 'worker-a', lease_seconds=60)
    assert not queue.renew(key, first['generation'], 'worker-b', lease_seconds=60)


def test_expired_generation_cannot_publish(jobs):
    queue, parent = jobs
    key = queue.request(parent, parser_id='test/1', max_attempts=2)
    old = queue.claim('a', lease_seconds=60)
    with psycopg.connect(queue.dsn) as c:
        c.execute("UPDATE capstone_product_index_jobs SET lease_until=clock_timestamp()-interval '1 second' WHERE job_id=%s", (key,))
    new = queue.claim('b', lease_seconds=60)
    assert new['generation'] > old['generation']
    assert not queue.finish(key, old['generation'], 'a', error='failed')
    assert queue.finish(key, new['generation'], 'b', error='failed')
    assert queue.claim('c', lease_seconds=60) is None


def test_expired_final_attempt_becomes_failed(jobs):
    queue, parent = jobs
    key = queue.request(parent, parser_id='test/1', max_attempts=1)
    queue.claim('a', lease_seconds=60)
    with psycopg.connect(queue.dsn) as c:
        c.execute("UPDATE capstone_product_index_jobs SET lease_until=clock_timestamp()-interval '1 second' WHERE job_id=%s", (key,))
    assert queue.claim('b', lease_seconds=60) is None
    assert queue.status(parent['thread_id'], key)['state'] == 'failed'
    with pytest.raises(KeyError):
        queue.status('other-thread', key)


def test_verified_receipt_survives_database_adapter_restart(jobs):
    from hashlib import sha256
    from capstone_agent.product_blocks import build_index
    from capstone_agent.product_block_store import ProductBlockStore
    from capstone_agent.artifacts import MemoryObjectStore
    queue, parent = jobs
    data = b'paragraph\n'; parent = {**parent, 'digest': sha256(data).hexdigest()}
    value = build_index(parent, data, max_input_bytes=1024, max_blocks=10)
    key = queue.request(parent, parser_id=value['parser_id'], max_attempts=2)
    claim = queue.claim('worker', lease_seconds=60)
    receipt = ProductBlockStore(MemoryObjectStore(), max_index_bytes=8192).publish(value)
    with pytest.raises(ValueError):
        queue.finish(key, claim['generation'], 'worker', receipt={**receipt, 'parent_ref':{**parent,'thread_id':'other'}})
    assert queue.finish(key, claim['generation'], 'worker', receipt=receipt)
    restored = ProductIndexJobs(queue.dsn).status(parent['thread_id'], key)
    assert restored['state'] == 'ready' and restored['receipt'] == receipt
    assert queue.claim('next', lease_seconds=60) is None
