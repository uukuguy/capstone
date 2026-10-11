import json
from pathlib import Path
from types import SimpleNamespace
import pytest


def test_latency_receipt_separates_queue_and_recognition_and_flags_slow_information():
    from validation.deployment.run import summarize_timing
    events = [SimpleNamespace(event_type=kind, occurred_at=stamp, payload=payload) for kind, stamp, payload in [
        ("command_accepted", "2026-10-11T12:00:00Z", {}),
        ("attempt_started", "2026-10-11T12:00:02Z", {}),
        ("task_recognition_timing", "2026-10-11T12:00:09Z", {"duration_ms": 7000, "details": {"calls": []}}),
        ("attempt_failed", "2026-10-11T12:00:11Z", {})]]
    timing = summarize_timing(events, elapsed_ms=11500, expectation="model-and-capabilities")
    assert timing["queue_ms"] == 2000 and timing["server_total_ms"] == 11000
    assert timing["phases"]["recognition"]["duration_ms"] == 7000
    assert timing["first_tool_ms"] is None
    assert set(timing["latency_review"]) == {"informational_turn_over_10s", "recognition_over_5s"}
    assert timing["review_status"] == "required"


def test_overview_clarification_cannot_pass_as_requested_information():
    from validation.deployment.checks import check_answer
    payload = {"answer": "请选择所需分析操作。", "result_refs": [], "evidence_refs": [],
               "admission": {"mode": "offline_information", "diagnostic_codes": ["task_clarification_verified"]}}
    assert "requested_information_missing" in check_answer("model-and-capabilities", payload)

from validation.deployment.checks import check_answer


@pytest.mark.parametrize("route,expected", [
    ("professional", []),
    ("general", ["professional_route_missing"]),
    ("invalid", ["professional_route_missing"]),
])
def test_routing_acceptance_does_not_claim_research_completion(route, expected):
    from validation.deployment.checks import check_professional_route
    event = SimpleNamespace(event_type="task_route_created", payload={"routing": {"route": route}})
    assert check_professional_route([event]) == expected
    assert check_professional_route([]) == ["professional_route_missing"]


def test_route_sample_stops_before_downstream_research_terminal():
    from validation.deployment.run import run_turn
    active = SimpleNamespace(id="context", selection_revision="selection", model_revision="revision")
    snapshot = SimpleNamespace(last_event_seq=0, active_model_context=active)
    events = [SimpleNamespace(event_type=kind, occurred_at=stamp, payload=payload,
        attempt_id="attempt_test", model_context_id="context", selection_revision="selection")
        for kind, stamp, payload in [
            ("command_accepted", "2026-10-12T00:00:00Z", {}),
            ("task_recognition_timing", "2026-10-12T00:00:01Z", {"duration_ms": 900}),
            ("task_route_created", "2026-10-12T00:00:01Z", {"routing": {"route": "professional"}})]]
    commands = []
    class Session:
        thread_id = "thread"
        def snapshot(self): return snapshot
        def command(self, kind, payload):
            if kind == "cancel_live_attempt":
                assert payload == {"attempt_id": "attempt_test"}
            commands.append(kind)
            return SimpleNamespace(status="accepted", target={"attempt_id": "attempt_test"})
        def events(self, **kwargs): return SimpleNamespace(next_event_seq=3, events=events)
    result = run_turn(Session(), {"text": "open research question", "expect": "professional-routing",
        "acceptance_stage": "intent-routing"}, {"profile_id": "test", "profile_version": "1"})
    assert result["status"] == "passed" and result["research_completion"] == "deferred"
    assert result["terminal"] == "routing_stage_observed"
    assert result["timing"]["routing_ready_ms"] == 1000
    assert result["timing"]["phases"]["recognition"]["duration_ms"] == 900
    assert commands == ["send_auto", "cancel_live_attempt"]


@pytest.mark.parametrize("answer", [
    "支持潮流、负荷修改和支路 N-1 分析。",
    "我无法确认39母线系统的线路情况，也无法提供分析。",
])
def test_mechanical_overview_checks_do_not_infer_meaning_from_words(answer):
    # These texts require semantic review. Neither word presence nor absence
    # establishes whether the requested model description is correct.
    assert check_answer("model-and-capabilities", {
        "answer": answer, "result_refs": [], "evidence_refs": [],
        "admission": {"diagnostic_codes": ["task_information_verified"]}}) == []


