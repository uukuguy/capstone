"""Local application acceptance for the registered PyPSA business cases."""

from __future__ import annotations

import json
import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).with_name("pypsa_cases.py")
_SPEC = importlib.util.spec_from_file_location("pypsa_cases", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
load_cases = _MODULE.load_cases
run_case = _MODULE.run_case


def test_case_catalog_distinguishes_runnable_from_catalog_only() -> None:
    cases = load_cases()
    assert len(cases) == 7
    assert {case["id"] for case in cases if case["status"] == "runnable"} == {
        "regional-demand-stress", "scigrid-dispatch", "ac-dc-interconnection",
    }
    assert all(case["question"] and case["limitations"] for case in cases)


def test_regional_stress_commits_two_real_dispatches_and_case_projection(tmp_path) -> None:
    presentation = run_case("regional-demand-stress", root=tmp_path)
    assert presentation["status"] == "completed"
    assert presentation["comparison"]["baseline_objective"] == 1300.0
    assert presentation["comparison"]["variant_objective"] == 1900.0
    assert presentation["comparison"]["objective_delta"] == 600.0
    assert len(presentation["result_refs"]) == 6
    assert len(presentation["evidence_refs"]) == 6
    assert presentation["answer_refs"]
    assert all(item["result_ref"] in presentation["result_refs"] for item in presentation["artifacts"])
    assert (tmp_path / presentation["run_id"] / "core" / "context-events.jsonl").exists()
    saved = json.loads((tmp_path / presentation["run_id"] / "presentation.json").read_text())
    assert saved == presentation
