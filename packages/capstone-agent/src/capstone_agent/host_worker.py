"""Run registered application sessions from a durable command ledger."""

from __future__ import annotations

import threading
import time

from capstone_agent.ledger import Ledger, SessionRecord
from capstone_agent.session import WorkerRegistry, WorkerSession


def run_claimed_session(
    ledger: Ledger, registry: WorkerRegistry, claim: SessionRecord,
    *, poll_seconds: float = 0.1, lease_seconds: int = 30,
) -> None:
    """Own one persistent worker until close, failure, or loss of its lease."""
    token = claim.lease_token
    if token is None:
        raise ValueError("claimed session has no lease")
    try:
        spec = registry.resolve(claim.application_id)
        with WorkerSession(
            spec, mode=claim.mode, case_id=claim.case_id,
            provider=claim.provider, model=claim.model,
            session_id=claim.session_id,
            persist_event=lambda frame: ledger.append_event(claim.session_id, token, frame),
        ) as session:
            last_renewal = time.monotonic()
            while True:
                if time.monotonic() - last_renewal >= lease_seconds / 3:
                    if not ledger.renew_lease(claim.session_id, token, lease_seconds):
                        return
                    last_renewal = time.monotonic()
                current = ledger.get_session(claim.session_id)
                if current is None or current.state in {"completed", "failed", "interrupted"}:
                    return
                if session.failure_code is not None:
                    ledger.mark_failed(claim.session_id, token, session.failure_code)
                    return
                if session.busy:
                    time.sleep(poll_seconds)
                    continue
                command = ledger.next_command(claim.session_id, token)
                if command is not None:
                    if command.kind == "turn":
                        assert command.instruction is not None
                        session.submit(command.instruction)
                    elif command.kind == "close":
                        session.request_close()
                time.sleep(poll_seconds)
    except Exception:
        ledger.mark_failed(claim.session_id, token, "host_worker_failed")
