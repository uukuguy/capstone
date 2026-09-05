"""Real application-boundary checks for domain answer admission."""

from __future__ import annotations

import json
import sys
import copy
from collections.abc import Mapping
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


def _questions_case(
    questions: list[dict[str, object]], run_id: str
) -> dict[str, object]:
    return {
        "schema_version": "application-instantiation/1.0",
        "case_id": run_id,
        "application_id": "pandapower-static-analysis",
        "run_id": run_id,
        "questions": questions,
    }


def _turn_admission(finalized: object):
    answer_path = finalized.answer_path  # type: ignore[attr-defined]
    admission_ref = finalized.admission_ref  # type: ignore[attr-defined]
    assert answer_path is not None
    assert admission_ref is not None
    decision = read_answer_admission_metadata(
        answer_path, expected_admission_ref=admission_ref
    )
    assert decision is not None
    return decision


def _emit_guide_event(
    transport: object,
    callback: object,
    *,
    turn_id: str,
    resource_id: str,
    ok: bool,
    result: Mapping[str, object] | None = None,
) -> None:
    assert callable(callback)
    call_id = f"{getattr(transport, 'run_id')}-guide-{len(getattr(transport, 'semantic_events')) + 1}"
    start = {
        "type": "tool_execution_start",
        "tool_call_id": call_id,
        "tool_name": "grid_guide_open",
        "capability": "grid_guide_open",
        "args": {"resource_id": resource_id},
        "correlation_id": turn_id,
    }
    completed = {
        "type": "tool_result",
        "tool_call_id": call_id,
        "tool_name": "grid_guide_open",
        "capability": "grid_guide_open",
        "ok": ok,
        "result": dict(result or {"resource_id": resource_id}),
        "correlation_id": turn_id,
    }
    for event in (start, completed):
        transport.semantic_events.append(event)  # type: ignore[attr-defined]
        callback(event, len(transport.semantic_events))  # type: ignore[attr-defined]


def _published_guide(transport: object, resource_id: str) -> Mapping[str, object]:
    binding = getattr(transport, "_binding")
    provider = binding.binding.profile.guide_provider
    guide = provider.open(resource_id)
    assert isinstance(guide, Mapping)
    return guide


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


def test_no_new_tool_answer_preserves_text_and_continues_to_real_powerflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = json.loads((ROOT / "validation/application/pandapower-scripted-task.json").read_text())
    question = "潮流计算工具（pandapower runpp）需要输入哪些参数?"
    reader_text = "必填参数是 context_ref；可选参数包括 algorithm、init、max_iteration。"
    case = _questions_case([
        {"id": "parameters", "text": question, "steps": []},
        *copy.deepcopy(source["questions"][:2]),
    ], "admission-no-new-tool")
    original = validation_run.ScriptedApplicationTransport.prompt_and_wait

    def prompt(self: object, *args: object, **kwargs: object) -> str:
        response = original(self, *args, **kwargs)
        return reader_text if args[0] == question else response

    monkeypatch.setattr(validation_run.ScriptedApplicationTransport, "prompt_and_wait", prompt)
    execution = execute_application_case(case, runs_root=tmp_path / "runs", timeout_seconds=17.0)
    first = execution.controller.finalized_turns[0]
    assert reader_text in first.answer_output
    assert first.status == "limited"
    assert _turn_admission(first).assurance == "limited"
    assert first.result_refs == first.evidence_refs == ()
    assert execution.outcome.status == "completed"
    assert execution.outcome.completed_questions == 3
    assert execution.controller.finalized_turns[-1].result_refs
    report = execution.outcome.report_path.read_text()
    assert "成功：2；未完成：1" in report
    assert "Guarantee scope" in report and "- limited" in report
    assert reader_text in report


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


