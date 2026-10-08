from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError
import time
import json

import pytest

from capstone_agent.request_intent import (
    IntentDecision, IntentEngineIdentity, IntentRecognizer, IntentRequest, NodeControl,
)


def request_document() -> dict:
    return {
        "schema": "capstone-intent-request/1", "thread_id": "thread_1",
        "turn_id": "turn_2", "attempt_id": "attempt_2", "instruction": "Translate it",
        "history_cutoff": 12,
        "messages": [{"message_id": "message_1", "role": "assistant", "content": "Prior answer",
                      "turn_id": "turn_1", "attempt_id": "attempt_1", "model_context_id": "context_1",
                      "status": "completed", "event_seq": 10}],
        "objects": [{"object_id": "context_1", "model_id": "model_1"}],
        "capabilities": [{"capability_id": "read_result", "available": True, "enabled": False}],
        "mode_hint": None,
    }


def decision_document() -> dict:
    return {
        "schema": "capstone-intent-decision/1", "attempt_id": "attempt_2", "history_cutoff": 12,
        "relationship": "continuation",
        "goals": [{"goal_id": "goal_1", "description": "Translate the prior answer", "operation": "rewrite",
                   "message_refs": ["message_1"], "object_refs": ["context_1"],
                   "capability_refs": [], "missing_requirements": []}], "clarification": None,
    }


def test_request_and_decision_defend_nested_input_and_output() -> None:
    document = request_document()
    original = deepcopy(document)
    request = IntentRequest.from_document(document)
    document["messages"][0]["turn_id"] = "other_turn"
    request.to_document()["capabilities"][0]["enabled"] = True
    assert request.to_document() == original
    assert request.request_id == "attempt_2"
    with pytest.raises((FrozenInstanceError, AttributeError)):
        request._document_json = "other"
    output = decision_document()
    decision = IntentDecision.from_document(output, request)
    output["goals"][0]["object_refs"].clear()
    decision.to_document()["goals"].clear()
    assert decision.to_document() == decision_document()
    assert decision.requires_business is False


@pytest.mark.parametrize("field,value", [
    ("unexpected", True), ("schema", "v2"), ("history_cutoff", True),
    ("history_cutoff", -1), ("instruction", "x" * 65537), ("mode_hint", 1),
    ("messages", [{}] * 257), ("objects", [{"object_id": "same"}] * 2),
    ("capabilities", [{"capability_id": "cap", "available": 1, "enabled": True}]),
    ("objects", [{"object_id": "obj", "value": float("nan")}]),
    ("objects", [{"object_id": "obj", "value": object()}]),
])
def test_request_rejects_invalid_or_unbounded_fields(field: str, value: object) -> None:
    document = request_document()
    document[field] = value
    with pytest.raises(ValueError):
        IntentRequest.from_document(document)


@pytest.mark.parametrize("field,value", [
    ("unexpected", True), ("relationship", "professional"), ("relationship", []), ("attempt_id", "another"),
    ("history_cutoff", 13), ("history_cutoff", True), ("goals", []),
])
def test_decision_rejects_invalid_identity_and_fields(field: str, value: object) -> None:
    document = decision_document()
    document[field] = value
    with pytest.raises(ValueError):
        IntentDecision.from_document(document, IntentRequest.from_document(request_document()))


@pytest.mark.parametrize("field,value", [
    ("operation", "shell"), ("operation", []), ("message_refs", ["invented"]), ("object_refs", ["invented"]),
    ("capability_refs", ["invented_weather"]), ("unexpected", True),
    ("missing_requirements", [float("inf")]), ("goal_id", ""),
    ("message_refs", ["message_1", "message_1"]),
])
def test_decision_rejects_invalid_goals(field: str, value: object) -> None:
    document = decision_document()
    document["goals"][0][field] = value
    with pytest.raises(ValueError):
        IntentDecision.from_document(document, IntentRequest.from_document(request_document()))


@pytest.mark.parametrize("operation", ["answer", "rewrite", "catalog_lookup", "external_lookup", "business_read", "business_execute"])
def test_operations_and_missing_capabilities_are_advice(operation: str) -> None:
    request = IntentRequest.from_document(request_document())
    document = decision_document()
    document["goals"][0].update(operation=operation, capability_refs=["read_result"],
                                 missing_requirements=["Weather service is unavailable"])
    decision = IntentDecision.from_document(document, request)
    assert decision.requires_business is (operation in {"business_read", "business_execute"})
    assert request.to_document()["capabilities"][0]["enabled"] is False


def test_implementations_use_one_engine_neutral_contract() -> None:
    class Recognizer:
        def __init__(self, engine: str):
            self.identity = IntentEngineIdentity(engine, "test-model", "revision-1")

        def recognize(self, request: IntentRequest, control: NodeControl) -> IntentDecision:
            control.checkpoint()
            return IntentDecision.from_document(decision_document(), request)

    request = IntentRequest.from_document(request_document())
    implementations: list[IntentRecognizer] = [Recognizer("pi"), Recognizer("small-model")]
    outputs = [impl.recognize(request, NodeControl(lambda: None, time.monotonic() + 10)).to_document()
               for impl in implementations]
    assert outputs[0] == outputs[1]
    assert implementations[0].identity.to_document()["engine"] == "pi"
    assert "engine" not in outputs[0]


