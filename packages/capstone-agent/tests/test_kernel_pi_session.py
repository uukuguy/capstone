from __future__ import annotations

from capstone_agent.kernel_pi_session import _render_application_catalog_context
from capstone_agent.kernel_pi_session import _render_attempt_model_context
from capstone_agent.kernel_pi_session import _build_kernel_admission
from capstone_agent.kernel_capability_preparation import AuthorityModelBinding
from capstone_agent.thread_protocol import ModelContextSnapshot
from types import SimpleNamespace
import pytest


def test_model_input_metrics_are_scoped_without_changing_the_model_or_prompt(tmp_path):
    from capability_agent.runtime.environment import PiLaunch
    from capstone_agent.kernel_pi_session import _with_model_input_metrics
    extension = tmp_path / 'domain-tools.mjs'
    extension.with_name('model-input-metrics.mjs').write_text('export default () => {}')
    launch = PiLaunch(('pi', '--model', 'selected', '--system-prompt', 'original'), {'SAFE': 'value'})
    measured = _with_model_input_metrics(launch, tmp_path / 'attempt', extension)
    assert measured.argv[:len(launch.argv)] == launch.argv
    assert measured.environment['SAFE'] == 'value'
    assert 'CAPSTONE_MODEL_INPUT_METRICS' not in launch.environment
    assert measured.environment['CAPSTONE_MODEL_INPUT_METRICS'] == str((tmp_path / 'attempt/model-input-metrics').resolve())


def test_selected_task_tool_launch_binds_private_input_and_preserves_original_launch(tmp_path):
    from capability_agent.runtime.environment import PiLaunch
    from capstone_agent.kernel_pi_session import _with_selected_task_tool
    extension = tmp_path / "extension" / "domain-tools.mjs"
    extension.parent.mkdir()
    tool_extension = extension.with_name("task-record-tools.mjs")
    tool_extension.write_text("export default () => {}")
    calls = []
    class Reader:
        def publish(self, directory):
            calls.append(directory)
            directory.mkdir()
            return directory
    launch = PiLaunch(("pi", "--mode", "rpc"), {"SAFE": "value"})
    directory = tmp_path / "attempt"
    directory.mkdir()
    bound = _with_selected_task_tool(launch, Reader(), directory, extension)
    assert bound.argv[-2:] == ("--extension", str(tool_extension))
    assert bound.environment["CAPSTONE_SELECTED_TASK_RECORDS"] == str(calls[0])
    assert "CAPSTONE_SELECTED_TASK_RECORDS" not in launch.environment


def test_research_work_protocol_is_candidate_only(tmp_path):
    from capstone_agent.kernel_pi_session import _compose_attempt_policy
    for enabled in (False, True):
        policy = _compose_attempt_policy(tmp_path / str(enabled), None, include_generic=False,
                                        application_catalog=None, include_research=enabled)
        assert ("Research work protocol" in policy.read_text()) is enabled


@pytest.mark.parametrize("wrong_revision", [False, True])
def test_bound_admission_checks_derived_result_revision(wrong_revision):
    from capstone_agent.kernel_pi_session import _verify_bound_attempt_references
    checks = []
    def descendant(reference, ancestor):
        checks.append((reference, ancestor))
        assert (reference, ancestor) == ("context:child", "context:root")
        return SimpleNamespace(document={"model_id": "grid", "revision_ref": "child-revision"})
    authority = SimpleNamespace(
        verify_context_descendant=descendant,
        verify_result=lambda _: SimpleNamespace(document={
            "context_ref": "context:child", "model_id": "grid",
            "revision_ref": "wrong" if wrong_revision else "child-revision"}),
        audit_answer_references=lambda *_: (),
    )
    binding = SimpleNamespace(runtime=SimpleNamespace(authority=authority))
    profile = SimpleNamespace(
        model_binding=SimpleNamespace(model_id="grid", model_revision="root-revision", context_ref="context:root"),
        prepared_application=SimpleNamespace(bindings={"grid": binding}),
    )
    def verify():
        _verify_bound_attempt_references((profile,), {"grid": binding}, {"result:child": "grid"},
            ("result:child",), (), ({"binding_id": "grid", "ok": True,
                                    "context_ref": "context:child", "model_revision": "child-revision"},))
    if wrong_revision:
        with pytest.raises(ValueError, match="artifact does not match"):
            verify()
    else:
        verify()
    assert checks == [("context:child", "context:root")]


