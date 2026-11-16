"""Agent-owned operation registry, separate from Control state."""
from copy import deepcopy
from threading import RLock


class MemoryDelegations:
    def __init__(self):
        self.lock, self.values = RLock(), {}

    def transact(self, workspace, operation_id, change):
        with self.lock:
            key = workspace, operation_id
            updated, result = change(deepcopy(self.values.get(key)))
            self.values[key] = deepcopy(updated)
            return deepcopy(result)

    def read(self, workspace, operation_id):
        with self.lock:
            return deepcopy(self.values[(workspace, operation_id)])


class PostgresDelegations:
    def __init__(self, dsn):
        self.dsn = dsn

    def connect(self):
        import psycopg
        from psycopg.rows import dict_row
        return psycopg.connect(self.dsn, row_factory=dict_row)

    def initialize(self):
        with self.connect() as connection:
            connection.execute('''CREATE TABLE IF NOT EXISTS capstone_agent_delegations (
                workspace text NOT NULL, operation_id text NOT NULL,
                document jsonb NOT NULL, PRIMARY KEY(workspace,operation_id))''')

    def transact(self, workspace, operation_id, change):
        from psycopg.types.json import Jsonb
        with self.connect() as connection:
            connection.execute('''INSERT INTO capstone_agent_delegations VALUES (%s,%s,'{}'::jsonb)
                ON CONFLICT DO NOTHING''', (workspace, operation_id))
            row = connection.execute('''SELECT document FROM capstone_agent_delegations
                WHERE workspace=%s AND operation_id=%s FOR UPDATE''', (workspace, operation_id)).fetchone()
            updated, result = change(row['document'] or None)
            connection.execute('''UPDATE capstone_agent_delegations SET document=%s
                WHERE workspace=%s AND operation_id=%s''', (Jsonb(updated), workspace, operation_id))
            return result

    def read(self, workspace, operation_id):
        with self.connect() as connection:
            row = connection.execute('''SELECT document FROM capstone_agent_delegations
                WHERE workspace=%s AND operation_id=%s''', (workspace, operation_id)).fetchone()
            if row is None:
                raise KeyError(operation_id)
            return row['document']

    def delete(self, workspace, operation_id):
        with self.connect() as connection:
            connection.execute('DELETE FROM capstone_agent_delegations WHERE workspace=%s AND operation_id=%s',
                               (workspace, operation_id))
