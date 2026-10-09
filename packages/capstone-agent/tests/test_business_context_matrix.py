"""Scenario checks with controlled semantic decisions, not quality judgments."""
from dataclasses import replace

import pytest

from test_delegated_runtime import ContextSelector, Executor, Recognizer, factory, goal, run
from test_intent_runtime import claim


@pytest.mark.parametrize("direct", [False, True])
@pytest.mark.parametrize("instruction,related", [
    ("Explain a cooking method.", False),
    ("What is the weather today?", False),
    ("Explain how weather affects the selected grid model.", True),
    ("Explain line 11 in the selected model; report missing endpoint data.", True),
])
def test_task_background_follows_checked_semantic_selection(direct, instruction, related):
    service, current = claim()
    current = replace(current, instruction=instruction,
        attempt=replace(current.attempt, runtime_mode="pi_reference" if direct else "capstone"))
    refs = ["ctx_test"] if related else []
    decision = goal("answer", excerpt=instruction)
    decision["object_refs"] = refs
    executor = Executor()
    outcome = run(service, current, factory(executor, Recognizer([decision]), selector=ContextSelector(refs)))
    assert outcome.status == "completed"
    assert len(executor.requests) == 1
    context = executor.requests[0].business_context.to_document()
    assert [item["object_id"] for item in context["object_refs"]] == refs
    assert context["selection"]["state"] == ("selected" if related else "none")
    assert context["materials"] == []
    assert not outcome.result_refs and not outcome.evidence_refs


def test_mixed_weather_and_model_goals_keep_distinct_contexts():
    service, current = claim()
    current = replace(current, instruction="Explain weather impact on this model. Also give today's weather.")
    related = goal("model_weather", excerpt="Explain weather impact on this model.")
    related["object_refs"] = ["ctx_test"]
    unrelated = goal("weather", excerpt="Also give today's weather.")
    executor = Executor()
    outcome = run(service, current, factory(executor, Recognizer([related, unrelated])))
    assert outcome.status == "completed"
    contexts = [request.business_context.to_document() for request in executor.requests]
    assert contexts[0]["object_refs"][0]["object_id"] == "ctx_test"
    assert contexts[1]["object_refs"] == []
    assert contexts[0]["materials"] == contexts[1]["materials"] == []
