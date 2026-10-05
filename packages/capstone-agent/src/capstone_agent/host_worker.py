"""Run registered application sessions from a durable command ledger."""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path

from capstone_agent.artifacts import ArtifactService
from capstone_agent.ledger import Ledger, SessionRecord
from capstone_agent.session import WorkerRegistry, WorkerSession


_LOG = logging.getLogger(__name__)


def run_claimed_session(
    ledger: Ledger, registry: WorkerRegistry, claim: SessionRecord,
    *, poll_seconds: float = 0.1, lease_seconds: int = 30,
    idle_seconds: float = 600,
    artifacts: ArtifactService | None = None,
) -> None:
    """Own one persistent worker until close, failure, or loss of its lease."""
    token = claim.lease_token
    if token is None:
        raise ValueError("claimed session has no lease")
    if lease_seconds < 1:
        raise ValueError("worker lease is invalid")
    renewal_stop = threading.Event()
    lease_lost = threading.Event()

    def renew() -> None:
        # Startup, evidence RPCs and artifact writes can block the owner loop.
        # Keep its existing claim alive independently of those operations.
        while not renewal_stop.is_set():
            try:
                owned = ledger.renew_lease(claim.session_id, token, lease_seconds)
            except Exception:
                _LOG.warning("Capstone lease unavailable for session %s", claim.session_id)
                owned = False
            if not owned:
                lease_lost.set()
                return
            if renewal_stop.wait(lease_seconds / 3):
                return

    renewal = threading.Thread(target=renew, daemon=True,
                               name=f"capstone-lease-{claim.session_id}")

    def persist(frame):
        if lease_lost.is_set():
            raise RuntimeError("worker lease is unavailable")
        if frame.kind == "completed" and artifacts is not None:
            path = frame.payload.get("report_path")
            if isinstance(path, str) and path:
                try:
                    artifacts.save_report(claim.session_id, Path(path))
                except Exception:
                    _LOG.warning("Capstone report unavailable for session %s", claim.session_id)
        ledger.append_event(claim.session_id, token, frame)

    try:
        renewal.start()
        spec = registry.resolve(claim.application_id)
        if lease_lost.is_set():
            return
        with WorkerSession(
            spec, mode=claim.mode, case_id=claim.case_id,
            provider=claim.provider, model=claim.model,
            session_id=claim.session_id,
            persist_event=persist,
        ) as session:
            idle_since: float | None = None
            observed_sequence = 0
            while True:
                if lease_lost.is_set():
                    session.abort()
                    return
                for event in session.events:
                    if event.sequence <= observed_sequence:
                        continue
                    observed_sequence = event.sequence
                    if artifacts is None:
                        continue
                    try:
                        if event.kind == "answer_committed":
                            for ref in event.payload["evidence_refs"]:
                                if ledger.get_artifact(claim.session_id, "evidence", ref) is not None:
                                    continue
                                projection = session.read_evidence(ref)
                                if lease_lost.is_set():
                                    session.abort()
                                    return
                                if projection is not None:
                                    artifacts.save_evidence(claim.session_id, ref, projection)
                    except Exception:
                        _LOG.warning("Capstone artifact unavailable for session %s",
                                     claim.session_id)
                current = ledger.get_session(claim.session_id)
                if current is not None and current.state == "completed" and not any(
                    event.kind == "completed" for event in session.events
                ):
                    time.sleep(poll_seconds)
                    continue
                if current is None or current.state == "interrupted":
                    session.abort()
                    return
                if current.state in {"completed", "failed"}:
                    return
                if session.failure_code is not None:
                    ledger.mark_failed(claim.session_id, token, session.failure_code)
                    return
                if session.busy:
                    idle_since = None
                    time.sleep(poll_seconds)
                    continue
                command = ledger.next_command(claim.session_id, token)
                if command is not None:
                    idle_since = None
                    if command.kind == "turn":
                        assert command.instruction is not None
                        session.submit(command.instruction)
                    elif command.kind == "close":
                        session.request_close()
                elif current.state == "ready":
                    now = time.monotonic()
                    idle_since = now if idle_since is None else idle_since
                    if now - idle_since >= idle_seconds:
                        if ledger.mark_interrupted_idle(claim.session_id, token):
                            session.abort()
                            return
                        idle_since = None
                else:
                    idle_since = None
                time.sleep(poll_seconds)
    except Exception:
        ledger.mark_failed(claim.session_id, token, "host_worker_failed")
    finally:
        renewal_stop.set()
        if renewal.ident is not None:
            renewal.join(timeout=lease_seconds / 3)


def serve_forever(
    ledger: Ledger, registry: WorkerRegistry, artifacts: ArtifactService,
    *, max_sessions: int = 8, poll_seconds: float = 0.25,
    lease_seconds: int = 30, idle_seconds: float = 600,
    eviction_grace_seconds: float = 30, pending_grace_seconds: float = 1,
    stop_event: threading.Event | None = None,
    wake_event: threading.Event | None = None,
) -> None:
    """Claim bounded independent sessions without relying on API affinity."""
    if (max_sessions < 1 or poll_seconds <= 0 or idle_seconds <= 0 or
            eviction_grace_seconds < 0 or pending_grace_seconds < 0):
        raise ValueError("worker capacity or poll interval is invalid")
    stop = stop_event or threading.Event()
    active: dict[str, threading.Thread] = {}
    worker_id = f"worker-{os.getpid()}"
    first_pass = True
    while not stop.is_set():
        if wake_event is not None and not first_pass and not active:
            if not wake_event.wait(timeout=1):
                continue
            wake_event.clear()
        first_pass = False
        if stop.is_set():
            break
        for session_id, thread in tuple(active.items()):
            if not thread.is_alive():
                thread.join()
                del active[session_id]
        ledger.mark_interrupted_stale()
        if len(active) >= max_sessions:
            ledger.evict_oldest_idle(
                minimum_idle_seconds=eviction_grace_seconds,
                minimum_wait_seconds=pending_grace_seconds,
            )
        while len(active) < max_sessions:
            claim = ledger.claim_pending(worker_id, lease_seconds)
            if claim is None:
                break
            thread = threading.Thread(
                target=run_claimed_session,
                args=(ledger, registry, claim),
                kwargs={"artifacts": artifacts, "poll_seconds": poll_seconds,
                        "lease_seconds": lease_seconds, "idle_seconds": idle_seconds},
                daemon=True, name=f"capstone-{claim.session_id}",
            )
            active[claim.session_id] = thread
            thread.start()
        if active or wake_event is None:
            stop.wait(poll_seconds)
    for thread in active.values():
        thread.join(timeout=2)
