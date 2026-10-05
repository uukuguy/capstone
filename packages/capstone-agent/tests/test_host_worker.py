from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import psycopg
import pytest

from capstone_agent.artifacts import ArtifactService, MemoryObjectStore
from capstone_agent.host_worker import run_claimed_session, serve_forever
from capstone_agent.ledger import Ledger
from capstone_agent.session import WorkerRegistry, WorkerSpec


@pytest.mark.parametrize("blocked_phase", ["startup", "evidence"])
def test_lease_renews_while_session_work_is_blocked(
    monkeypatch: pytest.MonkeyPatch, blocked_phase: str,
) -> None:
    blocked = threading.Event()
    release = threading.Event()
    renewed_while_blocked = threading.Event()
    done = threading.Event()
    renewals: list[float] = []

    class Store:
        def renew_lease(self, *_args):
            renewals.append(time.monotonic())
            if blocked.is_set() and not release.is_set():
                renewed_while_blocked.set()
            return True

        def get_session(self, *_args):
            return SimpleNamespace(state="completed" if done.is_set() else "ready")

        def get_artifact(self, *_args):
            return None

        def mark_failed(self, *_args):
            pytest.fail("healthy blocked session must not fail")

    class Session:
        def __init__(self, *_args, **_kwargs):
            self.events = [SimpleNamespace(sequence=1, kind="completed", payload={})]

        def __enter__(self):
            if blocked_phase == "startup":
                blocked.set()
                release.wait(3)
                done.set()
            else:
                self.events = [
                    SimpleNamespace(sequence=1, kind="answer_committed",
                        payload={"evidence_refs": ["evidence:current"]}),
                    SimpleNamespace(sequence=2, kind="completed", payload={}),
                ]
            return self

        def __exit__(self, *_args):
            pass

        def read_evidence(self, _ref):
            blocked.set()
            release.wait(3)
            done.set()
            return {"ref": "evidence:current"}

    class Artifacts:
        def save_evidence(self, *_args):
            pass

    monkeypatch.setattr("capstone_agent.host_worker.WorkerSession", Session)
    claim = SimpleNamespace(lease_token="fixture-lease", session_id="session-lease-test",
        application_id="fixture-app", mode="scripted-demo", case_id=None, provider=None, model=None)
    registry = WorkerRegistry((WorkerSpec("fixture-app", (sys.executable,)),))
    thread = threading.Thread(target=run_claimed_session, args=(Store(), registry, claim),
        kwargs={"lease_seconds": 1, "poll_seconds": 0.01, "artifacts": Artifacts()}, daemon=True)
    thread.start()
    try:
        assert blocked.wait(1), "session did not enter the blocked operation"
        renewed = renewed_while_blocked.wait(1.5)
    finally:
        release.set()
        thread.join(timeout=2)
    assert not thread.is_alive()
    assert renewed, "startup or evidence RPC must not suspend lease renewal"
    renewal_count = len(renewals)
    time.sleep(0.4)
    assert len(renewals) == renewal_count, "renewal must stop when the session ends"


@pytest.mark.parametrize("late_frame", [False, True])
def test_lost_lease_during_startup_blocks_fresh_commands(
    monkeypatch: pytest.MonkeyPatch, late_frame: bool,
) -> None:
    blocked = threading.Event()
    release = threading.Event()
    rejected = threading.Event()
    submitted: list[str] = []
    stored_reports: list[str] = []
    persisted: list[object] = []
    state = {"value": "ready"}

    class Store:
        def renew_lease(self, *_args):
            blocked.wait(1)
            rejected.set()
            return False

        def get_session(self, *_args):
            return SimpleNamespace(state=state["value"])

        def next_command(self, *_args):
            return SimpleNamespace(kind="turn", instruction="must stay fenced")

        def mark_failed(self, *_args):
            state["value"] = "failed"

        def append_event(self, *_args):
            persisted.append(_args[-1])

    class Session:
        events = ()
        busy = False
        failure_code = None

        def __init__(self, *_args, **_kwargs):
            self.persist_event = _kwargs["persist_event"]

        def __enter__(self):
            blocked.set()
            release.wait(3)
            if late_frame:
                self.persist_event(SimpleNamespace(kind="completed", payload={"report_path": __file__}))
            return self

        def __exit__(self, *_args):
            pass

        def abort(self):
            state["value"] = "interrupted"

        def submit(self, instruction):
            submitted.append(instruction)
            state["value"] = "failed"

    class Artifacts:
        def save_report(self, session_id, _path):
            stored_reports.append(session_id)

    monkeypatch.setattr("capstone_agent.host_worker.WorkerSession", Session)
    claim = SimpleNamespace(lease_token="fixture-lease", session_id="session-lease-test",
        application_id="fixture-app", mode="scripted-demo", case_id=None, provider=None, model=None)
    registry = WorkerRegistry((WorkerSpec("fixture-app", (sys.executable,)),))
    thread = threading.Thread(target=run_claimed_session, args=(Store(), registry, claim),
        kwargs={"lease_seconds": 1, "poll_seconds": 0.01, "artifacts": Artifacts()}, daemon=True)
    thread.start()
    try:
        assert blocked.wait(1)
        renewal_rejected = rejected.wait(1.5)
    finally:
        release.set()
        thread.join(timeout=2)
    assert not thread.is_alive()
    assert renewal_rejected, "lost ownership must be detected during startup"
    assert submitted == [], "a lost lease must not dispatch a fresh turn"
    assert stored_reports == persisted == [], "a known lost lease must not publish a late report"


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