def test_control_checks_cancellation_heartbeat_and_deadline() -> None:
    calls = []
    NodeControl(lambda: calls.append("check"), time.monotonic() + 10).checkpoint()
    assert calls == ["check"]
    with pytest.raises(TimeoutError):
        NodeControl(lambda: None, time.monotonic() - 1).checkpoint()
    def cancelled() -> None:
        raise RuntimeError("cancelled")
    with pytest.raises(RuntimeError, match="cancelled"):
        NodeControl(cancelled, time.monotonic() + 10).checkpoint()


@pytest.mark.parametrize("deadline", [float("nan"), float("inf"), True])
def test_control_rejects_invalid_deadlines(deadline: float) -> None:
    with pytest.raises(ValueError):
        NodeControl(lambda: None, deadline)


@pytest.mark.parametrize("field,value", [
    ("role", []), ("role", "toolResult"), ("unexpected", "untrusted"),
    ("event_seq", 13), ("thread_id", "another_thread"), ("turn_id", ""),
])
def test_history_sources_have_bounded_explicit_provenance(field: str, value: object) -> None:
    document = request_document()
    document["messages"][0][field] = value
    with pytest.raises(ValueError):
        IntentRequest.from_document(document)


def test_bounding_applies_to_bytes_and_recursive_metadata() -> None:
    document = request_document()
    document["messages"] = [dict(document["messages"][0], message_id=f"message_{i}", content="界" * 65536)
                            for i in range(2)]
    with pytest.raises(ValueError, match="byte limit"):
        IntentRequest.from_document(document)
    document = request_document()
    nested = document["objects"][0]
    for _ in range(20):
        nested["nested"] = {}
        nested = nested["nested"]
    with pytest.raises(ValueError, match="deeply nested"):
        IntentRequest.from_document(document)


def test_json_parser_rejects_duplicates_and_nonfinite_values() -> None:
    document = request_document()
    assert IntentRequest.from_json(json.dumps(document)).to_document() == document
    serialized = json.dumps(document).replace('"history_cutoff": 12', '"history_cutoff": 12, "history_cutoff": 11')
    with pytest.raises(ValueError, match="duplicate"):
        IntentRequest.from_json(serialized)
    document["objects"][0]["nonfinite"] = float("inf")
    with pytest.raises(ValueError):
        IntentRequest.from_json(json.dumps(document))
    request = IntentRequest.from_document(request_document())
    assert IntentDecision.from_json(json.dumps(decision_document()), request).to_document() == decision_document()
    for serialized in ("[]", "{", "x" * 65537):
        with pytest.raises(ValueError):
            IntentDecision.from_json(serialized, request)


def test_clarification_is_a_valid_decision_without_a_business_goal() -> None:
    document = decision_document()
    document.update(relationship="unclear", clarification="Which earlier answer should I translate?")
    decision = IntentDecision.from_document(document, IntentRequest.from_document(request_document()))
    assert decision.requires_business is False
    assert decision.to_document()["clarification"] == document["clarification"]


def test_control_checks_deadline_after_a_slow_lease_check(monkeypatch) -> None:
    ticks = iter([10.0, 12.0])
    monkeypatch.setattr("capstone_agent.request_intent.time.monotonic", lambda: next(ticks))
    with pytest.raises(TimeoutError):
        NodeControl(lambda: None, 11.0).checkpoint()


@pytest.mark.parametrize("identity", [("", "model", "revision"), ("pi", None, "revision"), ("pi", "model", "")])
def test_engine_identity_requires_explicit_nonempty_values(identity: tuple) -> None:
    with pytest.raises(ValueError):
        IntentEngineIdentity(*identity)


@pytest.mark.parametrize("role,status", [("assistant", "failed"), ("assistant", "cancelled"),
                                        ("assistant", "interrupted"), ("user", "running"),
                                        ("user", "unknown"), ("assistant", [])])
def test_history_rejects_nonterminal_and_partial_assistant_messages(role, status):
    document = request_document()
    document["messages"][0].update(role=role, status=status)
    with pytest.raises(ValueError):
        IntentRequest.from_document(document)


@pytest.mark.parametrize("status", ["completed", "failed", "cancelled", "interrupted"])
def test_user_history_keeps_terminal_attempt_status(status):
    document = request_document()
    document["messages"][0].update(role="user", status=status)
    assert IntentRequest.from_document(document).to_document()["messages"][0]["status"] == status


@pytest.mark.parametrize("section,field,value", [
    ("objects", "secret", "private"), ("objects", "model_id", []),
    ("capabilities", "endpoint", "https://unregistered.invalid"),
    ("capabilities", "registered", "yes"), ("capabilities", "implementation_families", "pandapower"),
    ("capabilities", "description", "x" * 8193),
    ("capabilities", "implementation_families", [""]),
])
def test_object_and_capability_metadata_are_explicit_bounded_fields(section, field, value):
    document = request_document()
    document[section][0][field] = value
    with pytest.raises(ValueError):
        IntentRequest.from_document(document)


