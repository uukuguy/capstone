"""Thread-scoped investigation register. Gateway credentials stay outside public records."""
from threading import RLock
from uuid import uuid4
from hashlib import sha256
import asyncio
import json
from psycopg.types.json import Jsonb


SCHEMA = """
CREATE TABLE IF NOT EXISTS capstone_debug_investigations (
    thread_id text NOT NULL REFERENCES capstone_threads(thread_id) ON DELETE CASCADE,
    workspace text NOT NULL,
    investigation_id text PRIMARY KEY,
    request_key text NOT NULL,
    objective text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(thread_id, workspace, request_key)
);
CREATE TABLE IF NOT EXISTS capstone_debug_calls (
    investigation_id text NOT NULL REFERENCES capstone_debug_investigations(investigation_id) ON DELETE CASCADE,
    operation_key text NOT NULL,
    call_digest text NOT NULL,
    client_call_id text NOT NULL UNIQUE,
    PRIMARY KEY(investigation_id, operation_key)
);
ALTER TABLE capstone_debug_investigations ADD COLUMN IF NOT EXISTS observation jsonb;
"""


class InvestigationRegister:
    def __init__(self, service):
        self.service = service
        self._memory = {}
        self._calls = {}
        self._lock = RLock()

    def _observe(self, thread_id, attempt_id):
        if attempt_id is None:
            return None
        through = self.service.snapshot(thread_id).last_event_seq
        after = 0
        reference = {'attempt_id': attempt_id, 'through': through, 'first_failure': None}
        while True:
            page = self.service.read_attempt_records(thread_id, attempt_id, after=after, limit=32)
            for event in page['events']:
                if event['event_seq'] > through:
                    return reference
                if event['visibility'] != 'public':
                    continue
                kind = event['event_type']
                failed = kind in {'tool_failed', 'validation_failed', 'attempt_interrupted', 'attempt_failed'}
                if failed or (kind == 'validation_observation' and event['payload'].get('status') == 'failed'):
                    reference['first_failure'] = {'seq': event['event_seq'], 'type': kind}
                    return reference
            if not page['has_more'] or page['next_after'] >= through:
                return reference
            if page['next_after'] <= after:
                raise ValueError('执行记录游标无效。')
            after = page['next_after']

    def start(self, workspace, thread_id, request_key, objective, attempt_id=None):
        self.service.require_workspace(thread_id, workspace)
        identity = 'inv_' + uuid4().hex
        observation = self._observe(thread_id, attempt_id)
        if hasattr(self.service, '_connect'):
            with self.service._connect() as connection:
                connection.execute('''INSERT INTO capstone_debug_investigations
                    (workspace,thread_id,investigation_id,request_key,objective,observation)
                    VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT(thread_id,workspace,request_key) DO NOTHING''',
                    (workspace, thread_id, identity, request_key, objective, Jsonb(observation) if observation else None))
                row = connection.execute('''SELECT investigation_id,objective,observation FROM capstone_debug_investigations
                    WHERE workspace=%s AND thread_id=%s AND request_key=%s''',
                    (workspace, thread_id, request_key)).fetchone()
        else:
            with self._lock:
                row = self._memory.setdefault((workspace, thread_id, request_key),
                    {'investigation_id': identity, 'objective': objective, 'observation': observation})
        if row['objective'] != objective or (row['observation'] or {}).get('attempt_id') != attempt_id:
            raise ValueError('同一请求标识已经用于其他调查目标。')
        return dict(row)

    def latest(self, workspace, thread_id):
        self.service.require_workspace(thread_id, workspace)
        if hasattr(self.service, '_connect'):
            with self.service._connect() as connection:
                return connection.execute('''SELECT investigation_id,objective,observation FROM capstone_debug_investigations
                    WHERE workspace=%s AND thread_id=%s ORDER BY created_at DESC,investigation_id DESC LIMIT 1''',
                    (workspace, thread_id)).fetchone()
        with self._lock:
            return next((dict(self._memory[key]) for key in reversed(self._memory)
                         if key[:2] == (workspace, thread_id)), None)

    def reserve_call(self, workspace, thread_id, investigation_id, operation_key, tool, arguments, binding_identity):
        """Return a committed call ID. Only its creator may dispatch; retries must read."""
        self.service.require_workspace(thread_id, workspace)
        digest = sha256(json.dumps([binding_identity,tool,arguments], sort_keys=True, allow_nan=False,
                                  separators=(',', ':')).encode()).hexdigest()
        call_id = 'call_' + uuid4().hex
        if hasattr(self.service, '_connect'):
            with self.service._connect() as connection:
                owner = connection.execute('''SELECT 1 FROM capstone_debug_investigations
                    WHERE investigation_id=%s AND workspace=%s AND thread_id=%s FOR KEY SHARE''',
                    (investigation_id, workspace, thread_id)).fetchone()
                if not owner:
                    raise KeyError('investigation_not_visible')
                connection.execute('''INSERT INTO capstone_debug_calls VALUES (%s,%s,%s,%s)
                    ON CONFLICT(investigation_id,operation_key) DO NOTHING''',
                    (investigation_id, operation_key, digest, call_id))
                row = connection.execute('''SELECT client_call_id,call_digest FROM capstone_debug_calls
                    WHERE investigation_id=%s AND operation_key=%s''',(investigation_id, operation_key)).fetchone()
        else:
            with self._lock:
                if not any(key[:2] == (workspace,thread_id) and item['investigation_id'] == investigation_id
                           for key,item in self._memory.items()):
                    raise KeyError('investigation_not_visible')
                row = self._calls.setdefault((investigation_id,operation_key),
                                            {'client_call_id':call_id,'call_digest':digest})
        if row['call_digest'] != digest:
            raise ValueError('调查步骤的绑定、工具或参数已改变。')
        return row['client_call_id'], row['client_call_id'] == call_id

    async def call_gateway(self, access, gateway, catalog, *, workspace, thread_id, investigation_id,
                           binding_handle, operation_key, tool, arguments, diagnostics):
        call_id, dispatch = await asyncio.to_thread(self.reserve_call, workspace, thread_id,
            investigation_id, operation_key, tool, arguments, binding_handle)
        scope = {'workspace_id': workspace, 'investigation_id': investigation_id, 'binding_handle': binding_handle}
        if not dispatch:
            return {'receipt': await access.invoke('read', {**scope, 'client_call_id': call_id})}
        return await access.call_registered(gateway, tool, arguments, catalog, scope=scope,
                                           diagnostics={**diagnostics, 'client_call_id': call_id})