def _worker(tmp_path: Path, *, startup_seconds: float = 0) -> tuple[str, ...]:
    script = tmp_path / "host_worker.py"
    script.write_text('''
import json
import sys
import time
from pathlib import Path
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
        time.sleep(STARTUP_DELAY)
        send("ready", {"run_id": "run-worker-test"})
    elif frame["kind"] == "turn":
        if frame["payload"]["instruction"] == "slow":
            time.sleep(0.35)
        turns.append(frame["payload"]["instruction"])
        send("answer_committed", {"ordinal": len(turns), "turn_id": f"turn-{len(turns)}",
             "answer_output": turns[-1].upper(), "answer_ref": f"answer:{len(turns)}",
             "result_refs": [], "evidence_refs": ["evidence:current"]})
    elif frame["kind"] == "close":
        report = Path(__file__).parent / "runs" / "run-worker-test" / "output" / "report.md"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("# Run report\\n", encoding="utf-8")
        send("completed", {"run_id": "run-worker-test", "result": {"turns": turns},
             "report_path": str(report)})
    elif frame["kind"] == "evidence":
        ref = frame["payload"]["ref"]
        send("evidence_result", {"ref": ref, "value": {"ref": ref}})
'''.replace("STARTUP_DELAY", repr(startup_seconds)), encoding="utf-8")
    return (sys.executable, "-u", str(script))


def _wait(ledger: Ledger, session_id: str, state: str) -> None:
    for _ in range(100):
        if ledger.get_session(session_id).state == state:
            return
        time.sleep(0.02)
    pytest.fail(f"session did not reach {state}")


def test_cold_start_longer_than_lease_survives_stale_reaper(
    ledger: Ledger, tmp_path: Path,
) -> None:
    registry = WorkerRegistry((WorkerSpec("fixture-app", _worker(tmp_path, startup_seconds=1.2)),))
    record = ledger.create_session("fixture-app", "scripted-demo", None, None, None)
    claim = ledger.claim_pending("worker-test", 1)
    assert claim is not None
    stop = threading.Event()

    def reap() -> None:
        while not stop.wait(0.02):
            ledger.mark_interrupted_stale()

    reaper = threading.Thread(target=reap, daemon=True)
    worker = threading.Thread(target=run_claimed_session, args=(ledger, registry, claim),
        kwargs={"lease_seconds": 1, "poll_seconds": 0.01}, daemon=True)
    reaper.start()
    worker.start()
    try:
        _wait(ledger, record.session_id, "ready")
        ledger.accept_close(record.session_id, "cold-close")
        _wait(ledger, record.session_id, "completed")
    finally:
        stop.set()
        reaper.join(timeout=2)
        worker.join(timeout=2)
    assert not worker.is_alive() and not reaper.is_alive()
    assert ledger.get_session(record.session_id).state == "completed"


def test_worker_runs_sequential_commands_for_cross_connection_reader(
    ledger: Ledger, tmp_path: Path,
) -> None:
    registry = WorkerRegistry((WorkerSpec("fixture-app", _worker(tmp_path)),))
    record = ledger.create_session("fixture-app", "scripted-demo", None, None, None)
    claim = ledger.claim_pending("worker-test", 30)
    assert claim is not None
    artifacts = ArtifactService(ledger, MemoryObjectStore(), tmp_path / "runs")
    thread = threading.Thread(target=run_claimed_session, args=(ledger, registry, claim),
                              kwargs={"poll_seconds": 0.01, "artifacts": artifacts}, daemon=True)
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
    assert [event.kind for event in events] == ["ready", "answer_committed",
                                               "evidence_result", "answer_committed",
                                               "completed"]
    assert events[-1].payload["result"] == {"turns": ["first", "second"]}
    assert artifacts.read_report(record.session_id) == "# Run report\n"
    assert artifacts.read_evidence(record.session_id, "evidence:current") == {
        "ref": "evidence:current"
    }


