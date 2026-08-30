"""Provider-free acceptance for the complete pandapower application path."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from validation.run import execute_application_case


ROOT = Path(__file__).resolve().parents[4]


@pytest.mark.parametrize(
    "case_name",
    ("pandapower-scripted-task.json", "pandapower-scripted-test.json"),
)
def test_scripted_pandapower_application_preserves_run_lineage(
    tmp_path: Path,
    case_name: str,
) -> None:
    """Run the generic entry point with real gridctl semantic calls.

    The assertions intentionally validate wiring and provenance rather than
    fixed network values.  Numerical and topology truth stays inside the
    simulator boundary and is admitted by the run-scoped authority.
    """

    case_path = ROOT / "validation" / "application" / case_name
    execution = execute_application_case(
        case_path,
        runs_root=tmp_path / "runs",
    )
    outcome = execution.outcome

    assert outcome.status == "completed"
    assert outcome.completed_questions == len(execution.case["questions"])
    assert outcome.total_questions == outcome.completed_questions
    assert execution.transport.started is True
    assert execution.transport.stopped is True
    assert execution.transport.calls
    assert len(execution.transport.semantic_events) == 2 * len(execution.transport.calls)

    # The model reuses the context emitted by the first real context.open call.
    context_refs = {
        result["context_ref"]
        for call in execution.transport.calls
        if isinstance(call.get("result"), dict)
        for result in (call["result"],)
        if isinstance(result.get("context_ref"), str)
    }
    assert len(context_refs) == 1

    # The runner returns the framework-owned composite output, not the legacy
    # two-field compatibility envelope.
    rendered = json.loads(outcome.rendered)
    assert set(rendered) == {"schema", "core", "domains"}
    assert rendered["schema"] == "capability-agent-output/1.0"
    assert set(rendered["domains"]) == {"grid"}
    assert rendered["core"]["status"] == "completed"
    assert rendered["domains"]["grid"]["status"] == "completed"
    assert set(rendered["domains"]["grid"]["payload"]) == {
        "mode",
        "instruction_count",
        "completed_count",
        "failed_count",
        "report_artifact_ref",
    }

    # Every model answer has been committed with current-turn simulator refs,
    # and the real answer audit emitted no error diagnostics.
    assert len(execution.controller.finalized_turns) == outcome.total_questions
    for finalized in execution.controller.finalized_turns:
        assert finalized.status == "success"
        assert finalized.result_refs or finalized.evidence_refs
        assert not any(
            getattr(diagnostic, "severity", None) == "error"
            or (
                isinstance(diagnostic, dict)
                and diagnostic.get("severity") == "error"
            )
            for diagnostic in finalized.audit_diagnostics
        )
        answer_payload = json.loads(finalized.answer_path.read_text(encoding="utf-8"))
        assert answer_payload["result_refs"] == list(finalized.result_refs)
        assert answer_payload["evidence_refs"] == list(finalized.evidence_refs)

    # Report creation, content-addressed admission, and context replay are
    # checked again here so this test remains useful independent of the CLI
    # validation report formatting.
    report_path = outcome.report_path
    report_ref = rendered["core"]["report_ref"]
    assert report_path.is_file()
    assert report_ref == "artifact:sha256:" + hashlib.sha256(
        report_path.read_bytes()
    ).hexdigest()
    assert report_ref in execution.store.snapshot.core.produced_refs
    assert execution.store.verify_materialized_snapshot() == execution.store.snapshot

    # Domain state is opaque to the Kernel but must be populated by the
    # Domain Pack projector and retain the simulator references from this run.
    domain_state = execution.store.snapshot.domains["grid"].state
    assert domain_state["model"]
    assert execution.transport.all_result_refs
    assert execution.transport.all_evidence_refs
