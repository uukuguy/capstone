from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from capstone_agent.session import WorkerRegistry, WorkerSession, WorkerSpec, _worker_environment


def test_scripted_worker_environment_excludes_provider_secrets() -> None:
    source = {"PATH": "/bin", "CAPSTONE_PYPSA_MODEL_LIBRARY_DIR": "/models",
              "OPENAI_API_KEY": "secret", "UV_CACHE_DIR": "/cache"}
    selected = _worker_environment(source, "scripted-demo")
    assert selected == {"PATH": "/bin", "CAPSTONE_PYPSA_MODEL_LIBRARY_DIR": "/models",
                        "UV_CACHE_DIR": "/cache"}
    assert _worker_environment(source, "provider") == source


def test_provider_worker_environment_drops_parent_virtual_environment() -> None:
    source = {"PATH": "/bin", "VIRTUAL_ENV": "/host/.venv",
              "OPENAI_API_KEY": "secret"}
    assert _worker_environment(source, "provider") == {
        "PATH": "/bin", "OPENAI_API_KEY": "secret",
    }


def test_failed_worker_start_terminates_its_process(tmp_path: Path) -> None:
    script = tmp_path / "unready.py"
    script.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
    session = WorkerSession(WorkerSpec("fixture-app", (sys.executable, str(script))),
                            mode="scripted-demo", timeout=0.2)
    with pytest.raises(TimeoutError):
        session.__enter__()
    assert session._process is not None
    assert session._process.poll() is not None


def test_worker_exit_during_close_is_reported_as_failure(tmp_path: Path) -> None:
    script = tmp_path / "exit_on_close.py"
    script.write_text('''
import json
import sys
for line in sys.stdin:
    frame = json.loads(line)
    if frame["kind"] == "open":
        print(json.dumps({"schema": "capstone-worker/1.0", "session_id": frame["session_id"],
                          "sequence": 1, "kind": "ready", "payload": {"run_id": "run-exit"}}), flush=True)
    else:
        break
''', encoding="utf-8")
    session = WorkerSession(WorkerSpec("fixture-app", (sys.executable, str(script))),
                            mode="scripted-demo", timeout=0.3)
    with session:
        with pytest.raises(RuntimeError, match="disconnected"):
            session.close()


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
        time.sleep(0.05)
        send("evidence_result", {"ref": ref,
             "value": {"ref": ref} if ref == "evidence:current" else None})
''', encoding="utf-8")
    return (sys.executable, "-u", str(script))


def test_session_waits_for_each_committed_answer_in_one_worker(tmp_path: Path) -> None:
    registry = WorkerRegistry((WorkerSpec("fixture-app", _worker(tmp_path)),))
    with pytest.raises(ValueError, match="registered"):
        registry.resolve("missing")

    with WorkerSession(registry.resolve("fixture-app"), mode="scripted-demo") as session:
        assert session.timeout >= 120
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


def test_concurrent_evidence_reads_keep_request_identity(tmp_path: Path) -> None:
    registry = WorkerRegistry((WorkerSpec("fixture-app", _worker(tmp_path)),))
    with WorkerSession(registry.resolve("fixture-app"), mode="scripted-demo") as session:
        session.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            current = pool.submit(session.read_evidence, "evidence:current")
            foreign = pool.submit(session.read_evidence, "evidence:foreign")
            assert current.result() == {"ref": "evidence:current"}
        assert foreign.result() is None


def test_host_session_persists_before_publishing_events(tmp_path: Path) -> None:
    persisted = []
    spec = WorkerSpec("fixture-app", _worker(tmp_path))
    with WorkerSession(spec, mode="scripted-demo", session_id="session-host-test",
                       persist_event=persisted.append) as session:
        assert session.session_id == "session-host-test"
        assert persisted[0] == session.events[0]
        session.submit_and_wait("hello")
        assert [frame.kind for frame in persisted[:2]] == ["ready", "answer_committed"]


def test_host_session_fails_if_event_persistence_fails(tmp_path: Path) -> None:
    def reject(_frame: object) -> None:
        raise OSError("ledger unavailable")

    session = WorkerSession(WorkerSpec("fixture-app", _worker(tmp_path)),
                            mode="scripted-demo", timeout=0.3,
                            persist_event=reject)
    with pytest.raises(RuntimeError, match="persistence"):
        session.__enter__()
    assert session.events == ()
