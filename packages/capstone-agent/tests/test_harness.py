from __future__ import annotations

import pytest

from capstone_agent.harness import (
    HarnessDSHClient,
    HarnessPiClient,
    HarnessRuntimeUnavailable,
    normalize_runtime_event,
)


class _PiSession:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def prompt_and_wait(self, question: str, **kwargs: object) -> str:
        assert question == "hello"
        callback = kwargs["on_semantic_event"]
        assert callable(callback)
        callback({"type": "text_delta", "text": "hi"})
        callback({"type": "tool_execution_start", "toolCallId": "call-1", "toolName": "grid_model_list"})
        return "answer"

    def stop(self) -> None:
        self.stopped = True


def test_pi_client_normalizes_native_events_and_preserves_answer() -> None:
    session = _PiSession()
    events: list[dict[str, object]] = []
    client = HarnessPiClient(session, runtime_mode="capstone")

    client.start()
    answer = client.prompt("hello", on_event=events.append)
    client.stop()

    assert answer == "answer"
    assert session.started and session.stopped
    assert [event["event_type"] for event in events] == [
        "assistant_text_delta", "tool_started",
    ]
    assert events[1]["runtime_mode"] == "capstone"
    assert events[1]["payload"] == {"tool_call_id": "call-1", "tool_name": "grid_model_list"}


def test_normalizer_drops_unbounded_native_payloads() -> None:
    event = normalize_runtime_event(
        {"type": "provider_internal", "messages": [{"secret": "do-not-persist"}], "text": "x" * 10000},
        runtime_mode="pi_reference",
    )

    assert event == {
        "event_type": "runtime_event",
        "runtime_mode": "pi_reference",
        "visibility": "diagnostic",
        "payload": {"native_type": "provider_internal"},
    }


def test_dsh_client_is_an_explicitly_unavailable_shell() -> None:
    client = HarnessDSHClient()
    with pytest.raises(HarnessRuntimeUnavailable, match="DSH"):
        client.start()
