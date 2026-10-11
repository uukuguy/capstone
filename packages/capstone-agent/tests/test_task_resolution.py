from types import SimpleNamespace
import pytest
from capability_agent.domain.task import ResolvedTaskGoal
from capstone_agent.task_understanding import TaskRequest


def test_resolution_replay_rejects_changed_digest():
    from capstone_agent.task_resolution import resolution_payload, resolution_state_from_events
    request = TaskRequest("t", "v", "a", "question", 0, "c", "m", "r")
    resolved = (ResolvedTaskGoal("g", "unsupported", "{}", "not registered", "grid"),)
    payload = resolution_payload(request, resolved)
    restored = resolution_state_from_events([SimpleNamespace(event_type="task_requirements_resolved", payload=payload)], request=request)
    assert restored["task_resolutions"] == resolved
    assert restored["task_resolution_route"] == "professional"
    payload["goals"][0]["reason"] = "changed"
    with pytest.raises(ValueError):
        resolution_state_from_events([SimpleNamespace(event_type="task_requirements_resolved", payload=payload)], request=request)


def test_formal_answer_keeps_supported_goal_when_other_is_unresolved():
    from capstone_agent.task_resolution import render_conclusions
    from capability_agent.domain.task import TaskConclusion
    text = render_conclusions((TaskConclusion("g1", "supported", "The outage produced 2 limit violations."),
        TaskConclusion("g2", "unresolved", "The changed-load result is missing.")), language="en", scale="concise")
    assert "2 limit violations" in text
    assert "changed-load result is missing" in text


def test_selected_pack_compatibility_keeps_execution_explicitly_uncertified():
    from capstone_agent.task_resolution import resolve_profiles, requirement_schemas
    from capstone_agent.task_understanding import DomainTaskProposal
    provider = SimpleNamespace(profile=SimpleNamespace(task_provider=None))
    profiles = (SimpleNamespace(prepared_application=SimpleNamespace(bindings={"pypsa": SimpleNamespace(runtime=provider)})),)
    schemas = requirement_schemas(profiles)
    assert schemas[0]["binding_id"] == "pypsa"
    assert schemas[0]["schema"] == "capstone-professional-task/1"
    goal = SimpleNamespace(id="g", execution="professional", missing_requirements=(), dependencies=(),
                           domain_request=DomainTaskProposal("pypsa", schemas[0]["schema"], '{"purpose":"run published dispatch"}'),
                           to_document=lambda: {"id": "g", "purpose": "run published dispatch"})
    resolved = resolve_profiles(SimpleNamespace(task_understanding=SimpleNamespace(goals=(goal,))), profiles)
    assert resolved[0].status == "uncertified"
    assert resolved[0].execution_required is True
    assert "unsupported" not in resolved[0].reason


def test_pypsa_compatibility_preserves_existing_reference_admission():
    from test_kernel_bound_admission import _admission, CONTEXT, REVISION, EVIDENCE
    from dataclasses import replace
    admit, claim, _ = _admission({"context_ref": CONTEXT, "revision_ref": REVISION}, family="pypsa")
    from capstone_agent.task_understanding import AnswerPolicy, SemanticGoal, TaskUnderstanding
    request = TaskRequest(claim.thread_id, claim.attempt.turn_id, claim.attempt.attempt_id, claim.instruction, 0,
                          claim.model_context.id, claim.model_context.model_id, claim.model_context.model_revision)
    understanding = TaskUnderstanding(request, "controlled", (SemanticGoal("g", "purpose", "model", "full", "baseline", None, "impact", None, ("result",), ()),), AnswerPolicy("en", "concise"))
    claim = replace(claim, task_request=request, task_understanding=understanding,
                    task_resolutions=(ResolvedTaskGoal("g", "uncertified", "{}", binding_id="grid", execution_required=True),))
    answer = admit(claim, "existing admitted answer", (), (EVIDENCE,), ({"binding_id": "grid", "ok": True, "evidence_refs": [EVIDENCE]},))
    assert answer.evidence_refs == (EVIDENCE,)
    assert "existing admitted answer" in answer.answer
    assert "task_goal_coverage_unverified" in answer.diagnostic_codes
    assert "has not verified task goal coverage" in answer.answer


def test_explicit_ordinary_mode_never_resolves_professional_objects():
    from capstone_agent.task_resolution import resolve_profiles
    goal = SimpleNamespace(id="g", execution="professional")
    claim = SimpleNamespace(kind="send_ordinary", task_understanding=SimpleNamespace(goals=(goal,)))
    resolved = resolve_profiles(claim, ())
    assert resolved[0].status == "clarification" and not resolved[0].execution_required