def test_research_conditions_accept_observed_bound_context_but_not_foreign_or_failed_reads():
    from capstone_agent import kernel_pi_session as module
    profile, _, _ = _research_admission_fixture()
    references = module._ResearchReferences((profile,))
    assert not references.admit("context:current")
    references.observe({"type": "tool_result", "tool_name": "grid_context_get", "capability": "context.get",
        "ok": False, "result": {"context_ref": "context:current"}})
    assert not references.admit("context:current")
    references.observe({"type": "tool_result", "tool_name": "grid_context_get", "capability": "context.get",
        "ok": True, "result": {"context_ref": "context:current", "revision_ref": "revision-1", "model": "selected-model"}})
    assert references.admit("context:current")
    references.observe({"type": "tool_result", "tool_name": "grid_context_get", "capability": "context.get",
        "ok": True, "result": {"context_ref": "context:foreign", "revision_ref": "revision-1", "model": "selected-model"}})
    assert not references.admit("context:foreign")
    wrong = module._ResearchReferences((profile,))
    wrong.observe({"type": "tool_result", "tool_name": "grid_context_get", "capability": "context.get",
        "ok": True, "result": {"context_ref": "context:current", "revision_ref": "revision-wrong", "model": "selected-model"}})
    assert not wrong.admit("context:current")


@pytest.mark.parametrize("ok,context,revision,expected", [
    (True, "context:current", "revision-1", True),
    (False, "context:current", "revision-1", False),
    (True, "context:foreign", "revision-1", False),
    (True, "context:current", "revision-wrong", False),
])
def test_research_input_dataset_sources_require_observed_bound_reads(ok, context, revision, expected):
    from capstone_agent import kernel_pi_session as module
    profile, _, _ = _research_admission_fixture()
    refs = module._ResearchReferences((profile,))
    source = "dataset:input.sources:sha256:" + "a" * 64
    assert not refs.admit(source)
    refs.observe({"type": "tool_result", "tool_name": "domain_dataset_query", "capability": "model.dataset.query", "ok": ok,
        "result": {"dataset_ref": source, "context_ref": context, "revision_ref": revision,
                   "rows": [{"private_data": "not a reference"}]}})
    assert refs.admit(source) is expected


def test_research_result_dataset_source_requires_its_verified_parent(monkeypatch):
    from capstone_agent import kernel_pi_session as module
    profile, _, _ = _research_admission_fixture()
    def verify(profiles, bindings, owners, results, evidence, events):
        if results and not evidence:
            raise ValueError("result has no verified evidence")
    monkeypatch.setattr(module, "_verify_bound_attempt_references", verify)
    refs = module._ResearchReferences((profile,))
    dataset = "dataset:result.values:sha256:" + "b" * 64
    refs.observe({"type": "tool_result", "tool_name": "domain_result_query", "capability": "result.dataset.query", "ok": True,
        "result": {"dataset_ref": dataset, "result_ref": "result:parent", "context_ref": "context:current", "revision_ref": "revision-1"}})
    assert not refs.admit(dataset)
    refs.observe({"type": "tool_result", "tool_name": "domain_calculate", "ok": True,
        "result_refs": ["result:parent"], "evidence_refs": ["evidence:parent"]})
    assert refs.admit(dataset)


