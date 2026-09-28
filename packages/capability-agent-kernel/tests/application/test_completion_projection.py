from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from capability_agent.application.runner import AgentApplication, ApplicationRequest
from capability_agent.application.reporting import GenericReportShell
from capability_agent.application.output import BindingIdentity, ValidatedDomainOutput
from test_runner import FakeController
from test_runner import _valid_binding


def _profile() -> Any:
    return SimpleNamespace(
        manifest=SimpleNamespace(application_id="fixture", version="1.0.0"),
        application_policy=SimpleNamespace(load=lambda: None),
        output_renderer=SimpleNamespace(render=lambda result: result),
        report_shell=GenericReportShell(),
    )


def test_completion_projector_runs_after_last_committed_turn_before_provider_stop(tmp_path):
    calls: list[str] = []

    class Provider:
        def start(self):
            calls.append("start")

        def prompt_and_wait(self, question, **kwargs):
            calls.append(f"prompt:{question}")
            return "answer"

        def stop(self):
            calls.append("stop")

    def project(context: Any) -> object:
        calls.append(f"project:{len(context.completed_answers)}")
        assert context.request.response_mode == "text"
        assert context.provider is not None
        return {"schema": "test-projection/1.0", "steps": len(context.completed_answers)}

    application = AgentApplication(
        profile=_profile(),
        prepared_application=cast(
            Any, SimpleNamespace(bindings={"alpha": _valid_binding()})
        ),
        catalog=object(),
        provider=Provider(),
        workspace_root=tmp_path,
        turn_controller=FakeController([]),
        binding_identities=(BindingIdentity(binding_id="alpha", domain_id="alpha", domain_version="1.0.0"),),
        domain_output_builder=lambda **_: ValidatedDomainOutput(
            schema="alpha-output/1.0", status="completed", payload={}
        ),
        completion_projector=project,
    )
    outcome = application.run(ApplicationRequest("fixture", ("one", "two")))

    assert outcome.status == "completed"
    assert outcome.completion_projection == {"schema": "test-projection/1.0", "steps": 2}
    assert calls[-2:] == ["project:2", "stop"]


def test_completion_projector_failure_is_bounded_and_does_not_fail_outcome(
    tmp_path, monkeypatch
):
    diagnostic_codes: list[str] = []

    monkeypatch.setattr(
        AgentApplication,
        "_record_diagnostic",
        lambda _self, code: diagnostic_codes.append(code),
    )

    def project(context: Any) -> object:
        del context
        raise RuntimeError("projection failed")

    application = AgentApplication(
        profile=_profile(),
        prepared_application=cast(
            Any, SimpleNamespace(bindings={"alpha": _valid_binding()})
        ),
        catalog=object(),
        provider=cast(
            Any,
            SimpleNamespace(
                start=lambda: None,
                prompt_and_wait=lambda _question, **_kwargs: "answer",
                stop=lambda: None,
            ),
        ),
        workspace_root=tmp_path,
        turn_controller=FakeController([]),
        binding_identities=(BindingIdentity(binding_id="alpha", domain_id="alpha", domain_version="1.0.0"),),
        domain_output_builder=lambda **_: ValidatedDomainOutput(
            schema="alpha-output/1.0", status="completed", payload={}
        ),
        completion_projector=project,
    )

    outcome = application.run(ApplicationRequest("fixture", ("one",)))

    assert outcome.status == "completed"
    assert outcome.completion_projection is None
    assert diagnostic_codes == ["completion_projection_unavailable"]