def test_worker_loop_claims_new_sessions_and_stops_cleanly(
    ledger: Ledger, tmp_path: Path,
) -> None:
    registry = WorkerRegistry((WorkerSpec("fixture-app", _worker(tmp_path)),))
    artifacts = ArtifactService(ledger, MemoryObjectStore(), tmp_path / "runs")
    stop = threading.Event()
    thread = threading.Thread(target=serve_forever, args=(ledger, registry, artifacts),
                              kwargs={"stop_event": stop, "poll_seconds": 0.01,
                                      "max_sessions": 2}, daemon=True)
    thread.start()
    session = ledger.create_session("fixture-app", "scripted-demo", None, None, None)
    _wait(ledger, session.session_id, "ready")
    ledger.accept_close(session.session_id, "close-key")
    _wait(ledger, session.session_id, "completed")
    stop.set()
    thread.join(timeout=5)
    assert not thread.is_alive()


def test_wake_mode_does_not_query_idle_ledger_until_signalled() -> None:
    class EmptyLedger:
        def __init__(self) -> None:
            self.claims = 0

        def mark_interrupted_stale(self) -> None:
            pass

        def claim_pending(self, _worker_id: str, _lease_seconds: int) -> None:
            self.claims += 1
            return None

    ledger = EmptyLedger()
    stop = threading.Event()
    wake = threading.Event()
    thread = threading.Thread(
        target=serve_forever,
        args=(ledger, WorkerRegistry(()), None),
        kwargs={"stop_event": stop, "wake_event": wake, "poll_seconds": 0.01},
        daemon=True,
    )
    thread.start()
    try:
        for _ in range(100):
            if ledger.claims:
                break
            time.sleep(0.01)
        assert ledger.claims == 1
        time.sleep(0.08)
        assert ledger.claims == 1
        wake.set()
        for _ in range(100):
            if ledger.claims == 2:
                break
            time.sleep(0.01)
        assert ledger.claims == 2
    finally:
        stop.set()
        wake.set()
        thread.join(timeout=2)
    assert not thread.is_alive()


def test_idle_session_releases_worker_slot_for_waiting_session(
    ledger: Ledger, tmp_path: Path,
) -> None:
    registry = WorkerRegistry((WorkerSpec("fixture-app", _worker(tmp_path)),))
    artifacts = ArtifactService(ledger, MemoryObjectStore(), tmp_path / "runs")
    stop = threading.Event()
    thread = threading.Thread(target=serve_forever, args=(ledger, registry, artifacts),
                              kwargs={"stop_event": stop, "poll_seconds": 0.01,
                                      "max_sessions": 1, "idle_seconds": 0.2}, daemon=True)
    first = ledger.create_session("fixture-app", "scripted-demo", None, None, None)
    thread.start()
    try:
        _wait(ledger, first.session_id, "interrupted")
        assert ledger.get_session(first.session_id).error_code == "session_idle_timeout"
        second = ledger.create_session("fixture-app", "scripted-demo", None, None, None)
        _wait(ledger, second.session_id, "ready")
        ledger.accept_close(second.session_id, "close-key")
        _wait(ledger, second.session_id, "completed")
    finally:
        stop.set()
        thread.join(timeout=5)
    assert not thread.is_alive()


def test_new_session_evicts_idle_session_when_worker_is_full(
    ledger: Ledger, tmp_path: Path,
) -> None:
    registry = WorkerRegistry((WorkerSpec("fixture-app", _worker(tmp_path)),))
    artifacts = ArtifactService(ledger, MemoryObjectStore(), tmp_path / "runs")
    stop = threading.Event()
    thread = threading.Thread(target=serve_forever, args=(ledger, registry, artifacts),
                              kwargs={"stop_event": stop, "poll_seconds": 0.01,
                                      "max_sessions": 1, "idle_seconds": 600,
                                      "eviction_grace_seconds": 0,
                                      "pending_grace_seconds": 0}, daemon=True)
    first = ledger.create_session("fixture-app", "scripted-demo", None, None, None)
    thread.start()
    try:
        _wait(ledger, first.session_id, "ready")
        waiting = ledger.create_session("fixture-app", "scripted-demo", None, None, None)
        _wait(ledger, first.session_id, "interrupted")
        assert ledger.get_session(first.session_id).error_code == "session_capacity_evicted"
        _wait(ledger, waiting.session_id, "ready")
        ledger.accept_close(waiting.session_id, "close-key")
        _wait(ledger, waiting.session_id, "completed")
    finally:
        stop.set()
        thread.join(timeout=5)
    assert not thread.is_alive()


