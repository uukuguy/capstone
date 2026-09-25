"""Provider-free application acceptance through the real model authority."""

from __future__ import annotations

from types import SimpleNamespace


def test_one_turn_application_commits_current_run_model_evidence(tmp_path) -> None:
    from capability_agent.application.manifest import ApplicationManifest
    from capability_agent.application.output import JsonOutputRenderer
    from capability_agent.application.profile import (
        ApplicationProfile, CredentialScope, DataSharingPolicy, DomainBinding,
    )
    from capability_agent.application.registry import DomainRegistry
    from capability_agent.application.reporting import GenericReportShell
    from capability_agent.application.runner import AgentApplication, ApplicationRequest
    from capability_agent.application.workspace import ApplicationWorkspace
    from pypsa_network_modeling.profile import build_pypsa_network_modeling_profile

    domain = build_pypsa_network_modeling_profile()
    registry = DomainRegistry()
    registry.register(domain.manifest.domain_id, domain.manifest.version, lambda: domain)
    workspace = ApplicationWorkspace.create(
        tmp_path / "runs", run_id="model-app", binding_ids=("pypsa-model",)
    )
    profile = ApplicationProfile(
        manifest=ApplicationManifest(
            "pypsa-model-conformance", "1.0", "PyPSA model conformance",
            "application-context/1.0", "application-result/1.0", "artifact/1.0", "agent_",
        ),
        domains=(DomainBinding(
            "pypsa-model", "pypsa_model_", domain, CredentialScope(),
            DataSharingPolicy(),
        ),),
        output_renderer=JsonOutputRenderer(),
        application_policy=SimpleNamespace(load=lambda: "Use registered PyPSA model capabilities."),
        report_shell=GenericReportShell(),
        acceptance_profile=SimpleNamespace(cases=lambda: ()),
    )

    class EmptyCredentials:
        def issue(self, *, binding_id, scope):
            return SimpleNamespace(scope_id=scope.scope_id, credentials={})

    class ScriptedProvider:
        def __init__(self, request, prepared_application, catalog):
            self.request = request
            self.binding = prepared_application.bindings["pypsa-model"]
            self.tool = next(tool for tool in catalog.domain_tools if tool.key.capability_id == "model.open")
            self.result = None

        def start(self):
            pass

        def stop(self):
            pass

        def prompt_and_wait(self, question, *, on_semantic_event, correlation_id, on_heartbeat):
            del question
            on_heartbeat()
            arguments = {"catalog_id": "two-bus"}
            identity = {
                "call_id": "model-open-1", "tool_name": self.tool.name,
                "capability": "model.open",
                "capability_key": {"binding_id": "pypsa-model", "capability_id": "model.open"},
                "run_id": self.request.run_id, "turn_id": correlation_id,
            }
            on_semantic_event({**identity, "type": "tool_execution_start", "arguments": arguments}, 1)
            self.result = self.binding.endpoint.executor.invoke("model.open", arguments)
            on_semantic_event({
                **identity, "type": "tool_result", "ok": True, "result": self.result,
                "result_refs": [self.result["result_ref"]],
                "evidence_refs": self.result["evidence_refs"],
                "projector_id": "pypsa-model-revision-v1",
                "result_kind": "pypsa-model.revision",
            }, 2)
            return "The registered model was opened."

    created = []

    def provider_factory(*, request, prepared_application, catalog, **_):
        provider = ScriptedProvider(request, prepared_application, catalog)
        created.append(provider)
        return provider

    application = AgentApplication(
        profile=profile, workspace=workspace, registry=registry,
        credentials=EmptyCredentials(), provider_factory=provider_factory,
    )
    outcome = application.run(ApplicationRequest(
        profile.manifest.application_id, ("Open the registered model",), workspace.run_id,
    ))

    assert outcome.status == "completed", outcome.error
    assert outcome.completed_questions == 1
    result = created[0].result
    assert result is not None
    assert outcome.result.domains["pypsa-model"].payload["active_model_ref"] == result["model_ref"]
    assert outcome.result.core.answer_refs
    assert (workspace.root / "core" / "context-events.jsonl").exists()