def test_research_references_require_observed_success_and_bound_authority(monkeypatch):
    from capstone_agent import kernel_pi_session as module
    profile, _, _ = _research_admission_fixture()
    checks = []
    monkeypatch.setattr(module, "_verify_bound_attempt_references",
        lambda *args: checks.append(args))
    references = module._ResearchReferences((profile,))
    assert not references.admit("result:unknown")
    references.observe({"type": "tool_result", "tool_name": "grid_run",
        "capability": "analysis.run", "ok": False, "result_refs": ["result:failed"]})
    assert not references.admit("result:failed")
    references.observe({"type": "tool_result", "tool_name": "grid_run",
        "capability": "analysis.run", "ok": True,
        "result_refs": ["result:good"], "evidence_refs": ["evidence:good"]})
    assert references.admit("result:good")
    assert checks[-1][3:5] == (("result:good",), ("evidence:good",))
    def reject(*args):
        raise ValueError("wrong model revision")
    monkeypatch.setattr(module, "_verify_bound_attempt_references", reject)
    assert not references.admit("result:good")


def test_research_conditions_accept_a_verified_descendant_context():
    from capstone_agent import kernel_pi_session as module
    profile, _, _ = _research_admission_fixture()
    checked = []
    def verify(reference, ancestor):
        checked.append((reference, ancestor))
        if reference != "context:derived":
            raise ValueError("not a descendant")
        return SimpleNamespace(document={"model_id": "selected-model", "revision_ref": "revision-derived"})
    profile.prepared_application.bindings["grid"].runtime.authority = SimpleNamespace(verify_context_descendant=verify)
    refs = module._ResearchReferences((profile,))
    refs.observe({"type": "tool_result", "tool_name": "grid_derive", "capability": "model.revision.derive",
        "ok": True, "result": {"context_ref": "context:derived", "revision_ref": "revision-derived", "model": "selected-model"}})
    assert refs.admit("context:derived")
    assert checked == [("context:derived", "context:current")]


def test_research_result_read_does_not_erase_its_observed_evidence(monkeypatch):
    from capstone_agent import kernel_pi_session as module
    profile, _, _ = _research_admission_fixture()
    def verify(profiles, bindings, owners, results, evidence, events):
        if not evidence:
            raise ValueError("result has no observed evidence")
    monkeypatch.setattr(module, "_verify_bound_attempt_references", verify)
    references = module._ResearchReferences((profile,))
    references.observe({"type": "tool_result", "tool_name": "grid_run", "ok": True,
        "result_refs": ["result:good"], "evidence_refs": ["evidence:good"]})
    references.observe({"type": "tool_result", "tool_name": "grid_result_query", "ok": True,
        "result_refs": ["result:good"], "evidence_refs": []})
    assert references.admit("result:good")


@pytest.mark.parametrize("linked_result", ["result:good", "result:other"])
def test_research_result_and_evidence_reads_can_form_a_verified_pair(monkeypatch, linked_result):
    from capstone_agent import kernel_pi_session as module
    profile, _, _ = _research_admission_fixture()
    profile.prepared_application.bindings["grid"].runtime.authority = SimpleNamespace(
        verify_evidence=lambda _: SimpleNamespace(document={"result_ref": linked_result}))
    def verify(profiles, bindings, owners, results, evidence, events):
        if results == ("result:good",) and evidence == ("evidence:good",):
            return
        raise ValueError("no linked result and evidence")
    monkeypatch.setattr(module, "_verify_bound_attempt_references", verify)
    references = module._ResearchReferences((profile,))
    references.observe({"type": "tool_result", "tool_name": "grid_result_query", "ok": True,
        "result_refs": ["result:good"], "evidence_refs": []})
    assert not references.admit("result:good")
    references.observe({"type": "tool_result", "tool_name": "grid_evidence_get", "ok": True,
        "result_refs": [], "evidence_refs": ["evidence:good"]})
    assert references.admit("result:good") is (linked_result == "result:good")


