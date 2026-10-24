from __future__ import annotations

from capstone_agent.harness import AdmittedAttemptAnswer, HarnessAttemptRunner, HarnessPiClient
from capstone_agent.harness import normalize_runtime_event
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


def test_routing_failure_still_persists_a_formal_reply():
    from capstone_agent.turn_router import DefaultTurnRouter, DecisionUnavailable

    class UnavailableRouter(DefaultTurnRouter):
        def plan(self, routing_input):
            raise DecisionUnavailable("llm_route_unavailable")

    service = _thread_service()
    outcome = HarnessAttemptRunner(service, HarnessPiClient(Session()), turn_router=UnavailableRouter()).run(claim_attempt(service))
    assert outcome.status == "failed"
    assert "尚未执行计算" in outcome.answer
    terminal = service.read_events("thr_harness", 0).events[-1]
    assert terminal.payload["answer"] == outcome.answer
    assert terminal.payload["outcome"]["stage"] == "routing"


def test_cancellation_still_persists_a_formal_reply(monkeypatch):
    from capstone_agent.harness import _AttemptCancelled

    service = _thread_service()
    runner = HarnessAttemptRunner(service, HarnessPiClient(Session()))
    monkeypatch.setattr(runner, "_renew_lease", lambda claim: (_ for _ in ()).throw(_AttemptCancelled()))
    outcome = runner.run(claim_attempt(service))
    assert outcome.status == "cancelled"
    assert outcome.answer
    assert service.read_events("thr_harness", 0).events[-1].payload["answer"] == outcome.answer


def test_tool_failure_keeps_bounded_reason_without_raw_error_details():
    event = normalize_runtime_event({
        "type": "tool_result", "event": "tool_result", "capability": "analysis.run",
        "ok": False, "error": {"code": "invalid_arguments", "phase": "validate",
            "message": "Missing required input; api_key=private-value",
            "details": {"raw_response": "private raw object"}},
    }, runtime_mode="capstone")
    assert event["payload"]["failure"]["code"] == "invalid_arguments"
    assert event["payload"]["failure"]["phase"] == "validate"
    assert "Missing required input" in event["payload"]["failure"]["message"]
    assert "private-value" not in str(event)
    assert "raw_response" not in str(event)


def test_session_preserves_request_and_links_semantic_event_to_persisted_trace():
    from types import SimpleNamespace
    from capstone_agent.kernel_pi_session import _KernelPiPromptSession
    records = []
    observations = []

    def append(kind, payload):
        records.append((kind, payload))
        return len(records)

    def prompt(question, **kwargs):
        kwargs["on_semantic_event"]({"type": "tool_result", "capability": "analysis.run", "ok": False}, 7)
        return "The calculation did not finish."

    session = _KernelPiPromptSession(SimpleNamespace(timeout_seconds=30, prompt_and_wait=prompt),
        SimpleNamespace(append=append), admission=None)
    session.prompt_and_wait("Inspect the active model", on_semantic_event=observations.append,
                            correlation_id="attempt-a", on_heartbeat=lambda: None)
    assert records[0][0] == "application_prompt"
    assert records[0][1]["question"] == "Inspect the active model"
    assert records[0][1]["correlation_id"] == "attempt-a"
    normalized = normalize_runtime_event(observations[0], runtime_mode="capstone")
    assert normalized["payload"]["trace_sequence"] == 7
    assert normalized["payload"]["trace_correlation_id"] == "attempt-a"


class Session:
    def start(self):
        pass

    def stop(self):
        pass

    def prompt_and_wait(self, question, **kwargs):
        raise RuntimeError("private provider details must not reach the answer")


