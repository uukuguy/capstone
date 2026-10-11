"""Compact intent is expanded from registered contracts, never query rules."""
import copy
import pytest
from capstone_agent import task_recognition


def intent():
    return {"schema": "capstone-task-intent/1", "answer_policy": {"language": "zh", "scale": "standard"},
        "goals": [{"id": "goal1", "intent": "检查所选设备变更后的约束", "scope": "subset",
            "scenario": "changed", "conclusion": "limit", "measure": None,
            "execution": "professional", "dependencies": [], "missing_requirements": [],
            "domain_request": {"binding_id": "example", "schema": "example/1",
                "payload": {"action": "assess", "target": "selected"}}}]}


SCHEMAS = ({"binding_id": "example", "schema": "example/1",
    "recognition_projection": {"scope": "coverage", "scenario": "case", "measure": "metric"},
    "payload_fields": {"action": ["assess"], "target": "identifier", "coverage": ["subset", "full"],
        "case": ["changed", "baseline"], "metric": [None, "value"]}},)


def test_compact_intent_expands_once_without_changing_user_or_pack_data():
    source = intent()
    before = copy.deepcopy(source)
    expanded = task_recognition.expand_recognition_intent(source, SCHEMAS)
    goal = expanded["goals"][0]
    assert expanded["schema"] == "capstone-task-understanding/2"
    assert goal["domain_request"]["payload"] == {
        "action": "assess", "target": "selected", "coverage": "subset", "case": "changed", "metric": None}
    assert goal["purpose"] == goal["subject"] == goal["change"] == source["goals"][0]["intent"]
    assert goal["obligations"] == [source["goals"][0]["intent"]]
    assert source == before


def test_compact_intent_rejects_duplicate_projection_instead_of_overwriting_it():
    source = intent()
    source["goals"][0]["domain_request"]["payload"]["metric"] = "value"
    with pytest.raises(ValueError, match="duplicate"):
        task_recognition.expand_recognition_intent(source, SCHEMAS)


def test_projection_rejects_unknown_semantic_fields_and_colliding_targets():
    for projection in ({"execution": "action"}, {"scope": "case", "scenario": "case"}):
        schemas = ({**SCHEMAS[0], "recognition_projection": projection},)
        with pytest.raises(ValueError, match="projection"):
            task_recognition.expand_recognition_intent(intent(), schemas)


def test_general_intent_cannot_acquire_a_professional_payload():
    source = intent()
    source["goals"][0]["execution"] = "general"
    with pytest.raises(ValueError, match="general"):
        task_recognition.expand_recognition_intent(source, SCHEMAS)


def test_compact_wire_reaches_existing_strict_task_validation():
    from capstone_agent.task_understanding import TaskRequest, recognize_decision
    request = TaskRequest("thread", "turn", "attempt", "检查所选设备变更后的约束", 0,
                          "context", "model", "revision")
    expanded = task_recognition.expand_recognition_intent(intent(), SCHEMAS)
    task = recognize_decision(request, expanded, recognizer="controlled")
    task_recognition._validate_published_payload_fields(task, SCHEMAS)
    assert task.request == request
    assert task.goals[0].scope == "subset"
    assert task.goals[0].change == request.instruction
    assert task.to_document()["schema"] == "capstone-task-understanding/2"


def test_registered_semantic_constraints_fail_before_immutable_acceptance():
    from capstone_agent.task_understanding import TaskRequest, recognize_decision
    request = TaskRequest("thread", "turn", "attempt", "检查所选设备变更后的约束", 0,
                          "context", "model", "revision")
    constraints = {"properties": {"conclusion": {"const": "description"}}}
    schemas = ({**SCHEMAS[0], "recognition_constraints": constraints},)
    task = recognize_decision(request, task_recognition.expand_recognition_intent(intent(), schemas),
                              recognizer="controlled")
    with pytest.raises(ValueError, match="published constraints"):
        task_recognition._validate_published_payload_fields(task, schemas)


def test_general_compact_intent_keeps_no_domain_grant():
    from capstone_agent.task_understanding import TaskRequest, recognize_decision
    source = intent()
    source["goals"][0].update(execution="general", domain_request=None, scenario="none", scope="unspecified")
    request = TaskRequest("thread", "turn", "attempt", "Explain a general topic", 0,
                          "context", "model", "revision")
    task = recognize_decision(request, task_recognition.expand_recognition_intent(source, ()), recognizer="controlled")
    assert task.goals[0].domain_request is None
    assert task.goals[0].change is None


@pytest.mark.parametrize("scenario", [["changed"], {"value": "changed"}])
def test_invalid_wire_enum_stays_inside_the_bounded_correction_path(monkeypatch, tmp_path, scenario):
    import json
    from types import SimpleNamespace
    from capstone_agent.task_understanding import TaskRequest
    request = TaskRequest("thread", "turn", "attempt", "检查所选设备变更后的约束", 0,
                          "context", "model", "revision")
    claim = SimpleNamespace(task_request=request, task_history=None,
                            model_context=SimpleNamespace(to_document=lambda: {}))
    prompts = []
    class Client:
        def __init__(self, *args, **kwargs): pass
        def start(self): pass
        def stop(self): pass
        def prompt_and_wait(self, prompt, **kwargs):
            prompts.append(json.loads(prompt))
            wire = intent()
            if len(prompts) == 1:
                wire["goals"][0]["scenario"] = scenario
            return json.dumps(wire)
    monkeypatch.setattr(task_recognition, "PiRpcClient", Client)
    monkeypatch.setattr(task_recognition, "build_pi_launch",
                        lambda *args, **kwargs: SimpleNamespace(argv=("pi",), environment={}))
    task = task_recognition.recognize_with_pi(claim,
        runtime_host=SimpleNamespace(command=SimpleNamespace(argv=("pi",)), project_pi_dir=tmp_path),
        resolved_llm=SimpleNamespace(secret=None, config=SimpleNamespace(model="controlled")),
        base_environment={}, timeout_seconds=60, on_heartbeat=lambda: None, requirement_schemas=SCHEMAS)
    assert task.goals[0].scenario == "changed"
    assert len(prompts) == 2
    assert "intent scenario is invalid" in prompts[1]["validation_error"]
