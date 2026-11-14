"""PostgreSQL series state and retry receipts under the owning Thread lock."""
from hashlib import sha256
import json
import re
from datetime import datetime, timezone

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
            c.execute('''CREATE TABLE IF NOT EXISTS capstone_product_series_members (
                thread_id text NOT NULL REFERENCES capstone_threads(thread_id) ON DELETE CASCADE,
                product_key text NOT NULL, series_id text NOT NULL,
                PRIMARY KEY(thread_id,product_key))''')
            c.execute('''CREATE TABLE IF NOT EXISTS capstone_product_series_events (
                thread_id text NOT NULL REFERENCES capstone_threads(thread_id) ON DELETE CASCADE,
                series_id text NOT NULL, revision bigint NOT NULL, event jsonb NOT NULL,
                PRIMARY KEY(thread_id,series_id,revision))''')

    def history(self, thread_id, series_id, *, limit=20, before=None):
        if type(limit) is not int or not 1 <= limit <= 100 or (before is not None and (type(before) is not int or before < 1)):
            raise ValueError('invalid history page')
        with self.threads._connect() as c:
            rows = c.execute('''SELECT event FROM capstone_product_series_events
                WHERE thread_id=%s AND series_id=%s AND (%s::bigint IS NULL OR revision<=%s)
                ORDER BY revision DESC LIMIT %s''', (thread_id, series_id, before, before, limit+1)).fetchall()
            events = [r['event'] for r in rows[:limit]]
            return {'events': events, 'next_revision': events[-1]['revision']-1 if len(rows)>limit else None}

    def read(self, thread_id, series_id):
        with self.threads._connect() as c:
            row = c.execute('SELECT state FROM capstone_product_series WHERE thread_id=%s AND series_id=%s',
                (thread_id, series_id)).fetchone()
            if row is None:
                raise KeyError('series unavailable')
            return row['state']

    def apply(self, thread_id, request, *, validate, actor):
        if not isinstance(actor, str) or not actor or len(actor) > 255:
            raise ValueError('authenticated actor required')
        fields = {'series_id', 'expected_revision', 'operation', 'product', 'command_id', 'idempotency_key'}
        if not isinstance(request, dict) or set(request) != fields:
            raise ValueError('invalid series command')
        for key in ('series_id', 'command_id', 'idempotency_key'):
            if not isinstance(request[key], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}', request[key]):
                raise ValueError('invalid command identity')
        digest = sha256(json.dumps({'request': request, 'actor': actor}, sort_keys=True, allow_nan=False,
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
                product_key = sha256(json.dumps(request['product'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
                member = c.execute('SELECT series_id FROM capstone_product_series_members WHERE thread_id=%s AND product_key=%s', (thread_id, product_key)).fetchone()
                if member and member['series_id'] != request['series_id']:
                    raise ValueError('product already belongs to another series')
                c.execute('INSERT INTO capstone_product_series_members(thread_id,product_key,series_id) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING', (thread_id, product_key, request['series_id']))
            c.execute('''INSERT INTO capstone_product_series(thread_id,series_id,state) VALUES(%s,%s,%s)
                ON CONFLICT(thread_id,series_id) DO UPDATE SET state=EXCLUDED.state''',
                (thread_id, request['series_id'], Jsonb(state)))
            event = {'actor': actor, 'created_at': datetime.now(timezone.utc).isoformat(),
                'operation': request['operation'], 'product': request['product'],
                'previous_revision': request['expected_revision'], 'revision': state['revision'],
                'adopted_ref': state['adopted_ref']}
            c.execute('INSERT INTO capstone_product_series_events(thread_id,series_id,revision,event) VALUES(%s,%s,%s,%s)',
                (thread_id, request['series_id'], state['revision'], Jsonb(event)))
            c.execute('INSERT INTO capstone_product_series_commands(thread_id,idempotency_key,command_id,request_hash,receipt) VALUES(%s,%s,%s,%s,%s)',
                (thread_id, request['idempotency_key'], request['command_id'], digest, Jsonb(state)))
            return state