@pytest.mark.parametrize("count", [131, 1024])
def test_reference_capacity_survives_tool_collection_admission_and_terminal_storage(count):
    from capstone_agent.thread_service import PriorResultReference

    service = _thread_service()
    results = tuple(f"result:sha256:{index:064x}" for index in range(count))
    evidence = tuple(f"evidence:sha256:{index:064x}" for index in range(count))

    class ManyReferences(Session):
        def prompt_and_wait(self, question, **kwargs):
            kwargs["on_semantic_event"]({
                "type": "tool_result", "tool_name": "analysis", "ok": True,
                "result_refs": results, "evidence_refs": evidence,
            })
            return "计算已完成，计算记录和证据可供查阅。"

    def admit(claim, answer, observed_results, observed_evidence, events):
        assert observed_results == results
        assert observed_evidence == evidence
        return AdmittedAttemptAnswer(answer, "authority_backed", "lineage_verified", results, evidence)

    outcome = HarnessAttemptRunner(service, HarnessPiClient(ManyReferences(), admission=admit)).run(claim_attempt(service))
    assert outcome.status == "completed"
    terminal = service.read_events("thr_harness", 0).events[-1]
    assert terminal.payload["answer"] == outcome.answer
    assert tuple(terminal.payload["evidence_refs"]) == evidence
    assert tuple(terminal.payload["result_refs"]) == results
    prior = PriorResultReference(results[0], evidence, "analysis", "attempt_previous")
    assert prior.evidence_refs == evidence


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


@pytest.mark.parametrize('code,reason', [
    ('native_continuation_no_progress', '后续动作未产生新的工具执行或已保存的状态进展'),
    ('native_transport_timeout', '执行器连接超时'),
    ('native_task_deadline', '执行时间上限'),
    ('native_contract_rejected', '系统校验未通过'),
    ('native_artifact_persistence_failed', '生成文件未能完整保存'),
    ('native_model_rate_limit', '模型服务限制'),
    ('native_model_context_limit', '上下文容量不足'),
    ('native_model_output_rejected', '模型服务拒绝'),
    ('native_model_turn_incomplete', '模型回复未正常结束'),
])
def test_native_failure_reason_reaches_saved_user_reply(code, reason):
    class FailedRuntime(HarnessPiClient):
        def prompt(self, question, *, on_event, **kwargs):
            on_event({'event_type': 'runtime_event', 'runtime_mode': 'capstone',
                'visibility': 'diagnostic', 'payload': {'child_status': 'failed',
                'failure_code': code, 'cancellation_confirmed': True}})
            raise RuntimeError('PRIVATE provider details')
    service = _thread_service()
    result = HarnessAttemptRunner(service, FailedRuntime(Session())).run(claim_attempt(service))
    terminal = service.read_events('thr_harness', 0).events[-1]
    assert reason in result.answer
    assert terminal.payload['error_code'] == code
    assert terminal.payload['answer'] == result.answer
    assert 'PRIVATE' not in result.answer


def test_executor_http_failure_saves_precise_allowlisted_cause_in_user_answer():
    class FailedRuntime(HarnessPiClient):
        def prompt(self, question, *, on_event, **kwargs):
            on_event({'event_type': 'runtime_event', 'runtime_mode': 'capstone',
                'visibility': 'diagnostic', 'payload': {'child_status': 'failed',
                'failure_code': 'native_executor_http_rejected', 'transport_failure': {
                    'operation': 'research_pending', 'http_status': 400,
                    'protocol_code': 'research_transport_file_changed'}}})
            raise RuntimeError('PRIVATE raw response')
    service = _thread_service()
    result = HarnessAttemptRunner(service, FailedRuntime(Session())).run(claim_attempt(service))
    terminal = service.read_events('thr_harness', 0).events[-1]
    assert terminal.payload['error_code'] == 'native_executor_http_rejected'
    assert terminal.payload['answer'] == result.answer
    assert 'research_pending' in result.answer and 'HTTP 400' in result.answer
    assert 'research_transport_file_changed' in result.answer and 'PRIVATE' not in result.answer
    from capstone_agent.failure_delivery import native_transport_summary
    assert native_transport_summary({'operation': 'PRIVATE', 'http_status': 400, 'protocol_code': 'invalid_task'}) == ''
    assert native_transport_summary({'operation': [], 'http_status': 400, 'protocol_code': 'invalid_task'}) == ''


