"""Real application-boundary checks for domain answer admission."""

from __future__ import annotations

import json
import sys
import copy
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from capability_agent.domain.answer_admission import read_answer_admission_metadata
from validation import run as validation_run
from validation.run import execute_application_case


ROOT = Path(__file__).resolve().parents[4]


def _case(question: str, steps: list[dict[str, object]], run_id: str) -> dict[str, object]:
    return {
        "schema_version": "application-instantiation/1.0",
        "case_id": run_id,
        "application_id": "pandapower-static-analysis",
        "run_id": run_id,
        "questions": [{"id": "admission", "text": question, "steps": steps}],
    }


def _admission(execution: object):
    finalized = execution.controller.finalized_turns[-1]  # type: ignore[attr-defined]
    assert finalized.answer_path is not None
    admission_ref = execution.store.snapshot.core.answer_lifecycle["admission_ref"]  # type: ignore[attr-defined]
    decision = read_answer_admission_metadata(
        finalized.answer_path, expected_admission_ref=admission_ref
    )
    assert decision is not None
    return finalized, decision


def test_real_boundary_limits_zero_reference_business_question(tmp_path: Path) -> None:
    execution = execute_application_case(
        _case("What is the bus voltage?", [], "admission-business"),
        runs_root=tmp_path / "runs",
        timeout_seconds=17.0,
    )

    finalized, admission = _admission(execution)
    assert finalized.status == "limited"
    assert admission.mode == "limited"
    assert admission.assurance == "limited"
    assert "execution limitation" in finalized.answer_output


def test_real_boundary_renders_natural_language_offline_knowledge(tmp_path: Path) -> None:
    execution = execute_application_case(
        _case("什么是交流潮流？", [], "admission-offline"),
        runs_root=tmp_path / "runs",
        timeout_seconds=17.0,
    )

    finalized, admission = _admission(execution)
    assert finalized.status == "success"
    assert admission.mode == "offline_information"
    assert admission.assurance == "deterministic_information"
    assert "AC" in finalized.answer_output


@pytest.mark.parametrize(
    "altered_output",
    (
        "The loss is 999 MW.",
        "The voltage is 999 kV.",
        "The N-1 scenario is secure for an unrelated line.",
    ),
)
def test_real_authority_results_only_verify_lineage_when_model_text_is_altered_before_admission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, altered_output: str
) -> None:
    source = json.loads(
        (ROOT / "validation/application/pandapower-scripted-test.json").read_text(
            encoding="utf-8"
        )
    )
    first = copy.deepcopy(source["questions"][0])
    baseline = execute_application_case(
        _case(str(first["text"]), first["steps"], "admission-baseline"),
        runs_root=tmp_path / "runs",
        timeout_seconds=17.0,
    )
    baseline_finalized, baseline_admission = _admission(baseline)
    original_prompt = validation_run.ScriptedApplicationTransport.prompt_and_wait

    def altered_prompt(self: object, *args: object, **kwargs: object) -> str:
        original_prompt(self, *args, **kwargs)
        return altered_output

    monkeypatch.setattr(
        validation_run.ScriptedApplicationTransport, "prompt_and_wait", altered_prompt
    )
    altered = execute_application_case(
        _case(str(first["text"]), first["steps"], "admission-altered"),
        runs_root=tmp_path / "runs",
        timeout_seconds=17.0,
    )
    finalized, admission = _admission(altered)

    assert finalized.result_refs == baseline_finalized.result_refs
    assert finalized.evidence_refs == baseline_finalized.evidence_refs
    assert finalized.answer_output == altered_output
    assert admission.mode == baseline_admission.mode == "authority_backed"
    assert admission.assurance == baseline_admission.assurance == "lineage_verified"
    assert "semantic_verification" not in admission.diagnostic_codes


def test_answer_admission_sidecars_detect_tampering_without_changing_envelopes(
    tmp_path: Path,
) -> None:
    execution = execute_application_case(
        ROOT / "validation/application/pandapower-scripted-test.json",
        runs_root=tmp_path / "runs",
        timeout_seconds=17.0,
    )

    finalized, admission = _admission(execution)
    assert admission.mode == "authority_backed"
    assert admission.assurance == "lineage_verified"
    assert "semantic_verification" not in admission.diagnostic_codes

    # Replacing a displayed number leaves the simulator lineage untouched, but
    # it must invalidate the sidecar rather than fabricate semantic proof.
    payload = json.loads(finalized.answer_path.read_text(encoding="utf-8"))
    payload["answer_output"] = "A substituted value is 999 MW."
    finalized.answer_path.write_text(json.dumps(payload), encoding="utf-8")
    admission_ref = execution.store.snapshot.core.answer_lifecycle["admission_ref"]
    with pytest.raises(ValueError, match="does not match"):
        read_answer_admission_metadata(
            finalized.answer_path, expected_admission_ref=admission_ref
        )
