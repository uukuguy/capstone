"""Domain-neutral application composition extracted from grid-agent."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from capability_agent.application import (
    AgentApplication, ApplicationWorkspace, prepare_application,
)
from capability_agent.application.composition import CredentialBroker
from capability_agent.application.profile import ApplicationProfile, CredentialScope
from capability_agent.application.registry import DomainRegistry
from capability_agent.application.runtime_protocols import (
    LegacyPromptSession, PreparedApplicationRuntime, ProviderFactory, ProviderSession,
)
from capability_agent.domain.provisioning import CredentialLease
from capability_agent.runtime.catalog import ProviderCatalog
from capability_agent.runtime.environment import RuntimeHost
from capability_agent.runtime.models import CliLLMOptions
from capstone_agent.application_registry import ApplicationRegistry


class EmptyCredentialBroker:
    """Issue only the declared empty credential lease."""

    def issue(self, *, binding_id: str, scope: CredentialScope) -> CredentialLease:
        del binding_id
        if tuple(scope.credential_names) != ():
            raise ValueError("generic composition only supports empty credentials")
        return cast(CredentialLease, SimpleNamespace(
            scope_id=scope.scope_id, credentials={},
        ))


def domain_registry(profile: ApplicationProfile) -> DomainRegistry:
    registry = DomainRegistry()
    for binding in profile.domains:
        manifest = binding.profile.manifest
        registry.register(
            manifest.domain_id, manifest.version,
            lambda selected=binding.profile: selected,
        )
    return registry


def build_application(
    application_id: str,
    *,
    registry: ApplicationRegistry,
    version: str | None = None,
    prepared_application: PreparedApplicationRuntime | None = None,
    provider: ProviderSession | LegacyPromptSession | str | None = None,
    provider_factory: ProviderFactory | None = None,
    credentials: CredentialBroker | None = None,
    workspace: ApplicationWorkspace | None = None,
    workspace_root: Path | None = None,
    run_id: str | None = None,
    provider_catalog: ProviderCatalog | None = None,
    cli_options: CliLLMOptions | None = None,
    environment: Mapping[str, str] | None = None,
    runtime_host: RuntimeHost | None = None,
    runtime_host_factory: Callable[[ApplicationProfile, Mapping[str, str] | None], RuntimeHost] | None = None,
    **application_options: Any,
) -> AgentApplication:
    """Build one explicitly registered Kernel application without domain imports."""

    provider_name = provider if isinstance(provider, str) else None
    selected_provider = (
        None if provider_name is not None else
        cast(ProviderSession | LegacyPromptSession | None, provider)
    )
    model_name = application_options.pop("model", None)
    if model_name is not None and not isinstance(model_name, str):
        raise TypeError("model must be text")
    if provider_name is not None or model_name is not None:
        if cli_options is not None and not isinstance(cli_options, CliLLMOptions):
            raise TypeError("cli_options must be a CliLLMOptions value")
        cli_options = CliLLMOptions(
            provider=provider_name, model=model_name,
            base_url=cli_options.base_url if cli_options is not None else None,
            api_key_env=cli_options.api_key_env if cli_options is not None else None,
            timeout_seconds=cli_options.timeout_seconds if cli_options is not None else None,
            max_retries=cli_options.max_retries if cli_options is not None else None,
        )
    profile = registry.resolve(application_id, version)
    selected_workspace = workspace
    if selected_workspace is None and prepared_application is None:
        selected_workspace = ApplicationWorkspace.create(
            workspace_root or Path.cwd() / "runs", run_id=run_id,
            binding_ids=tuple(binding.binding_id for binding in profile.domains),
        )
    prepared = prepared_application
    if prepared is None:
        if selected_workspace is None:
            raise ValueError("workspace is required to prepare a generic application")
        prepared = prepare_application(
            profile, registry=domain_registry(profile),
            workspace=selected_workspace.root,
            credentials=credentials if credentials is not None else EmptyCredentialBroker(),
        )
    if (
        runtime_host is None and selected_provider is None and provider_factory is None
        and provider_catalog is not None and application_options.get("runtime_paths") is None
        and runtime_host_factory is not None
    ):
        runtime_host = runtime_host_factory(profile, environment)
    return AgentApplication(
        profile=profile, prepared_application=prepared,
        provider=selected_provider, provider_factory=provider_factory,
        provider_catalog=provider_catalog, workspace=selected_workspace,
        cli_options=cli_options, environment=environment,
        runtime_host=runtime_host, **application_options,
    )