def test_registered_capability_metadata_round_trips_without_mutation():
    document = request_document()
    document["objects"][0].update(model_revision="revision_1", display_name="Selected model", implementation_family="pandapower")
    document["capabilities"][0].update(registered=True, display_name="Result reader", description="Read registered results",
                                         implementation_families=["pandapower"])
    expected = deepcopy(document)
    request = IntentRequest.from_document(document)
    document["capabilities"][0]["implementation_families"].clear()
    request.to_document()["capabilities"][0]["implementation_families"].clear()
    assert request.to_document() == expected


def _weather_and_business_document():
    document = decision_document()
    weather = dict(document["goals"][0], goal_id="weather", operation="external_lookup",
                   message_refs=[], object_refs=[], capability_refs=[],
                   missing_requirements=["Weather service is unavailable"], depends_on=[])
    business = dict(document["goals"][0], goal_id="business", operation="business_execute",
                    capability_refs=["read_result"], depends_on=[])
    document["goals"] = [weather, business]
    return document


def test_independent_business_goal_can_execute_when_weather_is_missing():
    document = _weather_and_business_document()
    decision = IntentDecision.from_document(document, IntentRequest.from_document(request_document()))
    assert decision.requires_business is True
    assert [goal["goal_id"] for goal in decision.execution_goals] == ["business"]
    decision.execution_goals[0]["capability_refs"].clear()
    assert decision.execution_goals[0]["capability_refs"] == ["read_result"]


def test_weather_dependent_business_goal_cannot_execute():
    document = _weather_and_business_document()
    document["goals"][1]["depends_on"] = ["weather"]
    decision = IntentDecision.from_document(document, IntentRequest.from_document(request_document()))
    assert decision.requires_business is True
    assert decision.execution_goals == ()


def test_absent_dependencies_keep_conservative_ordered_compatibility():
    document = _weather_and_business_document()
    for goal in document["goals"]:
        del goal["depends_on"]
    decision = IntentDecision.from_document(document, IntentRequest.from_document(request_document()))
    assert decision.execution_goals == ()
    document["goals"][0]["missing_requirements"] = []
    decision = IntentDecision.from_document(document, IntentRequest.from_document(request_document()))
    assert [goal["goal_id"] for goal in decision.execution_goals] == ["weather", "business"]


def test_later_missing_requirements_cannot_block_earlier_executable_goals():
    document = _weather_and_business_document()
    document["goals"].reverse()
    decision = IntentDecision.from_document(document, IntentRequest.from_document(request_document()))
    assert [goal["goal_id"] for goal in decision.execution_goals] == ["business"]


def test_clarification_globally_stops_goal_execution():
    document = _weather_and_business_document()
    document["clarification"] = "Which location should be used?"
    decision = IntentDecision.from_document(document, IntentRequest.from_document(request_document()))
    assert decision.execution_goals == ()


@pytest.mark.parametrize("index,dependencies", [
    (0, ["weather"]), (0, ["business"]), (1, ["missing"]),
    (1, ["weather", "weather"]), (1, "weather"), (1, [None]),
])
def test_dependency_references_must_be_distinct_prior_goal_ids(index, dependencies):
    document = _weather_and_business_document()
    document["goals"][index]["depends_on"] = dependencies
    with pytest.raises(ValueError):
        IntentDecision.from_document(document, IntentRequest.from_document(request_document()))


def test_dependency_failures_propagate_to_later_goals():
    document = _weather_and_business_document()
    document["goals"][1]["depends_on"] = ["weather"]
    document["goals"].append(dict(document["goals"][1], goal_id="summary", operation="rewrite", depends_on=["business"]))
    decision = IntentDecision.from_document(document, IntentRequest.from_document(request_document()))
    assert decision.execution_goals == ()


@pytest.mark.parametrize("truncated", [True, False])
def test_request_preserves_explicit_history_truncation(truncated):
    document = request_document()
    document["history_truncated"] = truncated
    request = IntentRequest.from_document(document)
    assert request.to_document()["history_truncated"] is truncated
    assert IntentRequest.from_json(json.dumps(document)).to_document() == document


@pytest.mark.parametrize("truncated", [0, 1, "false", None, []])
def test_request_requires_boolean_history_truncation(truncated):
    document = request_document()
    document["history_truncated"] = truncated
    with pytest.raises(ValueError):
        IntentRequest.from_document(document)


def test_direct_constructors_have_the_same_validation_and_frozen_storage():
    document = request_document()
    request = IntentRequest(document)
    document["messages"][0]["content"] = "Changed after construction"
    assert request.to_document()["messages"][0]["content"] == "Prior answer"
    output = decision_document()
    decision = IntentDecision(output, request)
    output["goals"][0]["description"] = "Changed after construction"
    assert decision.to_document()["goals"][0]["description"] == "Translate the prior answer"
    with pytest.raises(ValueError):
        IntentRequest(dict(request_document(), extra=True))
    with pytest.raises(ValueError):
        IntentDecision(dict(decision_document(), extra=True), request)