def test_public_process_prefix_blocks_chinese_handoff():
    assert "process_prefix" in check_answer("result-or-object-clarification", {
        "answer": "Clarify: 请确认线路标识。", "result_refs": [], "evidence_refs": []})


def test_calculation_without_current_run_evidence_blocks_handoff():
    assert "evidence_missing" in check_answer("calculation-or-object-clarification", {
        "answer": "跳闸后线路重载。", "result_refs": ["result:one"], "evidence_refs": []})


def test_required_calculation_cannot_pass_as_clarification():
    assert "required_calculation_missing" in check_answer("calculation-required", {
        "answer": "请明确对象及指标。", "result_refs": [], "evidence_refs": [],
        "admission": {"mode": "offline_information", "diagnostic_codes": ["task_clarification_verified"]}})


def test_evidence_cannot_hide_partial_task_coverage():
    assert "required_calculation_missing" in check_answer("calculation-required", {
        "answer": "部分任务已完成。", "result_refs": ["result:r"], "evidence_refs": ["evidence:e"],
        "admission": {"mode": "authority_backed", "diagnostic_codes": ["task_goal_coverage_partial"]}})


def test_overall_corpus_records_real_incidents_and_separate_update_selection():
    from validation.deployment.run import load_samples
    manifest = json.loads((Path(__file__).parent / "deployment/ieee39.json").read_text())
    assert len(manifest["cases"]) == 9
    assert manifest["suite_kind"] == "overall"
    assert set(manifest["incident_records"]) == {case["id"] for case in manifest["cases"]}
    for incident in manifest["incident_records"].values():
        assert incident["failure"] and incident["semantic_requirements"]
        assert (Path(__file__).parent / "deployment" / incident["source"]).is_file()
    update, hashes = load_samples(Path(__file__).parent / "deployment/task-answer-update.json")
    assert update["suite_kind"] == "update"
    assert [case["id"] for case in update["cases"]] == ["generation-n1", "model-overview", "clarification-to-overview"]
    assert len(hashes) == 2
    assert manifest["acceptance"]["skipped_is_pending"]


def test_update_cannot_silently_skip_unknown_historical_case(tmp_path):
    from validation.deployment.run import load_samples
    (tmp_path / "overall.json").write_text(json.dumps({"schema": "capstone-deployment-samples/2", "suite_kind": "overall", "cases": []}))
    update = tmp_path / "update.json"
    update.write_text(json.dumps({"schema": "capstone-deployment-samples/2", "suite_kind": "update", "corpus": "overall.json", "case_ids": ["missing"]}))
    with pytest.raises(ValueError):
        load_samples(update)


def test_update_rejects_duplicate_case_ids_in_overall_corpus(tmp_path):
    from validation.deployment.run import load_samples
    (tmp_path / "overall.json").write_text(json.dumps({"schema": "capstone-deployment-samples/2", "suite_kind": "overall",
        "cases": [{"id": "same", "turns": [{"text": "原始问题"}]}, {"id": "same", "turns": [{"text": "替代问题"}]}]}))
    update = tmp_path / "update.json"
    update.write_text(json.dumps({"schema": "capstone-deployment-samples/2", "suite_kind": "update", "corpus": "overall.json", "case_ids": ["same"]}))
    with pytest.raises(ValueError, match="sample_cases_invalid"):
        load_samples(update)


def test_provider_runner_requires_authorization_before_any_network(monkeypatch):
    from validation.deployment import run
    monkeypatch.setattr(run, "HttpThreadSession", lambda *args: pytest.fail("unauthorized network"))
    with pytest.raises(SystemExit) as error:
        run.main([])
    assert error.value.code == 2


def test_current_failed_attempt_cannot_pass_using_historical_success():
    from validation.deployment.run import run_turn
    active = SimpleNamespace(id="ctx", selection_revision="sel", model_revision="rev")
    events = [SimpleNamespace(attempt_id="old", event_type="attempt_completed", payload={"answer": "历史回答"}),
              SimpleNamespace(attempt_id="current", event_type="attempt_failed", payload={"error_code": "task_resolution_failed"},
                              model_context_id="ctx", selection_revision="sel")]
    session = SimpleNamespace(thread_id="thread", snapshot=lambda: SimpleNamespace(last_event_seq=1, active_model_context=active, result_projections=[]),
        command=lambda *args: SimpleNamespace(status="accepted", target={"attempt_id": "current"}),
        events=lambda **kwargs: SimpleNamespace(next_event_seq=3, events=events))
    result = run_turn(session, {"text": "介绍当前电网", "expect": "model-and-capabilities"},
                      {"profile_id": "grid", "profile_version": "1"})
    assert result["status"] == "failed"
    assert result["failures"] == ["attempt_failed"]


