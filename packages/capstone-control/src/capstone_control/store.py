"""Atomic aggregate storage. Callbacks never perform external execution."""
from copy import deepcopy
from threading import RLock

from .events import build_event, event_page, page_bounds


class MemoryStore:
    def __init__(self):
        self._lock = RLock()
        self._values = {}
        self._events = {}

    def transact(self, workspace, goal_id, change, *, event=None):
        with self._lock:
            key = (workspace, goal_id)
            current = deepcopy(self._values.get(key))
            updated, result = change(deepcopy(current))
            recorded = build_event(current, updated, event)
            saved, receipt = deepcopy(updated), deepcopy(result)
            records = self._events.get(key, [])
            if recorded is not None:
                records = [*records, recorded]
            self._values[key] = saved
            self._events[key] = records
            return receipt

    def read_events(self, workspace, goal_id, *, after=0, limit=50, through=None):
        with self._lock:
            through = page_bounds(self._values[(workspace, goal_id)], after, limit, through)
            records = self._events.get((workspace, goal_id), [])
            rows = [e for e in records if after < e['sequence'] <= through][:limit + 1]
            first = records[0] if records and records[0]['sequence'] <= through else None
            last = next((e for e in reversed(records) if e['sequence'] <= through), None)
            return deepcopy(event_page(workspace, goal_id, rows, first, last, after, limit, through))

    def read(self, workspace, goal_id):
        with self._lock:
            return deepcopy(self._values[(workspace, goal_id)])

    def active_missions_for_thread(self, workspace, thread_id):
        with self._lock:
            return sorted(goal_id for (owner, goal_id), goal in self._values.items()
                if owner == workspace and goal.get('_mission', {}).get('origin', {}).get('thread_id') == thread_id
                and goal['state'] not in {'accepted', 'cancelled'})[:2]

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
            connection.execute("SELECT pg_advisory_xact_lock(hashtext('capstone-control-schema/1'))")
            connection.execute('''CREATE TABLE IF NOT EXISTS capstone_control_goals (
                workspace text NOT NULL, goal_id text NOT NULL,
                document jsonb NOT NULL, PRIMARY KEY(workspace, goal_id))''')
            connection.execute('''CREATE TABLE IF NOT EXISTS capstone_control_events (
                workspace text NOT NULL, goal_id text NOT NULL, sequence bigint NOT NULL,
                document jsonb NOT NULL, PRIMARY KEY(workspace, goal_id, sequence),
                FOREIGN KEY(workspace, goal_id) REFERENCES capstone_control_goals(workspace, goal_id)
                ON DELETE CASCADE)''')

    def transact(self, workspace, goal_id, change, *, event=None):
        from psycopg.types.json import Jsonb
        with self.connect() as connection:
            connection.execute('''INSERT INTO capstone_control_goals
                (workspace,goal_id,document) VALUES (%s,%s,'{}'::jsonb)
                ON CONFLICT DO NOTHING''', (workspace, goal_id))
            row = connection.execute('''SELECT document FROM capstone_control_goals
                WHERE workspace=%s AND goal_id=%s FOR UPDATE''', (workspace, goal_id)).fetchone()
            current = row['document'] or None
            updated, result = change(deepcopy(current))
            recorded = build_event(current, updated, event)
            if recorded is not None:
                connection.execute('''INSERT INTO capstone_control_events
                    (workspace,goal_id,sequence,document) VALUES (%s,%s,%s,%s)''',
                    (workspace, goal_id, recorded['sequence'], Jsonb(recorded)))
            connection.execute('''UPDATE capstone_control_goals SET document=%s
                WHERE workspace=%s AND goal_id=%s''', (Jsonb(updated), workspace, goal_id))
            return deepcopy(result)

    def read_events(self, workspace, goal_id, *, after=0, limit=50, through=None):
        with self.connect() as connection:
            row = connection.execute('''SELECT document FROM capstone_control_goals
                WHERE workspace=%s AND goal_id=%s''', (workspace, goal_id)).fetchone()
            if row is None:
                raise KeyError(goal_id)
            through = page_bounds(row['document'], after, limit, through)
            rows = connection.execute('''SELECT document FROM capstone_control_events
                WHERE workspace=%s AND goal_id=%s AND sequence>%s AND sequence<=%s
                ORDER BY sequence LIMIT %s''', (workspace, goal_id, after, through, limit + 1)).fetchall()
            first = connection.execute('''SELECT document FROM capstone_control_events
                WHERE workspace=%s AND goal_id=%s AND sequence<=%s
                ORDER BY sequence LIMIT 1''', (workspace, goal_id, through)).fetchone()
            last = connection.execute('''SELECT document FROM capstone_control_events
                WHERE workspace=%s AND goal_id=%s AND sequence<=%s
                ORDER BY sequence DESC LIMIT 1''', (workspace, goal_id, through)).fetchone()
            return event_page(workspace, goal_id, [r['document'] for r in rows],
                              first['document'] if first else None,
                              last['document'] if last else None, after, limit, through)

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

    def active_missions_for_thread(self, workspace, thread_id):
        with self.connect() as connection:
            rows = connection.execute("""SELECT goal_id FROM capstone_control_goals
                WHERE workspace=%s AND document#>>'{_mission,origin,thread_id}'=%s
                AND document->>'state' NOT IN ('accepted','cancelled')
                ORDER BY goal_id LIMIT 2""", (workspace, thread_id)).fetchall()
            return [row['goal_id'] for row in rows]


ACTIVE_STATES = {'planning', 'ready', 'running', 'waiting', 'pausing', 'cancelling', 'revising'}
