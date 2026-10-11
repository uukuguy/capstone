"""Controlled semantic proposals with the real registered grid Authority."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from capstone_agent.task_understanding import TaskRequest, recognize_decision
from capstone_agent.task_resolution import resolve_profiles
from capstone_agent.kernel_pi_session import _build_kernel_admission, _ResolvedTaskSession
from capstone_agent.kernel_capability_preparation import AuthorityModelBinding
from grid_simulator.operations import dispatch
from grid_simulator.protocol import GridCapabilityRequest
from pandapower_domain import build_pandapower_profile
from pandapower_domain.execution import SimulatorCapabilityError


@pytest.mark.parametrize("namespace,identifier,status", [("name", "line7", "clarification"),
    ("pandapower_index", "99999", "clarification"), ("pandapower_index", "7", "ready"),
    ("name", "duplicate", "clarification"), ("name", "transport-failure", "transport-failure")])
def test_selector_resolution_through_registered_application(tmp_path, monkeypatch, namespace, identifier, status):
    from capability_agent.application.composition import prepare_application
    from capability_agent.application.workspace import ApplicationWorkspace
    from capstone_agent.application import EmptyCredentialBroker, domain_registry
    from grid_agent.application.profile import build_pandapower_application_profile
    from pandapower_domain.task_coverage import PandapowerTaskProvider
    profile = build_pandapower_application_profile()
    workspace = ApplicationWorkspace.create(tmp_path, binding_ids=("grid",))
    prepared = prepare_application(profile, registry=domain_registry(profile), workspace=workspace.root,
                                   credentials=EmptyCredentialBroker())
    executor = prepared.bindings["grid"].endpoint.executor
    context = executor.invoke("context.open", {"model_id": "ieee39"})
    if identifier == "duplicate":
        context = executor.invoke("model.revision.derive", {"context_ref": context["context_ref"], "patches": [
            {"operation": "set", "kind": "line", "selector": {"indices": [2, 3]}, "values": {"name": "duplicate"}}]})
    if status == "transport-failure":
        from pandapower_domain.execution import GridctlExecutor
        def unavailable(*args):
            raise RuntimeError("private transport detail")
        monkeypatch.setattr(GridctlExecutor, "invoke", unavailable)
    def resolve():
        return PandapowerTaskProvider().resolve("g", {
        "operation": "contingency", "objects": [{"kind": "line", "namespace": namespace, "identifier": identifier}],
        "changes": [], "measure": None, "direction": None, "scenario": "contingency", "scope": "subset"},
        context_ref=context["context_ref"], revision_ref=context["revision_ref"], invoke=executor.invoke)
    try:
        if status == "transport-failure":
            from capability_agent.application.errors import CapabilityTransportError
            with pytest.raises(CapabilityTransportError, match="capability transport failed"):
                resolve()
        else:
            assert resolve().status == status
    finally:
        prepared.bindings["grid"].endpoint.close()


@pytest.fixture
def environment(tmp_path):
    calls = []
    def invoke(capability, arguments):
        calls.append(capability)
        response = dispatch(GridCapabilityRequest(protocol="grid-capability", protocol_version="1.0", request_id="closure",
                            capability=capability, arguments=arguments), tmp_path)
        if not response.ok:
            raise SimulatorCapabilityError(response.error.model_dump())
        return response.result
    context = invoke("context.open", {"model_id": "ieee39"})
    pack = build_pandapower_profile()
    binding = SimpleNamespace(runtime=SimpleNamespace(profile=pack, authority=pack.create_authority(tmp_path), capability_documents=pack.contract_source.load()),
                              binding=SimpleNamespace(tool_namespace="grid_"), endpoint=SimpleNamespace(executor=SimpleNamespace(invoke=invoke)))
    profile = SimpleNamespace(prepared_application=SimpleNamespace(bindings={"grid": binding}),
                              model_binding=AuthorityModelBinding("grid", "ieee39", context["revision_ref"], "pandapower", context["context_ref"]))
    return invoke, context, (profile,), calls


def recognized(context, *, operation, scenario="baseline", objects=None, changes=None):
    request = TaskRequest("thread", "turn", "attempt", "controlled request", 0, "ctx", "ieee39", context["revision_ref"])
    understanding = recognize_decision(request, {"schema": "capstone-task-understanding/2", "goals": [{
        "id": "g", "purpose": "requested task", "subject": "selected model", "scope": "subset", "scenario": scenario,
        "change": None if scenario == "baseline" else "requested scenario", "conclusion": "description" if operation == "overview" else "impact", "measure": None,
        "obligations": ["requested conclusion"], "missing_requirements": [], "execution": "professional", "dependencies": [],
        "domain_request": {"binding_id": "grid", "schema": "pandapower-task-requirement/1", "payload": {
            "operation": operation, "objects": objects or [], "changes": changes or [], "measure": None,
            "direction": "descending", "scenario": scenario, "scope": "subset"}}}],
        "answer_policy": {"language": "en", "scale": "concise"}}, recognizer="controlled")
    return SimpleNamespace(task_understanding=understanding, task_request=request, task_resolutions=(),
                           turn_plan=SimpleNamespace(route="professional"), instruction=request.instruction,
                           model_context=SimpleNamespace(model_revision=context["revision_ref"], id="ctx", model_id="ieee39", implementation_family="pandapower"),
                           thread_id="thread", run_id="run", attempt=SimpleNamespace(turn_id="turn", attempt_id="attempt"))


def test_unsupported_generator_finishes_without_unrelated_authority_work(environment):
    invoke, context, profiles, calls = environment
    claim = recognized(context, operation="contingency", scenario="contingency",
                       objects=[{"kind": "gen", "namespace": "all", "identifier": "*"}])
    calls.clear()
    claim.task_resolutions = resolve_profiles(claim, profiles)
    session = _ResolvedTaskSession(claim, profiles)
    answer = session.prompt_and_wait("request", on_semantic_event=lambda event: None, correlation_id="a", on_heartbeat=lambda: None)
    admitted = session.admit_attempt(claim, answer, (), (), ())
    assert "not supported" in admitted.answer
    assert admitted.diagnostic_codes == ("task_capability_boundary_verified",)
    assert calls == []


def test_mixed_clarification_retains_verified_capability_boundary(environment):
    _, context, profiles, _ = environment
    claim = recognized(context, operation="contingency", scenario="contingency",
                       objects=[{"kind": "gen", "namespace": "all", "identifier": "*"}])
    original = claim.task_understanding.goals[0]
    claim.task_understanding = replace(claim.task_understanding, goals=(original,
        replace(original, id="followup", dependencies=(original.id,), missing_requirements=("Need a separate object",))))
    claim.task_resolutions = resolve_profiles(claim, profiles)
    session = _ResolvedTaskSession(claim, profiles)
    answer = session.prompt_and_wait("request", on_semantic_event=lambda event: None, correlation_id="a", on_heartbeat=lambda: None)
    admitted = session.admit_attempt(claim, answer, (), (), ())
    assert set(admitted.diagnostic_codes) == {"task_capability_boundary_verified", "task_clarification_verified"}
    assert "Need a separate object" not in admitted.answer
    assert "preceding goal" in admitted.answer


def test_outage_formal_conclusion_survives_optional_query_failure(environment):
    invoke, context, profiles, _ = environment
    claim = recognized(context, operation="contingency", scenario="contingency",
                       objects=[{"kind": "line", "namespace": "pandapower_index", "identifier": "0"}])
    claim.task_resolutions = resolve_profiles(claim, profiles)
    branch = claim.task_resolutions[0].requirement["targets"][0]["asset_ref"]
    result = invoke("analysis.contingency.n_minus_one.run", {"context_ref": context["context_ref"], "branch_refs": [branch]})
    refs, evidence = (result["result_ref"],), tuple(result["evidence_refs"])
    events = ({"binding_id": "grid", "ok": True, "capability": "analysis.contingency.n_minus_one.run",
               "result_refs": refs, "evidence_refs": evidence},
              {"binding_id": "grid", "ok": False, "capability": "result.query", "error_code": "field_unavailable"})
    answer = _build_kernel_admission(profiles)(claim, "unrelated baseline table", refs, evidence, events)
    assert "1 of 1" in answer.answer and "limit violations" in answer.answer
    assert "baseline table" not in answer.answer
    assert answer.mode == "authority_backed"


def test_changed_lineage_is_allowed_only_for_resolved_patches(environment):
    invoke, context, profiles, _ = environment
    claim = recognized(context, operation="powerflow", scenario="changed", changes=[{
        "target": {"kind": "bus", "namespace": "pandapower_index", "identifier": "3"}, "fields": ["p_mw", "q_mvar"], "factor": 1.2}])
    claim.task_resolutions = resolve_profiles(claim, profiles)
    changed = invoke("model.revision.derive", {"context_ref": context["context_ref"], "patches": claim.task_resolutions[0].requirement["patches"]})
    result = invoke("analysis.powerflow.ac.run", {"context_ref": changed["context_ref"]})
    refs, evidence = (result["result_ref"],), tuple(result["evidence_refs"])
    events = ({"binding_id": "grid", "ok": True, "capability": "analysis.powerflow.ac.run", "result_refs": refs, "evidence_refs": evidence},)
    answer = _build_kernel_admission(profiles)(claim, "baseline", refs, evidence, events)
    assert "changed-load" in answer.answer
    assert answer.evidence_refs == evidence


@pytest.mark.parametrize("actual_factor", [1.3, 1.4])
def test_registered_thread_catalog_allows_only_admitted_scenario_results(tmp_path, actual_factor):
    import json
    from jsonschema import Draft202012Validator
    from capability_agent.application.composition import prepare_application
    from capability_agent.application.workspace import ApplicationWorkspace
    from capstone_agent.application import EmptyCredentialBroker, domain_registry
    from grid_agent.application.profile import build_pandapower_application_profile
    from grid_agent.thread_binding import bind_thread_tool_catalog

    application = build_pandapower_application_profile()
    workspace = ApplicationWorkspace.create(tmp_path, binding_ids=("grid",))
    prepared = prepare_application(application, registry=domain_registry(application),
        workspace=workspace.root, credentials=EmptyCredentialBroker())
    binding = prepared.bindings["grid"]
    executor = binding.endpoint.executor
    try:
        context = executor.invoke("context.open", {"model_id": "ieee39"})
        bound = AuthorityModelBinding("grid", "ieee39", context["revision_ref"],
            "pandapower", context["context_ref"])
        profiles = (SimpleNamespace(prepared_application=prepared, model_binding=bound),)
        bind_thread_tool_catalog(binding.runtime.tool_catalog_path, bound)
        tools = {tool["capability"]: tool for tool in
            json.loads(binding.runtime.tool_catalog_path.read_text())["tools"]}
        assert not Draft202012Validator(tools["context.open"]["input_schema"]).is_valid(
            {"model_id": "case14"})
        claim = recognized(context, operation="powerflow", scenario="changed", changes=[{
            "target": {"kind": "bus", "namespace": "name", "identifier": "31"},
            "fields": ["p_mw", "q_mvar"], "factor": 1.3}])
        claim.task_resolutions = resolve_profiles(claim, profiles)
        assert claim.task_resolutions[0].status == "ready"
        patches = [{**patch, "factor": actual_factor}
            for patch in claim.task_resolutions[0].requirement["patches"]]
        changed = executor.invoke("model.revision.derive", {
            "context_ref": context["context_ref"], "patches": patches})
        arguments = {"context_ref": changed["context_ref"]}
        Draft202012Validator(tools["analysis.powerflow.ac.run"]["input_schema"]).validate(arguments)
        result = executor.invoke("analysis.powerflow.ac.run", arguments)
        refs, evidence = (result["result_ref"],), tuple(result["evidence_refs"])
        events = ({"binding_id": "grid", "ok": True, "capability": "analysis.powerflow.ac.run",
            "result_refs": refs, "evidence_refs": evidence},)
        admit = _build_kernel_admission(profiles)
        if actual_factor == 1.3:
            answer = admit(claim, "baseline", refs, evidence, events)
            assert answer.mode == "authority_backed"
            assert answer.evidence_refs == evidence
        else:
            with pytest.raises(ValueError):
                admit(claim, "wrong scenario", refs, evidence, events)
    finally:
        binding.endpoint.close()


def test_required_persistence_failure_remains_fatal_after_valid_result(environment):
    invoke, context, profiles, _ = environment
    claim = recognized(context, operation="powerflow")
    claim.task_resolutions = resolve_profiles(claim, profiles)
    result = invoke("analysis.powerflow.ac.run", {"context_ref": context["context_ref"]})
    refs, evidence = (result["result_ref"],), tuple(result["evidence_refs"])
    events = ({"binding_id": "grid", "ok": True, "capability": "analysis.powerflow.ac.run", "result_refs": refs, "evidence_refs": evidence},
              {"binding_id": "grid", "ok": False, "capability": "analysis.result.violations.evaluate", "error_code": "persist_failed"})
    with pytest.raises(ValueError, match="persistence"):
        _build_kernel_admission(profiles)(claim, "done", refs, evidence, events)


def test_pack_formal_answer_follows_chinese_policy(environment):
    invoke, context, profiles, _ = environment
    claim = recognized(context, operation="overview")
    claim.task_understanding = replace(claim.task_understanding, answer_policy=replace(claim.task_understanding.answer_policy, language="zh-CN"))
    claim.task_resolutions = resolve_profiles(claim, profiles)
    session = _ResolvedTaskSession(claim, profiles)
    answer = session.prompt_and_wait("request", on_semantic_event=lambda event: None, correlation_id="a", on_heartbeat=lambda: None)
    assert "无需运行计算" in answer and "交流潮流" in answer


def test_mixed_goals_keep_supported_result_and_specific_boundary(environment):
    invoke, context, profiles, _ = environment
    claim = recognized(context, operation="powerflow")
    unsupported = recognized(context, operation="contingency", scenario="contingency",
        objects=[{"kind": "gen", "namespace": "all", "identifier": "*"}]).task_understanding.goals[0]
    claim.task_understanding = replace(claim.task_understanding, goals=(*claim.task_understanding.goals, replace(unsupported, id="generator")))
    claim.task_resolutions = resolve_profiles(claim, profiles)
    result = invoke("analysis.powerflow.ac.run", {"context_ref": context["context_ref"]})
    refs, evidence = (result["result_ref"],), tuple(result["evidence_refs"])
    answer = _build_kernel_admission(profiles)(claim, "raw table", refs, evidence, ({"binding_id": "grid", "ok": True,
        "capability": "analysis.powerflow.ac.run", "result_refs": refs, "evidence_refs": evidence},))
    assert "baseline" in answer.answer and "not supported" in answer.answer
    assert answer.result_refs == refs
    assert "task_goal_coverage_verified" not in answer.diagnostic_codes
    assert "task_capability_boundary_verified" in answer.diagnostic_codes


def test_resolution_cannot_add_unpublished_capability_grants(environment):
    invoke, context, profiles, calls = environment
    claim = recognized(context, operation="contingency", scenario="contingency",
        objects=[{"kind": "line", "namespace": "pandapower_index", "identifier": "0"}])
    profiles[0].prepared_application.bindings["grid"].runtime.capability_documents = ()
    calls.clear()
    resolved = resolve_profiles(claim, profiles)
    assert resolved[0].status == "unsupported" and not resolved[0].execution_required
    assert calls == []


def test_optional_display_overflow_keeps_verified_answer(environment):
    invoke, context, profiles, _ = environment
    claim = recognized(context, operation="powerflow")
    claim.task_resolutions = resolve_profiles(claim, profiles)
    result = invoke("analysis.powerflow.ac.run", {"context_ref": context["context_ref"]})
    runtime = profiles[0].prepared_application.bindings["grid"].runtime
    def overflow(**kwargs):
        raise ValueError("optional projection exceeds display limit")
    runtime.profile = replace(runtime.profile, projector_registry=SimpleNamespace(result_projector=SimpleNamespace(project_admitted=overflow)))
    runtime.executor = SimpleNamespace(invoke=invoke)
    refs, evidence = (result["result_ref"],), tuple(result["evidence_refs"])
    answer = _build_kernel_admission(profiles)(claim, "raw table", refs, evidence, ({"binding_id": "grid", "ok": True,
        "capability": "analysis.powerflow.ac.run", "result_refs": refs, "evidence_refs": evidence},))
    assert "converged" in answer.answer
    assert answer.result_refs == refs
    assert answer.result_projections


@pytest.mark.parametrize("mismatch", [{"scenario": "changed", "change": "increase bus3 load 20%"},
    {"scope": "full"}, {"measure": "loading_percent"}, {"conclusion": "limit"}])
def test_semantic_goal_disagreement_cannot_certify_baseline(environment, mismatch):
    invoke, context, profiles, calls = environment
    claim = recognized(context, operation="powerflow")
    claim.task_understanding = replace(claim.task_understanding, goals=(replace(claim.task_understanding.goals[0], **mismatch),))
    calls.clear()
    claim.task_resolutions = resolve_profiles(claim, profiles)
    assert claim.task_resolutions[0].status == "clarification"
    assert not claim.task_resolutions[0].execution_required
    assert calls == []
    result = invoke("analysis.powerflow.ac.run", {"context_ref": context["context_ref"]})
    refs, evidence = (result["result_ref"],), tuple(result["evidence_refs"])
    answer = _build_kernel_admission(profiles)(claim, "baseline is the answer", refs, evidence, ({"binding_id": "grid", "ok": True,
        "capability": "analysis.powerflow.ac.run", "result_refs": refs, "evidence_refs": evidence},))
    assert answer.goal_conclusions[0].status == "clarification"
    assert not answer.result_refs and not answer.evidence_refs


def test_general_response_survives_mixed_answer_without_authority_certification(environment):
    _, context, profiles, _ = environment
    claim = recognized(context, operation="overview")
    general = replace(claim.task_understanding.goals[0], id="poem", purpose="Write a poem", execution="general", domain_request=None)
    claim.task_understanding = replace(claim.task_understanding, goals=(*claim.task_understanding.goals, general))
    claim.task_resolutions = resolve_profiles(claim, profiles)
    answer = _build_kernel_admission(profiles)(claim, "The wind sings softly.", (), (), ())
    assert "The wind sings softly." in answer.answer
    ordinary = next(item for item in answer.goal_conclusions if item.goal_id == "poem")
    assert ordinary.status == "general" and not ordinary.result_refs and not ordinary.evidence_refs
    assert "not Authority-verified" in answer.answer


def test_unresolved_dependency_blocks_general_execution(environment):
    _, context, profiles, _ = environment
    claim = recognized(context, operation="contingency", scenario="contingency", objects=[{"kind": "gen", "namespace": "all", "identifier": "*"}])
    general = replace(claim.task_understanding.goals[0], id="dependent", execution="general", domain_request=None, dependencies=("g",))
    claim.task_understanding = replace(claim.task_understanding, goals=(*claim.task_understanding.goals, general))
    resolved = resolve_profiles(claim, profiles)
    assert resolved[1].status == "clarification" and not resolved[1].execution_required


def test_unsupported_answer_language_has_explicit_nonexecuting_boundary(environment):
    _, context, profiles, calls = environment
    claim = recognized(context, operation="powerflow")
    claim.task_understanding = replace(claim.task_understanding, answer_policy=replace(claim.task_understanding.answer_policy, language="fr"))
    calls.clear()
    resolved = resolve_profiles(claim, profiles)
    assert resolved[0].status == "clarification" and not resolved[0].execution_required
    assert "fr" in resolved[0].reason and "language" in resolved[0].reason
    assert calls == []


def test_conclusion_rejects_changed_frozen_goal_obligations(environment):
    _, context, profiles, _ = environment
    claim = recognized(context, operation="overview")
    claim.task_resolutions = resolve_profiles(claim, profiles)
    claim.task_understanding = replace(claim.task_understanding, goals=(replace(claim.task_understanding.goals[0], obligations=("new obligation",)),))
    with pytest.raises(ValueError, match="semantic goal binding"):
        _build_kernel_admission(profiles)(claim, "answer", (), (), ())


def test_unspecified_scope_cannot_certify_exhaustive_ranking(environment):
    _, context, profiles, calls = environment
    claim = recognized(context, operation="ranking", objects=[{"kind": "line", "namespace": "all", "identifier": "*"}])
    from capstone_agent.task_understanding import DomainTaskProposal
    import json
    goal = claim.task_understanding.goals[0]
    payload = {**goal.domain_request.payload, "measure": "loading_percent", "scope": "full"}
    goal = replace(goal, scope="unspecified", conclusion="ranking", measure="loading_percent",
                   domain_request=DomainTaskProposal("grid", goal.domain_request.schema, json.dumps(payload)))
    claim.task_understanding = replace(claim.task_understanding, goals=(goal,))
    calls.clear()
    resolved = resolve_profiles(claim, profiles)
    assert resolved[0].status == "clarification" and not resolved[0].execution_required
    assert calls == []


def test_informational_overview_needs_no_object_scope(environment):
    _, context, profiles, calls = environment
    claim = recognized(context, operation="overview")
    claim.task_understanding = replace(claim.task_understanding, goals=(replace(claim.task_understanding.goals[0], scope="unspecified", scenario="none"),))
    calls.clear()
    claim.task_resolutions = resolve_profiles(claim, profiles)
    assert claim.task_resolutions[0].status == "ready" and not claim.task_resolutions[0].execution_required
    answer = _ResolvedTaskSession(claim, profiles).admit_attempt(claim, "unused", (), (), ())
    assert answer.goal_conclusions[0].status == "supported" and not answer.result_refs and not answer.evidence_refs
    assert calls == ["context.get"]
    assert "39" in answer.answer and "35" in answer.answer and "11" in answer.answer
    from capstone_agent.task_resolution import resolution_payload, resolution_state_from_events
    frozen = resolution_payload(claim.task_request, claim.task_resolutions)
    restored = resolution_state_from_events([SimpleNamespace(event_type="task_requirements_resolved", payload=frozen)], request=claim.task_request)
    claim.task_resolutions = restored["task_resolutions"]
    replay = _ResolvedTaskSession(claim, profiles).admit_attempt(claim, "unused", (), (), ())
    assert replay.answer == answer.answer and calls == ["context.get"]


def test_external_grid_outage_preserves_subject_and_registered_boundary(environment):
    _, context, profiles, calls = environment
    claim = recognized(context, operation="contingency", scenario="contingency",
        objects=[{"kind": "ext_grid", "namespace": "all", "identifier": "*"}])
    calls.clear()
    resolved = resolve_profiles(claim, profiles)
    assert resolved[0].status == "unsupported" and not resolved[0].execution_required
    assert resolved[0].requirement["objects"][0]["kind"] == "ext_grid"
    assert "registered" in resolved[0].reason and calls == []


@pytest.mark.parametrize("path", ["professional", "unsupported", "clarification", "mixed"])
def test_formal_paths_exclude_prior_rpc_process_message(environment, tmp_path, path):
    import json
    import sys
    from capability_agent.runtime.environment import PiLaunch
    from capability_agent.runtime.rpc import PiRpcClient
    from capability_agent.runtime.trace import JsonlTraceWriter
    invoke, context, profiles, _ = environment
    claim = recognized(context, operation="powerflow" if path == "professional" else "overview")
    if path == "unsupported":
        claim = recognized(context, operation="contingency", scenario="contingency", objects=[{"kind": "ext_grid", "namespace": "all", "identifier": "*"}])
    if path == "clarification":
        claim.task_understanding = replace(claim.task_understanding, goals=(replace(claim.task_understanding.goals[0], scope="full"),))
    if path == "mixed":
        general = replace(claim.task_understanding.goals[0], id="poem", execution="general", domain_request=None)
        claim.task_understanding = replace(claim.task_understanding, goals=(*claim.task_understanding.goals, general))
    claim.task_understanding = replace(claim.task_understanding, answer_policy=replace(claim.task_understanding.answer_policy, language="zh"))
    claim.task_resolutions = resolve_profiles(claim, profiles)
    events = [{"type": "prompt_ack", "ok": True}, {"type": "text_delta", "text": "I'll check runtime capabilities."},
        {"type": "tool_execution_start", "toolCallId": "c", "toolName": "lookup"},
        {"type": "tool_execution_end", "toolCallId": "c", "toolName": "lookup", "result": {}},
        {"type": "text_delta", "text": "春风轻拂，灯火相连。"}, {"type": "agent_end", "messages": []}]
    script = tmp_path / "rpc.py"
    script.write_text("import json\ninput()\n" + "\n".join(f"print(json.dumps({event!r}), flush=True)" for event in events))
    trace = JsonlTraceWriter(tmp_path / "rpc.jsonl")
    client = PiRpcClient(PiLaunch(argv=(sys.executable, str(script)), environment={}), SimpleNamespace(root_path=tmp_path), trace)
    stream = []
    client.start()
    try:
        answer = client.prompt_and_wait("question", on_semantic_event=lambda event, _: stream.append(event))
    finally:
        client.stop()
        trace.close()
    refs, evidence, provenance = (), (), ()
    if path == "professional":
        result = invoke("analysis.powerflow.ac.run", {"context_ref": context["context_ref"]})
        refs, evidence = (result["result_ref"],), tuple(result["evidence_refs"])
        provenance = ({"binding_id": "grid", "ok": True, "capability": "analysis.powerflow.ac.run", "result_refs": refs, "evidence_refs": evidence},)
    admitted = _build_kernel_admission(profiles)(claim, answer, refs, evidence, provenance)
    assert "I'll check" not in admitted.answer
    assert admitted.answer and any("\u4e00" <= char <= "\u9fff" for char in admitted.answer)
    if path == "mixed":
        assert "春风轻拂，灯火相连。" in admitted.answer
    assert any(event["type"] == "assistant_process_delta" and "I'll check" in event["text"] for event in stream)
    assert [event["text"] for event in stream if event["type"] == "assistant_message"] == ["春风轻拂，灯火相连。"]


@pytest.mark.parametrize("change", ["object", "measure", "impact"])
def test_overview_cannot_replace_object_measure_or_impact_obligation(environment, change):
    import json
    from capstone_agent.task_understanding import DomainTaskProposal
    _, context, profiles, calls = environment
    claim = recognized(context, operation="overview")
    goal = claim.task_understanding.goals[0]
    payload = goal.domain_request.payload
    if change == "object":
        payload["objects"] = [{"kind": "line", "namespace": "pandapower_index", "identifier": "999999"}]
    if change == "measure":
        payload["measure"] = "loading_percent"
        goal = replace(goal, measure="loading_percent")
    if change == "impact":
        goal = replace(goal, conclusion="impact")
    goal = replace(goal, domain_request=DomainTaskProposal("grid", goal.domain_request.schema, json.dumps(payload)))
    claim.task_understanding = replace(claim.task_understanding, goals=(goal,))
    calls.clear()
    claim.task_resolutions = resolve_profiles(claim, profiles)
    assert claim.task_resolutions[0].status == "clarification" and not claim.task_resolutions[0].execution_required
    answer = _ResolvedTaskSession(claim, profiles).admit_attempt(claim, "canned capabilities", (), (), ())
    assert answer.goal_conclusions[0].status == "clarification" and calls == []


def test_powerflow_reports_exact_requested_branch_measure_not_substitute_losses(environment):
    import json
    from capstone_agent.task_understanding import DomainTaskProposal
    invoke, context, profiles, _ = environment
    claim = recognized(context, operation="powerflow", objects=[{"kind": "line", "namespace": "pandapower_index", "identifier": "0"}])
    goal = claim.task_understanding.goals[0]
    goal = replace(goal, conclusion="description", measure="loading_percent", obligations=("Report loading_percent of line 0",),
        domain_request=DomainTaskProposal("grid", goal.domain_request.schema, json.dumps({**goal.domain_request.payload, "measure": "loading_percent"})))
    claim.task_understanding = replace(claim.task_understanding, goals=(goal,))
    claim.task_resolutions = resolve_profiles(claim, profiles)
    result = invoke("analysis.powerflow.ac.run", {"context_ref": context["context_ref"]})
    refs, evidence = (result["result_ref"],), tuple(result["evidence_refs"])
    answer = _build_kernel_admission(profiles)(claim, "raw", refs, evidence, ({"binding_id": "grid", "ok": True,
        "capability": "analysis.powerflow.ac.run", "result_refs": refs, "evidence_refs": evidence},))
    document = profiles[0].prepared_application.bindings["grid"].runtime.authority.verify_result(refs[0]).document
    value = next(row["loading_percent"] for row in document["branch_results"] if row["element_kind"] == "line" and row["pandapower_index"] == 0)
    assert answer.goal_conclusions[0].status == "supported"
    assert "loading_percent" in answer.answer and f"line 0: {value:.6g}" in answer.answer
    assert "loss" not in answer.answer


def test_mixed_compatibility_keeps_each_typed_goal_conclusion(environment):
    from capstone_agent.task_understanding import DomainTaskProposal
    from capstone_agent.task_resolution import requirement_schemas
    invoke, context, profiles, _ = environment
    assert any(item["schema"] == "capstone-professional-task/1" and item["binding_id"] == "grid" for item in requirement_schemas(profiles))
    claim = recognized(context, operation="powerflow")
    goal = claim.task_understanding.goals[0]
    compatibility = replace(goal, id="topology", purpose="Query line endpoints",
        domain_request=DomainTaskProposal("grid", "capstone-professional-task/1", '{"purpose":"Query line endpoints"}'))
    unsupported = recognized(context, operation="contingency", scenario="contingency", objects=[{"kind": "gen", "namespace": "all", "identifier": "*"}]).task_understanding.goals[0]
    unclear = replace(goal, id="unclear", measure="risk_score")
    claim.task_understanding = replace(claim.task_understanding, goals=(goal, compatibility, replace(unsupported, id="generator"), unclear))
    claim.task_resolutions = resolve_profiles(claim, profiles)
    flow = invoke("analysis.powerflow.ac.run", {"context_ref": context["context_ref"]})
    topology = invoke("topology.branch.endpoints.get", {"context_ref": context["context_ref"], "kind": "line", "namespace": "pandapower_index", "identifier": "0"})
    refs = (flow["result_ref"],)
    evidence = (*flow["evidence_refs"], topology["evidence_ref"])
    events = ({"binding_id": "grid", "ok": True, "capability": "analysis.powerflow.ac.run", "result_refs": refs, "evidence_refs": flow["evidence_refs"]},
        {"binding_id": "grid", "ok": True, "capability": "topology.branch.endpoints.get", "evidence_refs": [topology["evidence_ref"]]})
    answer = _build_kernel_admission(profiles)(claim, "The queried branch endpoints are available.", refs, evidence, events)
    assert {item.goal_id: item.status for item in answer.goal_conclusions} == {"g": "supported", "topology": "uncertified", "generator": "unsupported", "unclear": "clarification"}
    assert "converged" in answer.answer and "not supported" in answer.answer and "contradicts" in answer.answer
    assert "queried branch endpoints" in answer.answer and "not verified task goal coverage" in answer.answer
    assert set(answer.evidence_refs) == set(evidence)
