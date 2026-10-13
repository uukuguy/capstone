from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from capability_agent.runtime.rpc import PiProtocolError, PiRpcClient
from capability_agent.runtime.trace import JsonlTraceWriter
from capability_agent.runtime.environment import PiLaunch


def test_native_action_boundaries_expose_metadata_without_message_content():
    from capability_agent.runtime.rpc import _semantic_trace_payloads
    assert _semantic_trace_payloads({'type': 'turn_start'}, '', {}) == ({'type': 'runtime_action', 'phase': 'started'},)
    event = {'type': 'message_end', 'message': {'role': 'assistant', 'content': [{'type': 'thinking', 'thinking': 'private'}, {'type': 'toolCall', 'name': 'grid_check', 'arguments': {'secret': 'private'}}]}}
    result = _semantic_trace_payloads(event, '', {})
    assert result == ({'type': 'runtime_action', 'phase': 'response_completed', 'response_kind': 'tools'},)
    assert 'private' not in json.dumps(result)
    assert _semantic_trace_payloads({'type': 'turn_end'}, '', {}) == ({'type': 'runtime_action', 'phase': 'completed'},)
    assert _semantic_trace_payloads({'type': 'message_end', 'message': {'role': 'tool', 'content': []}}, '', {}) == ()


@dataclass(frozen=True)
class _Workspace:
    root_path: Path


def test_rpc_timing_distinguishes_slow_observer_from_native_receive(tmp_path):
    import time
    script = tmp_path / "stream.py"
    script.write_text("import json\ninput()\n"
        "print(json.dumps({'type':'prompt_ack','ok':True}), flush=True)\n"
        "for _ in range(40): print(json.dumps({'type':'text_delta','text':'private-text'}), flush=True)\n"
        "print(json.dumps({'type':'agent_end','messages':[]}), flush=True)\n")
    trace = JsonlTraceWriter(tmp_path / "trace.jsonl")
    client = PiRpcClient(PiLaunch(argv=(sys.executable, str(script)), environment={}), _Workspace(tmp_path), trace)
    def observe(event, _sequence):
        if event['type'] == 'assistant_process_delta':
            time.sleep(.005)
    client.start()
    try:
        assert client.prompt_and_wait("question", on_semantic_event=observe) == "private-text" * 40
    finally:
        client.stop()
        trace.close()
    rows = [json.loads(line) for line in trace.path.read_text().splitlines()]
    timing = next(row['payload'] for row in rows if row['event'] == 'rpc_prompt_timing')
    assert timing['observer_seconds'] >= .15
    assert timing['max_queue_delay_seconds'] >= .1
    assert timing['native_receive_span_seconds'] < timing['observer_seconds']
    assert timing['semantic_events'] == 43
    assert timing['status'] == 'returned'
    assert 'private-text' not in json.dumps(timing)
    assert len([row for row in rows if row['payload'].get('type') == 'assistant_process_delta']) == 40


def test_rpc_timing_is_retained_on_protocol_failure(tmp_path):
    script = tmp_path / "fail.py"
    script.write_text("input()\nprint('invalid-json', flush=True)\n")
    trace = JsonlTraceWriter(tmp_path / "trace.jsonl")
    client = PiRpcClient(PiLaunch(argv=(sys.executable, str(script)), environment={}), _Workspace(tmp_path), trace)
    client.start()
    try:
        with pytest.raises(PiProtocolError, match='invalid JSONL'):
            client.prompt_and_wait("question")
    finally:
        client.stop()
        trace.close()
    timing = next(json.loads(line)['payload'] for line in trace.path.read_text().splitlines()
        if json.loads(line)['event'] == 'rpc_prompt_timing')
    assert timing['status'] == 'failed'
    assert timing['raw_events'] == 1