def test_research_can_reference_a_result_linked_by_observed_authority_evidence(monkeypatch):
    from capstone_agent import kernel_pi_session as module
    profile, _, _ = _research_admission_fixture()
    profile.prepared_application.bindings["grid"].runtime.authority = SimpleNamespace(
        verify_evidence=lambda _: SimpleNamespace(document={"result_ref": "result:child"}))
    def verify(profiles, bindings, owners, results, evidence, events):
        if results != ("result:child",) or evidence != ("evidence:child",):
            raise ValueError("unverified source")
    monkeypatch.setattr(module, "_verify_bound_attempt_references", verify)
    references = module._ResearchReferences((profile,))
    assert not references.admit("result:child")
    references.observe({"type": "tool_result", "tool_name": "grid_contingency", "ok": True,
        "result_refs": ["result:aggregate"], "evidence_refs": ["evidence:child"]})
    assert references.admit("result:child")
    assert not references.admit("result:unobserved")


def _research_admission_fixture():
    from capability_agent.domain.answer_admission import AnswerAdmissionDecision
    requests = []

    def admit(request):
        requests.append(request)
        return AnswerAdmissionDecision("limited", "limited", request.answer_output, ())

    domain = SimpleNamespace(
        create_answer_admission_policy=lambda _: SimpleNamespace(admit=admit),
        answer_admission_capabilities=frozenset({"limited"}),
    )
    binding = SimpleNamespace(runtime=SimpleNamespace(profile=domain, authority=object()))
    profile = SimpleNamespace(
        prepared_application=SimpleNamespace(bindings={"grid": binding}),
        model_binding=SimpleNamespace(model_id="selected-model", model_revision="revision-1", context_ref="context:current"),
    )
    claim = SimpleNamespace(instruction="Study the selected model", turn_plan=None)
    return profile, claim, requests


@pytest.mark.parametrize("name", ["agent_research_update", "agent_task_progress"])
def test_registered_research_tools_do_not_count_as_authority_calculations(name):
    from capability_agent.tools.catalog import CoreToolCatalog
    profile, claim, requests = _research_admission_fixture()
    admit = _build_kernel_admission((profile,), core_catalog=CoreToolCatalog.default(include_research=True))
    events = ({"tool_name": name, "capability": name, "ok": True},)
    answer = admit(claim, "The research remains open.", (), (), events)
    assert answer.result_refs == answer.evidence_refs == ()
    assert requests[0].authority_attempted is False
    assert requests[0].observed_capabilities == ()


@pytest.mark.parametrize("ordinary", [False, True])
def test_selected_record_tool_is_application_observation_not_authority(ordinary):
    profile, claim, requests = _research_admission_fixture()
    claim.selected_task_reader = object()
    claim.turn_plan = SimpleNamespace(route="ordinary") if ordinary else None
    events = ({"tool_name": "agent_task_records_read", "capability": "agent_task_records_read", "ok": True},)
    admitted = _build_kernel_admission(() if ordinary else (profile,))(
        claim, "The original task has recorded failures.", (), (), events)
    assert admitted.result_refs == admitted.evidence_refs == ()
    assert admitted.mode == "limited"
    if not ordinary:
        assert requests[0].authority_attempted is False


@pytest.mark.parametrize("extra", [{"binding_id": "grid"}, {"result_refs": ["result:old"]},
                                   {"evidence_refs": ["evidence:old"]}])
def test_historical_record_tool_cannot_admit_old_references(extra):
    profile, claim, _ = _research_admission_fixture()
    claim.selected_task_reader = object()
    event = {"tool_name": "agent_task_records_read", "capability": "agent_task_records_read", "ok": True, **extra}
    with pytest.raises(ValueError):
        _build_kernel_admission((profile,))(claim, "Explanation", (), (), (event,))


