from __future__ import annotations

import os
from pathlib import Path

import psycopg
import pytest

from capstone_agent.artifacts import ArtifactService, MemoryObjectStore
from capstone_agent.ledger import Ledger
from capstone_agent.protocol import Frame


@pytest.fixture
def ledger() -> Ledger:
    dsn = os.environ.get("CAPSTONE_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("CAPSTONE_TEST_DATABASE_URL is required")
    store = Ledger(dsn)
    store.initialize()
    with psycopg.connect(dsn) as connection:
        connection.execute("TRUNCATE session_artifacts, session_events, session_commands, sessions CASCADE")
    return store


def test_evidence_requires_committed_ref_and_detects_tampering(
    ledger: Ledger, tmp_path: Path,
) -> None:
    session = ledger.create_session("fixture-app", "scripted-demo", None, None, None)
    claim = ledger.claim_pending("worker-one", 30)
    assert claim is not None
    ledger.append_event(session.session_id, claim.lease_token,
                        Frame(session.session_id, 1, "ready", {"run_id": "run-artifact"}))
    ledger.accept_turn(session.session_id, "first", "key-1")
    ledger.append_event(session.session_id, claim.lease_token,
                        Frame(session.session_id, 2, "answer_committed", {
                            "ordinal": 1, "turn_id": "turn-1", "answer_output": "done",
                            "answer_ref": "answer:1", "result_refs": [],
                            "evidence_refs": ["evidence:allowed"],
                        }))
    objects = MemoryObjectStore()
    service = ArtifactService(ledger, objects, tmp_path)
    with pytest.raises(ValueError, match="admitted"):
        service.save_evidence(session.session_id, "evidence:foreign", {"secret": 1})
    service.save_evidence(session.session_id, "evidence:allowed", {"ref": "evidence:allowed"})
    assert ArtifactService(Ledger(ledger.dsn), objects, tmp_path).read_evidence(
        session.session_id, "evidence:allowed"
    ) == {"ref": "evidence:allowed"}
    key = ledger.get_artifact(session.session_id, "evidence", "evidence:allowed").object_key
    objects.contents[key] = b'{"ref":"tampered"}'
    with pytest.raises(ValueError, match="integrity"):
        service.read_evidence(session.session_id, "evidence:allowed")


def test_report_path_must_stay_inside_current_run(ledger: Ledger, tmp_path: Path) -> None:
    session = ledger.create_session("fixture-app", "scripted-demo", None, None, None)
    claim = ledger.claim_pending("worker-one", 30)
    assert claim is not None
    ledger.append_event(session.session_id, claim.lease_token,
                        Frame(session.session_id, 1, "ready", {"run_id": "run-report"}))
    run_dir = tmp_path / "run-report" / "output"
    run_dir.mkdir(parents=True)
    report = run_dir / "report.md"
    report.write_text("# Current run\n", encoding="utf-8")
    outside = tmp_path / "other.md"
    outside.write_text("foreign", encoding="utf-8")
    service = ArtifactService(ledger, MemoryObjectStore(), tmp_path)
    with pytest.raises(ValueError, match="current run"):
        service.save_report(session.session_id, outside)
    service.save_report(session.session_id, report)
    assert service.read_report(session.session_id) == "# Current run\n"


def test_pypsa_report_uses_registered_application_run_directory(
    ledger: Ledger, tmp_path: Path,
) -> None:
    session = ledger.create_session("pypsa-business-cases", "scripted-demo", None, None, None)
    claim = ledger.claim_pending("worker-one", 30)
    assert claim is not None
    ledger.append_event(session.session_id, claim.lease_token,
                        Frame(session.session_id, 1, "ready", {"run_id": "run-pypsa-report"}))
    report = tmp_path / "pypsa" / "run-pypsa-report" / "output" / "report.md"
    report.parent.mkdir(parents=True)
    report.write_text("# PyPSA report\n", encoding="utf-8")
    service = ArtifactService(ledger, MemoryObjectStore(), tmp_path)
    service.save_report(session.session_id, report)
    assert service.read_report(session.session_id) == "# PyPSA report\n"
