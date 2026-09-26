from __future__ import annotations

import json

import pytest

from capstone_agent.protocol import Frame, ProtocolError


def test_worker_frames_round_trip_with_exact_contract() -> None:
    frame = Frame("session-1", 1, "turn", {"instruction": "检查当前模型"})
    encoded = frame.to_line()
    assert encoded.endswith(b"\n")
    assert Frame.from_line(encoded) == frame
    assert json.loads(encoded)["schema"] == "capstone-worker/1.0"


@pytest.mark.parametrize("mutation", [
    {"extra": "unexpected"},
    {"sequence": 2},
    {"kind": "shell"},
    {"kind": []},
    {"payload": {"command": "ls"}},
])
def test_worker_frame_rejects_unknown_or_unsequenced_input(
    mutation: dict[str, object],
) -> None:
    document: dict[str, object] = {
        "schema": "capstone-worker/1.0", "session_id": "session-1",
        "sequence": 1, "kind": "turn", "payload": {"instruction": "one"},
    }
    document.update(mutation)
    with pytest.raises(ProtocolError):
        Frame.from_line((json.dumps(document) + "\n").encode(), expected_sequence=1)


def test_worker_frame_rejects_oversized_line() -> None:
    with pytest.raises(ProtocolError, match="size"):
        Frame.from_line(b"x" * 1_000_001)