def test_resource_deadline_saves_actual_operation_without_raw_transport_text():
    class FailedRuntime(HarnessPiClient):
        def prompt(self, question, *, on_event, **kwargs):
            on_event({'event_type':'runtime_event','runtime_mode':'capstone','visibility':'diagnostic',
                'payload':{'child_status':'failed','failure_code':'native_transport_timeout',
                    'transport_failure':{'operation':'resource_complete','transport_phase':'task_deadline'}}})
            raise RuntimeError('PRIVATE network details')
    service = _thread_service()
    result = HarnessAttemptRunner(service,FailedRuntime(Session())).run(claim_attempt(service))
    terminal = service.read_events('thr_harness',0).events[-1]
    assert terminal.payload['answer'] == result.answer
    assert 'resource_complete' in result.answer and 'task_deadline' in result.answer
    assert 'PRIVATE' not in result.answer


@pytest.mark.parametrize('timeout', [600, 1800, 3600])
def test_native_timeout_reports_actual_application_limit(timeout):
    class FailedRuntime(HarnessPiClient):
        def prompt(self, question, *, on_event, **kwargs):
            on_event({'event_type': 'runtime_event', 'runtime_mode': 'capstone',
                'visibility': 'diagnostic', 'payload': {'child_status': 'failed',
                'failure_code': 'native_deadline_exceeded', 'timeout_seconds': timeout}})
            raise TimeoutError('PRIVATE provider details')
    service = _thread_service()
    result = HarnessAttemptRunner(service, FailedRuntime(Session())).run(claim_attempt(service))
    terminal = service.read_events('thr_harness', 0).events[-1]
    assert f'{timeout} 秒' in result.answer
    assert terminal.payload['answer'] == result.answer
    assert terminal.payload['error_code'] == 'native_deadline_exceeded'
    assert 'PRIVATE' not in result.answer


@pytest.mark.parametrize('native', [False, True])
def test_capacity_failure_retains_typed_actual_limit_and_phase_without_raw_exception(native):
    from capstone_agent.application_capacity import CapacityExceeded, limits
    detail = CapacityExceeded('native_context_bytes', limits.native_context_bytes + 1,
                              limits.native_context_bytes, 'native_context').to_document()
    expected_code = 'native_capacity_exceeded' if native else 'capacity_exceeded'
    class FailedRuntime(HarnessPiClient):
        def prompt(self, question, *, on_event, **kwargs):
            if native:
                on_event({'event_type': 'runtime_event', 'runtime_mode': 'capstone',
                    'visibility': 'diagnostic', 'payload': {'child_status': 'failed',
                    'failure_code': expected_code, 'failure': {'code': expected_code,
                        'phase': 'native_context', 'capacity': detail, 'message': 'PRIVATE details'}}})
                raise RuntimeError('PRIVATE exception')
            raise CapacityExceeded('native_context_bytes', limits.native_context_bytes + 1,
                                   limits.native_context_bytes, 'native_context')
    service = _thread_service()
    result = HarnessAttemptRunner(service, FailedRuntime(Session())).run(claim_attempt(service))
    terminal = service.read_events('thr_harness', 0).events[-1]
    assert result.status == 'failed' and result.error_code == expected_code
    assert terminal.payload['failure'] == {'code': expected_code, 'phase': 'native_context', 'capacity': detail}
    assert '容量' in result.answer and 'PRIVATE' not in result.answer
    assert 'PRIVATE' not in str(terminal.payload)


