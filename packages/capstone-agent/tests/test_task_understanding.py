import copy

import pytest

from capstone_agent import task_understanding as tasks


def test_independent_general_goal_cannot_select_a_business_scenario():
    value = typed_proposal()
    value["goals"][0].update(execution="general", domain_request=None,
                              dependencies=[], scenario="baseline", change=None)
    with pytest.raises(ValueError, match="independent general task"):
        tasks.recognize_decision(request(), value, recognizer="controlled-model/1")


def test_independent_general_goal_without_business_scenario_is_valid():
    value = typed_proposal()
    value["goals"][0].update(execution="general", domain_request=None,
                              dependencies=[], scenario="none", change=None)
    decision = tasks.recognize_decision(request(), value, recognizer="controlled-model/1")
    assert decision.goals[0].execution == "general"


def test_historical_general_baseline_task_remains_replayable():
    value = typed_proposal()
    value["goals"][0].update(execution="general", domain_request=None,
                              dependencies=[], scenario="none", change=None)
    document = tasks.recognize_decision(request(), value, recognizer="controlled-model/1").to_document()
    document["goals"][0]["scenario"] = "baseline"
    assert tasks.TaskUnderstanding.from_document(document).goals[0].scenario == "baseline"


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


def typed_proposal():
    source = proposal()
    source["schema"] = "capstone-task-understanding/2"
    source["goals"][0].update(execution="professional", dependencies=[], domain_request={
        "binding_id": "grid", "schema": "pandapower-task-requirement/1",
        "payload": {"operation": "contingency", "objects": [{"kind": "line", "namespace": "name", "identifier": "line7"}]},
    })
    return source


def test_typed_domain_proposal_is_immutable_and_v2_round_trips():
    source = typed_proposal()
    decision = tasks.recognize_decision(request(), source, recognizer="controlled")
    source["goals"][0]["domain_request"]["payload"]["objects"][0]["identifier"] = "foreign"
    domain = decision.goals[0].domain_request
    assert domain.payload["objects"][0]["identifier"] == "line7"
    read = domain.payload
    read["objects"][0]["identifier"] = "foreign"
    assert domain.payload["objects"][0]["identifier"] == "line7"
    assert tasks.TaskUnderstanding.from_document(decision.to_document()) == decision
    assert decision.to_document()["schema"] == "capstone-task-understanding/2"


@pytest.mark.parametrize("mutate", [
    lambda p: p["goals"][0].update(execution="general"),
    lambda p: p["goals"][0].update(domain_request=None),
    lambda p: p["goals"][0].update(dependencies=["missing"]),
    lambda p: p["goals"][0].update(dependencies=["impact"]),
    lambda p: p["goals"][0]["domain_request"].update(completed=True),
    lambda p: p["goals"][0]["domain_request"]["payload"].update(factor=float("inf")),
])
def test_typed_proposal_rejects_invalid_execution_and_dependencies(mutate):
    source = typed_proposal()
    mutate(source)
    with pytest.raises(ValueError):
        tasks.recognize_decision(request(), source, recognizer="controlled")


def test_typed_proposal_rejects_dependency_cycles():
    source = typed_proposal()
    second = copy.deepcopy(source["goals"][0])
    second.update(id="limits", dependencies=["impact"])
    source["goals"][0]["dependencies"] = ["limits"]
    source["goals"].append(second)
    with pytest.raises(ValueError):
        tasks.recognize_decision(request(), source, recognizer="controlled")


def test_v1_keeps_exact_document_shape_and_has_no_executable_certificate():
    decision = tasks.recognize_decision(request(), proposal(), recognizer="controlled")
    assert decision.goals[0].execution is None
    assert decision.goals[0].domain_request is None
    assert "execution" not in decision.to_document()["goals"][0]


def test_typed_payload_depth_is_bounded():
    source = typed_proposal()
    payload = source["goals"][0]["domain_request"]["payload"]
    for _ in range(12):
        payload["nested"] = {}
        payload = payload["nested"]
    with pytest.raises(ValueError):
        tasks.recognize_decision(request(), source, recognizer="controlled")


def test_general_goal_can_follow_a_professional_goal_without_getting_domain_grants():
    source = typed_proposal()
    general = copy.deepcopy(source["goals"][0])
    general.update(id="explain", execution="general", dependencies=["impact"], domain_request=None)
    source["goals"].append(general)
    decision = tasks.recognize_decision(request(), source, recognizer="controlled")
    assert decision.goals[1].dependencies == ("impact",)
    assert decision.goals[1].domain_request is None


def test_direct_domain_constructor_rejects_duplicate_payload_fields():
    with pytest.raises(ValueError):
        tasks.DomainTaskProposal("grid", "pack-task/1", '{"operation":"overview","operation":"powerflow"}')


def test_direct_domain_constructor_bounds_canonical_bytes_after_number_expansion():
    payload = "{" + ",".join('"k' + str(i) + '":[' + ",".join(["1e9"] * 64) + "]" for i in range(12)) + "}"
    assert len(payload.encode()) < 8192
    with pytest.raises(ValueError):
        tasks.DomainTaskProposal("grid", "pack-task/1", payload)