@pytest.mark.parametrize("extra", [
    {"result_refs": ["result:untrusted"]},
    {"evidence_refs": ["evidence:untrusted"]},
    {"binding_id": "grid"},
    {"capability": "analysis.run"},
])
@pytest.mark.parametrize("name", ["agent_research_update", "agent_task_progress"])
def test_research_tools_cannot_claim_domain_ownership_or_physical_references(extra, name):
    from capability_agent.tools.catalog import CoreToolCatalog
    profile, claim, _ = _research_admission_fixture()
    admit = _build_kernel_admission((profile,), core_catalog=CoreToolCatalog.default(include_research=True))
    event = {"tool_name": name, "capability": name, "ok": True, **extra}
    with pytest.raises(ValueError, match="core tool provenance"):
        admit(claim, "Study remains open.", (), (), (event,))


def test_unselected_research_tool_is_not_silently_assigned_to_the_domain():
    profile, claim, _ = _research_admission_fixture()
    with pytest.raises(ValueError, match="core tool provenance"):
        _build_kernel_admission((profile,))(
            claim, "Study remains open.", (), (),
            ({"tool_name": "agent_research_update", "capability": "agent_research_update", "ok": True},),
        )


def test_core_observations_do_not_hide_domain_execution_from_admission():
    profile, claim, requests = _research_admission_fixture()
    events = (
        {"tool_name": "agent_context_get", "capability": "agent_context_get", "ok": True},
        {"tool_name": "grid_model_describe", "capability": "model.describe", "ok": True},
    )
    _build_kernel_admission((profile,))(claim, "Model inspection complete.", (), (), events)
    assert requests[0].authority_attempted is True
    assert requests[0].observed_capabilities == ("model.describe",)


def test_core_record_cannot_admit_a_top_level_result_reference():
    from capability_agent.tools.catalog import CoreToolCatalog
    profile, claim, _ = _research_admission_fixture()
    event = {"tool_name": "agent_research_update", "capability": "agent_research_update", "ok": True}
    with pytest.raises(ValueError, match="no tool provenance owner"):
        _build_kernel_admission((profile,), core_catalog=CoreToolCatalog.default(include_research=True))(
            claim, "Study remains open.", ("result:untrusted",), (), (event,),
        )


@pytest.mark.parametrize("selected_task", [False, True])
def test_ordinary_session_has_no_business_tools_or_authority_handles(monkeypatch, tmp_path, selected_task):
    import capstone_agent.kernel_pi_session as module
    captured = []
    stream_settings = []
    class Client:
        def __init__(self, launch, workspace, trace, **kwargs):
            self.workspace = workspace
            stream_settings.append(kwargs)
        def stop(self):
            pass
    def launch(llm, paths, **kwargs):
        captured.append(paths)
        return SimpleNamespace(argv=("pi",), environment={})
    monkeypatch.setattr(module, "build_pi_launch", launch)
    monkeypatch.setattr(module, "PiRpcClient", Client)
    builder = object.__new__(module.PreparedKernelPiRpcSessionBuilder)
    builder._runtime_host = SimpleNamespace(command=object(), project_pi_dir=tmp_path / "auth",
                                           extension_path=tmp_path / "domain-tools.mjs")
    builder._resolved_llm = SimpleNamespace(secret=None)
    builder._base_environment = {}
    builder._timeout_seconds = 60
    claim = SimpleNamespace(turn_plan=SimpleNamespace(route="ordinary"), application_catalog=None,
        selected_task_reader=None,
        attempt=SimpleNamespace(attempt_id="attempt_general"),
        model_context=ModelContextSnapshot("ctx_current", "current-model", "revision-1", "pandapower", "sel_0"),
        previous_instruction=module.PreviousInstruction("attempt_saved", "Explain saved task", "Saved outcome", "completed",
            ModelContextSnapshot("ctx_old", "old-model", "revision-old", "pandapower", "sel_0")) if selected_task else None)
    business = tmp_path / "business-workspace"
    profile = SimpleNamespace(workspace=SimpleNamespace(root=business, core_path=business / "core"))
    session = builder(claim, object(), (profile,))
    paths = captured[0]
    assert stream_settings[0]['process_delta_batch_seconds'] == .1
    assert paths.workspace != business
    assert paths.extension_path is paths.runtime_descriptor_path is paths.tool_catalog_path is None
    assert paths.domain_search_paths == ()
    assert not (business / "core/pi/runtime-descriptor.json").exists()
    policy = paths.system_policy_path.read_text()
    assert ("Selected historical task" in policy) is selected_task
    if selected_task:
        assert '"instruction": "Explain saved task"' in policy
        assert '"model_id": "old-model"' in policy
    session.stop()


