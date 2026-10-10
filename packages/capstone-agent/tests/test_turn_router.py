from __future__ import annotations

import pytest

from capstone_agent.thread_service import InMemoryThreadService
from capstone_agent.turn_router import (
    DecisionUnavailable,
    DefaultTurnRouter,
    FakeDecisionRouter,
    JevDecisionRouter,
    RouterConfig,
    routing_input_for_claim,
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
    ).plan(routing_input_for_claim(claim))
    assert plan.route == "professional"
    assert plan.source == "fake"
    assert plan.context_snapshot == {
        "model_id": "ieee39", "model_revision": "revision:sha256:" + "a" * 64,
        "model_context_id": "ctx_ieee39", "implementation_family": "pandapower",
        "selection_revision": "sel_0", "enabled_profiles": [],
    }
    assert len(str(plan.to_payload())) < 1024
    del service


def test_jev_is_disabled_by_default_and_enabled_classifier_is_input_bounded() -> None:
    service, claim = _claim(text="api_key=supersecret /Users/private/file " + "x" * 5000)
    seen: list[str] = []
    router = JevDecisionRouter(lambda text: seen.append(text) or "ordinary")
    with pytest.raises(DecisionUnavailable, match="disabled"):
        router.plan(routing_input_for_claim(claim))
    router.enabled = True
    plan = router.plan(routing_input_for_claim(claim))
    assert plan.route == "ordinary"
    assert len(seen[0]) <= 2048
    assert "supersecret" not in seen[0]
    assert "/Users/private/file" not in seen[0]
    del service


def test_router_reports_invalid_decision_without_a_fallback() -> None:
    service, claim = _claim()
    router = DefaultTurnRouter(
        decision_router=JevDecisionRouter(lambda _text: "unknown", enabled=True),
    )
    with pytest.raises(DecisionUnavailable, match="intent_recognition_failed"):
        router.plan(claim)
    del service


def test_disabled_ordinary_policy_fails_closed() -> None:
    service, claim = _claim("send_ordinary")
    with pytest.raises(DecisionUnavailable, match="disabled"):
        DefaultTurnRouter(ordinary_conversation_enabled=False).plan(claim)
    del service


@pytest.mark.parametrize("text", [
    "hello", "明天北京天气", "把刚才的结论翻译成英文", "请检查 IEEE-39 线路越限",
    "What is power flow?", "Which PyPSA models are available?",
    "List pandapower networks and calculate voltages.",
])
def test_auto_without_recognizer_fails_for_every_request(text):
    service, claim = _claim(text=text)
    with pytest.raises(DecisionUnavailable, match="intent_recognizer_unavailable"):
        DefaultTurnRouter().plan(claim)
    del service


@pytest.mark.parametrize("kind,route", [("send_ordinary", "ordinary"), ("send_professional", "professional")])
@pytest.mark.parametrize("text", ["Hello", "Which models are available?", "Calculate model voltages"])
def test_explicit_compatibility_modes_keep_the_requested_route(kind, route, text):
    service, claim = _claim(kind, text)
    plan = DefaultTurnRouter().plan(claim)
    assert plan.route == route and plan.source == "explicit" and plan.fallback is False
    del service


@pytest.mark.parametrize("mode", ["off", "heuristic", "jev_shadow"])
def test_inactive_or_old_heuristic_modes_cannot_supply_an_auto_route(mode):
    service, claim = _claim()
    calls = []
    router = DefaultTurnRouter(
        decision_router=FakeDecisionRouter(lambda text: calls.append(text) or "ordinary"),
        config=RouterConfig(mode=mode),
    )
    with pytest.raises(DecisionUnavailable, match="intent_recognizer_unavailable"):
        router.plan(claim)
    assert calls == []
    del service
