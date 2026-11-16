"""Atomic aggregate storage. Callbacks never perform external execution."""
from copy import deepcopy
from threading import RLock


class MemoryStore:
    def __init__(self):
        self._lock = RLock()
        self._values = {}

    def transact(self, workspace, goal_id, change):
        with self._lock:
            key = (workspace, goal_id)
            current = deepcopy(self._values.get(key))
            updated, result = change(current)
            self._values[key] = deepcopy(updated)
            return deepcopy(result)

    def read(self, workspace, goal_id):
        with self._lock:
            return deepcopy(self._values[(workspace, goal_id)])

    def list(self, workspace=None, limit=128, *, after=None, active_only=False):
        with self._lock:
            return deepcopy([value for (owner, goal_id), value in sorted(self._values.items(),
                key=lambda item: (item[0][1], item[0][0]))
                if (workspace is None or workspace == owner)
                and (after is None or goal_id > after)
                and (not active_only or value['state'] in ACTIVE_STATES)][:limit])


class PostgresStore:
    """Control owns its table and connection, never Agent ledger rows."""
    def __init__(self, dsn):
        self.dsn = dsn

    def connect(self):
        import psycopg
        from psycopg.rows import dict_row
        return psycopg.connect(self.dsn, row_factory=dict_row)

    def initialize(self):
        with self.connect() as connection:
            connection.execute('''CREATE TABLE IF NOT EXISTS capstone_control_goals (
                workspace text NOT NULL, goal_id text NOT NULL,
                document jsonb NOT NULL, PRIMARY KEY(workspace, goal_id))''')

    def transact(self, workspace, goal_id, change):
        from psycopg.types.json import Jsonb
        with self.connect() as connection:
            connection.execute('''INSERT INTO capstone_control_goals
                (workspace,goal_id,document) VALUES (%s,%s,'{}'::jsonb)
                ON CONFLICT DO NOTHING''', (workspace, goal_id))
            row = connection.execute('''SELECT document FROM capstone_control_goals
                WHERE workspace=%s AND goal_id=%s FOR UPDATE''', (workspace, goal_id)).fetchone()
            updated, result = change(row['document'] or None)
            connection.execute('''UPDATE capstone_control_goals SET document=%s
                WHERE workspace=%s AND goal_id=%s''', (Jsonb(updated), workspace, goal_id))
            return deepcopy(result)

    def read(self, workspace, goal_id):
        with self.connect() as connection:
            row = connection.execute('''SELECT document FROM capstone_control_goals
                WHERE workspace=%s AND goal_id=%s''', (workspace, goal_id)).fetchone()
            if row is None:
                raise KeyError(goal_id)
            return row['document']

    def list(self, workspace=None, limit=128, *, after=None, active_only=False):
        with self.connect() as connection:
            rows = connection.execute('''SELECT document FROM capstone_control_goals
                WHERE (%s::text IS NULL OR workspace=%s)
                AND (%s::text IS NULL OR goal_id>%s)
                AND (NOT %s OR document->>'state'=ANY(%s))
                ORDER BY goal_id,workspace LIMIT %s''',
                (workspace, workspace, after, after, active_only, sorted(ACTIVE_STATES), limit)).fetchall()
            return [row['document'] for row in rows]


ACTIVE_STATES = {'ready', 'running', 'waiting', 'pausing', 'cancelling', 'revising'}
