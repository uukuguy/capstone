from __future__ import annotations

import json
import pytest
from types import SimpleNamespace

from capstone_agent.attempt_research import AttemptResearch
from capstone_agent.thread_protocol import ModelContextSnapshot

MODEL = ModelContextSnapshot("ctx_one", "model-one", "revision:current", "pandapower", "sel_0")


def test_unfinished_research_requires_thread_terminal_proof_before_recovery(tmp_path):
    def open_task(attempt):
        return AttemptResearch(tmp_path, thread_id="thr_one", run_id="run_one",
            attempt_id=attempt, model_context=MODEL, is_active=lambda: True, admit_reference=lambda _: False)
    old = open_task("attempt_one")
    old.controller.update({"request_id": "save-1", "expected_revision": 0,
                           "changes": {"goal": "Retain completed observations"}})
    resumed = open_task("attempt_two")
    assert not resumed.channel.is_active()
    with pytest.raises(RuntimeError, match="verified terminal"):
        resumed.bind_active_check(lambda: True, lambda _: None)
    assert resumed.store.snapshot.core.active_turn["attempt_id"] == "attempt_one"
    resumed.bind_active_check(lambda: True, lambda attempt: "interrupted" if attempt == "attempt_one" else None)
    assert resumed.channel.is_active()
    assert resumed.controller.read().goal == "Retain completed observations"
    assert resumed.store.snapshot.core.turns[-1]["terminal_phase"] == "interrupted"
    resumed.close(failed=False)


def test_switch_back_restores_default_research_and_keeps_task_history(tmp_path):
    def open_task(attempt, model):
        return AttemptResearch(tmp_path, thread_id="thr_one", run_id="run_one",
            attempt_id=attempt, model_context=model, is_active=lambda: True, admit_reference=lambda _: False)
    first = open_task("attempt_one", MODEL)
    first.controller.update({"request_id": "save-1", "expected_revision": 0,
                             "changes": {"goal": "Compare candidate actions"}})
    first.close(failed=False)
    other_model = ModelContextSnapshot("ctx_two", "model-two", "revision:other", "pandapower", "sel_1")
    other = open_task("attempt_two", other_model)
    assert other.controller.read() is None
    assert other.research_id != first.research_id
    other.close(failed=False)
    restored = open_task("attempt_three", MODEL)
    assert restored.research_id == first.research_id
    assert restored.controller.read().goal == "Compare candidate actions"
    assert len(restored.store.snapshot.core.turns) == 1
    assert first.identity_path.exists()
    assert restored.identity_path != first.identity_path
    restored.close(failed=False)


def test_worker_guard_prevents_research_write_after_cancellation(tmp_path):
    from capstone_agent.harness import HarnessPiClient
    from capstone_agent.kernel_pi_session import _KernelPiPromptSession
    research = AttemptResearch(tmp_path, thread_id="thr_one", run_id="run_one",
        attempt_id="attempt_one", model_context=MODEL, is_active=lambda: False, admit_reference=lambda _: False)
    session = _KernelPiPromptSession(SimpleNamespace(), SimpleNamespace(), admission=None, research=research)
    runtime = HarnessPiClient(session)
    cancelled = [False]
    runtime.bind_attempt_guard(lambda: not cancelled[0])
    assert research.channel.is_active()
    cancelled[0] = True
    request = {"request_id": "update-1", "expected_revision": 0,
               "changes": {"goal": "Do not commit after cancellation"}}
    (research.channel.requests_path / "update-1.json").write_text(json.dumps(request))
    research.channel.drain()
    receipt = json.loads((research.channel.receipts_path / "update-1.json").read_text())
    assert receipt["code"] == "attempt_closed"
    assert research.controller.read() is None


def test_research_isolated_by_attempt_and_preserves_thread_identity(tmp_path):
    first = AttemptResearch(tmp_path, thread_id="thr_one", run_id="run_one",
        attempt_id="attempt_one", model_context=MODEL, is_active=lambda: True, admit_reference=lambda _: False)
    first.close(failed=False)
    second = AttemptResearch(tmp_path, thread_id="thr_one", run_id="run_one",
        attempt_id="attempt_two", model_context=MODEL, is_active=lambda: True, admit_reference=lambda _: False)
    assert first.channel.root != second.channel.root
    identity = json.loads(first.identity_path.read_text())
    assert identity["thread_id"] == "thr_one"
    assert identity["run_id"] == "run_one"
    assert identity["attempt_id"] == "attempt_one"
    assert identity["baseline_model_context"] == MODEL.to_document()
    assert identity["research_id"] == first.controller.research_id
    assert first.research_id == second.research_id
    assert first.research_id.removeprefix("research-") != first.turn_id.removeprefix("turn-")
    assert first.controller.read() is None
    assert first.current_projection() is None