def _catalog_claim(instruction="列出 PyPSA 的电网模型"):
    return SimpleNamespace(
        instruction=instruction,
        turn_plan=SimpleNamespace(route="ordinary"),
        application_catalog={"models": [
            {"model_id": "example-alpha", "display_name": "Alpha", "implementation_family": "pypsa", "available": True},
            {"model_id": "example-beta", "display_name": "Beta", "implementation_family": "pypsa", "available": False},
            {"model_id": "unrelated-model", "display_name": "Other", "implementation_family": "pandapower", "available": True},
        ]},
    )


def test_catalog_admission_replaces_incomplete_answer_from_attempt_snapshot():
    claim = _catalog_claim()
    decision = _build_kernel_admission(())(
        claim, "有两个模型：Alpha（example-alpha）。", (), (), (),
    )
    assert "example-alpha" in decision.answer and "example-beta" in decision.answer
    assert "unrelated-model" not in decision.answer
    assert "2" in decision.answer and "暂不可用" in decision.answer
    assert decision.assurance == "deterministic_information"
    assert decision.result_refs == decision.evidence_refs == ()


def test_catalog_admission_preserves_complete_llm_answer():
    answer = "可选模型：example-alpha 和 example-beta；后者当前不可用。"
    decision = _build_kernel_admission(())(_catalog_claim(), answer, (), (), ())
    assert decision.answer == answer


def test_catalog_admission_checks_identifiers_instead_of_substrings():
    claim = _catalog_claim()
    claim.application_catalog["models"][1]["model_id"] = "alpha"
    decision = _build_kernel_admission(())(claim, "目录有 example-alpha。", (), (), ())
    assert "`alpha`" in decision.answer


def test_catalog_admission_does_not_replace_other_informational_answers():
    answer = "PyPSA 用于电力系统建模。"
    decision = _build_kernel_admission(())(_catalog_claim("解释 PyPSA 的模型概念"), answer, (), (), ())
    assert decision.answer == answer


def test_catalog_admission_does_not_replace_mixed_calculation_requests():
    answer = "需要执行调度。"
    decision = _build_kernel_admission(())(_catalog_claim("有哪些 PyPSA 模型？再执行经济调度"), answer, (), (), ())
    assert decision.answer == answer


def test_catalog_admission_lists_all_families_for_unscoped_query():
    decision = _build_kernel_admission(())(_catalog_claim("列出模型目录"), "example-alpha", (), (), ())
    assert "example-beta" in decision.answer and "unrelated-model" in decision.answer


def test_catalog_admission_handles_other_registered_families():
    claim = _catalog_claim("Which atlas models are available?")
    for item in claim.application_catalog["models"][:2]:
        item["implementation_family"] = "atlas"
    decision = _build_kernel_admission(())(claim, "example-alpha", (), (), ())
    assert "example-beta" in decision.answer and "unrelated-model" not in decision.answer


def test_catalog_admission_preserves_requested_examples_and_shortlists():
    answer = "例如 example-alpha。"
    for question in ["列出一个 PyPSA 模型", "列出 PyPSA 模型的几个示例", "List some PyPSA models", "List the first two PyPSA models"]:
        decision = _build_kernel_admission(())(_catalog_claim(question), answer, (), (), ())
        assert decision.answer == answer


