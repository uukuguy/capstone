from __future__ import annotations

from dataclasses import dataclass

from capstone_agent.thread_protocol import EventEnvelope
from validation.thread.m5_matrix import validate_attempt_projection, validate_ordinary_projection


def _event(event_type: str, payload: dict[str, object], seq: int) -> EventEnvelope:
    return EventEnvelope.from_document({
        "event_id": f"evt_{seq}", "event_seq": seq, "event_type": event_type,
        "event_version": 1, "thread_id": "thr_demo_39", "run_id": "run_001",
        "turn_id": "turn_001", "attempt_id": "attempt_001", "model_context_id": "ctx_1",
        "selection_revision": "sel_1", "occurred_at": "2026-10-01T00:00:00+00:00",
        "visibility": "public", "payload": payload,
    })


def test_professional_projection_requires_explicit_tool_source_and_evidence() -> None:
    events = (
        _event("attempt_started", {}, 1),
        _event("turn_route_selected", {"route": "professional"}, 2),
        _event("tool_completed", {"capability_key": {"binding_id": "grid", "capability_id": "context.open"}, "result_refs": ["result:1"], "evidence_refs": ["evidence:1"]}, 3),
        _event("attempt_completed", {"answer": "完成", "result_refs": ["result:1"], "evidence_refs": ["evidence:1"], "admission": {"mode": "authority_backed"}}, 4),
    )
    result = validate_attempt_projection(events, attempt_id="attempt_001", route="professional", implementation_family="pandapower", authority_backed=True)
    assert result.status == "passed"


def test_professional_projection_rejects_missing_admission_even_with_answer() -> None:
    events = (
        _event("attempt_started", {}, 1),
        _event("turn_route_selected", {"route": "professional"}, 2),
        _event("attempt_completed", {"answer": "完成", "result_refs": [], "evidence_refs": []}, 3),
    )
    result = validate_attempt_projection(events, attempt_id="attempt_001", route="professional", implementation_family="pypsa", authority_backed=True)
    assert result.status == "failed"


def test_ordinary_projection_requires_a_route_and_no_authority_references() -> None:
    events = (
        _event("attempt_started", {}, 1),
        _event("turn_route_selected", {"route": "ordinary"}, 2),
        _event("attempt_completed", {"answer": "你好", "result_refs": [], "evidence_refs": []}, 3),
    )
    result = validate_ordinary_projection(events, attempt_id="attempt_001")
    assert result.status == "passed"