def test_rpc_batches_process_fragments_without_crossing_tool_boundaries(tmp_path):
    script = tmp_path / 'batch.py'
    script.write_text("import json\ninput()\n"
        "print(json.dumps({'type':'prompt_ack','ok':True}), flush=True)\n"
        "for _ in range(20): print(json.dumps({'type':'text_delta','text':'前'}), flush=True)\n"
        "print(json.dumps({'type':'tool_execution_start','toolCallId':'one','toolName':'lookup'}), flush=True)\n"
        "print(json.dumps({'type':'tool_execution_end','toolCallId':'one','toolName':'lookup','result':{'details':{'capability':'lookup','ok':True,'result':{'value':7}}}}), flush=True)\n"
        "for _ in range(20): print(json.dumps({'type':'text_delta','text':'后'}), flush=True)\n"
        "print(json.dumps({'type':'agent_end','messages':[]}), flush=True)\n")
    trace = JsonlTraceWriter(tmp_path / 'trace.jsonl')
    client = PiRpcClient(PiLaunch(argv=(sys.executable, str(script)), environment={}), _Workspace(tmp_path), trace,
        process_delta_batch_seconds=.1)
    observed = []
    client.start()
    try:
        assert client.prompt_and_wait('question', on_semantic_event=lambda event, _: observed.append(event)) == '后' * 20
    finally:
        client.stop()
        trace.close()
    deltas = [event for event in observed if event['type'] == 'assistant_process_delta']
    assert len(deltas) < 5
    assert ''.join(event['text'] for event in deltas) == '前' * 20 + '后' * 20
    fragments = [fragment for event in deltas for fragment in event['delta_records']]
    assert len(fragments) == 40
    assert ''.join(fragment['text'] for fragment in fragments) == '前' * 20 + '后' * 20
    assert all('received_seconds' in fragment and 'native_ordinal' in fragment for fragment in fragments)
    start = next(index for index, event in enumerate(observed) if event['type'] == 'tool_execution_start')
    assert ''.join(event.get('text', '') for event in observed[:start]) == '前' * 20
    assert [event for event in observed if event['type'] == 'tool_result'][0]['result'] == {'value': 7}
    assert observed[-1]['type'] == 'assistant_message'


def test_rpc_flushes_batched_fragments_before_protocol_failure(tmp_path):
    script = tmp_path / 'batch-fail.py'
    script.write_text("import json\ninput()\n"
        "print(json.dumps({'type':'prompt_ack','ok':True}), flush=True)\n"
        "print(json.dumps({'type':'text_delta','text':'preserved'}), flush=True)\n"
        "print('invalid-json', flush=True)\n")
    trace = JsonlTraceWriter(tmp_path / 'trace.jsonl')
    client = PiRpcClient(PiLaunch(argv=(sys.executable, str(script)), environment={}), _Workspace(tmp_path), trace,
        process_delta_batch_seconds=.1)
    observed = []
    client.start()
    try:
        with pytest.raises(PiProtocolError, match='invalid JSONL'):
            client.prompt_and_wait('question', on_semantic_event=lambda event, _: observed.append(event))
    finally:
        client.stop()
        trace.close()
    assert [event['text'] for event in observed if event['type'] == 'assistant_process_delta'] == ['preserved']