def test_current_published_guide_admits_reader_text_without_refs_and_later_authority_turns_continue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = json.loads(
        (ROOT / "validation/application/pandapower-scripted-task.json").read_text(
            encoding="utf-8"
        )
    )
    first = copy.deepcopy(source["questions"][0])
    later_authority = copy.deepcopy(source["questions"][1])
    guide_question = "N-1静态安全校核需要检查哪些越限类型?"
    parameter_question = "潮流计算工具（pandapower runpp）需要输入哪些参数?"
    parameter_text = "交流潮流工具需要 context_ref；可选算法、初始化方式、最大迭代次数等参数以发布指南为准。"
    reader_text = "N-1静态安全校核需要检查热稳定越限、电压越限及孤岛等当前指南列出的风险。"
    case = _questions_case(
        [
            first,
            {"id": "current-guide", "text": guide_question, "steps": []},
            {"id": "parameter-guide", "text": parameter_question, "steps": [
                {"capability": "analysis.operation.list", "arguments": {}},
                {"capability": "analysis.operation.describe", "arguments": {"operation": "powerflow.ac"}},
            ]},
            later_authority,
        ],
        "admission-current-guide",
    )
    original_prompt = validation_run.ScriptedApplicationTransport.prompt_and_wait

    def guide_prompt(self: object, *args: object, **kwargs: object) -> str:
        question = args[0]
        response = original_prompt(self, *args, **kwargs)
        if question in (guide_question, parameter_question):
            resource_id = "contingency-analysis" if question == guide_question else "ac-powerflow"
            correlation_id = kwargs.get("correlation_id")
            assert isinstance(correlation_id, str)
            _emit_guide_event(
                self,
                kwargs.get("on_semantic_event"),
                turn_id=correlation_id,
                resource_id=resource_id,
                ok=True,
                result=_published_guide(self, resource_id),
            )
            return reader_text if question == guide_question else parameter_text
        return response

    monkeypatch.setattr(
        validation_run.ScriptedApplicationTransport, "prompt_and_wait", guide_prompt
    )
    execution = execute_application_case(
        case, runs_root=tmp_path / "runs", timeout_seconds=17.0
    )

    first_turn, guide_turn, parameter_turn, later_turn = execution.controller.finalized_turns
    guide_admission = _turn_admission(guide_turn)
    assert first_turn.status == "success"
    assert guide_turn.status == "success"
    assert guide_turn.answer_output == reader_text
    assert guide_turn.result_refs == ()
    assert guide_turn.evidence_refs == ()
    assert guide_admission.mode == "offline_information"
    assert guide_admission.assurance == "guide_access_verified"
    assert execution.outcome.status == "completed"
    assert execution.outcome.completed_questions == 4
    assert parameter_turn.status == "success"
    assert parameter_turn.answer_output == parameter_text
    assert _turn_admission(parameter_turn).assurance == "guide_access_verified"
    assert parameter_turn.result_refs == parameter_turn.evidence_refs == ()
    assert later_turn.status == "success"
    assert later_turn.result_refs


@pytest.mark.parametrize(
    ("name", "guide_turn", "next_question"),
    (
        ("no-guide", None, "N-1静态安全校核需要检查哪些越限类型?"),
        ("failed-guide", ("contingency-analysis", False), "N-1静态安全校核需要检查哪些越限类型?"),
        ("wrong-guide-body", ("contingency-analysis", True), "N-1静态安全校核需要检查哪些越限类型?"),
        ("prior-turn-guide", ("contingency-analysis", True), "这一题没有读取当前指南且没有任何结果引用。"),
    ),
)
def test_only_current_successful_published_guide_can_admit_zero_reference_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    guide_turn: tuple[str, bool] | None,
    next_question: str,
) -> None:
    first_question = "N-1静态安全校核需要检查哪些越限类型?"
    case = _questions_case(
        [
            {"id": "first", "text": first_question, "steps": []},
            {"id": "second", "text": next_question, "steps": []},
        ],
        f"admission-{name}",
    )
    original_prompt = validation_run.ScriptedApplicationTransport.prompt_and_wait

    def guide_prompt(self: object, *args: object, **kwargs: object) -> str:
        question = args[0]
        response = original_prompt(self, *args, **kwargs)
        if guide_turn is not None and question == first_question:
            resource_id, ok = guide_turn
            correlation_id = kwargs.get("correlation_id")
            assert isinstance(correlation_id, str)
            result: Mapping[str, object]
            if name == "wrong-guide-body":
                result = {"resource_id": resource_id, "text": "untrusted replacement"}
            else:
                result = _published_guide(self, resource_id)
            _emit_guide_event(
                self,
                kwargs.get("on_semantic_event"),
                turn_id=correlation_id,
                resource_id=resource_id,
                ok=ok,
                result=result,
            )
        return response

    monkeypatch.setattr(
        validation_run.ScriptedApplicationTransport, "prompt_and_wait", guide_prompt
    )
    execution = execute_application_case(
        case, runs_root=tmp_path / "runs", timeout_seconds=17.0
    )

    turns = execution.controller.finalized_turns
    assert len(turns) == 2
    assert execution.outcome.status == "completed"
    target = turns[-1]
    if name == "prior-turn-guide":
        assert len(turns) == 2
        first_turn = turns[0]
        prior_admission = _turn_admission(first_turn)
        assert first_turn.status == "success"
        assert prior_admission.mode == "offline_information"
        assert prior_admission.assurance == "guide_access_verified"
    admission = _turn_admission(target)
    assert target.status == "limited"
    assert target.result_refs == ()
    assert target.evidence_refs == ()
    assert admission.mode == "limited"
    assert admission.assurance == "limited"


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
