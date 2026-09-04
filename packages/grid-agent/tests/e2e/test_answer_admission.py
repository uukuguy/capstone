"""Provider-free admission metadata acceptance for the generic grid app."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from capability_agent.domain.answer_admission import read_answer_admission_metadata
from validation.run import execute_application_case


ROOT = Path(__file__).resolve().parents[4]


def test_answer_admission_sidecars_detect_tampering_without_changing_envelopes(
    tmp_path: Path,
) -> None:
    execution = execute_application_case(
        ROOT / "validation/application/pandapower-scripted-test.json",
        runs_root=tmp_path / "runs",
        timeout_seconds=17.0,
    )

    finalized = execution.controller.finalized_turns[-1]
    assert finalized.answer_path is not None
    admission_ref = execution.store.snapshot.core.answer_lifecycle["admission_ref"]
    admission = read_answer_admission_metadata(
        finalized.answer_path, expected_admission_ref=admission_ref
    )
    assert admission is not None
    assert admission.mode == "authority_backed"
    assert admission.assurance == "lineage_verified"
    assert "semantic_verification" not in admission.diagnostic_codes

    # Replacing a displayed number leaves the simulator lineage untouched, but
    # it must invalidate the sidecar rather than fabricate semantic proof.
    payload = json.loads(finalized.answer_path.read_text(encoding="utf-8"))
    payload["answer_output"] = "A substituted value is 999 MW."
    finalized.answer_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="does not match"):
        read_answer_admission_metadata(
            finalized.answer_path, expected_admission_ref=admission_ref
        )