def test_runtime_failure_describes_admitted_results_without_claiming_task_success():
    from test_result_projection import valid_projection

    service = _thread_service()
    claim = claim_attempt(service)
    projection = valid_projection()
    projection.update(thread_id=claim.thread_id, run_id=claim.run_id,
        turn_id=claim.attempt.turn_id, attempt_id=claim.attempt.attempt_id,
        model_context_id=claim.model_context.id, model_id=claim.model_context.model_id,
        model_revision=claim.model_context.model_revision)
    projection["_diagram_element_ids"] = ["line_11"]
    result_ref = projection["result_ref"]
    evidence = tuple(projection["evidence_refs"])

    class PartialSession(Session):
        def prompt_and_wait(self, question, **kwargs):
            kwargs["on_semantic_event"]({"type": "tool_result", "tool_name": "analysis",
                "ok": True, "result_refs": [result_ref], "evidence_refs": evidence})
            kwargs["on_semantic_event"]({"type": "tool_result", "tool_name": "followup",
                "ok": False, "error": {"code": "missing_inputs", "phase": "resolve",
                    "message": "Required source parameters are missing"}})
            raise RuntimeError("private provider exception")

    def admit(claim, answer, results, refs, events):
        return AdmittedAttemptAnswer(answer, "authority_backed", "lineage_verified",
            tuple(results), tuple(refs), result_projections=(projection,))

    outcome = HarnessAttemptRunner(service, HarnessPiClient(PartialSession(), admission=admit)).run(claim)
    assert outcome.status == "failed"
    assert "有功损耗" in outcome.answer and "43.64 MW" in outcome.answer
    assert "线路负载率" in outcome.answer
    assert "Required source parameters are missing" in outcome.answer
    assert "未完成" in outcome.answer
    assert "private provider" not in outcome.answer
    terminal = service.read_events(claim.thread_id, 0).events[-1]
    assert terminal.payload["answer"] == outcome.answer
    assert terminal.payload["result_projections"][0]["result_ref"] == result_ref


@pytest.mark.parametrize(("value", "expected"), [(None, "未提供"), (False, "否"), (0, "0")])
def test_partial_summary_preserves_missing_false_and_zero_observations(value, expected):
    from capstone_agent.failure_delivery import retained_result_summary
    from capstone_agent.result_projection import ResultProjection
    from test_result_projection import valid_projection
    projection = valid_projection()
    projection["status"] = "partial"
    projection["summary"] = [{"metric_id": "observation", "label": "观测值", "value": value}]
    summary = retained_result_summary((ResultProjection.from_document(projection),))
    assert "部分结果" in summary
    assert f"观测值：{expected}" in summary
    assert "不能替代尚未完成的检查" in summary


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
    events = service.read_events("thr_harness", 0).events
    failure = next(e for e in events if e.event_type == "validation_observation")
    assert failure.payload["status"] == "failed"
    assert failure.payload["task_terminal"] is False
    draft = next(e for e in events if e.event_type == "unverified_answer_recorded")
    assert draft.payload["text"] == "Initial answer"
    assert draft.visibility == "diagnostic"
    assert events[-1].event_type == "attempt_completed"


@pytest.mark.parametrize("first_decision", [None, "invalid", "offline"])
def test_admission_gate_failure_is_an_observation_for_the_same_agent(first_decision):
    service = _thread_service()
    calls = []
    feedback = []

    class RecoveringSession(Session):
        def prompt_and_wait(self, question, **kwargs):
            return "Initial response"

        def recover_after_failure(self, observation, **kwargs):
            feedback.append(observation)
            return "The request remains unresolved because required evidence is unavailable."

    def admit(claim, answer, *args):
        calls.append(answer)
        if len(calls) == 1:
            if first_decision == "offline":
                return AdmittedAttemptAnswer(answer, "offline_information", "general_knowledge")
            return first_decision
        return AdmittedAttemptAnswer(answer, "limited", "limited")

    result = HarnessAttemptRunner(service, HarnessPiClient(RecoveringSession(), admission=admit)).run(claim_attempt(service))
    assert result.status == "completed"
    assert len(feedback) == 1 and feedback[0]["task_terminal"] is False
    assert any(e.event_type == "validation_observation" for e in service.read_events("thr_harness", 0).events)


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
    session = _KernelPiPromptSession(client, SimpleNamespace(close=lambda: None, append=lambda *_: 1), admission=None)
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


