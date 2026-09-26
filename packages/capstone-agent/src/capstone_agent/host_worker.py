"""Run registered application sessions from a durable command ledger."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from capstone_agent.artifacts import ArtifactService
from capstone_agent.ledger import Ledger, SessionRecord
from capstone_agent.session import WorkerRegistry, WorkerSession


_LOG = logging.getLogger(__name__)


def run_claimed_session(
    ledger: Ledger, registry: WorkerRegistry, claim: SessionRecord,
    *, poll_seconds: float = 0.1, lease_seconds: int = 30,
    artifacts: ArtifactService | None = None,
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
            observed_sequence = 0
            while True:
                if time.monotonic() - last_renewal >= lease_seconds / 3:
                    if not ledger.renew_lease(claim.session_id, token, lease_seconds):
                        return
                    last_renewal = time.monotonic()
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
                                if projection is not None:
                                    artifacts.save_evidence(claim.session_id, ref, projection)
                        elif event.kind == "completed":
                            path = event.payload.get("report_path")
                            if isinstance(path, str) and path:
                                artifacts.save_report(claim.session_id, Path(path))
                    except Exception:
                        _LOG.warning("Capstone artifact unavailable for session %s",
                                     claim.session_id)
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
