"""Application-owned index job leases; independent of model Attempts."""
from hashlib import sha256
import json

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .thread_products import checked_ref

SCHEMA = """
CREATE TABLE IF NOT EXISTS capstone_product_index_jobs (
 job_id text PRIMARY KEY,
 thread_id text NOT NULL REFERENCES capstone_threads(thread_id) ON DELETE CASCADE,
 parent_ref jsonb NOT NULL, parser_id text NOT NULL,
 state text NOT NULL CHECK (state IN ('queued','running','ready','failed')),
 generation integer NOT NULL DEFAULT 0,
 max_attempts integer NOT NULL CHECK (max_attempts > 0),
 worker_id text, lease_until timestamptz, receipt jsonb, error text,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS capstone_product_index_jobs_queue
 ON capstone_product_index_jobs(state,created_at);
"""


def _positive(value):
    if type(value) is not int or not 0 < value <= 2147483647:
        raise ValueError('invalid index job budget')
    return value


class ProductIndexJobs:
    def __init__(self, dsn):
        self.dsn = dsn

    def _connect(self):
        return psycopg.connect(self.dsn, row_factory=dict_row)

    def initialize(self):
        with self._connect() as connection:
            connection.execute(SCHEMA)

    def request(self, parent_ref, *, parser_id, max_attempts):
        parent = checked_ref(parent_ref)
        if not isinstance(parser_id, str) or not 0 < len(parser_id) <= 256:
            raise ValueError('invalid index parser identity')
        _positive(max_attempts)
        identity = json.dumps([parent, parser_id, max_attempts], sort_keys=True,
                              separators=(',', ':')).encode()
        job_id = sha256(identity).hexdigest()
        with self._connect() as connection:
            connection.execute('''INSERT INTO capstone_product_index_jobs
                (job_id,thread_id,parent_ref,parser_id,state,max_attempts)
                VALUES (%s,%s,%s,%s,'queued',%s) ON CONFLICT (job_id) DO NOTHING''',
                (job_id, parent['thread_id'], Jsonb(parent), parser_id, max_attempts))
        return job_id

    def claim(self, worker_id, *, lease_seconds):
        _positive(lease_seconds)
        if not isinstance(worker_id, str) or not 0 < len(worker_id) <= 256:
            raise ValueError('invalid index worker identity')
        with self._connect() as connection:
            connection.execute('''UPDATE capstone_product_index_jobs
                SET state='failed',error='lease_exhausted',worker_id=NULL,lease_until=NULL
                WHERE state='running' AND lease_until<=clock_timestamp()
                  AND generation>=max_attempts''')
            return connection.execute('''WITH candidate AS (
                SELECT job_id FROM capstone_product_index_jobs
                WHERE (state='queued' OR (state='running' AND lease_until<=clock_timestamp()))
                  AND generation<max_attempts
                ORDER BY created_at,job_id FOR UPDATE SKIP LOCKED LIMIT 1
                ) UPDATE capstone_product_index_jobs j SET state='running',
                  generation=j.generation+1,worker_id=%s,
                  lease_until=clock_timestamp()+(%s * interval '1 second')
                FROM candidate WHERE j.job_id=candidate.job_id RETURNING j.*''',
                (worker_id, lease_seconds)).fetchone()

    def renew(self, job_id, generation, worker_id, *, lease_seconds):
        _positive(lease_seconds)
        with self._connect() as connection:
            return bool(connection.execute('''UPDATE capstone_product_index_jobs
                SET lease_until=clock_timestamp()+(%s * interval '1 second')
                WHERE job_id=%s AND generation=%s AND worker_id=%s
                  AND state='running' AND lease_until>clock_timestamp() RETURNING job_id''',
                (lease_seconds, job_id, generation, worker_id)).fetchone())

    def finish(self, job_id, generation, worker_id, *, receipt=None, error=None):
        if (receipt is None) == (error is None):
            raise ValueError('index completion needs receipt or error')
        if error is not None and (not isinstance(error, str) or not 0 < len(error) <= 128):
            raise ValueError('invalid index failure code')
        with self._connect() as connection:
            row = connection.execute('''SELECT * FROM capstone_product_index_jobs
                WHERE job_id=%s AND generation=%s AND worker_id=%s AND state='running'
                  AND lease_until>clock_timestamp() FOR UPDATE''',
                (job_id, generation, worker_id)).fetchone()
            if row is None:
                return False
            if receipt is not None:
                if (not isinstance(receipt, dict)
                        or receipt.get('schema') != 'capstone-block-index-object/1'
                        or receipt.get('parent_ref') != row['parent_ref']):
                    raise ValueError('index publication parent mismatch')
            return bool(connection.execute('''UPDATE capstone_product_index_jobs
                SET state=%s,receipt=%s,error=%s,worker_id=NULL,lease_until=NULL
                WHERE job_id=%s AND generation=%s AND worker_id=%s
                  AND lease_until>clock_timestamp() RETURNING job_id''',
                ('ready' if receipt is not None else 'failed',
                 Jsonb(receipt) if receipt is not None else None, error,
                 job_id, generation, worker_id)).fetchone())

    def status(self, thread_id, job_id):
        with self._connect() as connection:
            row = connection.execute('''SELECT * FROM capstone_product_index_jobs
                WHERE job_id=%s AND thread_id=%s''', (job_id, thread_id)).fetchone()
            if row is None:
                raise KeyError('index job unavailable')
            return row

    def published(self, thread_id, index_ref, parent_ref):
        with self._connect() as connection:
            row = connection.execute('''SELECT * FROM capstone_product_index_jobs
                WHERE thread_id=%s AND state='ready' AND parent_ref=%s
                  AND receipt->>'index_ref'=%s
                ORDER BY created_at,job_id LIMIT 1''',
                (thread_id, Jsonb(parent_ref), index_ref)).fetchone()
            if row is None:
                raise KeyError('published index unavailable')
            return row