@pytest.mark.parametrize("all_invalid", [False, True])
def test_one_invalid_reference_group_does_not_erase_other_verified_results(all_invalid):
    service = _thread_service()
    checks = []

    class MixedSession(Session):
        def prompt_and_wait(self, question, **kwargs):
            for label in ("good", "bad"):
                kwargs["on_semantic_event"]({
                    "type": "tool_result", "tool_name": "grid_analysis_run", "ok": True,
                    "capability": "analysis.run", "result_refs": ["result:" + label],
                    "evidence_refs": ["evidence:" + label],
                })
            raise RuntimeError("connection lost")

    def admit(claim, answer, results, evidence, events):
        checks.append((results, evidence))
        if all_invalid or "result:bad" in results:
            raise ValueError("reference unavailable")
        assert evidence == ("evidence:good",)
        return AdmittedAttemptAnswer(answer, "authority_backed", "lineage_verified", results, evidence)

    result = HarnessAttemptRunner(service, HarnessPiClient(MixedSession(), admission=admit)).run(claim_attempt(service))
    assert result.status == "failed"
    assert result.result_refs == (() if all_invalid else ("result:good",))
    assert result.evidence_refs == (() if all_invalid else ("evidence:good",))
    assert len(checks) <= 4
    if not all_invalid:
        assert checks[-1] == (("result:good",), ("evidence:good",))
    assert len([e for e in service.read_events("thr_harness", 0).events if e.event_type == "tool_completed"]) == 2


def test_incompatible_valid_groups_do_not_discard_all_results():
    service = _thread_service()

    class MixedRevisions(Session):
        def prompt_and_wait(self, question, **kwargs):
            for index in range(20):
                kwargs["on_semantic_event"]({
                    "type": "tool_result", "ok": True,
                    "result_refs": [f"result:{index}"], "evidence_refs": [f"evidence:{index}"],
                })
            raise RuntimeError("session interrupted")

    checked = set()

    def admit(claim, answer, results, evidence, events):
        checked.update(results)
        if len(results) > 1:
            raise ValueError("incompatible model revisions")
        return AdmittedAttemptAnswer(answer, "authority_backed", "lineage_verified", results, evidence)

    outcome = HarnessAttemptRunner(service, HarnessPiClient(MixedRevisions(), admission=admit)).run(claim_attempt(service))
    assert outcome.answer
    assert outcome.result_refs == ("result:19",)
    assert len(checked) == 20
    events = service.read_events("thr_harness", 0).events
    assert len([event for event in events if event.event_type == "tool_completed"]) == 20


def test_exceeding_answer_capacity_delivers_verified_subset_and_keeps_all_receipts(request):
    from capstone_agent.application_capacity import current_capacity, initialize_capacity
    previous = current_capacity()
    request.addfinalizer(lambda: initialize_capacity(previous))
    initialize_capacity({'context_references': 1024})
    service = _thread_service()

    class OverCapacity(Session):
        def prompt_and_wait(self, question, **kwargs):
            for group, count in (("batch", 1024), ("extra", 1)):
                kwargs["on_semantic_event"]({
                    "type": "tool_result", "ok": True, "result_refs": ["result:" + group],
                    "evidence_refs": [f"evidence:{group}:{index}" for index in range(count)],
                })
            return "Initial calculation summary"

        def recover_after_failure(self, *args, **kwargs):
            pytest.fail("A prose retry cannot fix the host reference capacity")

    def admit(claim, answer, results, evidence, events):
        return AdmittedAttemptAnswer(answer, "authority_backed", "lineage_verified", results, evidence)

    outcome = HarnessAttemptRunner(service, HarnessPiClient(OverCapacity(), admission=admit)).run(claim_attempt(service))
    assert outcome.result_refs
    assert "数量限制不表示这些计算失败" in outcome.answer
    events = service.read_events("thr_harness", 0).events
    assert sum(len(event.payload.get("evidence_refs", [])) for event in events if event.event_type == "tool_completed") == 1025
    assert events[-1].payload["outcome"]["status"] == "partial"
