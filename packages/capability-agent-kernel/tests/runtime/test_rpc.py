from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from capability_agent.runtime.rpc import PiProtocolError, PiRpcClient
from capability_agent.runtime.trace import JsonlTraceWriter
from capability_agent.runtime.environment import PiLaunch


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
        type("Workspace", (), {"root_path": workspace})(),
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
        type("Workspace", (), {"root_path": workspace})(),
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
        type("Workspace", (), {"root_path": workspace})(),
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
        type("Workspace", (), {"root_path": workspace})(),
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
        type("Workspace", (), {"root_path": workspace})(),
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
        type("Workspace", (), {"root_path": workspace})(),
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
        type("Workspace", (), {"root_path": workspace})(),
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
