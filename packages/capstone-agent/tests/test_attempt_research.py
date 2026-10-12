from __future__ import annotations

import json
from types import SimpleNamespace

from capstone_agent.attempt_research import AttemptResearch


def test_worker_guard_prevents_research_write_after_cancellation(tmp_path):
    from capstone_agent.harness import HarnessPiClient
    from capstone_agent.kernel_pi_session import _KernelPiPromptSession
    research = AttemptResearch(tmp_path, thread_id="thr_one", run_id="run_one",
        attempt_id="attempt_one", is_active=lambda: False, admit_reference=lambda _: False)
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
        attempt_id="attempt_one", is_active=lambda: True, admit_reference=lambda _: False)
    second = AttemptResearch(tmp_path, thread_id="thr_one", run_id="run_one",
        attempt_id="attempt_two", is_active=lambda: True, admit_reference=lambda _: False)
    assert first.channel.root != second.channel.root
    identity = json.loads(first.identity_path.read_text())
    assert identity["thread_id"] == "thr_one"
    assert identity["run_id"] == "run_one"
    assert identity["attempt_id"] == "attempt_one"
    assert identity["research_id"] == first.controller.research_id
    assert first.research_id != second.research_id
    assert first.research_id.removeprefix("research-") != first.turn_id.removeprefix("turn-")
    assert first.controller.read() is None


def test_ended_attempt_retains_research_and_rejects_new_updates(tmp_path):
    active = [True]
    research = AttemptResearch(tmp_path, thread_id="thr_one", run_id="run_one",
        attempt_id="attempt_one", is_active=lambda: active[0], admit_reference=lambda _: False)
    request = {"request_id": "update-1", "expected_revision": 0,
        "changes": {"goal": "Assess the selected model"}}
    (research.channel.requests_path / "update-1.json").write_text(json.dumps(request))
    research.channel.drain()
    assert research.controller.read().revision == 1
    research.close(failed=False)
    request.update(request_id="update-2", expected_revision=1)
    (research.channel.requests_path / "update-2.json").write_text(json.dumps(request))
    research.channel.drain()
    receipt = json.loads((research.channel.receipts_path / "update-2.json").read_text())
    assert receipt["status"] == "rejected"
    assert research.controller.read().revision == 1


def test_pi_services_research_requests_and_closes_state_on_stop(tmp_path):
    from capstone_agent.kernel_pi_session import _KernelPiPromptSession
    research = AttemptResearch(tmp_path, thread_id="thr_one", run_id="run_one",
        attempt_id="attempt_one", is_active=lambda: True, admit_reference=lambda _: False)
    def prompt(question, **kwargs):
        request = {"request_id": "update-1", "expected_revision": 0,
                   "changes": {"goal": question}}
        (research.channel.requests_path / "update-1.json").write_text(json.dumps(request))
        kwargs["on_control_requests"]()
        assert research.controller.read().goal == question
        return "Outcome"
    session = _KernelPiPromptSession(
        SimpleNamespace(timeout_seconds=30, prompt_and_wait=prompt, stop=lambda: None),
        SimpleNamespace(append=lambda *_: None, close=lambda: None),
        admission=lambda *args: "admitted", research=research)
    session.prompt_and_wait("Assess the model", on_semantic_event=lambda _: None,
                            correlation_id="attempt_one", on_heartbeat=lambda: None)
    session.admit_attempt(None, "Outcome", (), (), ())
    session.stop()
    assert not research.channel.is_active()
