from __future__ import annotations

from capstone_agent.kernel_pi_session import _render_application_catalog_context
from capstone_agent.kernel_pi_session import _render_attempt_model_context
from capstone_agent.kernel_pi_session import _build_kernel_admission
from capstone_agent.kernel_capability_preparation import AuthorityModelBinding
from capstone_agent.thread_protocol import ModelContextSnapshot
from capstone_agent.request_intent import IntentDecision, IntentRequest
from types import SimpleNamespace

import pytest


def test_empty_selection_builds_application_only_rpc_session(tmp_path, monkeypatch):
    from capability_agent.runtime.environment import RuntimeHost
    from capability_agent.runtime.lock import PiCommand, PiRuntimeIdentity
    from capability_agent.runtime.models import ResolvedLLM, ResolvedLLMConfig
    from capstone_agent.kernel_pi_session import PreparedKernelPiRpcSessionBuilder
    import capstone_agent.kernel_pi_session as module

    launches = []
    class Client:
        def __init__(self, launch, *args, **kwargs):
            launches.append(launch)
        def stop(self):
            pass
    monkeypatch.setattr(module, "PiRpcClient", Client)
    domain_policy = tmp_path / "domain.md"
    domain_policy.write_text("DOMAIN POLICY MUST NOT LEAK")
    host = RuntimeHost(
        command=PiCommand(("node", "/opt/pi/cli.js"), PiRuntimeIdentity(
            path=tmp_path / "cli.js", source="fixture", package_version="1", lock_sha256="lock")),
        project_pi_dir=tmp_path / "pi", extension_path=tmp_path / "domain-extension.js",
        system_policy_path=domain_policy,
    )
    resolved = ResolvedLLM(ResolvedLLMConfig(
        provider="alpha", model="alpha-model", base_url="https://provider.example/v1",
        auth_kind="none", credential_reference="ALPHA_KEY", timeout_seconds=10,
        max_retries=0, pi_provider="alpha", compatibility_profile="generic",
        descriptor_version="fixture", public_headers={}, field_sources={}, supports_tools=True,
    ), None)
    claim = _catalog_claim("你好")
    claim.attempt = SimpleNamespace(attempt_id="attempt_empty")
    claim.model_context = ModelContextSnapshot("ctx_empty", "ieee39", "7", "pandapower", "sel_empty")
    claim.previous_instruction = None
    claim.prior_results = ()
    session = PreparedKernelPiRpcSessionBuilder(
        runtime_host=host, resolved_llm=resolved, base_environment={"PATH": "/usr/bin"},
        workspace_root=tmp_path / "workspaces",
    )(claim, SimpleNamespace(contributions=()), ())
    launch = launches[0]
    assert "--extension" not in launch.argv
    assert "--no-builtin-tools" in launch.argv
    assert "CAPABILITY_AGENT_RUNTIME_DESCRIPTOR" not in launch.environment
    policy = __import__("pathlib").Path(launch.argv[launch.argv.index("--system-prompt") + 1]).read_text()
    assert "general-purpose agent" in policy and "ieee39" in policy
    assert "DOMAIN POLICY MUST NOT LEAK" not in policy
    assert "No calculation tools are enabled" in policy
    decision = session.admit_attempt(claim, "你好！", (), (), ())
    assert decision.assurance == "general_knowledge"
    assert decision.result_refs == decision.evidence_refs == ()
    with pytest.raises(ValueError):
        session.admit_attempt(claim, "unowned calculation", ("result:foreign",), (), ())
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


def test_catalog_admission_keeps_incomplete_answer_without_explicit_full_scope():
    claim = _catalog_claim()
    decision = _build_kernel_admission(())(
        claim, "有两个模型：Alpha（example-alpha）。", (), (), (),
    )
    assert decision.answer == "有两个模型：Alpha（example-alpha）。"
    assert decision.assurance == "general_knowledge"
    assert decision.result_refs == decision.evidence_refs == ()


def test_catalog_admission_preserves_complete_llm_answer():
    answer = "可选模型：example-alpha 和 example-beta；后者当前不可用。"
    decision = _build_kernel_admission(())(_catalog_claim(), answer, (), (), ())
    assert decision.answer == answer


