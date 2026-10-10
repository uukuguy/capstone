"""Private SQLite queue; atomic leases and conservative model cost receipts."""
import datetime
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.path.parent, 0o700)
        self.db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        os.chmod(self.path, 0o600)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
          PRAGMA journal_mode=DELETE;
          CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY, issue INTEGER, input_hash TEXT, policy_sha TEXT,
            source_sha TEXT, state TEXT DEFAULT 'triage', lease_until REAL DEFAULT 0,
            owner TEXT, attempts INTEGER DEFAULT 0, created REAL, payload TEXT DEFAULT '{}',
            UNIQUE(issue,input_hash,policy_sha));
          CREATE TABLE IF NOT EXISTS actions (
            action_key TEXT PRIMARY KEY, task_id TEXT, state TEXT, receipt TEXT DEFAULT '{}');
          CREATE TABLE IF NOT EXISTS costs (
            request_id TEXT PRIMARY KEY, task_id TEXT, day TEXT, reserved REAL, receipt TEXT DEFAULT '{}');
          CREATE TABLE IF NOT EXISTS commands (event_id INTEGER PRIMARY KEY);
        """)
        if "tokens" not in {r[1] for r in self.db.execute("PRAGMA table_info(costs)")}:
            self.db.execute("ALTER TABLE costs ADD COLUMN tokens INTEGER DEFAULT 0")

    def close(self):
        self.db.close()

    def enqueue(self, issue, input_hash, policy_sha, source_sha):
        task = uuid.uuid4().hex
        self.db.execute("INSERT OR IGNORE INTO tasks(task_id,issue,input_hash,policy_sha,source_sha,created) VALUES(?,?,?,?,?,?)", (task, issue, input_hash, policy_sha, source_sha, time.time()))
        return self.db.execute("SELECT task_id FROM tasks WHERE issue=? AND input_hash=? AND policy_sha=?", (issue, input_hash, policy_sha)).fetchone()[0]

    def get(self, task):
        row = self.db.execute("SELECT * FROM tasks WHERE task_id=?", (task,)).fetchone()
        if not row:
            raise ValueError("Task does not exist")
        result = dict(row)
        result["payload"] = json.loads(result["payload"])
        return result

    def list(self, issue=None):
        rows = self.db.execute("SELECT task_id FROM tasks " + ("WHERE issue=? " if issue else "") + "ORDER BY created DESC", (issue,) if issue else ())
        return [self.get(row[0]) for row in rows]

    def update(self, task, **values):
        allowed = {"state", "payload", "lease_until", "owner", "attempts"}
        if not values or set(values) - allowed:
            raise ValueError("Invalid task update")
        if "payload" in values:
            values["payload"] = json.dumps(values["payload"], ensure_ascii=False)
        self.db.execute("UPDATE tasks SET " + ",".join(k + "=?" for k in values) + " WHERE task_id=?", (*values.values(), task))

    def claim(self, task, owner, now=None, seconds=3900):
        now = time.time() if now is None else now
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.get(task)
            active = self.db.execute("SELECT 1 FROM tasks WHERE lease_until>?", (now,)).fetchone()
            if active or row["state"] not in {"ready", "working"}:
                self.db.execute("ROLLBACK")
                return False
            self.update(task, state="working", owner=owner, lease_until=now + seconds)
            self.db.execute("COMMIT")
            return True
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def pause(self, issue):
        self.db.execute("UPDATE tasks SET state='paused' WHERE issue=? AND state NOT IN ('review','release-pending','closed')", (issue,))

    def action(self, key):
        row = self.db.execute("SELECT * FROM actions WHERE action_key=?", (key,)).fetchone()
        return dict(row) if row else None

    def record_action(self, key, task, state, receipt=None):
        self.db.execute("INSERT INTO actions VALUES(?,?,?,?) ON CONFLICT(action_key) DO UPDATE SET state=excluded.state,receipt=excluded.receipt", (key, task, state, json.dumps(receipt or {})))

    def reserve(self, task, request_id, amount, task_limit, day_limit, tokens=0, task_token_limit=None, day_token_limit=None):
        if amount <= 0:
            return False
        day = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            task_total = self.cost(task)
            day_total = self.db.execute("SELECT coalesce(sum(reserved),0) FROM costs WHERE day=?", (day,)).fetchone()[0]
            task_tokens = self.db.execute("SELECT coalesce(sum(tokens),0) FROM costs WHERE task_id=?", (task,)).fetchone()[0]
            day_tokens = self.db.execute("SELECT coalesce(sum(tokens),0) FROM costs WHERE day=?", (day,)).fetchone()[0]
            exceeds_tokens = (task_token_limit is not None and task_tokens + tokens > task_token_limit) or (day_token_limit is not None and day_tokens + tokens > day_token_limit)
            if self.db.execute("SELECT 1 FROM costs WHERE request_id=?", (request_id,)).fetchone() or task_total + amount > task_limit or day_total + amount > day_limit or exceeds_tokens:
                self.db.execute("ROLLBACK")
                return False
            self.db.execute("INSERT INTO costs VALUES(?,?,?,?,?,?)", (request_id, task, day, amount, "{}", tokens))
            self.db.execute("COMMIT")
            return True
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def cost(self, task):
        return self.db.execute("SELECT coalesce(sum(reserved),0) FROM costs WHERE task_id=?", (task,)).fetchone()[0]

    def cost_receipt(self, request_id, receipt):
        self.db.execute("UPDATE costs SET receipt=? WHERE request_id=?", (json.dumps(receipt), request_id))

    def seen_command(self, event_id):
        return self.db.execute("SELECT 1 FROM commands WHERE event_id=?", (event_id,)).fetchone() is not None

    def finish_command(self, event_id):
        self.db.execute("INSERT OR IGNORE INTO commands VALUES(?)", (event_id,))
