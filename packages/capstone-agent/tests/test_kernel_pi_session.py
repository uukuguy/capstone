from __future__ import annotations

from capstone_agent.kernel_pi_session import _render_application_catalog_context
from capstone_agent.kernel_pi_session import _render_attempt_model_context
from capstone_agent.kernel_capability_preparation import AuthorityModelBinding
from capstone_agent.thread_protocol import ModelContextSnapshot
from types import SimpleNamespace


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
