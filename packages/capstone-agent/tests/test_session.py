from __future__ import annotations

import sys
from pathlib import Path

import pytest

from capstone_agent.session import WorkerRegistry, WorkerSession, WorkerSpec


def _worker(tmp_path: Path) -> tuple[str, ...]:
    script = tmp_path / "worker.py"
    script.write_text('''
import json
import sys
import time

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
        send("ready", {"run_id": "run-fixture"})
    elif frame["kind"] == "turn":
        instruction = frame["payload"]["instruction"]
        turns.append(instruction)
        time.sleep(0.15)
        send("answer_committed", {"ordinal": len(turns), "turn_id": f"run-fixture-t{len(turns):03d}",
             "answer_output": instruction.upper(), "answer_ref": f"answer:{len(turns)}",
             "result_refs": [], "evidence_refs": []})
    elif frame["kind"] == "close":
        send("completed", {"run_id": "run-fixture", "result": {"turns": turns}})
    elif frame["kind"] == "evidence":
        ref = frame["payload"]["ref"]
        send("evidence_result", {"ref": ref,
             "value": {"ref": ref} if ref == "evidence:current" else None})
''', encoding="utf-8")
    return (sys.executable, "-u", str(script))


def test_session_waits_for_each_committed_answer_in_one_worker(tmp_path: Path) -> None:
    registry = WorkerRegistry((WorkerSpec("fixture-app", _worker(tmp_path)),))
    with pytest.raises(ValueError, match="registered"):
        registry.resolve("missing")

    with WorkerSession(registry.resolve("fixture-app"), mode="scripted-demo") as session:
        assert session.run_id == "run-fixture"
        assert session.next_event(after=0).kind == "ready"
        first = session.submit_and_wait("first")
        assert first.payload["answer_output"] == "FIRST"
        second = session.submit_and_wait("second")
        assert second.payload["answer_output"] == "SECOND"
        completed = session.close()
        assert completed.payload["result"] == {"turns": ["first", "second"]}
        assert session.read_evidence("evidence:current") == {"ref": "evidence:current"}
        assert session.read_evidence("evidence:foreign") is None
        assert [event.sequence for event in session.events] == [1, 2, 3, 4, 5, 6]


def test_session_rejects_second_turn_while_first_is_active(tmp_path: Path) -> None:
    registry = WorkerRegistry((WorkerSpec("fixture-app", _worker(tmp_path)),))
    with WorkerSession(registry.resolve("fixture-app"), mode="scripted-demo") as session:
        session.submit("first")
        with pytest.raises(RuntimeError, match="active"):
            session.submit("second")
        assert session.wait_for("answer_committed").payload["answer_output"] == "FIRST"
        session.request_close()
        assert session.wait_for("completed").kind == "completed"