def test_application_catalog_context_keeps_cross_family_models_visible() -> None:
    rendered = _render_application_catalog_context({
        "schema": "capstone-thread-catalog/1",
        "default_model_id": "ieee39",
        "models": [
            {
                "model_id": "ieee39",
                "display_name": "IEEE-39",
                "implementation_family": "pandapower",
                "available": True,
            },
            {
                "model_id": "regional-six-bus",
                "display_name": "Regional six-bus",
                "implementation_family": "pypsa",
                "available": True,
            },
        ],
    })

    assert "Regional six-bus (regional-six-bus)" in rendered
    assert "family=pypsa" in rendered
    assert "Do not claim that another family has no models" in rendered
    assert "Current tool scope does not determine application-wide availability" in rendered
    assert "Only an explicit worker-unavailable catalog entry" in rendered
    assert "Do not apply the active binding's unsupported-operation or policy limits to another family" in rendered


def test_each_fresh_prompt_names_the_bound_model_and_authority_context():
    context = ModelContextSnapshot("ctx_rts", "case24_ieee_rts", "revision:sha256:" + "a" * 64, "pandapower", "sel_0")
    binding = AuthorityModelBinding("grid", context.model_id, context.model_revision, "pandapower", "context:sha256:" + "b" * 64)
    rendered = _render_attempt_model_context(context, (SimpleNamespace(model_binding=binding),))
    assert "case24_ieee_rts" in rendered
    assert binding.context_ref in rendered
    assert "Do not open or analyze a different model" in rendered


def test_followup_prompt_offers_existing_result_and_evidence_for_explicit_retrieval():
    context = ModelContextSnapshot("ctx_rts", "case24_ieee_rts", "revision:sha256:" + "a" * 64, "pandapower", "sel_0")
    prior = SimpleNamespace(result_ref="result:sha256:" + "c" * 64, evidence_refs=("evidence:sha256:" + "d" * 64,), capability_id="analysis.powerflow.ac.run", attempt_id="attempt_previous")
    rendered = _render_attempt_model_context(context, (), prior_results=(prior,))
    assert prior.result_ref in rendered and prior.evidence_refs[0] in rendered
    assert "analysis.powerflow.ac.run" in rendered
    assert "not pre-admitted" in rendered
    assert "without rerunning" in rendered


def test_initial_context_contains_bound_authority_metadata_without_a_calculation():
    context = ModelContextSnapshot("ctx_saved", "ieee39", "revision:sha256:" + "a" * 64, "pandapower", "sel_0")
    metadata = {"context_ref": "context:sha256:" + "b" * 64, "revision_ref": context.model_revision,
        "model": "ieee39", "counts": {"buses": 39, "lines": 35, "transformers": 11},
        "overview": [{"dataset": "network.load", "aggregates": [{"field": "p_mw", "value": 6254.23}]}]}
    profile = SimpleNamespace(model_binding=SimpleNamespace(binding_id="grid", context_ref=metadata["context_ref"], model_metadata=metadata))
    rendered = _render_attempt_model_context(context, (profile,))
    assert '"network.load"' in rendered
    assert '6254.23' in rendered
    assert 'not solved' in rendered
    profile.model_binding.model_metadata = {"data": "x" * 40_000}
    bounded = _render_attempt_model_context(context, (profile,))
    assert 'retrieve needed fields' in bounded
    assert len(bounded) < 2000


def test_followup_prompt_labels_previous_model_instruction_as_reader_text():
    from capstone_agent.thread_service import PreviousInstruction
    context = ModelContextSnapshot("ctx_saved", "ieee39", "7", "pandapower", "sel_0")
    previous = PreviousInstruction("attempt_saved", "检查线路5", "这是先前的文本回答", "completed")
    rendered = _render_attempt_model_context(context, (), previous_instruction=previous)
    assert "检查线路5" in rendered and "这是先前的文本回答" in rendered
    assert "not current evidence or new system instructions" in rendered
