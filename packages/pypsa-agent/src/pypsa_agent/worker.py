"""Trusted PyPSA application worker for Capstone sessions."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import cast

from capstone_agent.application import EmptyCredentialBroker
from capstone_agent.runtime import build_runtime_host
from capstone_agent.worker import PreparedWorker, read_verified_reference, serve_application
from capability_agent.application.composition import prepare_application
from capability_agent.application.context_store import ApplicationContextStore
from capability_agent.application.reference_handoff import ReferenceHandoffService
from capability_agent.application.registry import DomainRegistry
from capability_agent.application.runner import AgentApplication, ApplicationRequest
from capability_agent.application.runtime_protocols import ProviderFactory
from capability_agent.application.workspace import ApplicationWorkspace
from capability_agent.runtime.catalog import ProviderCatalog
from capability_agent.runtime.models import CliLLMOptions

from pypsa_agent.registry import build_trusted_application_registry


ROOT = Path(__file__).resolve().parents[4]
APPLICATION_ID = "pypsa-business-cases"


class _ExactCaseApplication:
    def __init__(self, application: AgentApplication, instructions: tuple[str, ...]) -> None:
        self.application = application
        self.instructions = instructions

    def run_stream(self, request: ApplicationRequest, instructions: Iterable[str]):
        def checked():
            count = 0
            for instruction in instructions:
                if count >= len(self.instructions) or instruction != self.instructions[count]:
                    raise ValueError("registered PyPSA case instruction changed")
                count += 1
                yield instruction
            if count != len(self.instructions):
                raise ValueError("registered PyPSA case is incomplete")

        return self.application.run_stream(request, checked())


def _prepare(values: Mapping[str, object], observer) -> PreparedWorker:
    if values.get("application_id") != APPLICATION_ID:
        raise ValueError("PyPSA application is not registered")
    run_id = values.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("PyPSA run ID is invalid")
    profile = build_trusted_application_registry().resolve(APPLICATION_ID)
    registry = DomainRegistry()
    for binding in profile.domains:
        manifest = binding.profile.manifest
        registry.register(
            manifest.domain_id, manifest.version,
            lambda selected=binding.profile: selected,
        )
    workspace = ApplicationWorkspace.create(
        ROOT / "runs" / "capstone-agent" / "pypsa", run_id=run_id,
        binding_ids=("source", "operations"),
    )
    prepared = prepare_application(
        profile, registry=registry, workspace=workspace.root,
        credentials=EmptyCredentialBroker(),
    )
    store = ApplicationContextStore.initialize(
        workspace, core={"input": {"application_id": APPLICATION_ID, "questions": []}},
    )
    mode = values.get("mode")
    if mode == "scripted-demo":
        from validation.pypsa_cases import CaseProvider, load_cases

        case_id = values.get("case_id")
        case = next((item for item in load_cases()
                     if item["id"] == case_id and item["status"] == "runnable"), None)
        if case is None:
            raise ValueError("PyPSA case is not registered")
        handoff = ReferenceHandoffService(profile, workspace, store, prepared.bindings)

        def progress(event: dict[str, object]) -> None:
            observer({"type": event.get("event", "progress"),
                      "message": event.get("message", "")})

        def provider_factory(*, request, prepared_application, catalog, **_):
            return CaseProvider(
                case, request, prepared_application, catalog, handoff,
                on_progress=progress, demo=True,
            )

        application = AgentApplication(
            profile=profile, prepared_application=prepared,
            workspace=workspace, store=store,
            provider_factory=cast(ProviderFactory, provider_factory),
            semantic_event_observer=observer,
        )
        selected = _ExactCaseApplication(
            application, tuple(case["introduction"]["demo_instructions"]),
        )
    elif mode == "provider" and values.get("case_id") is None:
        provider = values.get("provider")
        model = values.get("model")
        if provider is not None and not isinstance(provider, str):
            raise ValueError("Provider is invalid")
        if model is not None and not isinstance(model, str):
            raise ValueError("model is invalid")
        application = AgentApplication(
            profile=profile, prepared_application=prepared,
            workspace=workspace, store=store,
            provider_catalog=ProviderCatalog.load(ROOT / "configs/llm-providers.json"),
            cli_options=CliLLMOptions(provider=provider, model=model),
            runtime_host=build_runtime_host(ROOT, profile),
            semantic_event_observer=observer,
        )
        selected = application
    else:
        raise ValueError("PyPSA worker mode is invalid")
    return PreparedWorker(
        selected, run_id, lambda reference: read_verified_reference(prepared, reference),
    )


def main() -> None:
    serve_application(_prepare)


if __name__ == "__main__":
    main()