def test_ended_attempt_retains_research_and_rejects_new_updates(tmp_path):
    active = [True]
    research = AttemptResearch(tmp_path, thread_id="thr_one", run_id="run_one",
        attempt_id="attempt_one", model_context=MODEL, is_active=lambda: active[0], admit_reference=lambda _: False)
    request = {"request_id": "update-1", "expected_revision": 0,
        "changes": {"goal": "Assess the selected model"}}
    (research.channel.requests_path / "update-1.json").write_text(json.dumps(request))
    research.channel.drain()
    assert research.controller.read().revision == 1
    projection = research.current_projection()
    assert projection["goal"] == "Assess the selected model"
    assert projection["baseline_model_context"] == MODEL.to_document()
    research.close(failed=False)
    request.update(request_id="update-2", expected_revision=1)
    (research.channel.requests_path / "update-2.json").write_text(json.dumps(request))
    research.channel.drain()
    receipt = json.loads((research.channel.receipts_path / "update-2.json").read_text())
    assert receipt["status"] == "rejected"
    assert research.controller.read().revision == 1


def test_committed_projection_preserves_claims_and_notes_as_of_revision(tmp_path):
    from capstone_agent.harness import normalize_runtime_event
    research = AttemptResearch(tmp_path, thread_id="thr_one", run_id="run_one",
        attempt_id="attempt_one", model_context=MODEL, is_active=lambda: True,
        admit_reference=lambda ref: ref == "evidence:one")
    research.controller.update({"request_id": "save-1", "expected_revision": 0,
        "changes": {"goal": "Assess selected model", "claims": [{"claim_id": "claim-1",
            "statement": "Check remains open", "status": "pending", "refs": []}],
            "notes": [{"note_id": "note-1", "text": "A calculation failed", "refs": ["evidence:one"]}]}})
    projection = research.current_projection()
    event = normalize_runtime_event({"type": "research_state", **projection}, runtime_mode="capstone")
    snapshot = event["payload"]["research_snapshot"]
    assert snapshot["claims"][0]["status"] == "pending"
    assert snapshot["notes"][0]["refs"] == ["evidence:one"]
    research.controller.update({"request_id": "save-2", "expected_revision": 1,
        "changes": {"goal": "A later task"}})
    assert snapshot["goal"] == "Assess selected model"
    assert snapshot["revision"] == 1
    with pytest.raises(ValueError, match="identity does not match"):
        normalize_runtime_event({"type": "research_state", **projection,
            "research_revision": 2}, runtime_mode="capstone")


def test_research_snapshot_transport_preserves_large_committed_records(tmp_path):
    from capstone_agent.thread_service import _validate_runtime_payload
    research = AttemptResearch(tmp_path, thread_id="thr_one", run_id="run_one",
        attempt_id="attempt_one", model_context=MODEL, is_active=lambda: True, admit_reference=lambda _: False)
    research.controller.update({"request_id": "save-1", "expected_revision": 0,
        "changes": {"goal": "Assess selected model", "notes": [
            {"note_id": f"note-{index}", "text": "研究记录" * 400, "refs": []} for index in range(64)]}})
    projection = research.current_projection()
    assert len(json.dumps(projection, ensure_ascii=False).encode()) > 64 * 1024
    _validate_runtime_payload("research_state_updated", projection, None)


def test_pi_services_research_requests_and_closes_state_on_stop(tmp_path):
    from capstone_agent.kernel_pi_session import _KernelPiPromptSession
    from capstone_agent.harness import normalize_runtime_event
    events = []
    research = AttemptResearch(tmp_path, thread_id="thr_one", run_id="run_one",
        attempt_id="attempt_one", model_context=MODEL, is_active=lambda: True, admit_reference=lambda _: False)
    def prompt(question, **kwargs):
        request = {"request_id": "update-1", "expected_revision": 0,
                   "changes": {"goal": question}}
        (research.channel.requests_path / "update-1.json").write_text(json.dumps(request))
        kwargs["on_control_requests"]()
        kwargs["on_control_requests"]()
        assert research.controller.read().goal == question
        return "Outcome"
    session = _KernelPiPromptSession(
        SimpleNamespace(timeout_seconds=30, prompt_and_wait=prompt, stop=lambda: None),
        SimpleNamespace(append=lambda *_: None, close=lambda: None),
        admission=lambda *args: "admitted", research=research)
    session.prompt_and_wait("Assess the model", on_semantic_event=events.append,
                            correlation_id="attempt_one", on_heartbeat=lambda: None)
    assert len(events) == 1
    event = normalize_runtime_event(events[0], runtime_mode="capstone")
    assert event["event_type"] == "research_state_updated"
    assert event["payload"]["goal"] == "Assess the model"
    assert "result_refs" not in event["payload"]
    session.admit_attempt(None, "Outcome", (), (), ())
    session.stop()
    assert not research.channel.is_active()
