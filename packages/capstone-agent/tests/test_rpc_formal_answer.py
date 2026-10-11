from dataclasses import replace
from types import SimpleNamespace
import json
import sys

from capability_agent.runtime.rpc import PiRpcClient
from capability_agent.runtime.environment import PiLaunch
from capability_agent.runtime.trace import JsonlTraceWriter
from capstone_agent.kernel_pi_session import _KernelPiPromptSession, _build_kernel_admission
from capstone_agent.harness import HarnessPiClient, HarnessAttemptRunner
from test_harness import _thread_service


def session(tmp_path, admission):
    final = {"role": "assistant", "content": [{"type": "text", "text": "这是正式中文回答。"}], "stopReason": "stop"}
    events = [{"type": "prompt_ack", "ok": True},
        {"type": "message_start", "message": {"role": "assistant", "content": []}},
        {"type": "text_delta", "text": "I'll check runtime capabilities."},
        {"type": "message_end", "message": {"role": "assistant", "content": [{"type": "text", "text": "I'll check runtime capabilities."}]}},
        {"type": "message_start", "message": {"role": "assistant", "content": []}},
        {"type": "text_delta", "text": "这是正式中文回答。"},
        {"type": "message_end", "message": final}, {"type": "agent_end", "messages": [final]}]
    script = tmp_path / "provider.py"
    script.write_text("import json\ninput()\n" + "\n".join(f"print(json.dumps({event!r}), flush=True)" for event in events))
    trace = JsonlTraceWriter(tmp_path / "trace.jsonl")
    client = PiRpcClient(PiLaunch(argv=(sys.executable, str(script)), environment={}), SimpleNamespace(root_path=tmp_path), trace)
    return _KernelPiPromptSession(client, trace, admission=admission)


def test_ordinary_completed_projection_uses_final_message_and_process_is_diagnostic(tmp_path):
    service = _thread_service()
    service.submit_command({"schema": "capstone-command/1", "command_id": "formal", "idempotency_key": "formal",
        "thread_id": "thr_harness", "run_id": "run_harness", "kind": "send_ordinary", "expected_event_seq": 0,
        "payload": {"text": "请用中文回答"}})
    claim = service.claim_attempt("worker", lease_seconds=30)
    adapter = session(tmp_path, _build_kernel_admission(()))
    runtime = HarnessPiClient(adapter, admission=adapter.admit_attempt)
    result = HarnessAttemptRunner(service, runtime).run(claim)
    assert result.status == "completed" and result.answer == "这是正式中文回答。", (result, service.read_events("thr_harness", 0).events)
    events = service.read_events("thr_harness", 0).events
    processes = [event for event in events if event.event_type == "assistant_process_delta"]
    assert len(processes) == 2 and all(event.visibility == "diagnostic" for event in processes)
    public = [event for event in events if event.visibility == "public"]
    assert not any(event.event_type == "assistant_text_delta" for event in public)
    assert "I'll check" not in json.dumps([dict(event.payload) for event in public])
    assert events[-1].payload["answer"] == "这是正式中文回答。"


def test_pypsa_compatibility_admission_preserves_only_final_message(tmp_path):
    from test_kernel_bound_admission import _admission, CONTEXT, REVISION, EVIDENCE
    from capability_agent.domain.task import ResolvedTaskGoal
    from capstone_agent.task_understanding import TaskRequest, TaskUnderstanding, SemanticGoal, AnswerPolicy
    admit, claim, _ = _admission({"context_ref": CONTEXT, "revision_ref": REVISION}, family="pypsa")
    request = TaskRequest(claim.thread_id, claim.attempt.turn_id, claim.attempt.attempt_id, claim.instruction, 0,
                          claim.model_context.id, claim.model_context.model_id, REVISION)
    understanding = TaskUnderstanding(request, "controlled", (SemanticGoal("g", "purpose", "model", "full", "baseline", None, "impact", None, ("result",), ()),), AnswerPolicy("zh", "concise"))
    claim = replace(claim, task_request=request, task_understanding=understanding,
                    task_resolutions=(ResolvedTaskGoal("g", "uncertified", "{}", binding_id="grid", execution_required=True),))
    adapter = session(tmp_path, admit)
    adapter.start()
    try:
        answer = adapter.prompt_and_wait("question", on_semantic_event=lambda _: None, correlation_id=None, on_heartbeat=lambda: None)
        admitted = adapter.admit_attempt(claim, answer, (), (EVIDENCE,), ({"binding_id": "grid", "ok": True, "evidence_refs": [EVIDENCE]},))
    finally:
        adapter.stop()
    assert "这是正式中文回答。" in admitted.answer and "I'll check" not in admitted.answer
    assert admitted.evidence_refs == (EVIDENCE,)
