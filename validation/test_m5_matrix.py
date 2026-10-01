from __future__ import annotations

from capstone_agent.thread_protocol import EventEnvelope, ThreadSnapshot
from validation.thread.catalog import ThreadCatalog
from validation.thread.m5_matrix import _validate_catalog_expectation, validate_attempt_projection, validate_ordinary_projection


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
        _event("tool_completed", {"binding_id": "grid", "capability_id": "context.open", "ok": True, "result_refs": ["result:1"], "evidence_refs": ["evidence:1"]}, 3),
        _event("attempt_completed", {"answer": "完成", "result_refs": ["result:1"], "evidence_refs": ["evidence:1"], "admission": {"mode": "authority_backed"}}, 4),
    )
    result = validate_attempt_projection(events, attempt_id="attempt_001", route="professional", implementation_family="pandapower", authority_backed=True)
    assert result.status == "passed"


def test_professional_projection_rejects_terminal_references_not_emitted_by_current_tools() -> None:
    events = (
        _event("attempt_started", {}, 1),
        _event("turn_route_selected", {"route": "professional"}, 2),
        _event("tool_completed", {"binding_id": "grid", "capability_id": "context.open", "ok": True, "result_refs": ["result:1"], "evidence_refs": ["evidence:1"]}, 3),
        _event("attempt_completed", {"answer": "完成", "result_refs": ["result:foreign"], "evidence_refs": ["evidence:1"], "admission": {"mode": "authority_backed"}}, 4),
    )
    result = validate_attempt_projection(events, attempt_id="attempt_001", route="professional", implementation_family="pandapower", authority_backed=True)
    assert result.name == "attempt.references"
    assert result.status == "failed"


def test_professional_projection_rejects_fallback_and_failed_tool_completion() -> None:
    fallback = (
        _event("attempt_started", {}, 1),
        _event("turn_route_fallback", {"route": "professional"}, 2),
        _event("tool_completed", {"binding_id": "grid", "capability_id": "context.open", "ok": True, "result_refs": ["result:1"], "evidence_refs": ["evidence:1"]}, 3),
        _event("attempt_completed", {"answer": "完成", "result_refs": ["result:1"], "evidence_refs": ["evidence:1"], "admission": {"mode": "authority_backed"}}, 4),
    )
    assert validate_attempt_projection(fallback, attempt_id="attempt_001", route="professional", implementation_family="pandapower", authority_backed=True).status == "failed"

    failed_tool = (
        _event("attempt_started", {}, 1),
        _event("turn_route_selected", {"route": "professional"}, 2),
        _event("tool_completed", {"binding_id": "grid", "capability_id": "context.open", "ok": False, "result_refs": ["result:1"], "evidence_refs": ["evidence:1"]}, 3),
        _event("attempt_completed", {"answer": "完成", "result_refs": ["result:1"], "evidence_refs": ["evidence:1"], "admission": {"mode": "authority_backed"}}, 4),
    )
    assert validate_attempt_projection(failed_tool, attempt_id="attempt_001", route="professional", implementation_family="pandapower", authority_backed=True).name == "attempt.tool_result"


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


def test_catalog_gate_requires_exact_active_model_and_enabled_profile() -> None:
    snapshot = ThreadSnapshot.from_document({
        "schema": "capstone-thread-snapshot/1", "thread_id": "thr_demo", "run": {"run_id": "run_1", "state": "open"},
        "active_model_context": {
            "id": "ctx_1", "model_id": "pypsa-example/scigrid_de", "model_revision": "1",
            "implementation_family": "pypsa", "selection_revision": "sel_1",
        },
        "active_grid_page_id": "page_1", "current_attempt": None, "last_event_seq": 0, "base_event_seq": 0,
    })
    catalog = ThreadCatalog.from_document({
        "schema": "capstone-thread-catalog/1",
        "models": [{
            "model_id": "regional-six-bus", "authority_model_ref": "pypsa:regional-six-bus",
            "display_name": "Regional", "diagram_provider_id": "pypsa", "implementation_family": "pypsa",
        }],
        "profiles": [{
            "profile_id": "pypsa-business-cases", "profile_version": "1.0.0", "display_name": "Business",
            "implementation_families": ["pypsa"],
        }],
    })
    assert _validate_catalog_expectation("pypsa-business-cases", snapshot, catalog).status == "failed"

    valid = ThreadSnapshot.from_document({
        **snapshot.to_document(),
        "active_model_context": {
            **snapshot.active_model_context.to_document(),
            "model_id": "regional-six-bus",
            "enabled_profiles": {"schema": "capstone-model-capability-selection/1", "enabled_profiles": [{"profile_id": "pypsa-business-cases", "profile_version": "1.0.0"}]},
        },
    })
    assert _validate_catalog_expectation("pypsa-business-cases", valid, catalog).status == "passed"
