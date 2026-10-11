from types import SimpleNamespace
import pytest
from capability_agent.domain.task import ResolvedTaskGoal
from capstone_agent.task_understanding import TaskRequest


def test_prior_candidates_are_handed_only_to_the_selected_pack():
    from capstone_agent.task_resolution import resolve_profiles
    from capstone_agent.task_understanding import DomainTaskProposal
    selected = []
    class Provider:
        schema = "test/1"
        def required_capabilities(self, payload):
            return ()
        def resolve(self, goal_id, payload, **kwargs):
            return ResolvedTaskGoal(goal_id, "ready", "{}")
        def bind_result_candidates(self, task, *, authority, candidates):
            selected.extend(candidates)
            return task
    runtime = SimpleNamespace(profile=SimpleNamespace(manifest=SimpleNamespace(domain_id="selected-pack"), task_provider=Provider()),
                              authority=object(), capability_documents=())
    binding = SimpleNamespace(runtime=runtime, endpoint=SimpleNamespace(executor=None))
    profile = SimpleNamespace(prepared_application=SimpleNamespace(bindings={"binding": binding}),
                              model_binding=SimpleNamespace(context_ref="context", model_revision="revision"))
    goal = SimpleNamespace(id="g", execution="professional", missing_requirements=(), dependencies=(),
                          domain_request=DomainTaskProposal("binding", "test/1", "{}"), to_document=lambda: {})
    prior = tuple(SimpleNamespace(domain_pack_id=pack, result_ref=ref, evidence_refs=())
                  for pack, ref in (("selected-pack", "selected-result"), ("other-pack", "foreign-result")))
    claim = SimpleNamespace(task_understanding=SimpleNamespace(goals=(goal,),
        answer_policy=SimpleNamespace(language="en", scale="standard")), prior_results=prior)
    assert resolve_profiles(claim, (profile,))[0].status == "ready"
    assert selected == [("selected-result", ())]


@pytest.mark.parametrize("status,model_text,expected", [
    ("supported", "Complete reader report: voltage, loading and losses.", "Complete reader report: voltage, loading and losses."),
    ("supported", "", "Verified coverage summary."),
    ("partial", "All requested work is complete.", "Verified coverage summary."),
    ("unresolved", "All requested work is complete.", "Verified coverage summary."),
])
def test_supported_professional_answer_preserves_final_prose_without_bypassing_coverage(
    monkeypatch, status, model_text, expected,
):
    from dataclasses import replace
    from capability_agent.domain.task import TaskConclusion
    from capstone_agent.harness import AdmittedAttemptAnswer
    import capstone_agent.kernel_pi_session as module
    from test_kernel_bound_admission import _admission, CONTEXT, REVISION, EVIDENCE
    admit, claim, _ = _admission({"context_ref": CONTEXT, "revision_ref": REVISION})
    claim = replace(claim, task_resolutions=(ResolvedTaskGoal("g", "ready", "{}", binding_id="grid"),))
    formal = AdmittedAttemptAnswer(
        "Verified coverage summary.", "authority_backed", "lineage_verified", (), (EVIDENCE,),
        ("task_goal_coverage_verified",), goal_conclusions=(TaskConclusion("g", status, "Verified coverage summary.", evidence_refs=(EVIDENCE,)),),
    )
    monkeypatch.setattr(module, "_task_conclusion_answer", lambda *args, **kwargs: formal)
    result = admit(claim, model_text, (), (EVIDENCE,), ({"binding_id": "grid", "ok": True, "evidence_refs": [EVIDENCE]},))
    assert result.answer == expected
    assert result.goal_conclusions == formal.goal_conclusions
    assert result.evidence_refs == (EVIDENCE,)


def test_supported_final_prose_keeps_additional_verified_result_evidence(monkeypatch):
    from dataclasses import replace
    from capability_agent.domain.task import TaskConclusion
    from capstone_agent.harness import AdmittedAttemptAnswer
    import capstone_agent.kernel_pi_session as module
    from test_kernel_bound_admission import _admission, CONTEXT, REVISION, EVIDENCE
    extra = "evidence:sha256:" + "d" * 64
    admit, claim, _ = _admission({"context_ref": CONTEXT, "revision_ref": REVISION})
    claim = replace(claim, task_resolutions=(ResolvedTaskGoal("g", "ready", "{}", binding_id="grid"),))
    formal = AdmittedAttemptAnswer("Verified coverage summary.", "authority_backed", "lineage_verified",
        (), (EVIDENCE,), ("task_goal_coverage_verified",),
        goal_conclusions=(TaskConclusion("g", "supported", "Verified coverage summary.", evidence_refs=(EVIDENCE,)),))
    monkeypatch.setattr(module, "_task_conclusion_answer", lambda *args, **kwargs: formal)
    answer = admit(claim, "Report includes the verified optional assessment.", (), (EVIDENCE, extra),
        ({"binding_id": "grid", "ok": True, "evidence_refs": [EVIDENCE, extra]},))
    assert answer.evidence_refs == (EVIDENCE, extra)
    assert answer.goal_conclusions == formal.goal_conclusions
    assert "answer_semantics_not_verified" in answer.diagnostic_codes


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


def test_chinese_missing_requirements_do_not_gain_english_process_prefix():
    from capstone_agent.task_resolution import resolve_profiles, render_conclusions
    from capability_agent.domain.task import TaskConclusion
    goal = SimpleNamespace(id="g", execution="professional", missing_requirements=("请确认线路标识。",),
                           domain_request=None, dependencies=())
    claim = SimpleNamespace(task_understanding=SimpleNamespace(goals=(goal,)))
    resolved = resolve_profiles(claim, ())
    answer = render_conclusions((TaskConclusion("g", "clarification", resolved[0].reason),), language="zh", scale="concise")
    assert answer == "请确认线路标识。"


def test_pending_typed_proposal_never_checks_or_calls_pack():
    from capstone_agent.task_resolution import resolve_profiles
    from capstone_agent.task_understanding import DomainTaskProposal
    class ForbiddenPack:
        def required_capabilities(self, payload):
            raise AssertionError("Pending input must not reach Pack validation or execution")
    binding = SimpleNamespace(runtime=SimpleNamespace(profile=SimpleNamespace(task_provider=ForbiddenPack())))
    profiles = (SimpleNamespace(prepared_application=SimpleNamespace(bindings={"test": binding})),)
    proposal = DomainTaskProposal("test", "test/1", '{"changes":[{}]}')
    goal = SimpleNamespace(id="g", execution="professional", missing_requirements=("Multiplier is not chosen",),
                           domain_request=proposal, dependencies=())
    result, = resolve_profiles(SimpleNamespace(task_understanding=SimpleNamespace(goals=(goal,))), profiles)
    assert result.status == "clarification" and result.execution_required is False
    assert result.requirement_json == "{}"
    assert proposal.payload == {"changes": [{}]}