def test_model_step_budget_keeps_session_and_completed_tools_for_resume(tmp_path):
    script = tmp_path / "bounded-step.py"
    script.write_text('''import json, sys
completed = False
for line in sys.stdin:
 request = json.loads(line)
 if request['type'] == 'prompt':
  print(json.dumps({'type':'prompt_ack','ok':True}), flush=True)
  if not completed:
   completed = True
   print(json.dumps({'type':'tool_execution_start','toolCallId':'saved','toolName':'lookup'}), flush=True)
   print(json.dumps({'type':'tool_execution_end','toolCallId':'saved','toolName':'lookup','result':{'details':{'capability':'lookup','ok':True,'result':{'value':7}}}}), flush=True)
  else:
   print(json.dumps({'type':'text_delta','text':'used saved observations'}), flush=True)
   print(json.dumps({'type':'agent_end','messages':[]}), flush=True)
 elif request['type'] == 'abort':
  print(json.dumps({'type':'response','command':'abort','success':True}), flush=True)
  print(json.dumps({'type':'agent_end','messages':[]}), flush=True)
 elif request['type'] == 'set_thinking_level':
  assert request['level'] == 'off'
  print(json.dumps({'type':'response','command':'set_thinking_level','success':True}), flush=True)
''')
    trace = JsonlTraceWriter(tmp_path / "trace.jsonl")
    client = PiRpcClient(PiLaunch(argv=(sys.executable, str(script)), environment={}), _Workspace(tmp_path), trace)
    events = []
    client.start()
    try:
        pid = client.process.pid
        assert client.prompt_and_wait("work", model_idle_seconds=.05, timeout_seconds=1,
            on_semantic_event=lambda event, _: events.append(event)) == ""
        assert client.last_prompt_interrupted
        client.set_thinking_level("off")
        assert client.prompt_and_wait("continue", model_idle_seconds=.05, timeout_seconds=1) == "used saved observations"
        assert not client.last_prompt_interrupted
        assert client.process.pid == pid
    finally:
        client.stop()
        trace.close()
    assert any(event['type'] == 'tool_result' for event in events)


def test_model_step_budget_does_not_interrupt_a_running_tool(tmp_path):
    script = tmp_path / "long-tool.py"
    script.write_text('''import json, time
input()
print(json.dumps({'type':'prompt_ack','ok':True}), flush=True)
print(json.dumps({'type':'tool_execution_start','toolCallId':'long','toolName':'solver'}), flush=True)
time.sleep(.15)
print(json.dumps({'type':'tool_execution_end','toolCallId':'long','toolName':'solver','result':{}}), flush=True)
print(json.dumps({'type':'text_delta','text':'solver finished'}), flush=True)
print(json.dumps({'type':'agent_end','messages':[]}), flush=True)
''')
    trace = JsonlTraceWriter(tmp_path / "trace.jsonl")
    client = PiRpcClient(PiLaunch(argv=(sys.executable, str(script)), environment={}), _Workspace(tmp_path), trace)
    client.start()
    try:
        assert client.prompt_and_wait("work", model_idle_seconds=.05, timeout_seconds=1) == "solver finished"
        assert not client.last_prompt_interrupted
    finally:
        client.stop()
        trace.close()


def test_model_step_budget_keeps_a_streaming_public_report(tmp_path):
    script = tmp_path / "stream-report.py"
    script.write_text('''import json, time
input()
print(json.dumps({'type':'prompt_ack','ok':True}), flush=True)
for text in ['report ', 'from ', 'saved ', 'results']:
 print(json.dumps({'type':'text_delta','text':text}), flush=True)
 time.sleep(.03)
print(json.dumps({'type':'agent_end','messages':[]}), flush=True)
''')
    trace = JsonlTraceWriter(tmp_path / "trace.jsonl")
    client = PiRpcClient(PiLaunch(argv=(sys.executable, str(script)), environment={}), _Workspace(tmp_path), trace)
    client.start()
    try:
        assert client.prompt_and_wait("report", model_idle_seconds=.05, timeout_seconds=1) == "report from saved results"
        assert not client.last_prompt_interrupted
    finally:
        client.stop()
        trace.close()