def test_result_reference_without_attempt_projection_cannot_pass():
    from validation.deployment.run import run_turn
    active = SimpleNamespace(id="ctx", selection_revision="sel", model_revision="rev")
    event = SimpleNamespace(attempt_id="current", event_type="attempt_completed", model_context_id="ctx", selection_revision="sel",
        payload={"answer": "线路跳闸后存在重载。", "result_refs": ["result:one"], "evidence_refs": ["evidence:one"]})
    session = SimpleNamespace(thread_id="thread", snapshot=lambda: SimpleNamespace(last_event_seq=1, active_model_context=active, result_projections=[]),
        command=lambda *args: SimpleNamespace(status="accepted", target={"attempt_id": "current"}),
        events=lambda **kwargs: SimpleNamespace(next_event_seq=2, events=[event]))
    result = run_turn(session, {"text": "线路跳闸", "expect": "calculation-or-object-clarification"}, {"profile_id": "grid", "profile_version": "1"})
    assert result["failures"] == ["current_run_projection_missing"]


def test_positive_api_screening_does_not_claim_provider_or_business_acceptance(monkeypatch, tmp_path):
    from validation.deployment import run
    samples = tmp_path / "samples.json"
    samples.write_text(json.dumps({"schema": "capstone-deployment-samples/2", "suite_id": "test", "suite_kind": "overall", "model_id": "ieee39", "cases": [{"id": "overview", "turns": [{"text": "介绍"}]}]}))
    class Session:
        def __init__(self, *args): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def create(self, model): pass
    monkeypatch.setenv("CAPSTONE_SAMPLE_API_ORIGIN", "http://127.0.0.1:8767")
    monkeypatch.setenv("CAPSTONE_SAMPLE_OPERATOR_TOKEN", "private-test-token")
    monkeypatch.setattr(run, "HttpThreadSession", Session)
    monkeypatch.setattr(run, "run_turn", lambda *args: {"status": "passed"})
    assert run.main(["--allow-provider", "--samples", str(samples), "--receipt-dir", str(tmp_path)]) == 0
    content = next(tmp_path.glob("provider-*.json")).read_text()
    receipt = json.loads(content)
    assert receipt["automated_screening"] == "passed"
    assert receipt["business_samples"].startswith("pending_")
    assert receipt["provider_execution_identity"] == "unverified"
    assert receipt["mode"] == "deployed-api-screening"
    assert "private-test-token" not in content


@pytest.mark.parametrize("terminal", ["attempt_completed", "attempt_failed"])
def test_bad_answer_does_not_skip_the_next_conversation_turn(monkeypatch, tmp_path, terminal):
    from validation.deployment import run
    samples = tmp_path / "samples.json"
    samples.write_text(json.dumps({"schema": "capstone-deployment-samples/2", "suite_id": "continuity",
        "suite_kind": "overall", "model_id": "ieee39", "cases": [{"id": "continuous", "turns": [{"text": "先澄清"}, {"text": "再介绍"}]}]}))
    class Session:
        def __init__(self, *args): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def create(self, model): pass
    executed = []
    def turn(*args):
        executed.append(args[1]["text"])
        return {"status": "failed" if len(executed) == 1 else "passed", "terminal": terminal}
    monkeypatch.setenv("CAPSTONE_SAMPLE_API_ORIGIN", "http://127.0.0.1:8767")
    monkeypatch.setenv("CAPSTONE_SAMPLE_OPERATOR_TOKEN", "private-test-token")
    monkeypatch.setattr(run, "HttpThreadSession", Session)
    monkeypatch.setattr(run, "run_turn", turn)
    assert run.main(["--allow-provider", "--samples", str(samples), "--receipt-dir", str(tmp_path)]) == 1
    assert executed == ["先澄清", "再介绍"]
