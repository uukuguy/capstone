from __future__ import annotations

import pytest

from capstone_agent.thread_service import InMemoryThreadService
from capstone_agent.turn_router import (
    DecisionUnavailable,
    DefaultTurnRouter,
    FakeDecisionRouter,
    JevDecisionRouter,
)


def _service() -> InMemoryThreadService:
    return InMemoryThreadService.from_document({
        "schema": "capstone-thread-snapshot/1", "thread_id": "thr_router",
        "run": {"run_id": "run_router", "state": "open"},
        "active_model_context": {
            "id": "ctx_ieee39", "model_id": "ieee39",
            "model_revision": "revision:sha256:" + "a" * 64,
            "implementation_family": "pandapower", "selection_revision": "sel_0",
        },
        "active_grid_page_id": "page_ieee39", "current_attempt": None,
        "last_event_seq": 0, "base_event_seq": 0,
    })


def _claim(kind: str = "send_auto", text: str = "hello"):
    service = _service()
    service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_router_001",
        "idempotency_key": "idem_router_001", "thread_id": "thr_router",
        "run_id": "run_router", "kind": kind, "expected_event_seq": 0,
        "payload": {"text": text},
    })
    claim = service.claim_attempt("router-worker", lease_seconds=30)
    assert claim is not None
    return service, claim


def test_auto_router_uses_fixture_and_keeps_context_bounded() -> None:
    service, claim = _claim()
    plan = DefaultTurnRouter(
        decision_router=FakeDecisionRouter("professional"),
    ).plan(claim)
    assert plan.route == "professional"
    assert plan.source == "classifier"
    assert plan.context_snapshot == {
        "model_id": "ieee39", "implementation_family": "pandapower",
        "selection_revision": "sel_0", "enabled_profiles": [],
    }
    assert len(str(plan.to_payload())) < 1024
    del service


def test_jev_is_disabled_by_default_and_enabled_classifier_is_input_bounded() -> None:
    service, claim = _claim()
    seen: list[str] = []
    router = JevDecisionRouter(lambda text: seen.append(text) or "ordinary")
    with pytest.raises(DecisionUnavailable, match="disabled"):
        router.plan(claim)
    router.enabled = True
    plan = router.plan(claim)
    assert plan.route == "ordinary"
    assert seen == ["hello"]
    del service


def test_router_falls_back_to_ordinary_when_decision_is_unavailable() -> None:
    service, claim = _claim()
    plan = DefaultTurnRouter(
        decision_router=JevDecisionRouter(lambda _text: "unknown", enabled=True),
    ).plan(claim)
    assert plan.route == "ordinary"
    assert plan.fallback is True
    assert plan.source == "decision_unavailable"
    del service


def test_disabled_ordinary_policy_fails_closed() -> None:
    service, claim = _claim("send_ordinary")
    with pytest.raises(DecisionUnavailable, match="disabled"):
        DefaultTurnRouter(ordinary_conversation_enabled=False).plan(claim)
    del service


def test_auto_without_external_classifier_uses_bounded_domain_hint() -> None:
    service, claim = _claim(text="请检查 IEEE-39 线路越限")
    assert DefaultTurnRouter().plan(claim).route == "professional"
    del service
