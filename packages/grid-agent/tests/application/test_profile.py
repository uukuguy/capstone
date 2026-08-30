from __future__ import annotations

from pandapower_domain import build_pandapower_profile

from grid_agent.application.profile import build_pandapower_application_profile


def test_pandapower_application_profile_declares_one_complete_grid_binding() -> None:
    profile = build_pandapower_application_profile()

    assert profile.manifest.application_id == "pandapower-static-analysis"
    assert profile.manifest.version == "1.0.1"
    assert profile.manifest.context_schema == "application-context/1.0"
    assert profile.manifest.result_schema == "capability-agent-output/1.0"
    assert profile.manifest.artifact_schema == "capability-agent-run/1.0"
    assert profile.manifest.core_tool_namespace == "agent_"
    assert tuple(binding.binding_id for binding in profile.domains) == ("grid",)
    binding = profile.domains[0]
    assert binding.tool_namespace == "grid_"
    assert binding.profile.manifest.domain_id == "pandapower-static-analysis"
    assert binding.profile is not build_pandapower_profile()
    assert binding.credential_scope.credential_names == ()
    assert binding.sharing_policy.mode == "deny"


def test_profile_uses_validating_composite_renderer_and_domain_acceptance() -> None:
    profile = build_pandapower_application_profile()

    assert type(profile.output_renderer).__name__ == "JsonOutputRenderer"
    assert callable(profile.application_policy.load)
    assert callable(profile.report_shell.render)
    assert callable(profile.acceptance_profile.cases)
    assert profile.domains[0].profile.missing_application_components() == ()