@pytest.mark.parametrize("terminal_snapshot", [False, True])
def test_rpc_keeps_only_last_assistant_message_after_tool_cycle(tmp_path, terminal_snapshot):
    before = {"role": "assistant", "content": [{"type": "text", "text": "I'll check runtime capabilities."},
        {"type": "toolCall", "id": "c", "name": "lookup", "arguments": {}}], "stopReason": "toolUse"}
    after = {"role": "assistant", "content": [{"type": "text", "text": "已完成分析。"}], "stopReason": "stop"}
    events = [{"type": "prompt_ack", "ok": True}, {"type": "message_start", "message": before},
        {"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "delta": "I'll check runtime capabilities."}},
        {"type": "message_end", "message": before}, {"type": "tool_execution_start", "toolCallId": "c", "toolName": "lookup"},
        {"type": "tool_execution_end", "toolCallId": "c", "toolName": "lookup", "result": {}},
        {"type": "message_start", "message": {"role": "assistant", "content": []}},
        {"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "delta": "已完成"}},
        {"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "delta": "分析。"}},
        {"type": "message_end", "message": after},
        {"type": "agent_end", "messages": [before, {"role": "toolResult"}, after] if terminal_snapshot else []}]
    script = tmp_path / "messages.py"
    script.write_text("import json\ninput()\n" + "\n".join(f"print(json.dumps({event!r}), flush=True)" for event in events))
    trace = JsonlTraceWriter(tmp_path / "trace.jsonl")
    client = PiRpcClient(PiLaunch(argv=(sys.executable, str(script)), environment={}), _Workspace(tmp_path), trace)
    semantic = []
    client.start()
    try:
        answer = client.prompt_and_wait("question", on_semantic_event=lambda event, _: semantic.append(event))
    finally:
        client.stop()
        trace.close()
    assert answer == "已完成分析。"
    final = [event for event in semantic if event["type"] == "assistant_message"]
    assert [event["text"] for event in final] == ["已完成分析。"]


@pytest.mark.parametrize("emit_events", [False, True])
def test_rpc_services_control_requests_while_tool_waits_without_capture(tmp_path, emit_events):
    script = tmp_path / "control-provider.py"
    script.write_text(
        "import json, time\nfrom pathlib import Path\ninput()\n"
        "print(json.dumps({'type':'prompt_ack','ok':True}), flush=True)\n"
        "Path('pending').write_text('update')\n"
        "deadline=time.monotonic()+2\n"
        "while not Path('committed').exists() and time.monotonic()<deadline:\n"
        + (" print(json.dumps({'type':'text_delta','text':''}), flush=True)\n" if emit_events else "")
        + " time.sleep(.005)\n"
        "if not Path('committed').exists(): raise RuntimeError('host did not service request')\n"
        "print(json.dumps({'type':'text_delta','text':'done'}), flush=True)\n"
        "print(json.dumps({'type':'agent_end','messages':[]}), flush=True)\n",
    )
    trace = JsonlTraceWriter(tmp_path / "trace.jsonl")
    client = PiRpcClient(PiLaunch(argv=(sys.executable, str(script)), environment={}), _Workspace(tmp_path), trace)
    serviced = []
    def service():
        if (tmp_path / "pending").exists() and not (tmp_path / "committed").exists():
            (tmp_path / "committed").write_text("committed")
            serviced.append(True)
    client.start()
    try:
        assert client.prompt_and_wait("question", on_control_requests=service, timeout_seconds=1) == "done"
    finally:
        client.stop()
        trace.close()
    assert serviced == [True]


def test_rpc_control_failure_does_not_return_a_formal_answer(tmp_path):
    script = tmp_path / "control-failure.py"
    script.write_text("import time\ninput()\ntime.sleep(2)\n")
    trace = JsonlTraceWriter(tmp_path / "trace.jsonl")
    client = PiRpcClient(PiLaunch(argv=(sys.executable, str(script)), environment={}), _Workspace(tmp_path), trace)
    def fail():
        raise PiProtocolError("control commit failed")
    client.start()
    try:
        with pytest.raises(PiProtocolError, match="control commit failed"):
            client.prompt_and_wait("question", on_control_requests=fail, timeout_seconds=1)
    finally:
        client.stop()
        trace.close()


def test_rpc_terminal_snapshot_is_authoritative_without_deltas(tmp_path):
    script = tmp_path / "snapshot.py"
    events = [{"type": "prompt_ack", "ok": True}, {"type": "agent_end", "messages": [{"role": "assistant",
        "content": [{"type": "thinking", "thinking": "private"}, {"type": "text", "text": "正式回答。"}], "stopReason": "stop"}]}]
    script.write_text("import json\ninput()\n" + "\n".join(f"print(json.dumps({event!r}), flush=True)" for event in events))
    trace = JsonlTraceWriter(tmp_path / "trace.jsonl")
    client = PiRpcClient(PiLaunch(argv=(sys.executable, str(script)), environment={}), _Workspace(tmp_path), trace)
    client.start()
    try:
        assert client.prompt_and_wait("question") == "正式回答。"
    finally:
        client.stop()
        trace.close()


def test_rpc_framing_returns_only_assembled_answer(tmp_path: Path) -> None:
    script = tmp_path / "provider.py"
    script.write_text(
        "import json\n"
        "json.loads(input())\n"
        "print(json.dumps({'type':'prompt_ack','ok':True}), flush=True)\n"
        "print(json.dumps({'type':'text_delta','text':'done'}), flush=True)\n"
        "print(json.dumps({'type':'agent_end','messages':[]}), flush=True)\n",
        encoding="utf-8",
    )
    workspace = tmp_path / "run"
    workspace.mkdir()
    trace = JsonlTraceWriter(workspace / "events.jsonl")
    client = PiRpcClient(
        PiLaunch(argv=(sys.executable, str(script)), environment={}),
        _Workspace(workspace),
        trace,
    )

    client.start()
    try:
        assert client.prompt_and_wait("question") == "done"
    finally:
        client.stop()
        trace.close()


def test_rpc_timeout_fails_closed_and_does_not_wait_for_provider(
    tmp_path: Path,
) -> None:
    script = tmp_path / "slow-provider.py"
    script.write_text(
        "import json, time\n"
        "json.loads(input())\n"
        "time.sleep(2)\n",
        encoding="utf-8",
    )
    workspace = tmp_path / "run"
    workspace.mkdir()
    trace = JsonlTraceWriter(workspace / "events.jsonl")
    client = PiRpcClient(
        PiLaunch(argv=(sys.executable, str(script)), environment={}),
        _Workspace(workspace),
        trace,
        timeout_seconds=0.05,
    )

    client.start()
    try:
        with pytest.raises(PiProtocolError, match="timed out"):
            client.prompt_and_wait("question", heartbeat_seconds=0.01)
    finally:
        client.stop()
        trace.close()


def test_rpc_rejects_mismatched_explicit_correlation_id(tmp_path: Path) -> None:
    script = tmp_path / "mismatched-provider.py"
    script.write_text(
        "import json\n"
        "json.loads(input())\n"
        "print(json.dumps({'type':'prompt_ack','ok':True,'request_id':'wrong'}), flush=True)\n",
        encoding="utf-8",
    )
    workspace = tmp_path / "run"
    workspace.mkdir()
    trace = JsonlTraceWriter(workspace / "events.jsonl")
    client = PiRpcClient(
        PiLaunch(argv=(sys.executable, str(script)), environment={}),
        _Workspace(workspace),
        trace,
        correlation_id="turn-001",
    )

    client.start()
    try:
        with pytest.raises(PiProtocolError, match="correlation mismatch"):
            client.prompt_and_wait("question")
    finally:
        client.stop()
        trace.close()


@pytest.mark.parametrize("ack_type", ["prompt_ack", "response"])
def test_rpc_accepts_missing_event_correlation_and_uses_local_id(
    tmp_path: Path, ack_type: str
) -> None:
    script = tmp_path / "local-correlation-provider.py"
    ack = (
        {"type": "prompt_ack", "ok": True}
        if ack_type == "prompt_ack"
        else {"type": "response", "command": "prompt", "success": True}
    )
    script.write_text(
        "import json\n"
        "json.loads(input())\n"
        f"print(json.dumps({ack!r}), flush=True)\n"
        "print(json.dumps({'type':'text_delta','text':'done'}), flush=True)\n"
        "print(json.dumps({'type':'agent_end','messages':[]}), flush=True)\n",
        encoding="utf-8",
    )
    workspace = tmp_path / "run"
    workspace.mkdir()
    trace = JsonlTraceWriter(workspace / "events.jsonl")
    semantic: list[dict[str, object]] = []
    client = PiRpcClient(
        PiLaunch(argv=(sys.executable, str(script)), environment={}),
        _Workspace(workspace),
        trace,
        correlation_id="turn-001",
    )

    client.start()
    try:
        assert client.prompt_and_wait(
            "question",
            on_semantic_event=lambda payload, _sequence: semantic.append(payload),
        ) == "done"
    finally:
        client.stop()
        trace.close()

    assert semantic
    assert all(payload["correlation_id"] == "turn-001" for payload in semantic)
    persisted = [
        json.loads(line)["payload"]
        for line in (workspace / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert all(payload["correlation_id"] == "turn-001" for payload in persisted)


def test_rpc_rejects_invalid_utf8_stdout_without_decode_details(tmp_path: Path) -> None:
    script = tmp_path / "invalid-utf8-provider.py"
    script.write_text(
        "import sys\n"
        "sys.stdout.buffer.write(b'\\xff\\n')\n"
        "sys.stdout.flush()\n",
        encoding="utf-8",
    )
    workspace = tmp_path / "run"
    workspace.mkdir()
    trace = JsonlTraceWriter(workspace / "events.jsonl")
    client = PiRpcClient(
        PiLaunch(argv=(sys.executable, str(script)), environment={}),
        _Workspace(workspace),
        trace,
    )

    client.start()
    try:
        with pytest.raises(PiProtocolError, match="invalid UTF-8") as captured:
            client.prompt_and_wait("question")
    finally:
        client.stop()
        trace.close()
    assert "UnicodeDecodeError" not in str(captured.value)


def test_rpc_sanitizes_secret_in_response_error(tmp_path: Path) -> None:
    script = tmp_path / "error-provider.py"
    script.write_text(
        "import json\n"
        "json.loads(input())\n"
        "print(json.dumps({'type':'response','command':'prompt','success':False,'error':'preflight failed api_key=topsecret'}), flush=True)\n",
        encoding="utf-8",
    )
    workspace = tmp_path / "run"
    workspace.mkdir()
    trace = JsonlTraceWriter(workspace / "events.jsonl")
    client = PiRpcClient(
        PiLaunch(argv=(sys.executable, str(script)), environment={}),
        _Workspace(workspace),
        trace,
        secret_values={"topsecret"},
    )

    client.start()
    try:
        with pytest.raises(PiProtocolError, match="preflight failed") as captured:
            client.prompt_and_wait("question")
    finally:
        client.stop()
        trace.close()
    assert "topsecret" not in str(captured.value)


def test_rpc_sanitizes_capture_fatal_stderr(tmp_path: Path) -> None:
    script = tmp_path / "capture-fatal-provider.py"
    script.write_text(
        "import sys\n"
        "sys.stderr.write('trajectory model request commit failed secret=topsecret\\n')\n"
        "sys.stderr.flush()\n"
        "raise SystemExit(86)\n",
        encoding="utf-8",
    )
    workspace = tmp_path / "run"
    workspace.mkdir()
    trace = JsonlTraceWriter(workspace / "events.jsonl")
    client = PiRpcClient(
        PiLaunch(argv=(sys.executable, str(script)), environment={}),
        _Workspace(workspace),
        trace,
        secret_values={"topsecret"},
    )

    client.start()
    try:
        with pytest.raises(PiProtocolError, match="trajectory model request commit failed") as captured:
            client.prompt_and_wait("question")
    finally:
        client.stop()
        trace.close()
    assert "topsecret" not in str(captured.value)
