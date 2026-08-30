"""Grid-agent application composition and generic entry points."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Protocol, cast

from capability_agent.application import (
    AgentApplication,
    ApplicationOutcome,
    ApplicationRequest,
    ApplicationWorkspace,
    PreparedApplication,
    PreparedDomainRuntime,
    prepare_application,
    prepare_domain_runtime,
)
from capability_agent.application.errors import ApplicationConfigurationError
from capability_agent.application.profile import ApplicationProfile
from capability_agent.application.profile import CredentialScope
from capability_agent.domain.provisioning import CredentialLease
from capability_agent.application.registry import DomainRegistry
from capability_agent.runtime.catalog import ProviderCatalog
from capability_agent.runtime.environment import RuntimeHost
from capability_agent.runtime.models import CliLLMOptions

from grid_agent.application.registry import (
    ApplicationRegistry,
    build_trusted_application_registry,
)
from grid_agent.application.paths import ProjectPaths


class _EmptyCredentialBroker:
    """Issue only the empty lease declared by the first application binding."""

    def issue(
        self, *, binding_id: str, scope: CredentialScope
    ) -> CredentialLease:
        del binding_id
        scope_id = getattr(scope, "scope_id", None)
        credential_names = getattr(scope, "credential_names", ())
        if tuple(credential_names) != ():
            raise ValueError("generic composition only supports empty credentials")
        return cast(CredentialLease, SimpleNamespace(scope_id=scope_id, credentials={}))


def build_generic_application(
    application_id: str,
    *,
    version: str | None = None,
    registry: ApplicationRegistry | None = None,
    prepared_application: PreparedApplication | object | None = None,
    provider: object | None = None,
    provider_factory: Callable[..., object] | None = None,
    credentials: object | None = None,
    workspace: ApplicationWorkspace | None = None,
    workspace_root: Path | None = None,
    run_id: str | None = None,
    provider_catalog: ProviderCatalog | object | None = None,
    cli_options: CliLLMOptions | None = None,
    environment: Mapping[str, str] | None = None,
    runtime_host: RuntimeHost | None = None,
    **application_options: Any,
) -> AgentApplication:
    """Build a generic Kernel application from the trusted registry.

    The helper accepts prepared/injected objects for deterministic acceptance
    tests.  The normal path prepares the registered profile with its own
    explicit Domain Pack binding and never selects a domain by inference.
    """

    provider_name = provider if isinstance(provider, str) else None
    if provider_name is not None:
        provider = None
    model_name = application_options.pop("model", None)
    if model_name is not None and not isinstance(model_name, str):
        raise TypeError("model must be text")
    if provider_name is not None or model_name is not None:
        if cli_options is not None and not isinstance(cli_options, CliLLMOptions):
            raise TypeError("cli_options must be a CliLLMOptions value")
        cli_options = CliLLMOptions(
            provider=provider_name,
            model=model_name,
            base_url=cli_options.base_url if cli_options is not None else None,
            api_key_env=cli_options.api_key_env if cli_options is not None else None,
            timeout_seconds=(
                cli_options.timeout_seconds if cli_options is not None else None
            ),
            max_retries=cli_options.max_retries if cli_options is not None else None,
        )

    selected_registry = registry or build_trusted_application_registry()
    profile = selected_registry.resolve(application_id, version)
    selected_workspace = workspace
    if selected_workspace is None and prepared_application is None:
        root = workspace_root or Path.cwd() / "runs"
        binding_ids = tuple(binding.binding_id for binding in profile.domains)
        selected_workspace = ApplicationWorkspace.create(
            root,
            run_id=run_id,
            binding_ids=binding_ids,
        )
    prepared = prepared_application
    if prepared is None:
        if selected_workspace is None:
            raise ValueError("workspace is required to prepare a generic application")
        prepared = prepare_application(
            profile,
            registry=_domain_registry(profile),
            workspace=selected_workspace.root,
            credentials=cast(
                Any,
                credentials if credentials is not None else _EmptyCredentialBroker(),
            ),
        )

    if (
        runtime_host is None
        and provider is None
        and provider_factory is None
        and provider_catalog is not None
        and application_options.get("runtime_paths") is None
    ):
        runtime_host = _build_runtime_host(
            profile,
            environment,
        )
    return AgentApplication(
        profile=profile,
        prepared_application=prepared,
        provider=provider,
        provider_factory=provider_factory,
        provider_catalog=provider_catalog,
        workspace=selected_workspace,
        cli_options=cli_options,
        environment=environment,
        runtime_host=runtime_host,
        **application_options,
    )


def run_generic_application(
    application_id: str,
    questions: Sequence[str],
    *,
    application: AgentApplication | object | None = None,
    **application_options: Any,
) -> ApplicationOutcome:
    """Run ordered questions through ``AgentApplication`` without compatibility."""

    options = dict(application_options)
    provider_name = options.get("provider")
    model_name = options.get("model")
    if isinstance(provider_name, str) or isinstance(model_name, str):
        existing = options.get("cli_options")
        if existing is not None and not isinstance(existing, CliLLMOptions):
            raise TypeError("cli_options must be a CliLLMOptions value")
        options["cli_options"] = CliLLMOptions(
            provider=provider_name if isinstance(provider_name, str) else None,
            model=model_name if isinstance(model_name, str) else None,
            base_url=existing.base_url if isinstance(existing, CliLLMOptions) else None,
            api_key_env=existing.api_key_env if isinstance(existing, CliLLMOptions) else None,
            timeout_seconds=existing.timeout_seconds if isinstance(existing, CliLLMOptions) else None,
            max_retries=existing.max_retries if isinstance(existing, CliLLMOptions) else None,
        )
    options.pop("provider", None)
    options.pop("model", None)
    runner = application or build_generic_application(
        application_id,
        **options,
    )
    if not callable(getattr(runner, "run", None)):
        raise TypeError("generic application must provide run()")
    profile_application_id = getattr(
        getattr(getattr(runner, "profile", None), "manifest", None),
        "application_id",
        None,
    )
    if profile_application_id is not None and profile_application_id != application_id:
        raise ApplicationConfigurationError(
            "generic application identity does not match its selected profile"
        )
    run_id = options.get("run_id")
    request = ApplicationRequest(
        application_id=application_id,
        questions=tuple(questions),
        run_id=run_id if isinstance(run_id, str) else None,
    )
    outcome = cast(_RunnableApplication, runner).run(request)
    if not isinstance(outcome, ApplicationOutcome):
        raise TypeError("generic application returned an invalid outcome")
    return outcome


class _RunnableApplication(Protocol):
    profile: object

    def run(self, request: ApplicationRequest) -> ApplicationOutcome: ...


def _build_runtime_host(
    profile: ApplicationProfile | None,
    environment: Mapping[str, str] | None,
) -> RuntimeHost:
    """Resolve product-owned Pi assets before constructing the generic runner."""

    if profile is None:
        raise ApplicationConfigurationError("generic runtime profile is unavailable")
    if not profile.domains:
        raise ApplicationConfigurationError("generic runtime profile has no domain binding")
    project_paths = ProjectPaths.from_root(Path.cwd())
    runtime_environment = dict(os.environ if environment is None else environment)
    PiExtensionLocator, PiRuntimeLock, PiRuntimeLocator = _runtime_host_dependencies()
    runtime_lock = PiRuntimeLock.load(project_paths.runtime_lock)
    command = PiRuntimeLocator(
        project_paths.pi_runtime_dir,
        runtime_environment,
        runtime_lock=runtime_lock,
    ).resolve()
    extension_path = PiExtensionLocator(project_paths.root).resolve()
    manifest = profile.domains[0].profile.manifest
    return RuntimeHost(
        command=command,
        project_pi_dir=project_paths.pi_agent_dir,
        extension_path=extension_path,
        system_policy_path=manifest.system_policy_path,
    )


def _runtime_host_dependencies() -> tuple[type, type, type]:
    """Load grid runtime adapters lazily to keep package initialization acyclic."""

    from grid_agent.runtime.extension import PiExtensionLocator
    from grid_agent.runtime.lock import PiRuntimeLock
    from grid_agent.runtime.locator import PiRuntimeLocator

    return PiExtensionLocator, PiRuntimeLock, PiRuntimeLocator


def _domain_registry(profile: ApplicationProfile) -> DomainRegistry:
    registry = DomainRegistry()
    for binding in profile.domains:
        manifest = binding.profile.manifest
        registry.register(
            manifest.domain_id,
            manifest.version,
            lambda profile=binding.profile: profile,
        )
    return registry


__all__ = [
    "PreparedApplication",
    "PreparedDomainRuntime",
    "build_generic_application",
    "prepare_application",
    "prepare_domain_runtime",
    "run_generic_application",
]