def test_new_sessions_repeatedly_get_slots_after_eight_idle_sessions(
    ledger: Ledger, tmp_path: Path,
) -> None:
    registry = WorkerRegistry((WorkerSpec("fixture-app", _worker(tmp_path)),))
    artifacts = ArtifactService(ledger, MemoryObjectStore(), tmp_path / "runs")
    stop = threading.Event()
    thread = threading.Thread(target=serve_forever, args=(ledger, registry, artifacts),
                              kwargs={"stop_event": stop, "poll_seconds": 0.01,
                                      "max_sessions": 8, "idle_seconds": 600,
                                      "eviction_grace_seconds": 0,
                                      "pending_grace_seconds": 0}, daemon=True)
    initial = [ledger.create_session("fixture-app", "scripted-demo", None, None, None)
               for _ in range(8)]
    thread.start()
    try:
        for record in initial:
            _wait(ledger, record.session_id, "ready")
        all_records = list(initial)
        for expected_evictions in range(1, 4):
            newcomer = ledger.create_session("fixture-app", "scripted-demo", None, None, None)
            all_records.append(newcomer)
            _wait(ledger, newcomer.session_id, "ready")
            victims = [ledger.get_session(record.session_id) for record in all_records]
            evicted = [record for record in victims if record.state == "interrupted"]
            assert len(evicted) == expected_evictions
            assert all(record.error_code == "session_capacity_evicted" for record in evicted)
        remaining = [record for record in all_records
                     if ledger.get_session(record.session_id).state == "ready"]
        assert len(remaining) == 8
        for record in remaining:
            ledger.accept_close(record.session_id, f"close-{record.session_id}")
        for record in remaining:
            _wait(ledger, record.session_id, "completed")
    finally:
        stop.set()
        thread.join(timeout=10)
    assert not thread.is_alive()


def test_idle_timeout_does_not_interrupt_a_running_turn(
    ledger: Ledger, tmp_path: Path,
) -> None:
    registry = WorkerRegistry((WorkerSpec("fixture-app", _worker(tmp_path)),))
    session = ledger.create_session("fixture-app", "scripted-demo", None, None, None)
    claim = ledger.claim_pending("worker-test", 30)
    assert claim is not None
    thread = threading.Thread(target=run_claimed_session, args=(ledger, registry, claim),
                              kwargs={"poll_seconds": 0.01, "idle_seconds": 0.12}, daemon=True)
    thread.start()
    _wait(ledger, session.session_id, "ready")
    ledger.accept_turn(session.session_id, "slow", "slow-key")
    _wait(ledger, session.session_id, "executing")
    time.sleep(0.2)
    assert ledger.get_session(session.session_id).state == "executing"
    _wait(ledger, session.session_id, "ready")
    ledger.accept_close(session.session_id, "close-key")
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert ledger.get_session(session.session_id).state == "completed"


def test_completed_state_publishes_report_after_artifact_is_stored(
    ledger: Ledger, tmp_path: Path,
) -> None:
    class SlowStore(MemoryObjectStore):
        def put(self, key: str, content: bytes, mime: str) -> None:
            if mime.startswith("text/markdown"):
                time.sleep(0.2)
            super().put(key, content, mime)

    registry = WorkerRegistry((WorkerSpec("fixture-app", _worker(tmp_path)),))
    artifacts = ArtifactService(ledger, SlowStore(), tmp_path / "runs")
    session = ledger.create_session("fixture-app", "scripted-demo", None, None, None)
    claim = ledger.claim_pending("worker-test", 30)
    assert claim is not None
    thread = threading.Thread(target=run_claimed_session, args=(ledger, registry, claim),
                              kwargs={"poll_seconds": 0.01, "artifacts": artifacts}, daemon=True)
    thread.start()
    _wait(ledger, session.session_id, "ready")
    ledger.accept_close(session.session_id, "close-key")
    _wait(ledger, session.session_id, "completed")
    assert artifacts.read_report(session.session_id) == "# Run report\n"
    thread.join(timeout=5)
