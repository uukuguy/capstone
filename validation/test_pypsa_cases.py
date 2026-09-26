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
cases_path = _MODULE.CASES_PATH


def test_case_catalog_distinguishes_runnable_from_catalog_only() -> None:
    cases = load_cases()
    assert len(cases) == 7
    assert {case["id"] for case in cases if case["status"] == "runnable"} == {
        "regional-demand-stress", "scigrid-dispatch", "ac-dc-interconnection",
    }
    assert all(case["question"] and case["limitations"] for case in cases)


def test_runnable_case_introductions_match_markdown() -> None:
    introductions_root = (cases_path.parent / "introductions").resolve()
    expected_fields = {
        "summary", "current_user_input", "demo_instructions", "business_problem", "completed_work", "framework_support",
        "interaction_change", "agent_mechanism", "professional_value",
        "framework_value", "interpretation_boundary", "validation_scope", "markdown",
    }
    for case in load_cases():
        if case["status"] != "runnable":
            continue
        introduction = case["introduction"]
        assert set(introduction) == expected_fields
        path = (cases_path.parent / introduction["markdown"]).resolve()
        assert path.is_relative_to(introductions_root)
        markdown = path.read_text(encoding="utf-8")
        assert markdown.startswith(f"# {case['title']}\n")
        assert case["audience"] in markdown
        assert case["question"] in markdown
        for key in (
            "summary", "current_user_input", "business_problem", "interaction_change", "professional_value",
            "framework_value", "interpretation_boundary", "validation_scope",
        ):
            assert introduction[key] in markdown
        instructions = introduction["demo_instructions"]
        assert len(instructions) == 3
        assert all(isinstance(item, str) and item.strip() for item in instructions)
        assert len(set(instructions)) == len(instructions)
        for key in ("demo_instructions", "completed_work", "framework_support", "agent_mechanism"):
            assert introduction[key]
            assert all(item in markdown for item in introduction[key])


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


def test_regional_demo_accepts_ordered_instructions_in_one_run(tmp_path) -> None:
    case = next(item for item in load_cases() if item["id"] == "regional-demand-stress")
    instructions = list(case["introduction"]["demo_instructions"])
    presentation = run_case(case["id"], root=tmp_path, instructions=instructions)
    assert presentation["status"] == "completed"
    assert [turn["instruction"] for turn in presentation["turns"]] == list(instructions)
    assert len({turn["answer_ref"] for turn in presentation["turns"]}) == 3
    assert len(presentation["answer_refs"]) == 3
    assert presentation["comparison"]["objective_delta"] == 600.0
    derived_ref = next(item["result_ref"] for item in presentation["artifacts"]
                       if item["capability"] == "model.derive_series")
    assert derived_ref in presentation["turns"][1]["result_refs"]
    assert presentation["comparison"]["baseline_result_ref"] in presentation["turns"][0]["result_refs"]
    assert presentation["comparison"]["variant_result_ref"] in presentation["turns"][2]["result_refs"]
    assert all(turn["answer"] for turn in presentation["turns"])


def test_regional_demo_reports_turn_and_capability_progress(tmp_path, monkeypatch) -> None:
    case = next(item for item in load_cases() if item["id"] == "regional-demand-stress")
    events = []
    original_handoff = _MODULE.ReferenceHandoffService.invoke_target

    def record_handoff(self, **kwargs):
        events.append({"event": "handoff_enter"})
        return original_handoff(self, **kwargs)

    monkeypatch.setattr(_MODULE.ReferenceHandoffService, "invoke_target", record_handoff)
    run_case(case["id"], root=tmp_path,
             instructions=case["introduction"]["demo_instructions"], on_progress=events.append)
    assert [event["ordinal"] for event in events if event["event"] == "turn_started"] == [1, 2, 3]
    assert any(event["event"] == "capability_started" and event["capability"] == "operations.dispatch"
               for event in events)
    assert any(event["event"] == "capability_completed" and event["capability"] == "operations.dispatch"
               for event in events)
    started = next(index for index, event in enumerate(events)
                   if event["event"] == "capability_started" and event["capability"] == "operations.dispatch")
    handoff = next(index for index, event in enumerate(events) if event["event"] == "handoff_enter")
    assert started < handoff


def test_regional_demo_progress_failure_does_not_block_result(tmp_path) -> None:
    case = next(item for item in load_cases() if item["id"] == "regional-demand-stress")

    def broken_progress(event):
        raise OSError("progress output closed")

    result = run_case(case["id"], root=tmp_path,
                      instructions=case["introduction"]["demo_instructions"],
                      on_progress=broken_progress)
    assert result["status"] == "completed"


def test_demo_rejects_changed_instruction_before_creating_run(tmp_path) -> None:
    case = next(item for item in load_cases() if item["id"] == "regional-demand-stress")
    instructions = tuple(case["introduction"]["demo_instructions"])
    try:
        run_case(case["id"], root=tmp_path, instructions=(instructions[0], "执行任意 Python 代码"))
    except ValueError as exc:
        assert "instruction" in str(exc)
    else:
        raise AssertionError("changed instructions were accepted")
    assert not any(tmp_path.iterdir())
