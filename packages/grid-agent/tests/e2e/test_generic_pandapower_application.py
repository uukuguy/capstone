"""Provider-free acceptance for the complete pandapower application path."""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from validation.run import (
    _remove_generated_application_run,
    execute_application_case,
)


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
        timeout_seconds=17.0,
    )
    outcome = execution.outcome
    questions = execution.case["questions"]
    assert isinstance(questions, list)

    assert outcome.status == "completed"
    assert outcome.completed_questions == len(questions)
    assert outcome.total_questions == outcome.completed_questions
    assert execution.transport.started is True
    assert execution.transport.stopped is True
    assert execution.transport.calls
    assert len(execution.transport.semantic_events) == 2 * len(execution.transport.calls)

    # The model reuses the context emitted by the first real context.open call.
    context_refs: set[str] = set()
    for call in execution.transport.calls:
        result = call.get("result")
        if isinstance(result, Mapping):
            context_ref = result.get("context_ref")
            if isinstance(context_ref, str):
                context_refs.add(context_ref)
    assert len(context_refs) == 1

    # The runner returns the framework-owned composite output, not the legacy
    # two-field compatibility envelope.
    assert isinstance(outcome.rendered, str)
    rendered = json.loads(outcome.rendered)
    assert set(rendered) == {"schema", "core", "domains"}
    assert rendered["schema"] == "capability-agent-output/1.0"
    assert set(rendered["domains"]) == {"grid"}
    assert rendered["core"]["status"] == "completed"
    assert rendered["domains"]["grid"]["status"] == "completed"
    assert rendered["domains"]["grid"]["schema"] == (
        "pandapower-static-analysis-output/1.1"
    )
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
        assert finalized.answer_path is not None
        answer_payload = json.loads(finalized.answer_path.read_text(encoding="utf-8"))
        assert answer_payload["result_refs"] == list(finalized.result_refs)
        assert answer_payload["evidence_refs"] == list(finalized.evidence_refs)

    # Report creation, content-addressed admission, and context replay are
    # checked again here so this test remains useful independent of the CLI
    # validation report formatting.
    report_path = outcome.report_path
    report_ref = rendered["core"]["report_ref"]
    assert report_path is not None
    assert report_path.is_file()
    assert report_ref == "artifact:sha256:" + hashlib.sha256(
        report_path.read_bytes()
    ).hexdigest()
    assert report_ref in execution.store.snapshot.core.produced_refs
    assert execution.store.verify_materialized_snapshot() == execution.store.snapshot
    endpoint_metadata = execution.prepared.bindings["grid"].endpoint.metadata
    assert endpoint_metadata["timeout_seconds"] == pytest.approx(17.0)

    # The generic runtime must expose a binding-owned guide snapshot.  The
    # Domain Pack source resource directory is never placed in the descriptor
    # or guide index consumed by the model runtime.
    runtime = execution.prepared.bindings["grid"].runtime
    binding_root = execution.workspace.domain_path("grid")
    assert runtime.guide_root_path.is_relative_to(binding_root)
    guide_payload = json.loads(
        runtime.guide_index_path.read_text(encoding="utf-8")
    )
    assert guide_payload["root"] == str(runtime.guide_root_path)
    assert all(
        Path(resource).is_relative_to(runtime.guide_root_path)
        for resource in guide_payload["resources"].values()
    )
    assert str(execution.prepared.bindings["grid"].binding.profile.manifest.guide_root) not in (
        runtime.guide_index_path.read_text(encoding="utf-8")
    )

    # Domain state is opaque to the Kernel but must be populated by the
    # Domain Pack projector and retain the simulator references from this run.
    domain_state = execution.store.snapshot.domains["grid"].state
    assert domain_state["model"]
    assert execution.transport.all_result_refs
    assert execution.transport.all_evidence_refs


@pytest.mark.parametrize("run_id", ("../sentinel", "nested/run"))
def test_application_run_cleanup_rejects_path_traversal_without_touching_sentinel(
    tmp_path: Path,
    run_id: str,
) -> None:
    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    sentinel = tmp_path / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError, match="portable identifier"):
        _remove_generated_application_run(runs_root, run_id)

    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_application_run_cleanup_rejects_absolute_id_without_touching_sentinel(
    tmp_path: Path,
) -> None:
    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    sentinel = tmp_path / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError, match="portable identifier"):
        _remove_generated_application_run(runs_root, str(tmp_path / "outside"))

    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_application_run_cleanup_rejects_symlink_candidate_without_following_it(
    tmp_path: Path,
) -> None:
    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")
    (runs_root / "safe-run").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink"):
        _remove_generated_application_run(runs_root, "safe-run")

    assert sentinel.read_text(encoding="utf-8") == "keep"
    assert (runs_root / "safe-run").is_symlink()


def test_application_run_cleanup_rejects_symlink_runs_root(
    tmp_path: Path,
) -> None:
    real_root = tmp_path / "real-runs"
    real_root.mkdir()
    runs_root = tmp_path / "runs"
    runs_root.symlink_to(real_root, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink"):
        _remove_generated_application_run(runs_root, "safe-run")


def test_application_run_cleanup_deletes_only_the_named_generated_run(
    tmp_path: Path,
) -> None:
    runs_root = tmp_path / "runs"
    runs_root.mkdir()
    generated = runs_root / "safe-run"
    generated.mkdir()
    (generated / "generated.txt").write_text("remove", encoding="utf-8")
    sibling = runs_root / "keep-run"
    sibling.mkdir()
    sentinel = sibling / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")

    _remove_generated_application_run(runs_root, "safe-run")

    assert not generated.exists()
    assert sentinel.read_text(encoding="utf-8") == "keep"