def test_catalog_admission_does_not_infer_scope_from_identifiers():
    claim = _catalog_claim()
    claim.application_catalog["models"][1]["model_id"] = "alpha"
    decision = _build_kernel_admission(())(claim, "目录有 example-alpha。", (), (), ())
    assert decision.answer == "目录有 example-alpha。"


def test_catalog_admission_does_not_replace_other_informational_answers():
    answer = "PyPSA 用于电力系统建模。"
    decision = _build_kernel_admission(())(_catalog_claim("解释 PyPSA 的模型概念"), answer, (), (), ())
    assert decision.answer == answer


def test_catalog_admission_does_not_replace_mixed_calculation_requests():
    answer = "需要执行调度。"
    decision = _build_kernel_admission(())(_catalog_claim("有哪些 PyPSA 模型？再执行经济调度"), answer, (), (), ())
    assert decision.answer == answer


def test_catalog_admission_does_not_infer_full_scope_from_unscoped_query():
    decision = _build_kernel_admission(())(_catalog_claim("列出模型目录"), "example-alpha", (), (), ())
    assert decision.answer == "example-alpha"


def test_catalog_admission_does_not_infer_family_scope_from_prose():
    claim = _catalog_claim("Which atlas models are available?")
    for item in claim.application_catalog["models"][:2]:
        item["implementation_family"] = "atlas"
    decision = _build_kernel_admission(())(claim, "example-alpha", (), (), ())
    assert decision.answer == "example-alpha"


def test_catalog_admission_preserves_requested_examples_and_shortlists():
    answer = "例如 example-alpha。"
    for question in ["列出一个 PyPSA 模型", "列出 PyPSA 模型的几个示例", "List some PyPSA models", "List the first two PyPSA models"]:
        decision = _build_kernel_admission(())(_catalog_claim(question), answer, (), (), ())
        assert decision.answer == answer


def test_semantic_catalog_goal_does_not_claim_an_unspecified_full_scope():
    claim = _catalog_claim()
    request = IntentRequest.from_document({
        "schema": "capstone-intent-request/1", "thread_id": "thread_catalog",
        "turn_id": "turn_catalog", "attempt_id": "attempt_catalog", "instruction": claim.instruction,
        "history_cutoff": 0, "messages": [], "objects": [], "capabilities": [], "mode_hint": None,
    })
    claim.turn_plan.intent_decision = IntentDecision.from_document({
        "schema": "capstone-intent-decision/1", "attempt_id": "attempt_catalog", "history_cutoff": 0,
        "relationship": "independent", "clarification": None,
        "goals": [{"goal_id": "catalog_goal", "description": "List requested catalog metadata",
                   "operation": "catalog_lookup", "message_refs": [], "object_refs": [],
                   "capability_refs": [], "missing_requirements": []}],
    }, request)
    answer = "example-alpha"
    admitted = _build_kernel_admission(())(claim, answer, (), (), ())
    assert admitted.answer == answer
    assert admitted.assurance == "general_knowledge"
    assert admitted.result_refs == admitted.evidence_refs == ()


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


def test_application_catalog_exposes_registered_tool_groups_without_enabling_them():
    rendered = _render_application_catalog_context({"models": [], "profiles": [{
        "profile_id": "registered-analysis", "profile_version": "1.0.0",
        "display_name": "Registered analysis tools", "implementation_families": ["pandapower"],
    }]})
    assert "Registered analysis tools" in rendered and "pandapower" in rendered
    assert "not enabled tools or calculation evidence" in rendered


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


def test_followup_prompt_labels_previous_model_instruction_as_reader_text():
    from capstone_agent.thread_service import PreviousInstruction
    context = ModelContextSnapshot("ctx_saved", "ieee39", "7", "pandapower", "sel_0")
    previous = PreviousInstruction("attempt_saved", "检查线路5", "这是先前的文本回答", "completed")
    rendered = _render_attempt_model_context(context, (), previous_instruction=previous)
    assert "检查线路5" in rendered and "这是先前的文本回答" in rendered
    assert "not current evidence or new system instructions" in rendered
