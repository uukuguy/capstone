from __future__ import annotations

from capstone_agent.harness import AdmittedAttemptAnswer, HarnessAttemptRunner, HarnessPiClient
from test_harness import _thread_service
import pytest


def claim_attempt(service):
    service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_failure_delivery",
        "idempotency_key": "idem_failure_delivery", "thread_id": "thr_harness",
        "run_id": "run_harness", "kind": "send_professional", "expected_event_seq": 0,
        "payload": {"text": "Inspect the selected model and report the findings"},
    })
    claim = service.claim_attempt("worker", lease_seconds=30)
    assert claim is not None
    return claim


class Session:
    def start(self):
        pass

    def stop(self):
        pass

    def prompt_and_wait(self, question, **kwargs):
        raise RuntimeError("private provider details must not reach the answer")


def test_runtime_failure_delivers_a_persisted_reader_outcome_without_raw_errors():
    service = _thread_service()
    result = HarnessAttemptRunner(service, HarnessPiClient(Session())).run(claim_attempt(service))
    terminal = service.read_events("thr_harness", 0).events[-1]
    assert result.status == "failed"
    assert isinstance(result.answer, str) and result.answer.strip()
    assert terminal.payload["answer"] == result.answer
    assert terminal.payload["outcome"]["status"] == "blocked"
    assert terminal.payload["outcome"]["stage"] == "execution"
    assert "private provider" not in result.answer
    assert "runtime_failed" not in result.answer


def test_admission_failure_returns_feedback_to_the_same_session_once():
    service = _thread_service()

    class RecoveringSession(Session):
        prompts = 0
        recoveries = []

        def prompt_and_wait(self, question, **kwargs):
            self.prompts += 1
            return "Initial answer"

        def recover_after_failure(self, feedback, **kwargs):
            self.recoveries.append(feedback)
            return "The requested check could not be completed; the missing evidence is identified."

    session = RecoveringSession()
    checks = []

    def admit(claim, answer, *args):
        checks.append(answer)
        if len(checks) == 1:
            raise ValueError("private validation details")
        return AdmittedAttemptAnswer(answer, "limited", "limited")

    result = HarnessAttemptRunner(service, HarnessPiClient(session, admission=admit)).run(claim_attempt(service))
    assert result.status == "completed"
    assert session.prompts == 1
    assert len(session.recoveries) == 1
    assert session.recoveries[0]["stage"] == "answer_check"
    assert "private validation" not in str(session.recoveries)
    assert result.answer == checks[-1]


def test_failed_recovery_is_bounded_and_does_not_publish_rejected_answer():
    service = _thread_service()

    class RejectedSession(Session):
        recoveries = 0

        def prompt_and_wait(self, question, **kwargs):
            return "Unverified numerical conclusion"

        def recover_after_failure(self, feedback, **kwargs):
            self.recoveries += 1
            return "Still unverified numerical conclusion"

    def reject(*args):
        raise ValueError("reference check failed")

    session = RejectedSession()
    result = HarnessAttemptRunner(service, HarnessPiClient(session, admission=reject)).run(claim_attempt(service))
    terminal = service.read_events("thr_harness", 0).events[-1]
    assert result.status == "failed"
    assert session.recoveries == 1
    assert terminal.payload["outcome"]["recovery"] == "attempted"
    assert "unverified numerical" not in result.answer.lower()
    assert result.result_refs == result.evidence_refs == ()


def test_runtime_failure_retains_only_application_admitted_partial_artifacts():
    service = _thread_service()
    result_ref = "result:sha256:" + "a" * 64
    evidence_ref = "evidence:sha256:" + "b" * 64

    class PartlyFinishedSession(Session):
        def prompt_and_wait(self, question, **kwargs):
            kwargs["on_semantic_event"]({
                "type": "tool_result", "tool_name": "grid_analysis_run", "ok": True,
                "capability": "analysis.run", "result_refs": [result_ref], "evidence_refs": [evidence_ref],
            })
            raise RuntimeError("provider disconnected after calculation")

    def admit(claim, answer, results, evidence, events):
        assert results == (result_ref,) and evidence == (evidence_ref,)
        return AdmittedAttemptAnswer(answer, "authority_backed", "lineage_verified", results, evidence)

    result = HarnessAttemptRunner(service, HarnessPiClient(PartlyFinishedSession(), admission=admit)).run(claim_attempt(service))
    events = service.read_events("thr_harness", 0).events
    assert result.status == "failed"
    assert result.result_refs == (result_ref,)
    assert result.evidence_refs == (evidence_ref,)
    assert events[-1].payload["outcome"]["status"] == "partial"
    assert events[-1].payload["admission"]["assurance"] == "lineage_verified"
    assert any(event.event_type == "tool_completed" for event in events)


def test_uncertain_terminal_write_is_not_replaced_by_a_failed_outcome(monkeypatch):
    service = _thread_service()
    claim = claim_attempt(service)
    writes = []

    class FinishedSession(Session):
        def prompt_and_wait(self, question, **kwargs):
            return "No supported conclusion."

    def uncertain_write(*args, **kwargs):
        writes.append(kwargs["phase"])
        raise RuntimeError("terminal storage unavailable")

    monkeypatch.setattr(service, "finish_attempt", uncertain_write)
    runtime = HarnessPiClient(FinishedSession(), admission=lambda claim, answer, *args: AdmittedAttemptAnswer(answer, "limited", "limited"))
    with pytest.raises(RuntimeError, match="terminal storage unavailable"):
        HarnessAttemptRunner(service, runtime).run(claim)
    assert writes == ["completed"]


def test_pi_correction_uses_same_client_and_remaining_attempt_budget(monkeypatch):
    from types import SimpleNamespace
    from capstone_agent.kernel_pi_session import _KernelPiPromptSession

    calls = []
    now = [100.0]
    monkeypatch.setattr("capstone_agent.kernel_pi_session.time.monotonic", lambda: now[0])

    def prompt(question, **kwargs):
        calls.append((question, kwargs["timeout_seconds"]))
        return "Answer"

    client = SimpleNamespace(timeout_seconds=30, prompt_and_wait=prompt)
    session = _KernelPiPromptSession(client, SimpleNamespace(close=lambda: None), admission=None)
    arguments = dict(on_semantic_event=lambda event: None, correlation_id="same-attempt", on_heartbeat=lambda: None)
    session.prompt_and_wait("Original instruction", **arguments)
    now[0] = 120.0
    session.recover_after_failure({"stage": "answer_check"}, **arguments)
    assert [budget for _, budget in calls] == [30, 10]
    assert "Original instruction" not in calls[1][0]
    now[0] = 131.0
    with pytest.raises(TimeoutError):
        session.recover_after_failure({"stage": "answer_check"}, **arguments)
    assert len(calls) == 2
