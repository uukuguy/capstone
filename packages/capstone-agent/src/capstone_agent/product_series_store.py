"""PostgreSQL series state and retry receipts under the owning Thread lock."""
from hashlib import sha256
import json
import re

from psycopg.types.json import Jsonb

from .product_series import transition
from .thread_service import ThreadNotFound


class ProductSeriesStore:
    def __init__(self, threads):
        self.threads = threads

    def initialize(self):
        with self.threads._connect() as c:
            c.execute('''CREATE TABLE IF NOT EXISTS capstone_product_series (
                thread_id text NOT NULL REFERENCES capstone_threads(thread_id) ON DELETE CASCADE,
                series_id text NOT NULL, state jsonb NOT NULL,
                PRIMARY KEY(thread_id,series_id))''')
            c.execute('''CREATE TABLE IF NOT EXISTS capstone_product_series_commands (
                thread_id text NOT NULL REFERENCES capstone_threads(thread_id) ON DELETE CASCADE,
                idempotency_key text NOT NULL, command_id text NOT NULL,
                request_hash text NOT NULL, receipt jsonb NOT NULL,
                PRIMARY KEY(thread_id,idempotency_key), UNIQUE(thread_id,command_id))''')

    def read(self, thread_id, series_id):
        with self.threads._connect() as c:
            row = c.execute('SELECT state FROM capstone_product_series WHERE thread_id=%s AND series_id=%s',
                (thread_id, series_id)).fetchone()
            if row is None:
                raise KeyError('series unavailable')
            return row['state']

    def apply(self, thread_id, request, *, validate):
        fields = {'series_id', 'expected_revision', 'operation', 'product', 'command_id', 'idempotency_key'}
        if not isinstance(request, dict) or set(request) != fields:
            raise ValueError('invalid series command')
        for key in ('series_id', 'command_id', 'idempotency_key'):
            if not isinstance(request[key], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}', request[key]):
                raise ValueError('invalid command identity')
        digest = sha256(json.dumps(request, sort_keys=True, allow_nan=False,
            separators=(',', ':')).encode()).hexdigest()
        with self.threads._connect() as c:
            owner = c.execute('SELECT archived FROM capstone_threads WHERE thread_id=%s FOR UPDATE',
                (thread_id,)).fetchone()
            if owner is None:
                raise ThreadNotFound(thread_id)
            old = c.execute('SELECT request_hash,receipt FROM capstone_product_series_commands WHERE thread_id=%s AND idempotency_key=%s',
                (thread_id, request['idempotency_key'])).fetchone()
            if old:
                if old['request_hash'] != digest:
                    raise ValueError('idempotency conflict')
                return old['receipt']
            if owner['archived']:
                raise ValueError('Thread archived')
            if c.execute('SELECT 1 FROM capstone_product_series_commands WHERE thread_id=%s AND command_id=%s',
                (thread_id, request['command_id'])).fetchone():
                raise ValueError('command identity conflict')
            row = c.execute('SELECT state FROM capstone_product_series WHERE thread_id=%s AND series_id=%s',
                (thread_id, request['series_id'])).fetchone()
            state = transition(None if row is None else row['state'], thread_id=thread_id,
                **{key: request[key] for key in ('series_id', 'expected_revision', 'operation', 'product')})
            if request['product'] is not None:
                validate(c, request['product'])
            if request['operation'] == 'register':
                members = c.execute('SELECT series_id,state FROM capstone_product_series WHERE thread_id=%s', (thread_id,)).fetchall()
                if any(r['series_id'] != request['series_id'] and request['product'] in r['state']['members'] for r in members):
                    raise ValueError('product already belongs to another series')
            c.execute('''INSERT INTO capstone_product_series(thread_id,series_id,state) VALUES(%s,%s,%s)
                ON CONFLICT(thread_id,series_id) DO UPDATE SET state=EXCLUDED.state''',
                (thread_id, request['series_id'], Jsonb(state)))
            c.execute('INSERT INTO capstone_product_series_commands(thread_id,idempotency_key,command_id,request_hash,receipt) VALUES(%s,%s,%s,%s,%s)',
                (thread_id, request['idempotency_key'], request['command_id'], digest, Jsonb(state)))
            return state
