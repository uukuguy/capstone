from __future__ import annotations

import json
from pathlib import Path

import pytest

from capability_agent.runtime.trace import JsonlTraceWriter


def test_trace_rejects_unsupported_payload_with_bounded_error(tmp_path: Path) -> None:
    class Unsupported:
        def __repr__(self) -> str:
            return "secret-trace-object"

    writer = JsonlTraceWriter(tmp_path / "events.jsonl")
    with pytest.raises(ValueError, match="JSON-safe") as captured:
        writer.append("event", {"payload": Unsupported()})
    writer.close()

    assert "secret-trace-object" not in str(captured.value)
    assert not (tmp_path / "events.jsonl").read_text(encoding="utf-8").strip()


def test_trace_rejects_payload_cycles(tmp_path: Path) -> None:
    payload: dict[str, object] = {}
    payload["self"] = payload
    writer = JsonlTraceWriter(tmp_path / "events.jsonl")

    with pytest.raises(ValueError, match="JSON-safe"):
        writer.append("event", payload)
    writer.close()


def test_trace_refuses_symlinked_leaf_without_external_write(tmp_path: Path) -> None:
    outside = tmp_path / "outside.jsonl"
    outside.write_text("outside", encoding="utf-8")
    target = tmp_path / "events.jsonl"
    target.symlink_to(outside)

    with pytest.raises(ValueError, match="symlink"):
        JsonlTraceWriter(target)
    assert outside.read_text(encoding="utf-8") == "outside"


def test_trace_redacts_secret_assignments_without_configured_value(tmp_path: Path) -> None:
    target = tmp_path / "events.jsonl"
    writer = JsonlTraceWriter(target)
    writer.append("event", {"message": "authorization=should-not-persist"})
    writer.close()

    record = json.loads(target.read_text(encoding="utf-8"))
    assert "should-not-persist" not in target.read_text(encoding="utf-8")
    assert record["payload"]["message"] == "authorization=[REDACTED]"
