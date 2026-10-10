import copy

import pytest

from capstone_agent import task_understanding as tasks


def request():
    return tasks.TaskRequest("thread_1", "turn_1", "attempt_1", "分析故障影响", 12,
                             "context_1", "ieee39", "revision_1")


def proposal():
    return {
        "schema": "capstone-task-understanding/1",
        "goals": [{"id": "impact", "purpose": "判断线路故障影响", "subject": "线路7",
                   "scope": "subset", "scenario": "contingency", "change": "线路7断开",
                   "conclusion": "impact", "measure": None,
                   "obligations": ["故障后的越限情况"], "missing_requirements": []}],
        "answer_policy": {"language": "zh", "scale": "concise"},
    }


def test_task_round_trip_binds_host_identity_and_detaches_input():
    source = proposal()
    decision = tasks.recognize_decision(request(), source, recognizer="controlled-model/1")
    source["goals"][0]["obligations"].append("invented")
    document = decision.to_document()
    assert document["request"]["history_cutoff"] == 12
    assert document["request"]["model_revision"] == "revision_1"
    assert document["goals"][0]["obligations"] == ["故障后的越限情况"]
    assert tasks.TaskUnderstanding.from_document(document) == decision


@pytest.mark.parametrize("mutate", [
    lambda p: p.update(model_id="foreign"),
    lambda p: p["goals"].append(copy.deepcopy(p["goals"][0])),
    lambda p: p["goals"][0].update(scope="all"),
    lambda p: p["goals"][0].update(scenario="guessed"),
    lambda p: p["goals"][0].update(completed=True),
    lambda p: p["answer_policy"].update(scale="unbounded"),
    lambda p: p["goals"][0].update(obligations=[]),
    lambda p: p.update(goals=[]),
])
def test_invalid_or_self_certified_proposals_are_rejected(mutate):
    value = proposal()
    mutate(value)
    with pytest.raises(ValueError):
        tasks.recognize_decision(request(), value, recognizer="controlled-model/1")


def test_changed_scenario_requires_explicit_change():
    value = proposal()
    value["goals"][0].update(scenario="changed", change="")
    with pytest.raises(ValueError):
        tasks.recognize_decision(request(), value, recognizer="controlled-model/1")


def test_unresolved_scope_remains_unspecified():
    value = proposal()
    value["goals"][0].update(scope="unspecified", missing_requirements=["故障集合未指定"])
    decision = tasks.recognize_decision(request(), value, recognizer="controlled-model/1")
    assert decision.goals[0].scope == "unspecified"
    assert decision.goals[0].missing_requirements == ("故障集合未指定",)


def test_saved_contract_cannot_be_rebound_to_foreign_request():
    decision = tasks.recognize_decision(request(), proposal(), recognizer="controlled-model/1")
    document = decision.to_document()
    document["request"]["model_revision"] = "foreign"
    with pytest.raises(ValueError):
        tasks.TaskUnderstanding.from_document(document, expected_request=request())


def test_large_decision_is_rejected_before_semantic_decode():
    value = proposal()
    value["goals"][0]["subject"] = "x" * 40_000
    with pytest.raises(ValueError):
        tasks.recognize_decision(request(), value, recognizer="controlled-model/1")


def test_boolean_history_cutoff_is_rejected():
    with pytest.raises(ValueError):
        tasks.TaskRequest("thread_1", "turn_1", "attempt_1", "question", True,
                          "context_1", "ieee39", "revision_1")


def test_history_cutoff_fits_ledger_integer():
    with pytest.raises(ValueError):
        tasks.TaskRequest("thread_1", "turn_1", "attempt_1", "question", 2**63,
                          "context_1", "ieee39", "revision_1")


def test_direct_goal_constructor_detaches_lists():
    obligations = ["impact"]
    goal = tasks.SemanticGoal("g", "impact", "line7", "subset", "contingency", "outage",
                              "impact", None, obligations, [])
    obligations.append("invented")
    assert goal.obligations == ("impact",)


def test_direct_answer_policy_cannot_bypass_validation():
    with pytest.raises(ValueError):
        tasks.AnswerPolicy("zh", "unbounded")


def test_direct_task_constructor_rejects_empty_goals():
    with pytest.raises(ValueError):
        tasks.TaskUnderstanding(request(), "recognizer", (), tasks.AnswerPolicy("zh", "concise"))
