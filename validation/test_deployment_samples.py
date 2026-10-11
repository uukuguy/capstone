import json
from pathlib import Path
from types import SimpleNamespace
import pytest

from validation.deployment.checks import check_answer


def test_overview_cannot_pass_with_only_generic_capability_prose():
    assert "model_description_missing" in check_answer("model-and-capabilities", {
        "answer": "支持潮流、负荷修改和支路 N-1 分析。", "result_refs": [], "evidence_refs": []})


def test_public_process_prefix_blocks_chinese_handoff():
    assert "process_prefix" in check_answer("result-or-object-clarification", {
        "answer": "Clarify: 请确认线路标识。", "result_refs": [], "evidence_refs": []})


def test_calculation_without_current_run_evidence_blocks_handoff():
    assert "evidence_missing" in check_answer("calculation-or-object-clarification", {
        "answer": "跳闸后线路重载。", "result_refs": ["result:one"], "evidence_refs": []})


def test_sample_set_contains_overall_and_update_scopes():
    manifest = json.loads((Path(__file__).parent / "deployment/ieee39.json").read_text())
    assert len(manifest["overall"]) == 5
    assert set(manifest["update"]) == {"formal-answer", "runtime-window"}
    assert manifest["acceptance"]["skipped_is_pending"]


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
    samples.write_text(json.dumps({"model_id": "ieee39", "overall": [{"id": "overview", "turns": [{"text": "介绍"}]}]}))
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
