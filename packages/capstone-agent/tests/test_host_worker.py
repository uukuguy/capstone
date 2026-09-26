from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

import psycopg
import pytest

from capstone_agent.host_worker import run_claimed_session
from capstone_agent.ledger import Ledger
from capstone_agent.session import WorkerRegistry, WorkerSpec


@pytest.fixture
def ledger() -> Ledger:
    dsn = os.environ.get("CAPSTONE_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("CAPSTONE_TEST_DATABASE_URL is required")
    store = Ledger(dsn)
    store.initialize()
    with psycopg.connect(dsn) as connection:
        connection.execute("TRUNCATE session_events, session_commands, sessions CASCADE")
    return store


def _worker(tmp_path: Path) -> tuple[str, ...]:
    script = tmp_path / "host_worker.py"
    script.write_text('''
import json
import sys
session = None
sequence = 0
turns = []
def send(kind, payload):
    global sequence
    sequence += 1
    print(json.dumps({"schema": "capstone-worker/1.0", "session_id": session,
                      "sequence": sequence, "kind": kind, "payload": payload}), flush=True)
for line in sys.stdin:
    frame = json.loads(line)
    session = frame["session_id"]
    if frame["kind"] == "open":
        send("ready", {"run_id": "run-worker-test"})
    elif frame["kind"] == "turn":
        turns.append(frame["payload"]["instruction"])
        send("answer_committed", {"ordinal": len(turns), "turn_id": f"turn-{len(turns)}",
             "answer_output": turns[-1].upper(), "answer_ref": f"answer:{len(turns)}",
             "result_refs": [], "evidence_refs": []})
    elif frame["kind"] == "close":
        send("completed", {"run_id": "run-worker-test", "result": {"turns": turns}})
''', encoding="utf-8")
    return (sys.executable, "-u", str(script))


def _wait(ledger: Ledger, session_id: str, state: str) -> None:
    for _ in range(100):
        if ledger.get_session(session_id).state == state:
            return
        time.sleep(0.02)
    pytest.fail(f"session did not reach {state}")


def test_worker_runs_sequential_commands_for_cross_connection_reader(
    ledger: Ledger, tmp_path: Path,
) -> None:
    registry = WorkerRegistry((WorkerSpec("fixture-app", _worker(tmp_path)),))
    record = ledger.create_session("fixture-app", "scripted-demo", None, None, None)
    claim = ledger.claim_pending("worker-test", 30)
    assert claim is not None
    thread = threading.Thread(target=run_claimed_session, args=(ledger, registry, claim),
                              kwargs={"poll_seconds": 0.01}, daemon=True)
    thread.start()
    _wait(ledger, record.session_id, "ready")
    ledger.accept_turn(record.session_id, "first", "key-1")
    _wait(ledger, record.session_id, "ready")
    ledger.accept_turn(record.session_id, "second", "key-2")
    _wait(ledger, record.session_id, "ready")
    ledger.accept_close(record.session_id, "key-close")
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert ledger.get_session(record.session_id).state == "completed"
    events = Ledger(ledger.dsn).events_after(record.session_id, 0)
    assert [event.kind for event in events] == [
        "ready", "answer_committed", "answer_committed", "completed",
    ]
    assert events[-1].payload["result"] == {"turns": ["first", "second"]}
