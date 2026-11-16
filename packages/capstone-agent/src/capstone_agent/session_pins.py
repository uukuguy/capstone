"""Application-owned workspace preferences, independent of browser origins."""
from threading import RLock

from fastapi import HTTPException, Request
from psycopg.types.json import Jsonb

SCHEMA = """
CREATE TABLE IF NOT EXISTS capstone_workspace_pins (
    workspace text PRIMARY KEY,
    revision bigint NOT NULL DEFAULT 0,
    states jsonb NOT NULL DEFAULT '{}'::jsonb
);
"""


def document(workspace, revision, states):
    return {'schema': 'capstone-session-pins/1', 'workspace': workspace,
            'revision': revision, 'pins': [key for key, value in states.items() if value]}


def apply(states, ids, pinned, imported):
    result = dict(states)
    for thread_id in ids:
        if not imported or thread_id not in result:
            result[thread_id] = pinned
    return result


class MemorySessionPins:
    def __init__(self):
        self.lock = RLock()
        self.values = {}

    def read(self, workspace):
        with self.lock:
            revision, states = self.values.get(workspace, (0, {}))
            return document(workspace, revision, states)

    def update(self, workspace, ids, *, pinned=True, imported=False):
        with self.lock:
            revision, states = self.values.get(workspace, (0, {}))
            updated = apply(states, ids, pinned, imported)
            revision += updated != states
            self.values[workspace] = revision, updated
            return document(workspace, revision, updated)


class PostgresSessionPins:
    def __init__(self, service):
        self.service = service

    def read(self, workspace):
        with self.service._connect() as connection:
            row = connection.execute('SELECT revision, states FROM capstone_workspace_pins WHERE workspace=%s', (workspace,)).fetchone()
            if row is None:
                return document(workspace, 0, {})
            existing = {item['thread_id'] for item in connection.execute(
                'SELECT thread_id FROM capstone_threads WHERE workspace_name=%s AND thread_id=ANY(%s)',
                (workspace, list(row['states']))).fetchall()}
            return document(workspace, row['revision'], {key: value for key, value in row['states'].items() if key in existing})

    def update(self, workspace, ids, *, pinned=True, imported=False):
        from .thread_service import ThreadNotFound
        with self.service._connect() as connection:
            connection.execute('INSERT INTO capstone_workspace_pins(workspace) VALUES (%s) ON CONFLICT DO NOTHING', (workspace,))
            row = connection.execute('SELECT revision,states FROM capstone_workspace_pins WHERE workspace=%s FOR UPDATE', (workspace,)).fetchone()
            existing = {item['thread_id'] for item in connection.execute(
                'SELECT thread_id FROM capstone_threads WHERE workspace_name=%s AND thread_id=ANY(%s) FOR KEY SHARE',
                (workspace, ids)).fetchall()}
            if not imported and existing != set(ids):
                raise ThreadNotFound('thread not found')
            states = apply(row['states'], [key for key in ids if key in existing], pinned, imported)
            revision = row['revision'] + (states != row['states'])
            connection.execute('UPDATE capstone_workspace_pins SET revision=%s,states=%s WHERE workspace=%s',
                               (revision, Jsonb(states), workspace))
            all_existing = {item['thread_id'] for item in connection.execute(
                'SELECT thread_id FROM capstone_threads WHERE workspace_name=%s AND thread_id=ANY(%s)',
                (workspace, list(states))).fetchall()}
            return document(workspace, revision, {key: value for key, value in states.items() if key in all_existing})


def register_session_pin_routes(app, *, service, authorize):
    from .thread_service import ThreadNotFound
    store = PostgresSessionPins(service) if hasattr(service, '_connect') else MemorySessionPins()
    # Kept on the service so cleanup and tests use the same preference owner.
    service.session_pins = store

    @app.delete('/api/v1/workspace/session-pins/cleanup/{thread_id}', status_code=204)
    def cleanup_thread(thread_id: str, request: Request):
        from .thread_service import ThreadExecutionError
        from fastapi import Response
        authorize(request)
        workspace = request.state.workspace_name
        try:
            service.require_workspace(thread_id, workspace)
            if isinstance(store, PostgresSessionPins):
                with service._connect() as connection:
                    connection.execute('INSERT INTO capstone_workspace_pins(workspace) VALUES (%s) ON CONFLICT DO NOTHING', (workspace,))
                    row = connection.execute('SELECT states FROM capstone_workspace_pins WHERE workspace=%s FOR UPDATE', (workspace,)).fetchone()
                    if row['states'].get(thread_id):
                        raise HTTPException(409, 'pinned thread is protected')
                    service.delete_thread(thread_id)
            else:
                with store.lock:
                    if thread_id in store.read(workspace)['pins']:
                        raise HTTPException(409, 'pinned thread is protected')
                    service.delete_thread(thread_id)
        except ThreadNotFound:
            raise HTTPException(404, 'thread not found') from None
        except ThreadExecutionError:
            raise HTTPException(409, 'thread has active work') from None
        return Response(status_code=204)

    @app.get('/api/v1/workspace/session-pins')
    def read_pins(request: Request):
        authorize(request)
        return store.read(request.state.workspace_name)

    @app.put('/api/v1/workspace/session-pins')
    async def update_pins(request: Request):
        authorize(request)
        try:
            body = await request.json()
        except ValueError:
            raise HTTPException(422, 'invalid pin operation') from None
        if not isinstance(body, dict) or set(body) not in ({'thread_id', 'pinned'}, {'import'}):
            raise HTTPException(422, 'invalid pin operation')
        imported = 'import' in body
        ids = body['import'] if imported else [body['thread_id']]
        pinned = True if imported else body['pinned']
        if (not isinstance(ids, list) or len(ids) > 1000 or not isinstance(pinned, bool)
                or any(not isinstance(key, str) or not key or len(key) > 256 for key in ids)):
            raise HTTPException(422, 'invalid pin operation')
        workspace = request.state.workspace_name
        if not isinstance(store, PostgresSessionPins):
            valid = []
            for key in ids:
                try:
                    service.require_workspace(key, workspace)
                    valid.append(key)
                except ThreadNotFound:
                    if not imported:
                        raise HTTPException(404, 'thread not found') from None
            ids = valid
        try:
            from starlette.concurrency import run_in_threadpool
            return await run_in_threadpool(store.update, workspace, ids, pinned=pinned, imported=imported)
        except ThreadNotFound:
            raise HTTPException(404, 'thread not found') from None
